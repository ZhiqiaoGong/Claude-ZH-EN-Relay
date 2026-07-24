#!/usr/bin/env python3
"""Independent consistency checks for the large-sample benchmark results."""

from __future__ import annotations

import argparse
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
    corpus_manifest,
    load_flores,
    load_wmt_year,
    make_blocks,
    read_jsonl,
    validate_archive,
    validate_unique_pairs,
)


MODELS = ("claude-sonnet-4-6", "claude-sonnet-5")


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


def close_enough(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return abs(left - right) <= tolerance


def verify_model(
    model: str,
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    expected_pairs: dict[str, Any],
    expected_block_count: int,
) -> None:
    record_ids = [row["record_id"] for row in rows]
    if len(record_ids) != len(set(record_ids)):
        raise AssertionError(f"{model}: duplicate record IDs")
    if any(row["model"] != model for row in rows):
        raise AssertionError(f"{model}: wrong model field in count rows")

    types = Counter(row["record_type"] for row in rows)
    expected_types = {
        "envelope": 1,
        "corpus": 3,
        "pair": len(expected_pairs),
        "block": expected_block_count,
    }
    if dict(types) != expected_types:
        raise AssertionError(
            f"{model}: record type counts {dict(types)} != {expected_types}"
        )

    pair_rows = [row for row in rows if row["record_type"] == "pair"]
    pair_row_ids = {row["pair_id"] for row in pair_rows}
    if pair_row_ids != set(expected_pairs):
        missing = sorted(set(expected_pairs).difference(pair_row_ids))[:5]
        extra = sorted(pair_row_ids.difference(expected_pairs))[:5]
        raise AssertionError(
            f"{model}: pair IDs differ; missing={missing}, extra={extra}"
        )

    for row in pair_rows:
        expected = expected_pairs[row["pair_id"]]
        fields = {
            "corpus": expected.corpus,
            "split": expected.split,
            "domain": expected.domain,
            "topic": expected.topic,
            "origlang": expected.origlang,
            "document_id": expected.document_id,
            "zh_characters": len(expected.zh),
            "en_characters": len(expected.en),
            "en_words": len(expected.en.split()),
        }
        for field, expected_value in fields.items():
            if row[field] != expected_value:
                raise AssertionError(
                    f"{model}:{row['pair_id']}: {field} mismatch"
                )
        if row["zh_input_tokens"] <= 0 or row["en_input_tokens"] <= 0:
            raise AssertionError(f"{model}:{row['pair_id']}: non-positive count")

    corpus_rows = [row for row in rows if row["record_type"] == "corpus"]
    direct_zh = sum(row["zh_input_tokens"] for row in corpus_rows)
    direct_en = sum(row["en_input_tokens"] for row in corpus_rows)
    primary = summary["primary_result"]
    if primary["zh_input_tokens"] != direct_zh:
        raise AssertionError(f"{model}: primary Chinese total mismatch")
    if primary["en_input_tokens"] != direct_en:
        raise AssertionError(f"{model}: primary English total mismatch")
    if not close_enough(primary["zh_to_en_ratio"], round(direct_zh / direct_en, 6)):
        raise AssertionError(f"{model}: primary ratio mismatch")

    empty_tokens = summary["empty_message_input_tokens"]
    sensitivity = aggregate_pair_totals(pair_rows, empty_tokens=empty_tokens)
    reported = summary["envelope_baseline_sensitivity"][str(empty_tokens)]
    if sensitivity != reported:
        raise AssertionError(f"{model}: pair sensitivity recomputation mismatch")

    block_rows = [row for row in rows if row["record_type"] == "block"]
    if sum(row["pair_count"] for row in block_rows) != len(expected_pairs):
        raise AssertionError(f"{model}: block pair coverage mismatch")
    adjusted_zh = sum(row["zh_input_tokens"] - empty_tokens for row in block_rows)
    adjusted_en = sum(row["en_input_tokens"] - empty_tokens for row in block_rows)
    block_summary = summary["block_sensitivity"]
    if block_summary["adjusted_zh_input_tokens"] != adjusted_zh:
        raise AssertionError(f"{model}: block Chinese total mismatch")
    if block_summary["adjusted_en_input_tokens"] != adjusted_en:
        raise AssertionError(f"{model}: block English total mismatch")


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
    pairs = (
        load_flores(args.flores_archive)
        + load_wmt_year(args.wmt17_archive, 2017)
        + load_wmt_year(args.wmt18_archive, 2018)
    )
    validate_unique_pairs(pairs)
    blocks = make_blocks(pairs)
    expected_manifest = corpus_manifest(pairs, blocks, archives)
    stored_manifest = read_json(args.results_dir / "parallel-corpus-manifest.json")
    for field in ("pair_count", "block_count", "pair_id_sha256", "text_sha256"):
        if stored_manifest[field] != expected_manifest[field]:
            raise AssertionError(f"manifest {field} mismatch")

    expected_pairs = {pair.pair_id: pair for pair in pairs}
    row_sets: dict[str, set[str]] = {}
    for model in MODELS:
        rows = read_jsonl(args.results_dir / f"parallel-counts-{model}.jsonl")
        summary = read_json(args.results_dir / f"parallel-summary-{model}.json")
        verify_model(
            model,
            rows=rows,
            summary=summary,
            expected_pairs=expected_pairs,
            expected_block_count=len(blocks),
        )
        row_sets[model] = {row["record_id"] for row in rows}
        print(f"{model}: {len(rows)} records verified")

    if row_sets[MODELS[0]] != row_sets[MODELS[1]]:
        raise AssertionError("model result files cover different record IDs")
    print(
        f"Cross-model coverage verified: {len(row_sets[MODELS[0]])} identical IDs"
    )
    print(f"Corpus text SHA-256: {stored_manifest['text_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
