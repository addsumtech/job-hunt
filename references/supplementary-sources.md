# Supplementary sources for career consultations

Use these when they can answer the user's question. Start with an employer's
careers page and current official JD for vacancy status, conditions and pay.
Broaden only for a concrete evidence gap: company/product context, technical work,
public hiring announcements, interview preparation or industry changes. Do not
run every source on every consultation.

## Routing

| Need | Preferred route | Boundary |
|---|---|---|
| Official sites, public web, company news | AnySearch public search | Open the original page; a search snippet is discovery, not full-page evidence. |
| Several keywords or companies | AnySearch `batch_search` | Parallelize independent public queries only; deduplicate URLs and syndicated stories. |
| A specified website | AnySearch `site:target-domain` | Search public indexed pages; no private-page claims. |
| Unspecified social discussion | AnySearch social-media vertical | Discover public candidates first; keep opinions separate from employer facts. |
| Employer engineering work, open-source evidence | `gh search repos`, `gh search code`, `gh search issues`, `gh search prs` | Search public content only; inspect original repo/issue/PR. Never upload a candidate CV or private code as a query. |
| WeChat public accounts | OpenCLI Sogou WeChat public search | Anonymous search only; follow the public article. No personal WeChat history or contacts. |
| Xiaohongshu | OpenCLI site search using Chrome login | Requires explicit authorization for this platform in the current consultation before reading the login state; otherwise use public indexed candidates. |
| Douyin | OpenCLI site search using Chrome login | Same current-consultation authorization; low-frequency reads and a small relevant sample. |
| Toutiao | OpenCLI article/image-text search | Use a dedicated anonymous environment; do not attach a personal login. |
| X/Twitter | Grok OAuth + `grok-consult` public X search | Only when configured; require original post URLs and dates. Do not treat generated commentary as a source. |
| Bilibili | `bili search` | Anonymous public-video metadata and links; read content only when needed. |
| YouTube | `yt-dlp --skip-download --flat-playlist --dump-json "ytsearch5:<query>"` | Anonymous search; information and links only, no video/audio download. |
| Xiaoyuzhou | AnySearch `site:xiaoyuzhoufm.com` | Public episode pages, descriptions and available transcripts; do not claim to have listened. |
| A relevant legal, financial, academic or security question | Corresponding AnySearch vertical | On demand only, then verify primary law/regulator/paper/advisory sources and their dates/jurisdiction. |

## Availability and invocation

This table is a routing policy, not a promise that every provider is installed.
Inspect the current tool registry/help before invocation. AnySearch and
`grok-consult` names do not imply a fixed local CLI syntax: use the available
connector/skill schema. For OpenCLI inspect `opencli list -f json` and the listed
site's `search --help`; never invent an adapter name. If a route is unavailable,
use an available public search tool with the same source boundary. Do not install
all optional providers or request social account access just to complete setup.

Keep existing recruitment adapters and their receipts unchanged. These routes are
supplementary web/background research, not new verified OpenCLI job adapters. A
public hiring lead may become a shortlist candidate only after its original
posting has been read through the supported evidence workflow. An unavailable
source is not evidence that no jobs exist.

## Evidence and client report

For each used source record the original URL, publisher/account, publication date
(if available), read date, claim supported and reading scope (snippet, full text,
metadata or transcript). Keep captured evidence in the workspace. Distinguish
company statements, independent reporting and individual experience. Seek a
primary source for consequential hiring conditions; anonymous anecdotes cannot
establish pay, vacancy status, guaranteed interview questions or a candidate's
success probability.

Answer the client question in `report.md` with relevant source links and career
uncertainties. Technical errors and provider setup/debugging belong in internal
records. If unavailable evidence limits a conclusion, say which career fact could
not be verified, without inserting tool logs. Deliver the verified report PDF with
any requested CV in the same consultation folder.
