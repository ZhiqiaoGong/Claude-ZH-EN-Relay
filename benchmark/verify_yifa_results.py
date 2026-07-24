#!/usr/bin/env python3
"""Independent consistency checks for the Yifa product benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from run_parallel_benchmark import (
    DEFAULT_FLORES_ARCHIVE,
    DEFAULT_RESULTS_DIR,
    DEFAULT_WMT17_ARCHIVE,
    DEFAULT_WMT18_ARCHIVE,
    aggregate_pair_totals,
    load_flores,
    load_wmt_year,
    make_blocks,
    read_jsonl,
    validate_archive,
    validate_unique_pairs,
)


MODELS = ("claude-sonnet-4-6", "claude-sonnet-5")
EXPECTED_TRANSLATION_HASH = (
    "08ac4c8ac1ec6668fefc9f7e2b48815617481ceca5901c5476504de24ecce328"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flores-archive", type=Path, default=DEFAULT_FLORES_ARCHIVE)
    parser.add_argument("--wmt17-archive", type=Path, default=DEFAULT_WMT17_ARCHIVE)
    parser.add_argument("--wmt18-archive", type=Path, default=DEFAULT_WMT18_ARCHIVE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_translations(
    pairs: list[Any], rows: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], str]:
    expected = {pair.pair_id: pair for pair in pairs}
    ids = [row["pair_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("translation file contains duplicate pair IDs")
    if set(ids) != set(expected):
        raise AssertionError("translation file does not exactly cover expected pairs")

    translations = {row["pair_id"]: row for row in rows}
    for pair_id, pair in expected.items():
        row = translations[pair_id]
        fields = {
            "corpus": pair.corpus,
            "document_id": pair.document_id,
            "topic": pair.topic,
            "origlang": "zh",
            "zh": pair.zh,
            "translation_engine": "google-unofficial",
        }
        for field, expected_value in fields.items():
            if row[field] != expected_value:
                raise AssertionError(f"{pair_id}: translation {field} mismatch")
        if not isinstance(row["google_en"], str) or not row["google_en"].strip():
            raise AssertionError(f"{pair_id}: empty Google translation")

    payload = "\n".join(
        f"{pair.pair_id}\t{pair.zh}\t{translations[pair.pair_id]['google_en']}"
        for pair in pairs
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if digest != EXPECTED_TRANSLATION_HASH:
        raise AssertionError(
            f"translation text SHA-256 changed: {digest} "
            f"!= {EXPECTED_TRANSLATION_HASH}"
        )
    return translations, digest


def verify_model(
    model: str,
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    pairs: list[Any],
    expected_blocks: list[Any],
    translation_hash: str,
    results_dir: Path,
) -> None:
    expected_pairs = {pair.pair_id: pair for pair in pairs}
    record_ids = [row["record_id"] for row in rows]
    if len(record_ids) != len(set(record_ids)):
        raise AssertionError(f"{model}: duplicate record IDs")
    if any(row["model"] != model for row in rows):
        raise AssertionError(f"{model}: wrong model field")

    types = Counter(row["record_type"] for row in rows)
    expected_types = {
        "corpus": 2,
        "pair": len(pairs),
        "block": len(expected_blocks),
    }
    if dict(types) != expected_types:
        raise AssertionError(
            f"{model}: record type counts {dict(types)} != {expected_types}"
        )

    pair_rows = [row for row in rows if row["record_type"] == "pair"]
    if {row["pair_id"] for row in pair_rows} != set(expected_pairs):
        raise AssertionError(f"{model}: pair coverage mismatch")

    parallel_rows = read_jsonl(
        results_dir / f"parallel-counts-{model}.jsonl"
    )
    expected_zh_counts = {
        row["pair_id"]: row["zh_input_tokens"]
        for row in parallel_rows
        if row["record_type"] == "pair" and row["origlang"] == "zh"
    }
    if set(expected_zh_counts) != set(expected_pairs):
        raise AssertionError(f"{model}: source Chinese count coverage mismatch")

    for row in pair_rows:
        pair = expected_pairs[row["pair_id"]]
        if row["corpus"] != pair.corpus:
            raise AssertionError(f"{model}:{pair.pair_id}: corpus mismatch")
        if row["zh_input_tokens"] != expected_zh_counts[pair.pair_id]:
            raise AssertionError(
                f"{model}:{pair.pair_id}: reused Chinese count mismatch"
            )
        if row["en_input_tokens"] <= 0:
            raise AssertionError(
                f"{model}:{pair.pair_id}: non-positive English count"
            )

    corpus_rows = [row for row in rows if row["record_type"] == "corpus"]
    if {row["corpus"] for row in corpus_rows} != {"wmt2017", "wmt2018"}:
        raise AssertionError(f"{model}: corpus records mismatch")
    corpus_sizes = Counter(pair.corpus for pair in pairs)
    for row in corpus_rows:
        if row["pair_count"] != corpus_sizes[row["corpus"]]:
            raise AssertionError(f"{model}:{row['corpus']}: pair count mismatch")

    direct_zh = sum(row["zh_input_tokens"] for row in corpus_rows)
    direct_en = sum(row["en_input_tokens"] for row in corpus_rows)
    primary = summary["primary_result"]
    expected_ratio = round(direct_zh / direct_en, 6)
    expected_reduction = round((1 - direct_en / direct_zh) * 100, 4)
    if primary["zh_input_tokens"] != direct_zh:
        raise AssertionError(f"{model}: primary Chinese total mismatch")
    if primary["en_input_tokens"] != direct_en:
        raise AssertionError(f"{model}: primary English total mismatch")
    if primary["zh_to_en_ratio"] != expected_ratio:
        raise AssertionError(f"{model}: primary ratio mismatch")
    if primary["english_reduction_percent"] != expected_reduction:
        raise AssertionError(f"{model}: primary reduction mismatch")

    parallel_summary = read_json(
        results_dir / f"parallel-summary-{model}.json"
    )
    empty_tokens = parallel_summary["empty_message_input_tokens"]
    pair_sensitivity = aggregate_pair_totals(
        pair_rows, empty_tokens=empty_tokens
    )
    reported_pair_sensitivity = summary["envelope_baseline_sensitivity"][
        str(empty_tokens)
    ]
    if pair_sensitivity != reported_pair_sensitivity:
        raise AssertionError(f"{model}: pair sensitivity mismatch")

    block_rows = [row for row in rows if row["record_type"] == "block"]
    expected_block_map = {block.block_id: block for block in expected_blocks}
    if {row["block_id"] for row in block_rows} != set(expected_block_map):
        raise AssertionError(f"{model}: block coverage mismatch")
    for row in block_rows:
        block = expected_block_map[row["block_id"]]
        if row["corpus"] != block.corpus:
            raise AssertionError(f"{model}:{block.block_id}: block corpus mismatch")
        if row["pair_count"] != len(block.pairs):
            raise AssertionError(f"{model}:{block.block_id}: block size mismatch")

    adjusted_zh = sum(
        row["zh_input_tokens"] - empty_tokens for row in block_rows
    )
    adjusted_en = sum(
        row["en_input_tokens"] - empty_tokens for row in block_rows
    )
    block_summary = summary["block_sensitivity"]
    if block_summary["pair_count"] != len(pairs):
        raise AssertionError(f"{model}: block pair total mismatch")
    if block_summary["adjusted_zh_input_tokens"] != adjusted_zh:
        raise AssertionError(f"{model}: block Chinese total mismatch")
    if block_summary["adjusted_en_input_tokens"] != adjusted_en:
        raise AssertionError(f"{model}: block English total mismatch")

    if summary["pair_count"] != len(pairs):
        raise AssertionError(f"{model}: summary pair count mismatch")
    if summary["translation_text_sha256"] != translation_hash:
        raise AssertionError(f"{model}: summary translation hash mismatch")


def main() -> int:
    args = parse_args()
    validate_archive(args.flores_archive, "flores200")
    validate_archive(args.wmt17_archive, "wmt17")
    validate_archive(args.wmt18_archive, "wmt18")
    all_pairs = (
        load_flores(args.flores_archive)
        + load_wmt_year(args.wmt17_archive, 2017)
        + load_wmt_year(args.wmt18_archive, 2018)
    )
    validate_unique_pairs(all_pairs)
    pairs = [pair for pair in all_pairs if pair.origlang == "zh"]
    if len(pairs) != 3481:
        raise AssertionError(
            f"expected 3,481 original-Chinese pairs, found {len(pairs)}"
        )
    expected_blocks = make_blocks(pairs)

    translation_rows = read_jsonl(
        args.results_dir / "yifa-google-translations.jsonl"
    )
    _, digest = verify_translations(pairs, translation_rows)
    print(f"Translations: {len(translation_rows)} rows verified")
    print(f"Translation text SHA-256: {digest}")

    row_sets: dict[str, set[str]] = {}
    for model in MODELS:
        rows = read_jsonl(args.results_dir / f"yifa-counts-{model}.jsonl")
        summary = read_json(args.results_dir / f"yifa-summary-{model}.json")
        verify_model(
            model,
            rows=rows,
            summary=summary,
            pairs=pairs,
            expected_blocks=expected_blocks,
            translation_hash=digest,
            results_dir=args.results_dir,
        )
        row_sets[model] = {row["record_id"] for row in rows}
        print(f"{model}: {len(rows)} records verified")

    if row_sets[MODELS[0]] != row_sets[MODELS[1]]:
        raise AssertionError("model result files cover different record IDs")
    print(
        f"Cross-model coverage verified: {len(row_sets[MODELS[0]])} identical IDs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
