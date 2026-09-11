# Agent-managed first-run setup

The user installs job-hunt only. Its AnySearch client, browser reader and OpenCLI
CDP patches are bundled; do not install or invoke another skill. The agent runs
setup and continues the original task rather than handing the user installation
commands. Ordinary dependency preparation is included in a request to use this
skill. Respect an explicit no-install preference and actual host permissions.
Never use browser extensions, including already installed ones.

## One setup entry

Locate the skill root. Select a working Python 3.10+ from the host runtime or
installed interpreters; `python3` can still be macOS's older system Python. If
none exists, the agent prepares Python from an official distribution or an
available OS package manager. Do not ask the user to install each dependency.
On Linux, a Python without `venv`/`ensurepip` may need its distribution's matching
venv package. If the host requires an approval the agent cannot provide, state
that specific blocker after completing independent preparation.

From the skill root, using that interpreter:

```sh
python scripts/setup_dependencies.py
```

This creates/reuses a private virtual environment and installs `requirements.txt`
(PyYAML, python-docx, PyMuPDF), without touching system Python. For live discovery,
add `--discovery` and the customer's selected daily browser:

```sh
python scripts/setup_dependencies.py --discovery --browser chrome
```

Use `edge` when that is the customer's browser; infer from the session when
known, otherwise clarify the browser choice. This also:

- Reuses Node 22+ or downloads an official Node 22 LTS binary, verifies its
  SHA-256 against the official release manifest, and extracts it privately.
- Installs OpenCLI 1.8.7 in a private npm prefix with lifecycle hooks disabled,
  then applies the bundled, checksum-guarded CDP-only patches. No extension is
  installed or contacted. An existing private installation is reused; unknown
  edits are preserved and reported. Global OpenCLI and custom adapters remain
  untouched. This version is pinned because the patches target its exact bytes.
- Checks the bundled AnySearch client's offline `doc` command. It requires no
  npm packages, account registration, API key or separate skill installation.

The default runtime root is `~/.local/share/job-hunt` (`%LOCALAPPDATA%/job-hunt`
on Windows); `--root PATH` selects another user-writable location. `runtime.json`
stores executable paths and browser selection, never credentials. `--node PATH`
can select an existing Node 22+ executable. Setup requires internet access for
missing packages; it does not imply an offline installation bundle.

## Use the prepared runtime

Use the wrapper from the skill root so every command resolves to the prepared
Python, Node and OpenCLI, including paths with spaces:

```sh
python scripts/run_tool.py python scripts/doctor.py
python scripts/run_tool.py opencli --version
python scripts/run_tool.py anysearch doc
python scripts/run_tool.py browser --url https://example.com --output raw/page.json
```

Pass `--root PATH` before the tool name when setup used a custom root. The wrapper
adds the private executables to subprocess PATH; no shell-profile edit is needed.
All `python`, `node`, `opencli` and AnySearch examples in other references refer
to these prepared tools. For direct commands, use the exact recorded executable
paths and the wrapper's PATH layout, not an unrelated global installation.

The OpenCLI wrapper discovers the selected daily browser's current endpoint for
each live command. `--browser edge` before `opencli` temporarily overrides the
saved choice. It never launches a separate browser, reads cookies/history,
changes settings, or operates existing tabs. Follow [daily-browser.md](daily-browser.md)
for browser support and connection consent. Verify OpenCLI's offline website
CDP routing with `doctor.py` before a site read; help/version success does not
prove the live connection. Diagnose unsupported routes before using the bundled
reader under [browser-fallback.md](browser-fallback.md).

AnySearch's bundled entry is `third_party/anysearch/anysearch_cli.js`. Read its
`doc` output for current command/parameter schemas; use `batch_search` for
independent queries. It uses an HTTP API, not CDP. Anonymous quotas and service
failures are reported as such; do not rotate identities. An explicitly configured
API key can be inherited via environment without printing it.

## Prepare conditional capabilities only when needed

| Requested capability | Dependencies / preparation |
|---|---|
| Assess, interview, Markdown and Word documents | Default setup's Python environment |
| Consultation report PDF in Chinese, English, Japanese, Korean or Spanish | Default setup: PyMuPDF and bundled report fonts; no Pandoc or TeX required |
| Template-based CV/letter PDF | Pandoc, Tectonic or XeLaTeX, Poppler, and output-language fonts; agent installs missing tools and verifies a real render |
| CJK template-based CV PDF | A usable XeTeX engine plus xeCJK and the selected fonts; LuaLaTeX/pdfLaTeX alone do not satisfy this capability |
| Japanese form PDF | Follow the template's Word/LibreOffice export workflow; prepare its converter only when requested |
| GitHub-specific research | Reuse or prepare official GitHub CLI `gh`; existing login may be needed, and remains with the user |

For conditional tools, use an available OS package manager or official portable
release, verify package names for that OS, and prefer user-writable installs.
Reuse an existing compatible engine instead of installing a second one. Do not
assume apt or Homebrew exists everywhere. A doctor's missing optional capability
does not block a task that does not need it. `doctor.py --install` still only
installs Python packages; the setup entry above owns the broader common runtime,
and the agent prepares conditional tools as needed.

## Finish and resume

Before the first Indeed or 51job read, follow [opencli-compat.md](opencli-compat.md)
to check and apply recognized adapter patches through the prepared Python/PATH.
The separate CDP patch sources and Apache-2.0 license are in `assets/opencli-cdp/`;
AnySearch's source provenance, license and notices are in `third_party/anysearch/`.

Verify a small public AnySearch query and an actual bounded page read when live
research is needed. Site login, verification challenges and browser connection
consent remain with the user. Local setup never clears a site's refusal lock.
Record reused/installed tools, exact runtime paths, verified capabilities and
remaining blockers in the task workspace's `setup.md`, without credentials.
Continue the original task. Retain active runtimes; remove disposable download
and installation scratch files.

A fresh prefix/virtualenv on an existing OS is not a clean-machine test. Report
separately whether missing-Node download, Python bootstrap, OS prompts, native
Windows/Linux behavior and actual site access were tested.
