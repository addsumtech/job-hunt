# Sources for career consultations

Choose sources that answer the current career question. Start with the employer's
careers page and current JD for vacancy status, requirements and pay. Add a source
when it can change the application decision or help the user prepare. The table
below is a selection guide, not a checklist to run in full.

## Useful sources

| Need | Source and route | What to verify |
|---|---|---|
| Current openings and requirements | Employer careers pages and recruitment platforms; daily-browser CDP, with OpenCLI when its CDP adapter works | Original posting, location, requirements, pay and posting date. |
| Employer or industry background | AnySearch public search, then the original website or news article | Publisher, date and the claim supported; a snippet is not a full-page read. |
| Recruitment announcements, referral leads and industry analysis | WeChat public accounts; anonymous Sogou WeChat search through CDP | Account name, article date and original article. Follow recruitment links to confirm the job; reposts and old announcements do not establish a current opening. |
| A candidate's public work or an employer's technical projects | GitHub public repositories, code, issues or PRs through `gh search` | Read the relevant original material; distinguish project activity from the candidate's personal contribution. |

For China-related hiring, use WeChat when recruitment announcements or industry
context are relevant;
consider it explicitly during source selection rather than silently omitting it.
A generic web search is not a substitute for an actual WeChat search. If Sogou or
an article cannot be accessed, record that result and the scope actually read.

Other channels are outside the default search plan. Add one only for a concrete
information gap or an explicit user request, after checking that it serves the
question. Do not expand into unrelated social, video or podcast research to make
a report look comprehensive.

## Availability and execution

Apply [daily-browser.md](daily-browser.md) to independent reads: separate browser
tabs, shared site budgets and serial journal imports. Prepare OpenCLI, AnySearch
and web-access using [agent-setup.md](agent-setup.md). Browser reads prefer CDP;
a site adapter that requires an extension is replaced by direct CDP page reading.
Inspect current help before calling a tool. AnySearch `batch_search` can group
independent queries; use its documented schema. If a provider is unavailable,
use an available public source with the same access boundary and record the gap.

Before retrieval, briefly record the selected sources and the question each one
will answer in the workspace. For each source selected, record whether it was
read, unavailable or no longer needed, and why. Do not count a source as searched
just because this reference names it. Do not install unrelated providers or
request additional social accounts to complete setup.

These supplementary reads are background research. A hiring lead may become a
shortlist candidate only after its original posting has been read through the
supported evidence workflow. Use [browser-fallback.md](browser-fallback.md) for
browser posting captures and keep the recruitment gates and refusal locks.

## Evidence and client report

For every source used, retain the original URL, publisher/account, publication
date when available, read date, claim supported and reading scope (snippet, full
text or metadata). Save actual captured evidence in the workspace. Distinguish
company statements, independent reporting and individual experience. Confirm
important hiring conditions with primary sources.

Use relevant findings in `report.md` and place source links beside the claims or
in a short source list. WeChat findings should name the account and article, with
the reading scope clear. Do not add a link merely to show platform coverage.
Tool diagnostics and the full source-selection audit stay in internal records.
If a missing source limits a career conclusion, explain the fact that remains
unverified. Deliver the verified report PDF with any requested CV in the same
consultation folder.
