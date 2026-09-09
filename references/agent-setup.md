# Agent-managed first-run setup

Read before the first mode on a new machine, or when an environment check reports
a missing capability needed for the task. The agent executes setup; do not hand
the user a list of terminal commands. A request to set up or use job-hunt includes
ordinary dependency preparation. Respect an explicit no-install preference and
the host's actual execution permissions. Do not add a separate approval step for
each dependency. Use CDP with the user's daily browser; extensions are not a
required dependency. Browser connection consent, account login and human
verification remain with the user.

## Reuse, then install what the task needs

1. Locate the installed skill root and inspect the OS, executable paths and
   versions. Reuse working Python, Node, OpenCLI, browser and rendering tools.
   Do not upgrade, downgrade or replace a working installation just to match a
   test version. Read the current official requirements before a new install.
2. Ensure Python 3.10+ is available, using the host's provided runtime or an
   official distribution/package manager. Create or reuse a dedicated virtual
   environment, install `requirements.txt`, and use that interpreter for every
   job-hunt command. Do not install into an externally managed system Python.
3. Run `python scripts/doctor.py` from the skill root using that interpreter.
   `--install` installs missing Python packages only; **this is the helper's
   scope, not a prohibition on the agent installing other dependencies**.
4. Install missing tools needed for the requested output. For live discovery,
   prepare Node/npm, OpenCLI, AnySearch, web-access and the daily browser
   connection as described below. For PDF output, prepare Pandoc, a usable
   LaTeX engine (prefer a smaller working option such as Tectonic), Poppler and
   fonts required by the output language. Reuse an existing LaTeX engine; do not
   install a second one merely because its name differs. Assessing a pasted job
   does not require setting up a browser, and Word-only output does not require
   installing the PDF toolchain.
5. Use an available package manager or official portable distribution appropriate
   to the OS. For example, Homebrew on macOS, a detected distribution's package
   manager on Linux, or verified winget packages on Windows. Check package names
   and availability rather than assuming an apt package exists everywhere.
   Prefer user-writable installs if a system prefix is unavailable. Do not alter
   unrelated environment settings or ask for a password in chat. If the OS or
   host requires an approval the agent cannot provide, report that specific
   blocker after completing the independent preparation.

## OpenCLI

Use the [official OpenCLI installation instructions](https://github.com/jackwener/opencli#quick-start)
and [release assets](https://github.com/jackwener/opencli/releases). For automation,
the npm CLI route avoids a separate desktop-app setup flow:

```sh
node --version
npm view @jackwener/opencli version engines --json
npm install --prefix "$tool_dir" @jackwener/opencli
```

Choose `tool_dir` as a durable, dedicated user-writable tool directory before
running the example; do not use the skill checkout. Only install when OpenCLI is
absent or unusable, after checking the current Node requirement. Prefer this
non-global install: upstream global-install hooks can synchronize/delete local
adapter overrides. Do not run those hooks over a user's custom adapters. Prepend
`<tool_dir>/node_modules/.bin` to the agent's subprocess PATH (on Windows this
contains `opencli.cmd`) and include the chosen Node executable's directory.
Then run `opencli --version` and verify it resolves to that installation.
Keep runtime, tool directory and executable paths in the workspace setup record
so later tasks use the same tools without shell-profile edits. Invoke commands
with correctly quoted paths or argument arrays, including spaces. If an older
broken installation needs replacement, preserve its custom adapters first; do
not delete the old installation merely because the new command works.

Do not download or require the OpenCLI extension. Inspect the installed version
and adapter help before using CDP: `OPENCLI_CDP_ENDPOINT` alone does not enable
website CDP in every released version. Follow [daily-browser.md](daily-browser.md)
for the connection and compatibility decision; a working browser route does not
need an unsuccessful OpenCLI call first.

## AnySearch and web-access

Reuse installed, working skills. Otherwise install from the official repositories:

- [AnySearch](https://github.com/anysearch-ai/anysearch-skill): resolve a current
  release tag, download its archive and place the skill under `anysearch` in the
  host's actual skill directory. Read its `SKILL.md`, run its offline `doc` entry
  check using an available runtime, and record the working command in
  `runtime.conf` as upstream describes. Use anonymous access by default; no API
  key or account registration is required. Reuse a configured key without
  exposing it. Do not register an account just to complete setup. Verify a small
  public query; quotas or unavailable service are reported as such.
- [web-access](https://github.com/eze-is/web-access): use its documented
  `npx skills add eze-is/web-access` installation, selecting the current host,
  or place a reviewed release/commit checkout in its actual skill directory as
  `web-access`. Inspect installer help before choosing unattended flags. Read the
  installed skill and run
  `node <web_access_dir>/scripts/check-deps.mjs --browser chrome` (or the supported browser the user selected). Use the Node version
  required by that release; current CDP scripts require Node 22+.

Choose the skill directory from the host's configured search roots; do not assume
Claude's path on Codex. Do not overwrite an existing skill or its configuration.
For downloaded archives, reject absolute and parent-traversing paths, verify the
root `SKILL.md` and entry scripts, and record the exact release/commit and path.
These are upstream dependencies, not vendored copies in job-hunt. If the host
cannot hot-load a skill, read its installed instructions and use its documented
CLI in this task. Do not require an agent restart merely to discover its tools.

Use AnySearch `batch_search` for independent queries and the shared concurrency
rules in [daily-browser.md](daily-browser.md). Use its current command help;
do not invent an npm package called AnySearch. If anonymous quota is exhausted,
continue independent sources and explain the gap; do not rotate identities.

## Finish and resume

Before using an OpenCLI adapter for the first Indeed or 51job read, follow [opencli-compat.md](opencli-compat.md)
to check and automatically apply recognized patches. A new OpenCLI version is
used normally; an unsupported patch does not justify a downgrade. Local setup
does not clear any site's refusal lock or authorize account login.

Re-run the relevant capability checks after installation. Verify the actual PDF
render when PDF output is needed and an actual page read in the selected daily
browser for live browser reads. `doctor.py` checks the OpenCLI route only; its
missing-bridge warning does not invalidate a verified CDP/host-browser route.
Proceed with the user's original task, using the recorded executable paths; do
not stop at “dependencies installed.” Record what was reused, installed, tested,
and still blocked in `setup.md` in the task workspace (no credentials). Retain
the installed skills and active runtimes; delete only disposable download and
installation scratch files created by this run.

Validation must distinguish a fresh prefix/virtualenv on an existing OS from a
clean machine: the former does not test missing Python/Node, package-manager
bootstrap, OS prompts, or Windows/Linux behavior. Unit tests also do not prove
that the user authorized a browser connection or that a site accepted access.
