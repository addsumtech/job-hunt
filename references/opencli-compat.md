# Known OpenCLI compatibility patches

OpenCLI remains the default reader. The optional patches here address defects
reproduced with `@jackwener/opencli` 1.8.7; they are maintained by this skill,
not an OpenCLI upstream release. Before the first Indeed or 51job read, the agent
runs the read-only check below. If all affected bytes match the known original or
patched version, apply automatically; users need not copy commands or approve
this reversible local compatibility repair. Unknown versions or custom edits
are left unchanged. A rejected patch is not proof the installed adapter is broken:
use the normal reader, or the browser fallback when incompatibility is diagnosed.

## Diagnosed defects

| Observed defect | Narrow repair | Verified scope |
|---|---|---|
| 51job's `/pc/search?keyword=…&searchType=2` navigation times out while `/pc/search` renders results | Open the plain entry page; retain the existing keyword, area and limit in the search API request | Python / Shanghai / 3 rows on 2026-09-09 |
| Indeed detail returns a sign-in heading as a job | Detect account pages with no job description and report a login error | Account-page DOM regressions and classifier stop-lock tests |
| Indeed puts `Full-time` into salary, losing job type | Separate labelled pay and job-type fields; only use pay-like header text as salary | Real no-pay posting plus pay/type DOM variants |
| Indeed search cards have ids but empty titles | Read the identified title link, including its existing title-attribute variant | Real search and DOM variants |
| Indeed header's `Remote` has no old location test id | Read the observed company-header sibling when the explicit location markers are absent | Real detail and old/new header DOM variants |

## Check, apply, revert

`python scripts/opencli_compat.py --site indeed` is read-only; substitute `51job`
for that adapter. It checks the installed package version and exact source hashes.
Unknown versions, official-source drift, or local edits are refused, not guessed
at. `--package-dir` supports installations where the executable wrapper does not
resolve to the npm package. `--config-dir` supports a different OpenCLI config
root (the default respects `OPENCLI_CONFIG_DIR`).

For recognized source, the agent runs:

```sh
python scripts/opencli_compat.py --site indeed --action apply
opencli validate indeed
```

The helper creates a local override from the installed adapter only when none
exists. It never ejects over an existing override, and only edits recognized
bytes in the listed files, preserving other adapter files. It never edits the installed npm package, contacts
a site, changes browser settings, installs dependencies, or retries a stopped
source. A second apply is a no-op. All files are checked before any is written.

Revert only this skill's recognized edits:

```sh
python scripts/opencli_compat.py --site indeed --action revert
```

The local override remains, with the original file contents. Use `opencli adapter
reset <site>` only if the user intends to discard that **entire** local override.
After upgrading OpenCLI, re-check; don't force an old patch onto new source.

The versioned replacement data is in [opencli-patches/1.8.7.json](opencli-patches/1.8.7.json).
Upstream-derived snippets retain the [OpenCLI Apache-2.0 license](opencli-patches/LICENSE).
They were modified for the fixes listed above; no candidate data or cookies are
part of these patches.

## Browser fallback is independent of patching

When a supported browser can complete the requested search but a **diagnosed
adapter incompatibility** prevents extraction, use `unsupported_extraction` under
[browser-fallback.md](browser-fallback.md). Preserve the failed adapter output
and the evidence for the incompatibility. A patch is optional, not a required
step before browser use. Read and import the actual page results with their
URLs, timestamps and verbatim text; do not pass a browser capture off as an
adapter response. The bundled fallback reads known URLs and links. If the site needs an
interactive search that its adapter cannot execute, request the result URL or
original JD from the user; do not claim that a known-URL capture tested its search box. Google/search-engine discovery is a separate source
strategy, not the definition of built-in CDP and not a substitute for a site's
search acceptance test.

One timeout or blank field alone is not that diagnosis. A login wall, CAPTCHA,
permission denial or rate limit still stops the site across tools. Fixing local
code does not authorize a new read after such a refusal; follow the existing
user-confirmed recovery workflow. Never call all live tests passed merely because
unit tests or a patch checksum passed.

The optional DOM integration tests exercise the actual patched browser scripts:
with `jsdom` available to Node and `OPENCLI_TEST_ADAPTER_DIR` pointing to the local
`clis` directory, run `node --test scripts/tests/opencli-dom.test.cjs`. No live
site access is made by these tests.
