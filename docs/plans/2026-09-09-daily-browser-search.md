# Daily-browser reuse and parallel source research

The user requested daily-browser login reuse, parallel information searches across
providers, and the fewest possible first-run actions. Preserve the current
consultation output work on this PR; no unrelated CV changes.

## Decision

Prefer CDP to the user's daily browser and selected profile. Reuse an already
authorized connection when suitable. On hosts without one, prepare web-access
or supported Chrome 144+ auto-connect/CDP. No extension installation is required.
Provide agent-managed OpenCLI, AnySearch and web-access installation. Fresh isolated browsers are not the default for
session-backed research. Public API/search queries do not need browser setup.

Direct CDP, a host browser connection, and OpenCLI are distinct capabilities.
As checked on 2026-09-09, npm/installed OpenCLI is 1.8.7; its ordinary-site factory
still selects BrowserBridge with OPENCLI_CDP_ENDPOINT set. Upstream commit
4e8109b6c84afea5e535a7b9a35bc352d1b92fc2 honors that variable for web adapters.
Do not promise the unreleased fix, patch installed core files, or equate a factory
probe with a successful site read. Prefer native browser capture when appropriate.

Chrome's official live-session path requires remote debugging to be enabled and
browser permission for a connection. It can avoid extension loading, but cannot
promise a single click on every machine. Never relaunch the default profile with
old debugging flags or copy browser credentials into an automation profile.

## Implementation boundary

- Add preferred-browser capture provenance alongside existing fallback reasons,
  preserving source refusal locks, row/page limits and evidence hashes.
- Teach setup and doctor messaging to distinguish missing OpenCLI/extension from
  missing live-browser capability. Do not force extension setup on a working host
  browser connection.
- Parallelize independent public searches and cross-site reads in bounded batches.
  AnySearch batch_search is one route, not the only parallel route. Keep one
  in-flight read per protected site and use distinct explicit tab/session IDs.
  The coordinator serializes receipt imports and owns counters/refusal state.
- Update the five README editions and relevant mode/source documentation.

## Evidence and completion criteria

Official Chrome documentation: https://developer.chrome.com/blog/chrome-devtools-mcp-debug-your-browser-session
Chrome default-profile flag restriction: https://developer.chrome.com/blog/remote-debugging-port
OpenCLI upstream fix: https://github.com/jackwener/opencli/commit/4e8109b6c84afea5e535a7b9a35bc352d1b92fc2

A live host-browser test reused the existing daily Chrome profile and two separate
task tabs. Both public official pages were read concurrently and the task tabs
were closed. This used an existing host extension, so it does not establish an
extension-free connection or login status on any job website. One navigation
wait timed out while the target DOM had loaded; inspecting the page confirmed
it without another navigation.

Complete when preferred browser records pass the existing evidence/refusal gates,
public and browser parallel rules are consistent across instructions, current
CI passes, and the PR accurately distinguishes verified capabilities from setup
paths that have not been exercised on a clean machine.
