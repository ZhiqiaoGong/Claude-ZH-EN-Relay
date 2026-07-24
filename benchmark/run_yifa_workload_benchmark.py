#!/usr/bin/env python3
"""Product benchmark: original Chinese -> Yifa default Google English."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from run_benchmark import google_translate, load_api_key
from run_parallel_benchmark import (
    DEFAULT_FLORES_ARCHIVE,
    DEFAULT_RESULTS_DIR,
    DEFAULT_WMT17_ARCHIVE,
    DEFAULT_WMT18_ARCHIVE,
    RateLimiter,
    aggregate_pair_rows,
    aggregate_pair_totals,
    aggregate_rows,
    append_jsonl,
    bootstrap_interval,
    count_with_retry,
    load_flores,
    load_wmt_year,
    make_blocks,
    read_jsonl,
    validate_archive,
    validate_unique_pairs,
    write_json,
)


TRANSLATION_ENGINE = "google-unofficial"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flores-archive", type=Path, default=DEFAULT_FLORES_ARCHIVE)
    parser.add_argument("--wmt17-archive", type=Path, default=DEFAULT_WMT17_ARCHIVE)
    parser.add_argument("--wmt18-archive", type=Path, default=DEFAULT_WMT18_ARCHIVE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", help="Exact Anthropic model ID")
    parser.add_argument(
        "--translate-only",
        action="store_true",
        help="Generate/cache Google translations without token counting",
    )
    parser.add_argument(
        "--google-requests-per-second",
        type=float,
        default=6.0,
        help="Global unofficial Google translation rate (default: 6/s)",
    )
    parser.add_argument(
        "--token-requests-per-second",
        type=float,
        default=20.0,
        help="Global Anthropic Token Counting rate (default: 20/s)",
    )
    parser.add_argument("--workers", type=int, default=10)
    return parser.parse_args()


def load_original_chinese_pairs(
    flores_archive: Path, wmt17_archive: Path, wmt18_archive: Path
) -> list[Any]:
    validate_archive(flores_archive, "flores200")
    validate_archive(wmt17_archive, "wmt17")
    validate_archive(wmt18_archive, "wmt18")
    pairs = (
        load_flores(flores_archive)
        + load_wmt_year(wmt17_archive, 2017)
        + load_wmt_year(wmt18_archive, 2018)
    )
    validate_unique_pairs(pairs)
    selected = [pair for pair in pairs if pair.origlang == "zh"]
    if len(selected) != 3481:
        raise ValueError(
            f"expected 3,481 original-Chinese pairs, found {len(selected)}"
        )
    return selected


def google_translate_with_retry(
    text: str,
    *,
    rate_limiter: RateLimiter,
    attempts: int = 6,
) -> str:
    for attempt in range(attempts):
        try:
            rate_limiter.wait()
            return google_translate(text)
        except RuntimeError as exc:
            if attempt == attempts - 1:
                raise
            message = str(exc)
            if not any(
                marker in message
                for marker in (
                    "HTTP 429",
                    "HTTP 500",
                    "HTTP 502",
                    "HTTP 503",
                    "failed:",
                )
            ):
                raise
            wait_seconds = min(30, 2**attempt)
            print(
                f"Google retry in {wait_seconds}s "
                f"({attempt + 1}/{attempts - 1})",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)
    raise AssertionError("unreachable")


def translate_pairs(
    pairs: list[Any],
    *,
    path: Path,
    requests_per_second: float,
    workers: int,
) -> dict[str, dict[str, Any]]:
    existing_rows = read_jsonl(path)
    existing = {row["pair_id"]: row for row in existing_rows}
    for pair in pairs:
        row = existing.get(pair.pair_id)
        if row and row["zh"] != pair.zh:
            raise ValueError(f"cached Chinese text mismatch: {pair.pair_id}")

    pending = [pair for pair in pairs if pair.pair_id not in existing]
    print(
        f"Google translations: {len(existing)}/{len(pairs)} cached; "
        f"translating {len(pending)} at <= {requests_per_second:g}/s"
    )
    limiter = RateLimiter(requests_per_second)
    started = time.monotonic()

    def translate_one(pair: Any) -> dict[str, Any]:
        translated = google_translate_with_retry(pair.zh, rate_limiter=limiter)
        return {
            "pair_id": pair.pair_id,
            "corpus": pair.corpus,
            "document_id": pair.document_id,
            "topic": pair.topic,
            "origlang": pair.origlang,
            "zh": pair.zh,
            "google_en": translated,
            "translation_engine": TRANSLATION_ENGINE,
            "translated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    completed_now = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(translate_one, pair) for pair in pending]
        try:
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                append_jsonl(path, row)
                existing[row["pair_id"]] = row
                completed_now += 1
                if completed_now % 100 == 0 or len(existing) == len(pairs):
                    elapsed = max(time.monotonic() - started, 0.001)
                    rate = completed_now / elapsed
                    remaining = len(pairs) - len(existing)
                    eta = remaining / rate / 60 if rate else 0
                    print(
                        f"Google translations: {len(existing)}/{len(pairs)} "
                        f"({rate:.2f}/s, ETA {eta:.1f}m)"
                    )
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    if set(existing) != {pair.pair_id for pair in pairs}:
        raise ValueError("translation cache coverage mismatch")
    return existing


def safe_model_slug(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")


def translation_hash(
    pairs: list[Any], translations: dict[str, dict[str, Any]]
) -> str:
    payload = "\n".join(
        f"{pair.pair_id}\t{pair.zh}\t{translations[pair.pair_id]['google_en']}"
        for pair in pairs
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_model(
    *,
    model: str,
    pairs: list[Any],
    translations: dict[str, dict[str, Any]],
    results_dir: Path,
    requests_per_second: float,
    workers: int,
) -> tuple[Path, Path]:
    api_key = load_api_key()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    slug = safe_model_slug(model)
    counts_path = results_dir / f"yifa-counts-{slug}.jsonl"
    summary_path = results_dir / f"yifa-summary-{slug}.json"
    existing_rows = read_jsonl(counts_path)
    existing = {row["record_id"]: row for row in existing_rows}
    limiter = RateLimiter(requests_per_second)

    parallel_summary_path = results_dir / f"parallel-summary-{slug}.json"
    with parallel_summary_path.open("r", encoding="utf-8") as handle:
        parallel_summary = json.load(handle)
    empty_tokens = parallel_summary["empty_message_input_tokens"]

    parallel_counts_path = results_dir / f"parallel-counts-{slug}.jsonl"
    parallel_rows = read_jsonl(parallel_counts_path)
    original_zh_counts = {
        row["pair_id"]: row["zh_input_tokens"]
        for row in parallel_rows
        if row["record_type"] == "pair" and row["origlang"] == "zh"
    }
    if set(original_zh_counts) != {pair.pair_id for pair in pairs}:
        raise ValueError(f"{model}: reusable Chinese count coverage mismatch")

    grouped: dict[str, list[Any]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.corpus].append(pair)

    for corpus, group in sorted(grouped.items()):
        record_id = f"corpus:{corpus}"
        if record_id in existing:
            continue
        zh_text = "\n".join(pair.zh for pair in group)
        en_text = "\n".join(translations[pair.pair_id]["google_en"] for pair in group)
        zh_tokens = count_with_retry(
            zh_text, model=model, api_key=api_key, rate_limiter=limiter
        )
        en_tokens = count_with_retry(
            en_text, model=model, api_key=api_key, rate_limiter=limiter
        )
        row = {
            "record_id": record_id,
            "record_type": "corpus",
            "corpus": corpus,
            "model": model,
            "pair_count": len(group),
            "zh_input_tokens": zh_tokens,
            "en_input_tokens": en_tokens,
            "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        append_jsonl(counts_path, row)
        existing[record_id] = row

    pending = [
        pair for pair in pairs if f"pair:{pair.pair_id}" not in existing
    ]
    print(
        f"{model} Google-English counts: {len(pairs) - len(pending)}/"
        f"{len(pairs)} cached; counting {len(pending)}"
    )

    def count_one(pair: Any) -> dict[str, Any]:
        en_tokens = count_with_retry(
            translations[pair.pair_id]["google_en"],
            model=model,
            api_key=api_key,
            rate_limiter=limiter,
        )
        zh_tokens = original_zh_counts[pair.pair_id]
        return {
            "record_id": f"pair:{pair.pair_id}",
            "record_type": "pair",
            "pair_id": pair.pair_id,
            "corpus": pair.corpus,
            "model": model,
            "pair_count": 1,
            "zh_input_tokens": zh_tokens,
            "en_input_tokens": en_tokens,
            "zh_count_source": f"parallel-counts-{slug}.jsonl",
            "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    completed_now = 0
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(count_one, pair) for pair in pending]
        try:
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                append_jsonl(counts_path, row)
                existing[row["record_id"]] = row
                completed_now += 1
                if completed_now % 250 == 0 or completed_now == len(pending):
                    elapsed = max(time.monotonic() - started, 0.001)
                    rate = completed_now / elapsed
                    remaining = len(pending) - completed_now
                    eta = remaining / rate / 60 if rate else 0
                    print(
                        f"{model} Google-English counts: "
                        f"{len(pairs) - len(pending) + completed_now}/{len(pairs)} "
                        f"({rate:.2f}/s, ETA {eta:.1f}m)"
                    )
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    product_blocks = make_blocks(pairs)
    pending_blocks = [
        block
        for block in product_blocks
        if f"block:{block.block_id}" not in existing
    ]
    print(
        f"{model} product blocks: {len(product_blocks) - len(pending_blocks)}/"
        f"{len(product_blocks)} cached; counting {len(pending_blocks)}"
    )

    def count_block(block: Any) -> dict[str, Any]:
        zh_text = "\n".join(pair.zh for pair in block.pairs)
        en_text = "\n".join(
            translations[pair.pair_id]["google_en"] for pair in block.pairs
        )
        zh_tokens = count_with_retry(
            zh_text, model=model, api_key=api_key, rate_limiter=limiter
        )
        en_tokens = count_with_retry(
            en_text, model=model, api_key=api_key, rate_limiter=limiter
        )
        return {
            "record_id": f"block:{block.block_id}",
            "record_type": "block",
            "block_id": block.block_id,
            "corpus": block.corpus,
            "model": model,
            "pair_count": len(block.pairs),
            "zh_input_tokens": zh_tokens,
            "en_input_tokens": en_tokens,
            "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(count_block, block) for block in pending_blocks]
        for index, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            row = future.result()
            append_jsonl(counts_path, row)
            existing[row["record_id"]] = row
            if index % 50 == 0 or index == len(pending_blocks):
                print(
                    f"{model} product blocks: "
                    f"{len(product_blocks) - len(pending_blocks) + index}/"
                    f"{len(product_blocks)}"
                )

    rows = list(existing.values())
    pair_rows = [row for row in rows if row["record_type"] == "pair"]
    block_rows = [row for row in rows if row["record_type"] == "block"]
    corpus_rows = [row for row in rows if row["record_type"] == "corpus"]
    if len(pair_rows) != len(pairs):
        raise ValueError(f"{model}: product pair coverage mismatch")
    if len(block_rows) != len(product_blocks):
        raise ValueError(f"{model}: product block coverage mismatch")
    if len(corpus_rows) != 2:
        raise ValueError(f"{model}: product corpus coverage mismatch")

    direct_zh = sum(row["zh_input_tokens"] for row in corpus_rows)
    direct_en = sum(row["en_input_tokens"] for row in corpus_rows)
    summary = {
        "benchmark": "Yifa default-engine original-Chinese workload benchmark",
        "model": model,
        "pair_count": len(pairs),
        "translation_engine": TRANSLATION_ENGINE,
        "translation_text_sha256": translation_hash(pairs, translations),
        "primary_result": {
            "method": "sum of direct WMT17 and WMT18 corpus counts",
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
        "block_sensitivity": aggregate_rows(
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
        "by_corpus": {
            row["corpus"]: {
                "pair_count": row["pair_count"],
                "zh_input_tokens": row["zh_input_tokens"],
                "en_input_tokens": row["en_input_tokens"],
                "zh_to_en_ratio": round(
                    row["zh_input_tokens"] / row["en_input_tokens"], 6
                ),
                "english_reduction_percent": round(
                    (
                        1
                        - row["en_input_tokens"]
                        / row["zh_input_tokens"]
                    )
                    * 100,
                    4,
                ),
            }
            for row in corpus_rows
        },
        "limitations": [
            "The corpus is news text rather than private Claude chat history.",
            "Google's unofficial endpoint can change independently of Yifa.",
            "Translation quality is not scored; all outputs are retained.",
            "Token Counting API results are estimates according to Anthropic.",
        ],
    }
    write_json(summary_path, summary)
    return counts_path, summary_path


def main() -> int:
    args = parse_args()
    pairs = load_original_chinese_pairs(
        args.flores_archive, args.wmt17_archive, args.wmt18_archive
    )
    print(f"Loaded {len(pairs)} original-Chinese WMT pairs")

    translations_path = args.results_dir / "yifa-google-translations.jsonl"
    translations = translate_pairs(
        pairs,
        path=translations_path,
        requests_per_second=args.google_requests_per_second,
        workers=args.workers,
    )
    print(f"Translation text SHA-256: {translation_hash(pairs, translations)}")
    if args.translate_only:
        return 0
    if not args.model:
        print("error: --model is required unless --translate-only is used", file=sys.stderr)
        return 2

    counts_path, summary_path = run_model(
        model=args.model,
        pairs=pairs,
        translations=translations,
        results_dir=args.results_dir,
        requests_per_second=args.token_requests_per_second,
        workers=args.workers,
    )
    print(f"Wrote counts: {counts_path}")
    print(f"Wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
