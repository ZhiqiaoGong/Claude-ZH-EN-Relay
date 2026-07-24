# Manual review of Google translations

Reviewed against `results/translations-google.jsonl` on 2026-07-22.

All 30 outputs are retained in the token benchmark. Removing weaker
translations after seeing them would make the corpus less representative of
Yifa's default engine and could bias the token result.

Twenty-three outputs preserve the requested meaning without a notable issue.
The following seven contain awkward or incorrect terminology:

| Prompt | Severity | Review note |
| --- | --- | --- |
| `coding-04` | Minor | “Upstream interfaces” is awkward for upstream API endpoints. |
| `coding-05` | Material | “With a directory” loses the intended “with a table of contents.” |
| `debugging-01` | Material | “Retroactive explosion” mistranslates catastrophic backtracking. |
| `debugging-03` | Minor | “Joint index” is nonstandard wording for a composite index. |
| `data-04` | Material | “Statistical caliber” mistranslates the statistical definition or measurement convention. |
| `productivity-03` | Material | “Follow-up inspections” mistranslates analytics instrumentation checks. |
| `productivity-05` | Material | “Congestion issues” mistranslates blocking issues. |

These findings do not invalidate a text-token comparison, but they prevent the
benchmark from being interpreted as a translation-quality evaluation. They
also support Yifa's review-before-send guard and the option to use DeepL or
Gemini for technical text.
