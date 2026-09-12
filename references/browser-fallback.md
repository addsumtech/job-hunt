# OpenCLI-first read-only browser fallback

First inspect OpenCLI's version, read-adapter help and offline website CDP routing
with `python3 scripts/doctor.py`. Do not run OpenCLI's extension-oriented health
probe or instantiate Browser Bridge. The selection order is fixed:

1. Use **OpenCLI** when the required read adapter actually uses CDP and the
   selected browser/profile connection is verified.
2. Use **built-in CDP** only when that probe diagnoses `cli_missing`,
   `bridge_disconnected` (the selected CDP connection failed), or
   `unsupported_extraction` (including a website factory that selects Browser Bridge).
3. If built-in CDP is unavailable after the diagnosis, disclose the gap;
   do not switch back to OpenCLI for the same round. The built-in reader is a one-way
   fallback, not a second route for re-reading the site.

Never use browser extensions, including ones already installed or connected.
A successful extension health check or an endpoint variable alone is not proof
that a website command uses CDP. Preserve the actual offline probe output and
version; do not execute a disallowed backend to manufacture a fallback reason.

Use job-hunt's bundled `scripts/browser_cdp.mjs` with the selected daily browser.
It needs Node 22+ and no separate browser skill. Do not assume a localhost port, restart the user's browser or
change its settings. A browser tool policy denial remains a denial.

## Check a local CDP boundary before falling back

A sandbox can reject a local CDP connection. Retain the actual error and, when
available and authorized, verify the same selected connection through the
platform's approved host-local or unsandboxed path. Ask only for a permission the
platform actually requires; existing authorization is sufficient.

- If that route works, repeat the single bounded read using the same CDP path.
- If it still fails, `bridge_disconnected` permits the one-way browser CDP fallback.
- `EADDRINUSE` does not authorize killing a shared process, changing its port,
  reinstalling tools or restarting the user's browser. Extension daemon status
  is not evidence for this CDP check.

This applies only before a site refusal. A captcha, login wall, 401/403/429 or
platform limit stops the site across every execution path and backend.

Only these reasons are accepted by the recorder:

- `cli_missing`: executable unavailable.
- `bridge_disconnected`: diagnostic confirms the selected CDP connection is unavailable.
- `unsupported_extraction`: no suitable documented read extraction, including an
  adapter that cannot serve the requested market or a diagnosed adapter
  incompatibility while the requested browser search demonstrably works.
  Preserve the help/diagnostic evidence under `raw/` and explain the reason in
  shortlist §0. Known optional repairs are in [opencli-compat.md](opencli-compat.md);
  patching is not required before using a supported browser fallback.

A generic timeout, blank fields or unclassified transport error does not establish
one of these reasons. Diagnose first using [network recovery](network-recovery.md);
existing detail recovery still applies. A site refusal (captcha, login wall,
401/403/429, platform limit) is different from a backend capability failure: it
stops this site for this round across both allowed retrieval backends. Use the
same stable `site` name for both backends, e.g. `51job`.

The stop is keyed on three things, so a rename does not quietly reset it: the
declared name, the host actually read, and the hosts that name was already seen
using in this journal. `51job`, `51job.com` and `www.51job` are one site; so is a
differently-named read whose URL resolves to a host the refused site had already
used, which is how `boss` and `zhipin.com` are joined without anyone maintaining
a table of adapters to domains. **A rename that shares no text with the refused
name and no host the run has actually seen cannot be joined to it** — the check
says so rather than pretending otherwise, and the stable name is what keeps that
edge from mattering. Pause and follow [user recovery](user-recovery.md): explain
what happened, ask the user to resolve login/verification themselves, and wait.
Their explicit confirmation that they completed the action and want to continue
is the request for a new bounded round; they need not restate the search brief.
The new round keeps the same source/backend and preserves the old evidence.
Never switch backends after a refusal. If no approved browser capability exists,
request a pasted JD/export and disclose that live discovery was unavailable.

## Capture, then import

Use the selected read-only browser tool to open/read the page. Navigation and the user's requested job
search are allowed; login submission, applications, recruiter messages and any
other account mutation are not. Record every retrieved search/detail page,
including empty results and refusal pages, immediately and before another read of the same site. Independent sites may
be in flight; one coordinator imports captures serially.
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

For the bundled reader, capture directly to a new workspace file:

```sh
node scripts/browser_cdp.mjs --browser chrome --url '<original-page-url>' \
  --output '<ws>/raw/<site>-browser-1.json'
```

The helper creates and closes its own background tab, captures the rendered DOM,
and records a main-document HTTP status when CDP reports it. It never selects an
existing tab. Read/classify and import this file before the next read of the same
site. Navigation failures return an error, not an empty success. The reader
supports known HTTP(S) URLs; it does not submit forms or synthesize clicks. If a
source requires unsupported interaction, retain that limitation and request a
user-provided original URL or JD. Do not install another browser skill to fill it.

Rendering waits use three increasing budgets: 15, 30 and 60 seconds in the same
tab. For a job page whose shell loads first, add `--wait-for-text "About the job"`
(or its observed local-language heading). A timeout retains the actual DOM for
diagnosis; `load_timed_out: true` with no extracted rows is recorded as transport,
not zero matches. Login and human-verification pages stop the wait and require
the user hand-off below, including a verification screen that keeps spinning.

Save the JSON string's contents as `raw/<site>-browser-<n>.json`, without rewriting
its text or URLs. If a tool reports a refusal outside the DOM (HTTP 403, for
example), retain that output and set `http_status: 403` or `blocked: true` on the
snapshot; never record it as an empty successful page. Bare navbar links labelled
Login do not establish a login wall. Explicit wall language does.

If a tool returns richer link objects, preserve its original output and make a
separate deterministic projection to the snapshot shape above: retain `text`
unchanged and extract only original HTTP(S) link URLs. Do not pass link objects
or `javascript:` links to the importer, and never reconstruct text from memory.
Workers must return that shape to the coordinator and wait for import/classification
before their next read of the same site. A late bulk import does not establish
that this ordering was followed; retain the deviation and rerun a bounded sample.

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
  --backend builtin-cdp --fallback-reason unsupported_extraction --command search \
  --query 'Python' --page 1
```

This importer performs no network operation. Exit 0 means **recorded**, even for
`classification: platform_limit`; inspect that result and stop the site. Exit 2
means invalid input; repair the evidence/reporting error before any further read.
Select the actual `--backend`: `builtin-cdp` (default). Older backend identifiers remain readable only for
historical capture verification. Use the actual diagnosed fallback reason; the example assumes
`unsupported_extraction`. The recorder retains `preferred_browser` for older
captures, but it is not a capability diagnosis for a new OpenCLI-first round.
It appends `browser_call` with that backend, `operation: snapshot`, query,
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
