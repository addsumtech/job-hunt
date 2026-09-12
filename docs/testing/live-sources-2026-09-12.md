# Live source acceptance — 2026-09-12

All seven job and interview-information sources were exercised in the user's
daily Chrome with OpenCLI 1.8.7 and the project compatibility patches. This is
bounded source acceptance, not a candidate recommendation or a complete
discover/apply/interview workflow test. No applications or messages were sent.

| Source | Search evidence | Detail evidence | Status |
| --- | --- | --- | --- |
| 51job | OpenCLI returned three Beijing AI product roles | After user-completed slider verification, OpenCLI returned the selected role's full description, company metadata and address | Passed for this sample |
| BOSS | OpenCLI returned three Beijing roles | OpenCLI returned full responsibilities and requirements, salary, employer and address | Passed for this sample |
| Indeed | US OpenCLI search and China/UK/Germany/Netherlands browser searches returned usable rows | One independent full description in each of the five country cases | Passed for these cases; the CLI adapter remains US-only |
| LinkedIn | Adapter returned HTTP 400; browser search rendered results | Of three distinct browser detail samples, one rendered its full body after extended waiting; two still contained only the header | Partial; adapter and two detail samples remain unresolved |
| Upwork | Adapter timed out; its retained trace showed a main-document HTTP 403 Cloudflare page held at human verification | Not attempted after the refusal | Awaiting user recovery |
| 1point3acres | Actual search returned HTTP 403 | Not attempted after the refusal | Awaiting user inspection/recovery; 403 alone does not establish the cause |
| Nowcoder | A narrow query returned no rows; a broader product-manager query returned three posts | Selected post text returned successfully | Text read passed; embedded images were not inspected |

Maimai is a recruiter-only people-search adapter, so it was excluded from this
job/interview-content scope. Its presence in the historical adapter catalogue
does not establish job-discovery support.

## Country and completeness checks

Indeed cases were Beijing (`cn.indeed.com`), London (`uk.indeed.com`), Berlin
(`de.indeed.com`), Amsterdam (`nl.indeed.com`) and the earlier same-day New York
area test (`www.indeed.com`). Each non-US search retained three rows and followed
one original regional result URL to an independent detail. Region, employer,
role, duties and requirements were checked. Missing salary was left undisclosed.
The US result is earlier same-day evidence, not a new capture in this round.

The 51job repair was verified against the real page: company type, size and
industry no longer shift columns; the address is present; the 1,018-character
description has 38 line breaks and is unchanged after whitespace normalization.

The successful LinkedIn sample took about 53 seconds. The other two exhausted
same-page wait stages of 15, 30 and 60 seconds without rendering the description.
Their headers are retained as partial evidence. Neither a login wall nor a
human-verification wall was observed on those two pages; their cause remains
unconfirmed. An earlier employer-careers-page supplement for one role does not
count as a successful LinkedIn detail read.

## Fixes and regression evidence

- The browser reader waits through three increasing rendering budgets in one
  owned tab, can wait for an observed description heading, and preserves the
  final DOM and timeout state. A timed-out capture with no rows is a transport
  result, never a successful empty search.
- Explicit guest-group denial requests login even when a cached auth flag says
  logged in. Stalled human verification requests user intervention. Site refusal
  still stops all reads from that source until explicit user confirmation.
- The 51job compatibility patch recognizes the observed slider wording and
  repairs company fields, address extraction and paragraph breaks. Only exact
  known earlier patches upgrade automatically; custom edits remain protected.
- `make check eval-lint`: **4,192 passed, 8 skipped**; lossless accounting
  **1,317/1,317**, conventions and eval lint passed. Five dependency deprecation
  warnings remain.
- **29** offline DOM checks execute the actual patched Indeed and 51job
  extraction code. Synthetic guest/verification and slow-rendering regressions
  are code checks, not successful live reads of blocked sources.

Raw page snapshots, original URLs, command timestamps, stopped journals and
linked recovery rounds remain in private local evidence. Historical failures
were retained. Upwork and 1point3acres must be rechecked after user recovery;
this report does not claim that every source passed, fresh-machine installation,
all countries, all postings, later pages or long-term access stability.
