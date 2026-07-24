# Yifa Chinese/English token benchmark

This repository contains two complementary benchmarks:

1. **Product workload:** 3,481 WMT sentences whose recorded original language
   is Chinese, translated through Yifa's default Google path. This is the
   closest test of what Yifa actually sends.
2. **Human-parallel corpus:** 7,991 Chinese/English sentence pairs from
   FLORES-200, WMT17, and WMT18. This tests how the conclusion changes with
   corpus and translation direction.

The benchmark answers only an input-token question. It does **not** claim that
a Claude Pro or Max usage limit changes by the same percentage; product usage
also depends on responses, conversation history, tools, caching, and model
choice.

## Product result: original Chinese -> Yifa Google English

Measured on 2026-07-22 PT (2026-07-23 UTC) with Anthropic's Token Counting API.
The primary result is the sum of one direct aggregate count for WMT17 and one
for WMT18, avoiding per-message fixed-overhead distortion.

| Model | Pairs | Chinese tokens | Yifa English tokens | Chinese / English | Effect of sending English |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Sonnet 4.6 | 3,481 | 161,157 | 130,760 | 1.232x | 18.86% fewer |
| Claude Sonnet 5 | 3,481 | 161,675 | 191,719 | 0.843x | 18.58% more |

The independently counted 25-sentence blocks agree with the direct aggregates:

| Model | Block-adjusted effect | Paired bootstrap 95% CI |
| --- | ---: | ---: |
| Claude Sonnet 4.6 | 18.95% fewer English tokens | 17.90% to 19.97% fewer |
| Claude Sonnet 5 | 18.60% more English tokens | 16.76% to 20.44% more |

The same English text rose from 130,760 tokens on Sonnet 4.6 to 191,719 on
Sonnet 5 (**+46.62%**), while the Chinese rose only **+0.32%**. Anthropic
documents that Sonnet 5 uses a new tokenizer and explicitly recommends
recounting the actual workload instead of reusing earlier-model counts.

**Conclusion for Yifa:** the old claim that Chinese costs roughly 1.5-2x the
tokens of English is not supportable as a current, model-independent product
claim. Yifa's English relay reduced input tokens on Sonnet 4.6 in this
news-domain benchmark, but increased them on Sonnet 5.

## Why common online claims can still show Chinese as more expensive

Translation direction materially changes the text. In the human-parallel
benchmark, English-original sentences and Chinese-original sentences give
different results:

| Model | Original language | Pairs | Adjusted Chinese / English | Effect of English |
| --- | --- | ---: | ---: | ---: |
| Sonnet 4.6 | English | 4,510 | 1.664x | 39.90% fewer |
| Sonnet 4.6 | Chinese | 3,481 | 1.273x | 21.44% fewer |
| Sonnet 5 | English | 4,510 | 1.150x | 13.02% fewer |
| Sonnet 5 | Chinese | 3,481 | 0.847x | 18.03% more |

Thus, a benchmark that starts with natural English and compares a Chinese
translation can correctly find that Chinese uses more tokens. Yifa starts with
natural Chinese and sends an English translation—the opposite direction. On
Sonnet 5, the English translation is longer in token terms for both the human
WMT references and Yifa's Google output.

Across all 7,991 human-parallel pairs:

| Model | Chinese tokens | English tokens | Chinese / English | Effect of English |
| --- | ---: | ---: | ---: | ---: |
| Claude Sonnet 4.6 | 370,982 | 260,411 | 1.425x | 29.81% fewer |
| Claude Sonnet 5 | 373,836 | 375,318 | 0.996x | 0.40% more |

The Sonnet 5 all-corpus bootstrap interval includes parity: the English effect
ranges from 2.17% more to 1.31% fewer. Corpus composition and direction—not
only language labels—therefore determine the headline.

## Data

The human-parallel corpus contains 7,991 unique pairs:

- FLORES-200 `dev` + `devtest`: 2,009 pairs
- WMT17 Chinese/English test set: 2,001 pairs
- WMT18 Chinese/English test set: 3,981 pairs
- Recorded original language: 4,510 English and 3,481 Chinese
- Domains: 5,982 news, 652 Wikibooks, 689 Wikinews, 668 Wikivoyage

WMT's `zhen` and `enzh` files are mirrors, not independent examples. The
loader verifies the mirror relationship and counts each pair once.

The source archives are not committed. Their URLs and SHA-256 digests are
recorded in `results/parallel-corpus-manifest.json`; the normalized 7,991-pair
text hash is:

```text
9c201fadfcc495819c35a207dec0272b84271f0c9c25273dba4ede83675df498
```

The exact 3,481 Yifa Google translations have this text hash:

```text
08ac4c8ac1ec6668fefc9f7e2b48815617481ceca5901c5476504de24ecce328
```

## Method

For both studies:

1. Use the exact same user-message envelope for Chinese and English.
2. Ask Anthropic's `POST /v1/messages/count_tokens` endpoint for the specified
   model; never call `POST /v1/messages` or generate a completion.
3. Use direct corpus aggregates as the primary result.
4. Count deterministic blocks of about 25 pairs and run a paired bootstrap
   with 10,000 resamples and seed `20260722`.
5. Keep per-pair counts for stratification, but do not use their raw sum as the
   headline because a fixed message envelope is repeated thousands of times.
6. Retain all Google outputs; no translation is removed based on its token
   count.

Anthropic states that token counting is free but rate-limited and that counts
are estimates. The run was limited to 20 token-count requests per second.
Google translation used Yifa's unauthenticated unofficial endpoint, limited to
6 requests per second. No paid text-generation request was made.

## Reproduce

Python 3.9+ is sufficient; the scripts have no third-party dependencies.
Download the three archives listed in
`results/parallel-corpus-manifest.json`, verify their SHA-256 hashes, and pass
their paths explicitly if they are not at the script defaults.

Validate and build the corpus manifest without an API call:

```bash
python3 benchmark/run_parallel_benchmark.py --validate-only
```

Run the human-parallel counts:

```bash
python3 benchmark/run_parallel_benchmark.py --model claude-sonnet-4-6
python3 benchmark/run_parallel_benchmark.py --model claude-sonnet-5
```

Generate/cache the product translations, then count them:

```bash
python3 benchmark/run_yifa_workload_benchmark.py --translate-only
python3 benchmark/run_yifa_workload_benchmark.py --model claude-sonnet-4-6
python3 benchmark/run_yifa_workload_benchmark.py --model claude-sonnet-5
```

Verify raw records, corpus hashes, coverage, reused Chinese counts, direct
totals, block totals, and cross-model IDs:

```bash
python3 benchmark/verify_parallel_results.py
python3 benchmark/verify_yifa_results.py
```

The scripts read `ANTHROPIC_API_KEY` from the environment or from a
repository-root `.env.local`. `.env.local` is ignored by Git; the key is never
written to result files.

## Exploratory pilot

`prompts.zh.jsonl` is the original 30-prompt engineering/productivity pilot.
Its result was useful for discovering the tokenizer reversal, but it is not
used for the final headline. Its raw translations, token counts, and manual
translation review remain checked in for transparency.

## Limitations

- The product corpus is news text, not private Claude chat history.
- Translation style and direction are confounded with language; that is why
  both directions are reported separately.
- Translation quality was not scored for all 3,481 Google outputs.
- Yifa's unofficial Google endpoint and Anthropic tokenizers can change.
- Token counts estimate input tokens, not Claude subscription usage limits.

## Evidence files

- `results/parallel-corpus-manifest.json`
- `results/parallel-summary-claude-sonnet-4-6.json`
- `results/parallel-summary-claude-sonnet-5.json`
- `results/yifa-google-translations.jsonl`
- `results/yifa-summary-claude-sonnet-4-6.json`
- `results/yifa-summary-claude-sonnet-5.json`
- `verify_parallel_results.py`
- `verify_yifa_results.py`

Raw per-pair and per-block count files are also retained under `results/`.

Official references:

- [Anthropic token counting guide](https://platform.claude.com/docs/en/build-with-claude/token-counting)
- [Anthropic Sonnet 5 tokenizer notes](https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5)
- [FLORES-200 documentation](https://github.com/facebookresearch/flores/blob/main/flores200/README.md)
- [WMT17 translation task](https://www.statmt.org/wmt17/translation-task.html)
- [WMT18 translation task](https://www.statmt.org/wmt18/translation-task.html)
