# Agent-managed first-run setup

Read before the first mode on a new machine, or when an environment check reports
a missing capability needed for the task. The agent executes setup; do not hand
the user a list of terminal commands. A request to set up or use job-hunt includes
ordinary dependency preparation. Respect an explicit no-install preference and
the host's actual execution permissions. Do not add a separate approval step for
each dependency. The normal manual setup step is loading the prepared extension
in Chrome; account login and human verification remain with the user.

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
   prepare Node/npm, OpenCLI and Chrome. For PDF output, prepare Pandoc, a usable
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

## OpenCLI and the extension

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

Run `opencli doctor` and inspect its output before downloading anything. If the
extension and connectivity are already confirmed, reuse them and skip manual
loading. Otherwise:

1. Resolve an `opencli-extension-v*.zip` asset from an official release. The
   extension version is independent of the CLI version. Do not download GitHub's
   source-code archive or pin an old release merely to enable our patches.
2. Download and extract it into a durable, versioned directory in user storage,
   outside temporary folders and the replaceable skill checkout. Use the host's
   available download/archive tools. Reject absolute or parent-traversing ZIP
   paths; do not overwrite an existing loaded extension directory. Reuse a
   previously prepared directory only after checking its manifest.
3. Find the folder directly containing a valid `manifest.json`; verify that it
   is the extension root, not an outer wrapper. Record the asset URL, release,
   manifest version and absolute folder path. Open that folder and
   `chrome://extensions/` in the intended Chrome profile using available tools.
4. Give the user only the remaining action: enable Developer mode, choose
   **Load unpacked**, and select the prepared folder. On macOS, `Command + Shift
   + G` accepts its full path. Do not try to bypass Chrome's extension approval
   or edit its profile files. Wait for the user's completion reply.
5. Run `opencli doctor` again. Both extension and connectivity must be confirmed;
   a running CLI or daemon is not enough. With multiple profiles, use the profile
   the user selected; do not silently switch accounts. Diagnose ordinary local
   connection errors before requesting more user action. A repeated unchanged
   failure is a blocker, not a successful setup or a reason for an endless retry.

## Finish and resume

Before the first Indeed or 51job read, follow [opencli-compat.md](opencli-compat.md)
to check and automatically apply recognized patches. A new OpenCLI version is
used normally; an unsupported patch does not justify a downgrade. Local setup
does not clear any site's refusal lock or authorize account login.

Re-run the relevant capability checks after installation. Verify the actual PDF
render when PDF output is needed and Browser Bridge connectivity for live reads.
Proceed with the user's original task, using the recorded executable paths; do
not stop at “dependencies installed.” Record what was reused, installed, tested,
and still blocked in `setup.md` in the task workspace (no credentials). Retain
the loaded extension and active runtimes; delete only disposable download and
installation scratch files created by this run.

Validation must distinguish a fresh prefix/virtualenv on an existing OS from a
clean machine: the former does not test missing Python/Node, package-manager
bootstrap, OS prompts, or Windows/Linux behavior. Unit tests and a prepared ZIP
also do not prove that a human loaded the extension or a site accepted access.
