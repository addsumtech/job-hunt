# job-hunt: build every application on real experience

<p align="center">
  <a href="README.md">简体中文</a> ·
  <a href="README_EN.md"><strong>English</strong></a> ·
  <a href="README_JA.md">日本語</a> ·
  <a href="README_KO.md">한국어</a> ·
  <a href="README_ES.md">Español</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="For Claude Code and Codex" src="https://img.shields.io/badge/agents-Claude_Code_·_Codex-5b5bd6">
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="Release: v1.0.0" src="https://img.shields.io/badge/release-v1.0.0-1f883d"></a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="CV entries connected to their sources: a paper, notes, certificates and project work">
</p>

**Find roles, decide where to apply, tailor your materials, and rehearse the interview. Make your experience clear, along with the requirements you do not yet meet.**

job-hunt is a career skill for Claude Code and Codex. You provide a goal, a CV, or a job posting. The agent reads the material, checks the evidence, edits, typesets, and reviews; Python scripts check provenance, file consistency, and delivery conditions. Guidance covers technical, research, and other career paths, including career changes, employment gaps, new graduates, and international applications.

The aim is a CV whose every line you can explain in an interview from experience.

## Start with the step you need

| Mode | When to use it | Main output |
|---|---|---|
| **discover** | You have a direction and want roles worth exploring | A shortlist with real posting sources, retrieval status, and provisional assessments |
| **assess** | You have a posting and want to decide whether to invest time | Requirements mapped to evidence, hard barriers, gaps, and application advice |
| **apply** | You have chosen a role and need targeted materials | A tailored CV, optional cover letter, review records, and an interview brief |
| **interview** | You have a posting and CV and want to practise | One mock round, a transcript, two independent assessment passes, and open questions |

Use each mode independently. At the end of a round, you choose whether to continue with a suggested next step. A shortlist does not automatically become a batch of CVs. You decide whether to submit the finished materials and handle submission yourself.

After installation, try:

```text
Use job-hunt. Find me MRI reconstruction roles in the Netherlands.
Use job-hunt. Here is a posting link and my CV. Is this worth applying to?
Use job-hunt. Tailor my CV to this role and write a cover letter.
Use job-hunt. Run a technical mock interview based on this posting and my CV.
```

The agent confirms the mode and target market, then asks for the preferences and material it needs. You confirm the market; it is not inferred from past work locations or the language of the conversation.

## How real experience becomes an application

**Claims carry sources.** A new skill, tool, responsibility, or result must trace to a specific part of your source profile, an answer you gave during the session, or your own paper or project that the agent actually read. Existing experience can be reordered, emphasised, and reworded. Unsupported additions stay on the gaps list. `claims.yaml` records the links, and tailoring uses a copy of your profile while preserving the master.

**Assessments show their evidence.** Each must-have is marked as strongly evidenced, partially supported, or missing. Hard barriers, such as work authorisation or licences, come first. Thin inputs produce `insufficient_evidence` and an explanation of what is missing. The project prohibits invented interview or offer probabilities and arbitrary 0–100 fit scores; its prediction lint checks predefined expressions in all nine CV languages. ATS keyword coverage measures text coverage, not hiring odds.

**Standard CV applications receive three independent AI reviews.** The ATS reviewer checks keywords and parseability, the recruiter reviewer checks readability and basic eligibility, and the hiring manager reviewer checks experience, scope, and credibility. Each uses a fresh context. All three must return `PASS` to clear this internal review. Fixable issues lead to edits and another review, up to three rounds. A remaining gap that no truthful edit can close ends the loop early, with an explanation.

**Interview feedback checks what you actually said.** One assessment pass examines the answers; the other checks their factual sources. The skill helps you organise existing experience and clarify uncertain details. CV claims you cannot support go onto a correction list.

## Install

You need an agent environment that can run local commands and read and write files, plus **Python 3.10+**. Installation with `npx` also requires Node.js/npm. Choose one of the three paths below.

### Option 1: install with `npx skills`

```bash
npx skills add addsumtech/job-hunt
```

Choose your agent and installation scope when prompted. Use `-g` for a user-wide installation, `-a claude-code` or `-a codex` to select an agent, and `-y` to skip confirmation prompts. The repository root is the skill; its scripts and reference files must be installed with it.

### Option 2: install as a Claude Code plugin

Run inside Claude Code:

```text
/plugin marketplace add addsumtech/job-hunt
/plugin install job-hunt@job-hunt
/reload-plugins
```

Invoke it with `/job-hunt:job-hunt`. Run `/plugin marketplace update job-hunt` to update the marketplace. Keeping both a manual copy and the plugin may show the same skill twice.

### Option 3: clone and symlink

Useful for reading or editing the source. This example registers the skill with Claude Code:

```bash
git clone https://github.com/addsumtech/job-hunt.git
cd job-hunt
mkdir -p ~/.claude/skills
ln -s "$PWD" ~/.claude/skills/job-hunt
```

For Codex, replace `~/.claude/skills` with `~/.codex/skills` in the last two lines. If the destination already exists, inspect the existing installation first.

### Install dependencies and check the environment

Enter the installed **job-hunt root directory**, containing `SKILL.md` and `requirements.txt`, and run these commands with Python 3.10+:

First run `python3 --version` and confirm it is 3.10 or newer. If it is older, install Python 3.10+ and use its command (for example, `python3.12`) to create the virtual environment below.

```bash
python3 -m venv ~/.venvs/job-hunt
source ~/.venvs/job-hunt/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/doctor.py
```

The activation command above is for macOS/Linux; on Windows, use the activation script under the environment's `Scripts` directory. Have the agent use this Python environment for the project scripts too. The base packages are `PyYAML` and `python-docx`. `doctor.py --install` can install missing packages into the current Python environment.

| Capability | Additional dependency | What happens without it |
|---|---|---|
| CV and cover-letter PDFs | A LaTeX engine; `tectonic` is recommended | Markdown, Word, and `.tex` for later compilation remain available |
| Markdown reports as PDFs | `pandoc` and a LaTeX engine | Reports in Downloads may be Markdown only |
| PDF text extraction and checking | Poppler's `pdftotext` | PDF text integrity cannot be fully verified |
| Live job search | `opencli` and its browser environment | Assess, apply, and interview can still use a pasted posting |
| Chinese, Japanese, and Korean PDFs | Fonts for the output language | Install suitable fonts for reliable typesetting |

`doctor.py` attempts to generate an actual PDF and reports missing capabilities. Its `--install` option installs Python packages only; follow the report to install system tools.

### Set up the OpenCLI Chrome extension

**Live job retrieval needs both the OpenCLI CLI and Browser Bridge extension. Install the extension manually in Chrome.** Neither `npm install` nor `doctor.py --install` installs it for you.

1. **Install the CLI.** Run in a terminal:

   ```bash
   npm install -g @jackwener/opencli
   opencli doctor
   ```

   A disconnected extension is expected before you install it.

2. **Download and extract the extension.** Under Assets in [official OpenCLI Releases](https://github.com/jackwener/opencli/releases), download `opencli-extension-v*.zip`, not `Source code`. Extract it into a permanent location and find the folder directly containing `manifest.json`.
3. **Load it in Chrome.** Enter `chrome://extensions/` in the address bar, enable **Developer mode**, click **Load unpacked**, and select that folder. Select the folder, not the ZIP or `manifest.json` file. Review the extension permissions shown by Chrome.
4. **Check the connection.** Keep Chrome open and run `opencli doctor` again. Confirm **Extension: connected** and **Connectivity: connected**; a working CLI or daemon alone is not enough. Keep the extension folder in place.

| Problem | What to do |
|---|---|
| Cannot find the folder in the file picker | On macOS, press `Command + Shift + G` and paste the full path; folders beginning with `.` are hidden by default |
| Missing-manifest error | Select the folder directly containing `manifest.json`, which may be one level inside the extracted directory |
| Extension loaded but still disconnected | Confirm it is enabled in the current Chrome profile, then run `opencli doctor` again |

Sign in to job platforms yourself when needed. A connected extension confirms the browser connection; access to each platform still needs to be checked.


## Markets, platforms, and languages

Discovery reads postings through `opencli` adapters. The repository's source catalogue includes 51job, Indeed, LinkedIn, and BOSS Zhipin, with distinctions between login requirements, job listings, and interview-experience sources. Availability is checked at runtime. The Indeed adapter connects to the US site and cannot switch country sites. For other markets, prefer local job sources. See the [source catalogue](references/discovery-sources.md) and [source policy](references/source-policy.md).

For China, the skill also asks about employer preferences: large private companies, small and medium private companies, state-owned enterprises, and foreign companies. These affect ranking without silently filtering other categories. Nowcoder and 1point3acres provide interview and process context; forum posts do not become job-listing rows.

You handle any required login. A CAPTCHA, rate limit, or platform refusal stops retrieval from that site for the round and is disclosed. When real postings cannot be retrieved, the output is explicitly labelled as suggested directions. Discovery is read-only: it does not send messages, edit online profiles, or submit applications.

**Market rules and output language are separate.** The CV renderer includes section headings and personal-data labels in English, Dutch, German, French, Spanish, Italian, Chinese, Japanese, and Korean. Some required text and counts cards in `discover` and `assess` currently support English and Chinese only. Reports written entirely in Japanese, Korean or Spanish may fail validation and need English or Chinese structure. Five README languages do not imply complete workflow localisation; PDFs also need fonts for the output language.

The project includes **5 market-convention tables with 38 entries** for the US, UK, Germany, the Netherlands, and China, with sources and review dates. Entries past their review date are flagged, and missing market data is disclosed. These tables provide sourced context to be read within each entry's stated scope.

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="Repository rendering examples: a US-targeted CV omits personal data; a Germany-targeted CV retains a supplied photo and date of birth">
</p>

Personal data follows the target-market rules. For standard CVs targeting the US, Canada, UK, Ireland, Australia, or New Zealand, the renderer suppresses photos and `contact.personal` fields, and the workflow explains the change. Unrecognised markets also default to omission. Other recognised markets can display supplied information according to the rules. The image demonstrates renderer behaviour; it does not imply that every employer in a country requires the same format.

## What you receive

| Material | Formats and details |
|---|---|
| Tailored CV | Markdown, Word (`.docx`), and PDF; PDF typesetting also preserves `.tex` |
| Cover or motivation letter | Optional; Markdown, Word, and PDF |
| Japanese rirekisho (履歴書) | A separate form renderer produces a Markdown preview and editable `.docx`; export the form to PDF through Word or LibreOffice |
| Structured supporting statement | Evidence organised by criterion, with word-limit checks, for applications such as NHS and Civil Service forms |
| Assessment and interview material | Shortlists, fit assessments, interview briefs, mock transcripts, and debriefs |

Structured applications review the supporting statement against the employer's criteria. If a standard CV is also required, it receives the three-reviewer check separately. A Japanese rirekisho is checked for form completeness; its companion career-history document follows the standard CV review process.

Readable materials from each round are delivered to `~/Downloads` by default, for example `<company>-<role>-<date>-cv.md` and its PDF. PDF generation and verification depend on the toolchain; delivery reports identify missing files or incomplete checks.

## Where files live

Source profiles, application workspaces, and check records default to `~/.claude/job-profiles/`, including when running on Codex. Set `JOBHUNT_PROFILES_ROOT` to use another root directory.

Each person can retain source profiles in several languages, such as `profile.zh.yaml` and `profile.en.yaml`; the legacy `profile.yaml` is still supported. Applications have separate workspaces, and provenance records plus `journal.jsonl` preserve the check history. See [REFERENCE.md](REFERENCE.md) for the full layout.

Files are stored locally. Model calls and web access still depend on your chosen agent and its service configuration.

## Verification and further reading

Automated checks cover evidence references, source-profile preservation, verdict parsing, personal-data handling, rendering, and mode handoffs:

```bash
python3 -m pip install pytest
make check
make eval-lint
```

`make check` runs the Python tests, migration content-preservation check, and market-table checks. Some tests inspect the machine's skill installation and external tools, so read the results in that environment's context. **Passing checks do not guarantee correct output** or demonstrate job-search outcomes.

[`evals/`](evals/README.md) contains 20 behavioural evaluation scenarios. The recorded second iteration, dated 2026-09-05/06, paired 15 scenarios with and without the skill. Ten checks designed to distinguish the two groups changed from baseline `FAIL` to with-skill `PASS`. **There was one run per scenario per group, n = 1**. This is not a stable success rate or a forecast of hiring results. The full record also includes unexercised checks and an invalid scenario result: see the [evaluation record](evals/iterations/iteration-2-with-skill.md).

The repository also records a 2026-09-06 verification of the three CV reviewers through `codex exec`. See [agent portability](references/portability.md) for host mechanisms and the scope of that verification. Untested hosts are not presented as verified integrations.

- [SKILL.md](SKILL.md): mode routing and core rules.
- [REFERENCE.md](REFERENCE.md): architecture, workspaces, data structures, and script usage.
- [Example profile](assets/profile.example.yaml) and [claim-provenance example](assets/claims.example.yaml): structured data formats.
- [Evaluation guide](evals/README.md): methods and limitations.

These technical references are currently written mainly in English. Released under the [MIT License](LICENSE).
