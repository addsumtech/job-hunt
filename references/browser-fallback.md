# Read-only browser fallback

OpenCLI is preferred when the required read adapter and its connection work.
Before the first call, run `opencli doctor` (with a bounded process timeout) and
inspect the adapter's help. This is a capability probe, not a login operation.
If the CLI is missing, its browser bridge is disconnected, or no documented
extraction command serves this page/market, use an available **web-access** skill.
Read that skill and follow its supported browser setup; do not assume a localhost
port, install extensions, restart the user's browser, or change browser settings.
A browser tool policy denial remains a denial, never a fallback trigger.

Only these reasons are accepted by the recorder:

- `cli_missing`: executable unavailable.
- `bridge_disconnected`: diagnostic confirms the required bridge is unavailable.
- `unsupported_extraction`: no suitable documented read extraction, including an
  adapter that cannot serve the requested market. Preserve the help/diagnostic
  evidence under `raw/` and explain the reason in shortlist §0.

A generic timeout, blank fields or unclassified transport error does not establish
one of these reasons. Diagnose first; existing detail recovery still applies.
A site refusal (captcha, login wall, 401/403/429, platform limit) stops this site
for this round across **both** tools. Use the same stable `site` name for both
backends, e.g. `51job`.

The stop is keyed on three things, so a rename does not quietly reset it: the
declared name, the host actually read, and the hosts that name was already seen
using in this journal. `51job`, `51job.com` and `www.51job` are one site; so is a
differently-named read whose URL resolves to a host the refused site had already
used, which is how `boss` and `zhipin.com` are joined without anyone maintaining
a table of adapters to domains. **A rename that shares no text with the refused
name and no host the run has actually seen cannot be joined to it** — the check
says so rather than pretending otherwise, and the stable name is what keeps that
edge from mattering. Let the user
resolve a login/captcha themselves, then start a separately requested new round.
Never switch backends after a refusal. If no approved browser capability exists,
request a pasted JD/export and disclose that live discovery was unavailable.

## Capture, then import

Use web-access to open/read the page. Navigation and the user's requested job
search are allowed; login submission, applications, recruiter messages and any
other account mutation are not. Record every retrieved search/detail page,
including empty results and refusal pages, immediately and before another read.
Save the actual tool output; do not ask a model to recreate a snapshot from memory.
When the tool supports a read-only JavaScript expression, this snapshot shape can
be returned directly (HTTP status is unknown unless the tool actually reports it):

```javascript
JSON.stringify({url: location.href, retrieved_at: new Date().toISOString(),
  text: document.body.innerText,
  links: [...new Set([...document.querySelectorAll('a[href]')]
    .map(a => a.href).filter(u => /^https?:\/\//.test(u)))],
  http_status: null})
```

Save the JSON string's contents as `raw/<site>-browser-<n>.json`, without rewriting
its text or URLs. If a tool reports a refusal outside the DOM (HTTP 403, for
example), retain that output and set `http_status: 403` or `blocked: true` on the
snapshot; never record it as an empty successful page. Bare navbar links labelled
Login do not establish a login wall. Explicit wall language does.

Separately extract a JSON array into `raw/<site>-browser-<n>-rows.json`:

```json
[{"source_id":"job-1234","url":"https://careers.example.org/jobs/job-1234",
  "title":"Python Engineer","raw_text":"Python Engineer\nExample Ltd\nLondon"}]
```

Each card's `raw_text` is a contiguous verbatim piece of snapshot text; title must
occur in that piece, and URL/identifier must exist in the snapshot. For missing
IDs, use the original job URL as `source_id`. Company-only links are not job URLs.
Missing fields stay empty; a card is not a complete JD. Refusal and genuine empty
pages have `[]` rows, distinguished by the snapshot's status/text.

```bash
python3 scripts/record_browser_capture.py --workspace <ws> --site 51job \
  --snapshot-file <ws>/raw/51job-browser-1.json \
  --rows-file <ws>/raw/51job-browser-1-rows.json \
  --fallback-reason unsupported_extraction --command search \
  --query 'Python' --page 1
```

This importer performs no network operation. Exit 0 means **recorded**, even for
`classification: platform_limit`; inspect that result and stop the site. Exit 2
means invalid input; repair the evidence/reporting error before any further read.
It appends `browser_call` with `backend: web-access`, `operation: snapshot`, query,
page, row count, classification, source URL/time and both file hashes. It does not
fabricate an `adapter_call`, shell command or OpenCLI access metadata.

In `shortlist.yaml`, browser rows use `extraction_method: browser_page`, copied
`source_id`, `url`, `title`, `raw_text`, `retrieved_at`, and the usual quality and
verification fields. `sources` uses the same site, `command: search` (or `detail`),
actual classification, counts and both `raw_files`. If a site used multiple
commands, omit `sources.command` to aggregate them; do not hide failed calls.
All existing page, query, count, detail and disclosure rules apply. The row
budget counts search rows returned across both backends per site, before
shortlisting or de-duplication; discarding a row does not undo the read. Browser
`--page` is the page actually visited, not a counter reset on every query.

Run `check_no_write.py` and `check_shortlist.py` normally. They read both types of
retrieval, reject altered/missing captures, unknown browser operations, invented
browser rows, missing queries, excess pages and reads after a refusal. Mark any
browser detail fetch `quality: complete` only when the full JD was obtained;
partial detail fetches also need `detail_fetch_exceptions` if their final verdict
is outside the top three. Follow the detail cap before fetching, not after.

These checks establish consistency of recorded evidence. They cannot prove a
snapshot's browser origin or detect operations absent from the journal. Keep the
actual tool trace and never claim that a hash proves an unlogged action was safe.
