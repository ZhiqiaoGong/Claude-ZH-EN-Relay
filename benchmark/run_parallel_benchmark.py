#!/usr/bin/env python3
"""Large-sample Chinese/English token benchmark using human translations."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html
import json
import random
import re
import statistics
import sys
import tarfile
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from run_benchmark import load_api_key, count_tokens


BENCHMARK_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = BENCHMARK_DIR / "results"
DEFAULT_FLORES_ARCHIVE = Path("/private/tmp/flores200_dataset.tar.gz")
DEFAULT_WMT17_ARCHIVE = Path("/private/tmp/wmt17-test.tgz")
DEFAULT_WMT18_ARCHIVE = Path("/private/tmp/wmt18-test.tgz")
BLOCK_SIZE = 25
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260722
TEXT_SEPARATOR = "\n"

SOURCES = {
    "flores200": {
        "url": "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz",
        "sha256": "b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6",
        "license": "CC BY-SA 4.0",
    },
    "wmt17": {
        "url": "https://data.statmt.org/wmt17/translation-task/test.tgz",
        "sha256": "aa1a76f61c0ca68fbf62233ee90ea9ebe2b01b43323092728510037e05e73d8d",
        "license": "WMT official evaluation data",
    },
    "wmt18": {
        "url": "https://data.statmt.org/wmt18/translation-task/test.tgz",
        "sha256": "d4094eb9949571e90b162a690d8bb064fa10986d8f2afb9ae709809ca6bd92ff",
        "license": "WMT official evaluation data",
    },
}


@dataclass(frozen=True)
class Pair:
    pair_id: str
    corpus: str
    split: str
    domain: str
    topic: str
    origlang: str
    document_id: str
    zh: str
    en: str


@dataclass(frozen=True)
class Block:
    block_id: str
    corpus: str
    pairs: tuple[Pair, ...]

    @property
    def zh(self) -> str:
        return TEXT_SEPARATOR.join(pair.zh for pair in self.pairs)

    @property
    def en(self) -> str:
        return TEXT_SEPARATOR.join(pair.en for pair in self.pairs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flores-archive", type=Path, default=DEFAULT_FLORES_ARCHIVE)
    parser.add_argument("--wmt17-archive", type=Path, default=DEFAULT_WMT17_ARCHIVE)
    parser.add_argument("--wmt18-archive", type=Path, default=DEFAULT_WMT18_ARCHIVE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", help="Exact Anthropic model ID")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate archives and corpus alignment without calling an API",
    )
    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=20.0,
        help="Global Token Counting API request rate (default: 20/s)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Concurrent pair-count workers (default: 12)",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path, source_name: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing {source_name} archive: {path}")
    actual = sha256_file(path)
    expected = SOURCES[source_name]["sha256"]
    if actual != expected:
        raise ValueError(
            f"{source_name} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return {
        "path": path.name,
        "url": SOURCES[source_name]["url"],
        "sha256": actual,
        "license": SOURCES[source_name]["license"],
        "bytes": path.stat().st_size,
    }


def read_tar_text(archive: Path, member_name: str) -> str:
    with tarfile.open(archive, "r:gz") as tar:
        try:
            member = tar.getmember(member_name)
        except KeyError:
            if member_name.startswith("./"):
                member = tar.getmember(member_name[2:])
            else:
                member = tar.getmember("./" + member_name)
        extracted = tar.extractfile(member)
        if extracted is None:
            raise ValueError(f"cannot read {member_name} from {archive}")
        return extracted.read().decode("utf-8")


def load_flores(archive: Path) -> list[Pair]:
    pairs: list[Pair] = []
    for split in ("dev", "devtest"):
        zh_lines = read_tar_text(
            archive, f"./flores200_dataset/{split}/zho_Hans.{split}"
        ).splitlines()
        en_lines = read_tar_text(
            archive, f"./flores200_dataset/{split}/eng_Latn.{split}"
        ).splitlines()
        metadata_text = read_tar_text(
            archive, f"./flores200_dataset/metadata_{split}.tsv"
        )
        metadata = list(csv.DictReader(metadata_text.splitlines(), delimiter="\t"))
        if not (len(zh_lines) == len(en_lines) == len(metadata)):
            raise ValueError(
                f"FLORES {split} alignment mismatch: "
                f"zh={len(zh_lines)}, en={len(en_lines)}, metadata={len(metadata)}"
            )
        for index, (zh, en, meta) in enumerate(
            zip(zh_lines, en_lines, metadata), start=1
        ):
            if not zh.strip() or not en.strip():
                raise ValueError(f"FLORES {split}:{index} contains empty text")
            pairs.append(
                Pair(
                    pair_id=f"flores200:{split}:{index:04d}",
                    corpus="flores200",
                    split=split,
                    domain=meta["domain"],
                    topic=meta["topic"],
                    origlang="en",
                    document_id=meta["URL"],
                    zh=zh.strip(),
                    en=en.strip(),
                )
            )
    return pairs


SEGMENT_RE = re.compile(r'<seg\s+id="([^"]+)">(.*?)</seg>')
DOC_RE = re.compile(r"<doc\s+([^>]+)>")
ATTRIBUTE_RE = re.compile(r'([A-Za-z_]+)="([^"]*)"')


def parse_wmt_sgm(text: str, label: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current_doc: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        doc_match = DOC_RE.match(line)
        if doc_match:
            current_doc = dict(ATTRIBUTE_RE.findall(doc_match.group(1)))
            continue
        segment_match = SEGMENT_RE.search(line)
        if not segment_match:
            continue
        if "docid" not in current_doc:
            raise ValueError(f"{label}:{line_number}: segment outside document")
        rows.append(
            {
                "docid": current_doc["docid"],
                "origlang": current_doc.get("origlang", "unknown"),
                "genre": current_doc.get("genre", "unknown"),
                "segid": segment_match.group(1),
                "text": html.unescape(segment_match.group(2)).strip(),
            }
        )
    if not rows:
        raise ValueError(f"{label}: found no segments")
    return rows


def load_wmt_year(archive: Path, year: int) -> list[Pair]:
    base = f"test/newstest{year}"
    zh_source = parse_wmt_sgm(
        read_tar_text(archive, f"{base}-zhen-src.zh.sgm"),
        f"wmt{year}-zhen-src",
    )
    en_reference = parse_wmt_sgm(
        read_tar_text(archive, f"{base}-zhen-ref.en.sgm"),
        f"wmt{year}-zhen-ref",
    )
    en_mirror = parse_wmt_sgm(
        read_tar_text(archive, f"{base}-enzh-src.en.sgm"),
        f"wmt{year}-enzh-src",
    )
    zh_mirror = parse_wmt_sgm(
        read_tar_text(archive, f"{base}-enzh-ref.zh.sgm"),
        f"wmt{year}-enzh-ref",
    )
    lengths = {
        len(zh_source),
        len(en_reference),
        len(en_mirror),
        len(zh_mirror),
    }
    if len(lengths) != 1:
        raise ValueError(f"WMT{year} direction files have different row counts")

    pairs: list[Pair] = []
    for index, (zh, en, en_copy, zh_copy) in enumerate(
        zip(zh_source, en_reference, en_mirror, zh_mirror), start=1
    ):
        identity = (zh["docid"], zh["segid"])
        if identity != (en["docid"], en["segid"]):
            raise ValueError(f"WMT{year}:{index}: zh/en alignment mismatch")
        if identity != (en_copy["docid"], en_copy["segid"]):
            raise ValueError(f"WMT{year}:{index}: en mirror alignment mismatch")
        if identity != (zh_copy["docid"], zh_copy["segid"]):
            raise ValueError(f"WMT{year}:{index}: zh mirror alignment mismatch")
        if zh["text"] != zh_copy["text"] or en["text"] != en_copy["text"]:
            raise ValueError(
                f"WMT{year}:{index}: opposite directions are not exact mirrors"
            )
        if not zh["text"] or not en["text"]:
            raise ValueError(f"WMT{year}:{index}: empty aligned text")
        pairs.append(
            Pair(
                pair_id=f"wmt{year}:{zh['docid']}:{zh['segid']}",
                corpus=f"wmt{year}",
                split=f"newstest{year}",
                domain=zh["genre"],
                topic="news",
                origlang=zh["origlang"],
                document_id=zh["docid"],
                zh=zh["text"],
                en=en["text"],
            )
        )
    return pairs


def validate_unique_pairs(pairs: list[Pair]) -> None:
    pair_ids = [pair.pair_id for pair in pairs]
    duplicates = [key for key, count in Counter(pair_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate pair IDs: {duplicates[:5]}")


def length_thresholds(pairs: list[Pair]) -> tuple[int, int]:
    lengths = sorted(len(pair.en.split()) for pair in pairs)
    return (
        lengths[len(lengths) // 3],
        lengths[(2 * len(lengths)) // 3],
    )


def length_bucket(pair: Pair, thresholds: tuple[int, int]) -> str:
    words = len(pair.en.split())
    if words <= thresholds[0]:
        return "short"
    if words <= thresholds[1]:
        return "medium"
    return "long"


def make_blocks(pairs: list[Pair], block_size: int = BLOCK_SIZE) -> list[Block]:
    grouped: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.corpus].append(pair)

    blocks: list[Block] = []
    for corpus, corpus_pairs in sorted(grouped.items()):
        for start in range(0, len(corpus_pairs), block_size):
            chunk = tuple(corpus_pairs[start : start + block_size])
            blocks.append(
                Block(
                    block_id=f"{corpus}:block:{start // block_size:04d}",
                    corpus=corpus,
                    pairs=chunk,
                )
            )
    return blocks


def corpus_manifest(
    pairs: list[Pair],
    blocks: list[Block],
    archives: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    thresholds = length_thresholds(pairs)
    return {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "pair_count": len(pairs),
        "block_count": len(blocks),
        "block_size": BLOCK_SIZE,
        "corpora": dict(sorted(Counter(pair.corpus for pair in pairs).items())),
        "domains": dict(sorted(Counter(pair.domain for pair in pairs).items())),
        "original_languages": dict(
            sorted(Counter(pair.origlang for pair in pairs).items())
        ),
        "english_word_length_tertiles": {
            "short_max": thresholds[0],
            "medium_max": thresholds[1],
        },
        "length_buckets": dict(
            sorted(
                Counter(length_bucket(pair, thresholds) for pair in pairs).items()
            )
        ),
        "archives": archives,
        "pair_id_sha256": hashlib.sha256(
            "\n".join(pair.pair_id for pair in pairs).encode("utf-8")
        ).hexdigest(),
        "text_sha256": hashlib.sha256(
            "\n".join(f"{pair.zh}\t{pair.en}" for pair in pairs).encode("utf-8")
        ).hexdigest(),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


class RateLimiter:
    """Thread-safe fixed-interval request limiter."""

    def __init__(self, requests_per_second: float):
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.interval = 1.0 / requests_per_second
        self.lock = threading.Lock()
        self.next_allowed = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self.next_allowed - now)
            self.next_allowed = max(now, self.next_allowed) + self.interval
        if wait_seconds:
            time.sleep(wait_seconds)


def count_with_retry(
    text: str,
    *,
    model: str,
    api_key: str,
    rate_limiter: RateLimiter,
    attempts: int = 6,
) -> int:
    for attempt in range(attempts):
        try:
            rate_limiter.wait()
            result = count_tokens(text, model=model, api_key=api_key)
            return result
        except RuntimeError as exc:
            if attempt == attempts - 1:
                raise
            message = str(exc)
            if not any(
                marker in message
                for marker in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 529")
            ):
                raise
            wait_seconds = min(30, 2**attempt)
            print(
                f"retryable API error; waiting {wait_seconds}s "
                f"({attempt + 1}/{attempts - 1})",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)
    raise AssertionError("unreachable")


def safe_model_slug(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")


def record_pair_counts(
    *,
    record_id: str,
    record_type: str,
    corpus: str,
    pairs: Iterable[Pair],
    model: str,
    api_key: str,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    pair_list = list(pairs)
    zh_text = TEXT_SEPARATOR.join(pair.zh for pair in pair_list)
    en_text = TEXT_SEPARATOR.join(pair.en for pair in pair_list)
    zh_tokens = count_with_retry(
        zh_text, model=model, api_key=api_key, rate_limiter=rate_limiter
    )
    en_tokens = count_with_retry(
        en_text, model=model, api_key=api_key, rate_limiter=rate_limiter
    )
    return {
        "record_id": record_id,
        "record_type": record_type,
        "corpus": corpus,
        "model": model,
        "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "pair_count": len(pair_list),
        "zh_characters": sum(len(pair.zh) for pair in pair_list),
        "en_characters": sum(len(pair.en) for pair in pair_list),
        "en_words": sum(len(pair.en.split()) for pair in pair_list),
        "zh_input_tokens": zh_tokens,
        "en_input_tokens": en_tokens,
        "zh_to_en_ratio": round(zh_tokens / en_tokens, 6),
        "english_reduction_percent": round(
            (1 - en_tokens / zh_tokens) * 100, 4
        ),
    }


def percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot take percentile of empty data")
    position = probability * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def bootstrap_interval(
    blocks: list[dict[str, Any]],
    *,
    empty_tokens: int,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    adjusted = [
        (
            row["zh_input_tokens"] - empty_tokens,
            row["en_input_tokens"] - empty_tokens,
        )
        for row in blocks
    ]
    if any(zh <= 0 or en <= 0 for zh, en in adjusted):
        raise ValueError("empty-envelope adjustment produced non-positive tokens")

    rng = random.Random(BOOTSTRAP_SEED)
    ratios: list[float] = []
    reductions: list[float] = []
    for _ in range(samples):
        sampled = [adjusted[rng.randrange(len(adjusted))] for _ in adjusted]
        zh_total = sum(item[0] for item in sampled)
        en_total = sum(item[1] for item in sampled)
        ratios.append(zh_total / en_total)
        reductions.append((1 - en_total / zh_total) * 100)
    ratios.sort()
    reductions.sort()
    return {
        "method": "paired block bootstrap after subtracting empty-message envelope",
        "samples": samples,
        "seed": BOOTSTRAP_SEED,
        "ratio_95_percent_ci": [
            round(percentile(ratios, 0.025), 6),
            round(percentile(ratios, 0.975), 6),
        ],
        "english_reduction_95_percent_ci": [
            round(percentile(reductions, 0.025), 4),
            round(percentile(reductions, 0.975), 4),
        ],
    }


def aggregate_rows(
    rows: list[dict[str, Any]], *, empty_tokens: int
) -> dict[str, Any]:
    zh_raw = sum(row["zh_input_tokens"] for row in rows)
    en_raw = sum(row["en_input_tokens"] for row in rows)
    zh_adjusted = sum(row["zh_input_tokens"] - empty_tokens for row in rows)
    en_adjusted = sum(row["en_input_tokens"] - empty_tokens for row in rows)
    return {
        "records": len(rows),
        "pair_count": sum(row["pair_count"] for row in rows),
        "raw_zh_input_tokens": zh_raw,
        "raw_en_input_tokens": en_raw,
        "adjusted_zh_input_tokens": zh_adjusted,
        "adjusted_en_input_tokens": en_adjusted,
        "adjusted_zh_to_en_ratio": round(zh_adjusted / en_adjusted, 6),
        "adjusted_english_reduction_percent": round(
            (1 - en_adjusted / zh_adjusted) * 100, 4
        ),
        "blocks_where_chinese_uses_more": sum(
            row["zh_input_tokens"] > row["en_input_tokens"] for row in rows
        ),
    }


def aggregate_pair_rows(
    rows: list[dict[str, Any]], *, empty_tokens: int
) -> dict[str, Any]:
    zh_adjusted = sum(row["zh_input_tokens"] - empty_tokens for row in rows)
    en_adjusted = sum(row["en_input_tokens"] - empty_tokens for row in rows)
    ratios = [
        (row["zh_input_tokens"] - empty_tokens)
        / (row["en_input_tokens"] - empty_tokens)
        for row in rows
    ]
    ratios.sort()
    return {
        "pair_count": len(rows),
        "adjusted_zh_input_tokens": zh_adjusted,
        "adjusted_en_input_tokens": en_adjusted,
        "adjusted_zh_to_en_ratio": round(zh_adjusted / en_adjusted, 6),
        "adjusted_english_reduction_percent": round(
            (1 - en_adjusted / zh_adjusted) * 100, 4
        ),
        "pairs_where_chinese_uses_more": sum(
            (row["zh_input_tokens"] - empty_tokens)
            > (row["en_input_tokens"] - empty_tokens)
            for row in rows
        ),
        "per_pair_ratio_p10": round(percentile(ratios, 0.10), 6),
        "per_pair_ratio_median": round(statistics.median(ratios), 6),
        "per_pair_ratio_p90": round(percentile(ratios, 0.90), 6),
    }


def aggregate_pair_totals(
    rows: list[dict[str, Any]], *, empty_tokens: int
) -> dict[str, Any]:
    zh_adjusted = sum(row["zh_input_tokens"] - empty_tokens for row in rows)
    en_adjusted = sum(row["en_input_tokens"] - empty_tokens for row in rows)
    if zh_adjusted <= 0 or en_adjusted <= 0:
        raise ValueError("envelope adjustment produced non-positive total tokens")
    return {
        "pair_count": len(rows),
        "adjusted_zh_input_tokens": zh_adjusted,
        "adjusted_en_input_tokens": en_adjusted,
        "adjusted_zh_to_en_ratio": round(zh_adjusted / en_adjusted, 6),
        "adjusted_english_reduction_percent": round(
            (1 - en_adjusted / zh_adjusted) * 100, 4
        ),
    }


def derived_block_rows(
    blocks: list[Block],
    pair_rows: list[dict[str, Any]],
    *,
    empty_tokens: int,
) -> list[dict[str, Any]]:
    by_pair_id = {row["pair_id"]: row for row in pair_rows}
    derived: list[dict[str, Any]] = []
    for block in blocks:
        rows = [by_pair_id[pair.pair_id] for pair in block.pairs]
        derived.append(
            {
                "record_id": f"derived:{block.block_id}",
                "record_type": "derived_block",
                "corpus": block.corpus,
                "pair_count": len(rows),
                "zh_input_tokens": sum(
                    row["zh_input_tokens"] - empty_tokens for row in rows
                ),
                "en_input_tokens": sum(
                    row["en_input_tokens"] - empty_tokens for row in rows
                ),
            }
        )
    return derived


def build_summary(
    *,
    model: str,
    rows: list[dict[str, Any]],
    empty_tokens: int,
    manifest: dict[str, Any],
    blocks: list[Block],
) -> dict[str, Any]:
    pair_rows = [row for row in rows if row["record_type"] == "pair"]
    block_rows = [row for row in rows if row["record_type"] == "block"]
    corpus_rows = [row for row in rows if row["record_type"] == "corpus"]
    if len(corpus_rows) != len(manifest["corpora"]):
        raise ValueError("missing direct corpus aggregate rows")
    if len(pair_rows) != manifest["pair_count"]:
        raise ValueError(
            f"missing pair rows: expected {manifest['pair_count']}, "
            f"found {len(pair_rows)}"
        )
    if len(block_rows) != manifest["block_count"]:
        raise ValueError(
            f"missing block rows: expected {manifest['block_count']}, "
            f"found {len(block_rows)}"
        )

    direct_zh = sum(row["zh_input_tokens"] for row in corpus_rows)
    direct_en = sum(row["en_input_tokens"] for row in corpus_rows)
    by_corpus = {
        row["corpus"]: {
            "pair_count": row["pair_count"],
            "zh_input_tokens": row["zh_input_tokens"],
            "en_input_tokens": row["en_input_tokens"],
            "zh_to_en_ratio": row["zh_to_en_ratio"],
            "english_reduction_percent": row["english_reduction_percent"],
        }
        for row in corpus_rows
    }

    block_by_corpus: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block_row in block_rows:
        block_by_corpus[block_row["corpus"]].append(block_row)

    thresholds = (
        manifest["english_word_length_tertiles"]["short_max"],
        manifest["english_word_length_tertiles"]["medium_max"],
    )
    by_origlang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_length: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        by_origlang[row["origlang"]].append(row)
        by_domain[row["domain"]].append(row)
        words = row["en_words"]
        bucket = (
            "short"
            if words <= thresholds[0]
            else "medium"
            if words <= thresholds[1]
            else "long"
        )
        by_length[bucket].append(row)

    return {
        "benchmark": "Yifa large-sample human-parallel Chinese/English token benchmark",
        "model": model,
        "pair_count": manifest["pair_count"],
        "block_count": len(block_rows),
        "empty_message_input_tokens": empty_tokens,
        "empty_message_estimation": {
            "method": "count one ASCII letter ('a') and subtract its one content token",
            "note": "The API rejects empty user messages; pair-level sensitivity is also reported for baseline ±1.",
        },
        "primary_result": {
            "method": "sum of one direct aggregate count per corpus",
            "zh_input_tokens": direct_zh,
            "en_input_tokens": direct_en,
            "zh_to_en_ratio": round(direct_zh / direct_en, 6),
            "english_reduction_percent": round(
                (1 - direct_en / direct_zh) * 100, 4
            ),
        },
        "bootstrap": bootstrap_interval(
            block_rows, empty_tokens=empty_tokens
        ),
        "pair_sensitivity": aggregate_pair_rows(
            pair_rows, empty_tokens=empty_tokens
        ),
        "envelope_baseline_sensitivity": {
            str(candidate): aggregate_pair_totals(
                pair_rows, empty_tokens=candidate
            )
            for candidate in (
                max(0, empty_tokens - 1),
                empty_tokens,
                empty_tokens + 1,
            )
        },
        "block_sensitivity": aggregate_rows(
            block_rows, empty_tokens=empty_tokens
        ),
        "by_corpus": by_corpus,
        "by_corpus_block_sensitivity": {
            corpus: aggregate_rows(
                corpus_blocks, empty_tokens=empty_tokens
            )
            for corpus, corpus_blocks in sorted(block_by_corpus.items())
        },
        "by_original_language": {
            key: aggregate_pair_rows(group, empty_tokens=empty_tokens)
            for key, group in sorted(by_origlang.items())
        },
        "by_original_language_baseline_sensitivity": {
            str(candidate): {
                key: aggregate_pair_totals(group, empty_tokens=candidate)
                for key, group in sorted(by_origlang.items())
            }
            for candidate in (
                max(0, empty_tokens - 1),
                empty_tokens,
                empty_tokens + 1,
            )
        },
        "by_domain": {
            key: aggregate_pair_rows(group, empty_tokens=empty_tokens)
            for key, group in sorted(by_domain.items())
        },
        "by_length": {
            key: aggregate_pair_rows(group, empty_tokens=empty_tokens)
            for key, group in sorted(by_length.items())
        },
        "manifest_text_sha256": manifest["text_sha256"],
        "limitations": [
            "FLORES-200 and WMT are general/news translation corpora, not Claude chat logs.",
            "Token Counting API results are estimates according to Anthropic.",
            "The result is model-specific and may change for a different tokenizer.",
            "The product-specific Google-translation pilot is reported separately.",
        ],
    }


def run_model(
    *,
    model: str,
    pairs: list[Pair],
    blocks: list[Block],
    results_dir: Path,
    manifest: dict[str, Any],
    api_key: str,
    requests_per_second: float,
    workers: int,
) -> tuple[Path, Path]:
    slug = safe_model_slug(model)
    counts_path = results_dir / f"parallel-counts-{slug}.jsonl"
    summary_path = results_dir / f"parallel-summary-{slug}.json"
    existing_rows = read_jsonl(counts_path)
    existing = {row["record_id"]: row for row in existing_rows}
    rate_limiter = RateLimiter(requests_per_second)

    empty_id = "envelope:estimated-empty"
    if empty_id not in existing:
        sentinel_tokens = count_with_retry(
            "a", model=model, api_key=api_key, rate_limiter=rate_limiter
        )
        empty_tokens = sentinel_tokens - 1
        if empty_tokens < 0:
            raise ValueError("single-character sentinel count was unexpectedly below 1")
        empty_row = {
            "record_id": empty_id,
            "record_type": "envelope",
            "corpus": "none",
            "model": model,
            "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "pair_count": 0,
            "sentinel": "a",
            "sentinel_input_tokens": sentinel_tokens,
            "estimation_method": "sentinel_input_tokens - 1",
            "zh_input_tokens": empty_tokens,
            "en_input_tokens": empty_tokens,
        }
        append_jsonl(counts_path, empty_row)
        existing[empty_id] = empty_row
    empty_tokens = existing[empty_id]["zh_input_tokens"]

    grouped: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.corpus].append(pair)

    corpus_work: list[tuple[str, str, str, Iterable[Pair]]] = []
    for corpus, corpus_pairs in sorted(grouped.items()):
        corpus_work.append((f"corpus:{corpus}", "corpus", corpus, corpus_pairs))

    for record_id, record_type, corpus, record_pairs in corpus_work:
        if record_id in existing:
            continue
        row = record_pair_counts(
            record_id=record_id,
            record_type=record_type,
            corpus=corpus,
            pairs=record_pairs,
            model=model,
            api_key=api_key,
            rate_limiter=rate_limiter,
        )
        append_jsonl(counts_path, row)
        existing[record_id] = row

    pending_pairs = [
        pair for pair in pairs if f"pair:{pair.pair_id}" not in existing
    ]
    total_pairs = len(pairs)
    already_complete = total_pairs - len(pending_pairs)
    print(
        f"{model}: {already_complete}/{total_pairs} pair records cached; "
        f"counting {len(pending_pairs)} at <= {requests_per_second:g} requests/s"
    )
    started = time.monotonic()

    def count_one_pair(pair: Pair) -> dict[str, Any]:
        row = record_pair_counts(
            record_id=f"pair:{pair.pair_id}",
            record_type="pair",
            corpus=pair.corpus,
            pairs=[pair],
            model=model,
            api_key=api_key,
            rate_limiter=rate_limiter,
        )
        row.update(
            {
                "pair_id": pair.pair_id,
                "split": pair.split,
                "domain": pair.domain,
                "topic": pair.topic,
                "origlang": pair.origlang,
                "document_id": pair.document_id,
            }
        )
        return row

    completed_now = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(count_one_pair, pair) for pair in pending_pairs]
        try:
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                append_jsonl(counts_path, row)
                existing[row["record_id"]] = row
                completed_now += 1
                total_complete = already_complete + completed_now
                if completed_now % 250 == 0 or total_complete == total_pairs:
                    elapsed = max(time.monotonic() - started, 0.001)
                    rate = completed_now / elapsed
                    remaining = total_pairs - total_complete
                    eta_minutes = remaining / rate / 60 if rate else 0
                    print(
                        f"{model}: {total_complete}/{total_pairs} pairs "
                        f"({rate:.2f} pairs/s, ETA {eta_minutes:.1f}m)"
                    )
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    pending_blocks = [
        block for block in blocks if f"block:{block.block_id}" not in existing
    ]
    already_complete_blocks = len(blocks) - len(pending_blocks)
    print(
        f"{model}: {already_complete_blocks}/{len(blocks)} block records cached; "
        f"counting {len(pending_blocks)}"
    )

    def count_one_block(block: Block) -> dict[str, Any]:
        row = record_pair_counts(
            record_id=f"block:{block.block_id}",
            record_type="block",
            corpus=block.corpus,
            pairs=block.pairs,
            model=model,
            api_key=api_key,
            rate_limiter=rate_limiter,
        )
        row["block_id"] = block.block_id
        return row

    completed_blocks_now = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        block_futures = [
            executor.submit(count_one_block, block) for block in pending_blocks
        ]
        try:
            for future in concurrent.futures.as_completed(block_futures):
                row = future.result()
                append_jsonl(counts_path, row)
                existing[row["record_id"]] = row
                completed_blocks_now += 1
                total_blocks_complete = (
                    already_complete_blocks + completed_blocks_now
                )
                if (
                    completed_blocks_now % 50 == 0
                    or total_blocks_complete == len(blocks)
                ):
                    print(
                        f"{model}: {total_blocks_complete}/{len(blocks)} "
                        "block records complete"
                    )
        except BaseException:
            for future in block_futures:
                future.cancel()
            raise

    rows = list(existing.values())
    summary = build_summary(
        model=model,
        rows=rows,
        empty_tokens=empty_tokens,
        manifest=manifest,
        blocks=blocks,
    )
    write_json(summary_path, summary)
    return counts_path, summary_path


def main() -> int:
    args = parse_args()
    archive_paths = {
        "flores200": args.flores_archive,
        "wmt17": args.wmt17_archive,
        "wmt18": args.wmt18_archive,
    }
    archives = {
        source: validate_archive(path, source)
        for source, path in archive_paths.items()
    }
    print("Archive SHA-256 validation passed")

    flores_pairs = load_flores(args.flores_archive)
    wmt17_pairs = load_wmt_year(args.wmt17_archive, 2017)
    wmt18_pairs = load_wmt_year(args.wmt18_archive, 2018)
    pairs = flores_pairs + wmt17_pairs + wmt18_pairs
    validate_unique_pairs(pairs)
    blocks = make_blocks(pairs)
    manifest = corpus_manifest(pairs, blocks, archives)
    manifest_path = args.results_dir / "parallel-corpus-manifest.json"
    write_json(manifest_path, manifest)
    print(
        f"Loaded {len(pairs)} unique pairs in {len(blocks)} blocks: "
        f"{manifest['corpora']}"
    )
    print(f"Wrote manifest: {manifest_path}")

    if args.validate_only:
        return 0
    if not args.model:
        print("error: --model is required unless --validate-only is used", file=sys.stderr)
        return 2
    api_key = load_api_key()
    if not api_key:
        print("error: ANTHROPIC_API_KEY is not configured", file=sys.stderr)
        return 2

    counts_path, summary_path = run_model(
        model=args.model,
        pairs=pairs,
        blocks=blocks,
        results_dir=args.results_dir,
        manifest=manifest,
        api_key=api_key,
        requests_per_second=args.requests_per_second,
        workers=args.workers,
    )
    print(f"Wrote counts: {counts_path}")
    print(f"Wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
