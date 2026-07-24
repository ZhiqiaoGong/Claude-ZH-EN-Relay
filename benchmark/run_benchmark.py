#!/usr/bin/env python3
"""Reproducible Chinese-to-English input-token benchmark for Yifa."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BENCHMARK_DIR / "prompts.zh.jsonl"
DEFAULT_RESULTS_DIR = BENCHMARK_DIR / "results"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
COUNT_URL = "https://api.anthropic.com/v1/messages/count_tokens"
ANTHROPIC_VERSION = "2023-06-01"
SEPARATOR = "\n\n---\n\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", help="Exact Anthropic model ID used for counting")
    parser.add_argument(
        "--translate-only",
        action="store_true",
        help="Generate/cache Google translations without calling Anthropic",
    )
    parser.add_argument(
        "--refresh-translations",
        action="store_true",
        help="Ignore cached translations and call Google again",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Delay between external requests in seconds (default: 0.15)",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def validate_corpus(rows: list[dict[str, Any]]) -> None:
    required = {"id", "category", "length", "zh"}
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = required.difference(row)
        if missing:
            raise ValueError(f"row {index} is missing fields: {sorted(missing)}")
        if row["id"] in seen:
            raise ValueError(f"duplicate prompt id: {row['id']}")
        seen.add(row["id"])
        if row["length"] not in {"short", "medium", "long"}:
            raise ValueError(f"{row['id']}: invalid length bucket")
        if not isinstance(row["zh"], str) or not row["zh"].strip():
            raise ValueError(f"{row['id']}: zh must be non-empty text")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 30,
) -> Any:
    data = None
    request_headers = {"User-Agent": "Yifa-Token-Benchmark/1.0"}
    if headers:
        request_headers.update(headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {url.split('?')[0]} returned HTTP {exc.code}: "
            f"{response_text[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url.split('?')[0]} failed: {exc.reason}") from exc


def google_translate(text: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "zh-CN",
            "tl": "en",
            "dt": "t",
            "q": text,
        }
    )
    payload = request_json(f"{TRANSLATE_URL}?{query}")
    try:
        translated = "".join(part[0] for part in payload[0] if part and part[0])
    except (IndexError, TypeError) as exc:
        raise RuntimeError("Google returned an unexpected translation payload") from exc
    if not translated.strip():
        raise RuntimeError("Google returned an empty translation")
    return translated


def translate_corpus(
    prompts: list[dict[str, Any]],
    translations_path: Path,
    *,
    refresh: bool,
    delay: float,
) -> list[dict[str, Any]]:
    cached: dict[str, dict[str, Any]] = {}
    if translations_path.exists() and not refresh:
        cached = {row["id"]: row for row in read_jsonl(translations_path)}

    translations: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts, start=1):
        cached_row = cached.get(prompt["id"])
        if cached_row and cached_row.get("zh") == prompt["zh"]:
            row = cached_row
            status = "cached"
        else:
            english = google_translate(prompt["zh"])
            row = {
                **prompt,
                "en": english,
                "translation_engine": "google-unofficial",
            }
            status = "translated"
            if delay:
                time.sleep(delay)
        translations.append(row)
        print(f"[{index:02d}/{len(prompts)}] {prompt['id']}: {status}")

    write_jsonl(translations_path, translations)
    return translations


def load_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    local_env = REPO_ROOT / ".env.local"
    if not local_env.exists():
        return None
    for raw_line in local_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "ANTHROPIC_API_KEY":
            return value.strip().strip("\"'")
    return None


def count_tokens(text: str, *, model: str, api_key: str) -> int:
    payload = request_json(
        COUNT_URL,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        body={
            "model": model,
            "messages": [{"role": "user", "content": text}],
        },
    )
    value = payload.get("input_tokens") if isinstance(payload, dict) else None
    if not isinstance(value, int):
        raise RuntimeError("Anthropic returned no integer input_tokens value")
    return value


def safe_model_slug(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")


def summarize(
    counted: list[dict[str, Any]],
    *,
    model: str,
    combined_zh_tokens: int,
    combined_en_tokens: int,
    measured_at: str,
) -> dict[str, Any]:
    category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in counted:
        category_rows[row["category"]].append(row)

    def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        zh_total = sum(row["zh_input_tokens"] for row in rows)
        en_total = sum(row["en_input_tokens"] for row in rows)
        ratios = [row["zh_to_en_ratio"] for row in rows]
        return {
            "n": len(rows),
            "summed_zh_input_tokens": zh_total,
            "summed_en_input_tokens": en_total,
            "summed_zh_to_en_ratio": round(zh_total / en_total, 4),
            "summed_english_reduction_percent": round(
                (1 - en_total / zh_total) * 100, 2
            ),
            "median_per_prompt_zh_to_en_ratio": round(
                statistics.median(ratios), 4
            ),
        }

    combined_ratio = combined_zh_tokens / combined_en_tokens
    return {
        "benchmark": "Yifa Chinese-to-English prompt token benchmark",
        "measured_at_utc": measured_at,
        "anthropic_model": model,
        "anthropic_version": ANTHROPIC_VERSION,
        "translation_engine": "google-unofficial",
        "primary_result": {
            "method": "all prompt texts joined into one message per language",
            "zh_input_tokens": combined_zh_tokens,
            "en_input_tokens": combined_en_tokens,
            "zh_to_en_ratio": round(combined_ratio, 4),
            "english_reduction_percent": round(
                (1 - combined_en_tokens / combined_zh_tokens) * 100, 2
            ),
        },
        "per_prompt_aggregate": aggregate(counted),
        "by_category": {
            category: aggregate(rows)
            for category, rows in sorted(category_rows.items())
        },
        "limitations": [
            "Anthropic documents token counts as estimates.",
            "The result applies to this corpus, translation engine, and model.",
            "Prompt-token reduction is not an end-to-end Pro or Max usage-limit claim.",
            "Translation quality must be reviewed separately from token efficiency.",
        ],
    }


def count_corpus(
    translations: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
    results_dir: Path,
    delay: float,
) -> tuple[Path, Path]:
    measured_at = dt.datetime.now(dt.timezone.utc).isoformat()
    counted: list[dict[str, Any]] = []
    for index, row in enumerate(translations, start=1):
        zh_tokens = count_tokens(row["zh"], model=model, api_key=api_key)
        if delay:
            time.sleep(delay)
        en_tokens = count_tokens(row["en"], model=model, api_key=api_key)
        if delay:
            time.sleep(delay)
        counted.append(
            {
                **row,
                "anthropic_model": model,
                "measured_at_utc": measured_at,
                "zh_input_tokens": zh_tokens,
                "en_input_tokens": en_tokens,
                "zh_to_en_ratio": round(zh_tokens / en_tokens, 4),
                "english_reduction_percent": round(
                    (1 - en_tokens / zh_tokens) * 100, 2
                ),
            }
        )
        print(
            f"[{index:02d}/{len(translations)}] {row['id']}: "
            f"zh={zh_tokens}, en={en_tokens}"
        )

    combined_zh = SEPARATOR.join(row["zh"] for row in translations)
    combined_en = SEPARATOR.join(row["en"] for row in translations)
    combined_zh_tokens = count_tokens(combined_zh, model=model, api_key=api_key)
    if delay:
        time.sleep(delay)
    combined_en_tokens = count_tokens(combined_en, model=model, api_key=api_key)

    slug = safe_model_slug(model)
    counts_path = results_dir / f"counts-{slug}.jsonl"
    summary_path = results_dir / f"summary-{slug}.json"
    write_jsonl(counts_path, counted)
    write_json(
        summary_path,
        summarize(
            counted,
            model=model,
            combined_zh_tokens=combined_zh_tokens,
            combined_en_tokens=combined_en_tokens,
            measured_at=measured_at,
        ),
    )
    return counts_path, summary_path


def main() -> int:
    args = parse_args()
    prompts = read_jsonl(args.input)
    validate_corpus(prompts)
    print(f"Loaded {len(prompts)} prompts from {args.input}")

    translations_path = args.results_dir / "translations-google.jsonl"
    translations = translate_corpus(
        prompts,
        translations_path,
        refresh=args.refresh_translations,
        delay=args.delay,
    )
    print(f"Wrote translations: {translations_path}")

    if args.translate_only:
        return 0
    if not args.model:
        print("error: --model is required unless --translate-only is used", file=sys.stderr)
        return 2

    api_key = load_api_key()
    if not api_key:
        print(
            "error: set ANTHROPIC_API_KEY or add it to the ignored .env.local file",
            file=sys.stderr,
        )
        return 2

    counts_path, summary_path = count_corpus(
        translations,
        model=args.model,
        api_key=api_key,
        results_dir=args.results_dir,
        delay=args.delay,
    )
    print(f"Wrote counts: {counts_path}")
    print(f"Wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
