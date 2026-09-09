# Daily browser and concurrent research

## CDP first; no extension installation

For browser reads, prefer a supported CDP connection to the user's daily browser
and profile, retaining that profile's existing login state. Public APIs, AnySearch
and static pages need no browser. Follow an explicitly selected browser. Verify
browser/profile identity before reading: a host's default may be an isolated
agent browser or an in-app browser. Do not silently use those as the daily browser.
If multiple daily profiles remain ambiguous, ask which one to use.

1. Reuse an authorized connection to the intended daily browser, preferring CDP.
   A working host browser connection is also usable without installing anything;
   describe its actual transport rather than claiming it proves extension-free
   CDP. Open only task-owned tabs and retain their IDs. Do not read unrelated
   tabs, history, credentials or cookies to establish access.
2. If no suitable connection exists, prepare web-access via
   [agent-setup.md](agent-setup.md). Verify its reported browser identity, not just
   a healthy localhost proxy. Never kill a shared proxy/daemon or restart the
   daily browser to change its target. Use an independently supported connection
   or report the specific remaining connection action.
3. On supported Chrome (144+), the user enables remote debugging at
   `chrome://inspect/#remote-debugging` and accepts Chrome's connection prompt.
   Agent tools handle the rest. A supported Chrome DevTools MCP connection using
   `--autoConnect` is another route. Verify current runtime help and status before
   starting: its default fresh/headless browser does not inherit daily login.
   Edge support follows installed web-access/browser capabilities; do not promise
   this mechanism on every browser or managed machine.
4. OpenCLI is an optional extraction layer over a verified connection. Inspect
   the installed runtime and official help before selecting its CDP endpoint.
   Version 1.8.7 still selects Browser Bridge for ordinary website adapters even
   with `OPENCLI_CDP_ENDPOINT`; upstream commit
   [4e8109b](https://github.com/jackwener/opencli/commit/4e8109b6c84afea5e535a7b9a35bc352d1b92fc2)
   fixes that selection. Re-check newer releases rather than assuming the fix is
   installed. If an adapter requires the extension, use web-access CDP directly
   and record browser evidence. Do not install an extension or patch global
   OpenCLI core to make this route work.

Chrome's consent is distinct from macOS automation permission. This is minimal
manual setup, not guaranteed zero configuration. Modern Chrome does not honor
legacy remote-debugging flags on the default data directory; do not relaunch the
user's browser with those flags, copy a profile, or export cookies as a shortcut.
Close only tabs created for this task when finished. Site refusal and login
recovery rules still apply across all tools and survive a connection change.

Official references: [Chrome existing-session connection](https://developer.chrome.com/blog/chrome-devtools-mcp-debug-your-browser-session),
[default-profile debugging restriction](https://developer.chrome.com/blog/remote-debugging-port),
[OpenCLI CDP guide](https://github.com/jackwener/opencli/blob/main/docs/advanced/cdp.md).

## Parallelize independent sources

Apply this to all research modes and information sources, including job boards,
company sites, AnySearch, GitHub, articles and public video metadata. Do not run
unneeded sources merely to fill a batch.

- Schedule independent reads concurrently, normally at most **4 in flight** in
  total, with at most **1 per protected site**. Lower limits from a provider or
  the host take precedence. Count individual queries inside AnySearch
  `batch_search` against the total; batch up to available capacity. If batch is
  unavailable, use bounded parallel tool calls. Inspect every success or error.
- Give each browser read its own task-owned tab ID/session. Never share a global
  active page. If a backend cannot reliably isolate targets (including an
  OpenCLI CDP endpoint that automatically picks one page), serialize that backend
  while other independent sources continue in parallel.
- Same-site pagination, dependent detail reads and login recovery are sequential.
  Classify and import a site's current capture before scheduling its next read.
  On refusal cancel queued work for that site and follow user recovery; do not
  switch tools or launch another worker. Already authorized independent sites
  may finish. Existing per-site page, query, row and detail budgets are shared
  across workers/backends, never multiplied by concurrency.
- One coordinator owns budgets and appends journal/import receipts serially as
  results arrive. Give raw captures unique filenames; workers must not append
  to the same journal concurrently. Preserve original outputs, partial failures
  and source identity, then deduplicate findings for the report.

Use native parallel tool calls; extra agents are not required. If concurrency is
not supported, serialize only the affected operations and record that limitation.
Profile reuse does not authorize a new social platform: existing per-consultation
platform authorization and anonymous-source requirements remain unchanged.
