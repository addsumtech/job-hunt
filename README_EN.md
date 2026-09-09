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

### First use: let the agent prepare the environment

After installing the skill, tell the agent: **“Set up job-hunt and start my task; I will load the Chrome extension.”**

The agent reuses working tools, installs the Python dependencies, Node.js, OpenCLI and document tools needed for your task, and downloads and extracts the [official OpenCLI extension](https://github.com/jackwener/opencli/releases). You do not need to copy terminal commands.

**Normally, your only manual setup step is loading the Chrome extension:**

1. The agent opens `chrome://extensions/` and gives you the full extracted folder path.
2. Enable **Developer mode**, click **Load unpacked**, and select the prepared folder directly containing `manifest.json`, not the ZIP. On macOS, `Command + Shift + G` lets you paste the path.
3. Tell the agent it is loaded. The agent runs `opencli doctor`, verifies extension and connectivity, applies eligible compatibility patches, and resumes your task. A connected extension is reused.

Keep the loaded extension directory in place. Site login, CAPTCHA or a system permission requiring your action still needs you; the agent completes the independent preparation first and explains only the remaining action.

`doctor.py` checks actual capabilities; `doctor.py --install` installs Python packages only. The agent installs other tools through the [first-run setup workflow](references/agent-setup.md). Word-only output or assessment of a pasted posting does not require unrelated PDF/browser tools.

### Compatibility patches and browser fallback

The patches ship with this skill and the agent applies them before the first relevant site read; importing the browser extension alone does not install them.

**You normally do not need to install patches manually.** Before reading Indeed or 51job, the skill checks known compatibility issues and automatically patches a local copy only when the OpenCLI version and source bytes match. The installed package stays unchanged. Current patches target 1.8.7; other versions and custom edits are not overwritten. You can tell the agent “check job-site compatibility patches” or “revert compatibility patches.” See [check, apply and revert instructions](references/opencli-compat.md).

For a diagnosed adapter incompatibility, web-access can use **the job site's own search box** in Chrome or another supported browser and read the results. It is not limited to Google search and does not require a patch first. Login, CAPTCHA and permission barriers still require your action; switching tools cannot bypass them.

## Markets, platforms, and languages

Discovery reads postings through `opencli` adapters. The repository's source catalogue includes 51job, Indeed, LinkedIn, and BOSS Zhipin, with distinctions between login requirements, job listings, and interview-experience sources. Availability is checked at runtime. The Indeed adapter connects to the US site and cannot switch country sites. For other markets, prefer local job sources. See the [source catalogue](references/discovery-sources.md) and [source policy](references/source-policy.md).

For China, the skill also asks about employer preferences: large private companies, small and medium private companies, state-owned enterprises, and foreign companies. These affect ranking without silently filtering other categories. Nowcoder and 1point3acres provide interview and process context; forum posts do not become job-listing rows.

If login or human verification is required, the skill explains the obstacle, asks you to handle it in the browser, and pauses that source. Reply “done, continue” to start a new bounded round that preserves the earlier record and checks whether access has recovered. Rate limits and permission problems are explained separately. If access remains unavailable, choose another source, paste a posting, or review the results already retrieved. Discovery is read-only: it does not send messages, edit online profiles, or submit applications.

**Market rules and output language are separate.** The CV renderer includes section headings and personal-data labels in English, Dutch, German, French, Spanish, Italian, Chinese, Japanese, and Korean. `discover` and `assess` support counts cards, required headings and disclosures in Chinese, English, Japanese, Korean and Spanish using the [report language templates](references/report-localization.md). Some internal documents, diagnostics and sourced market-convention cards remain untranslated; PDFs also need fonts for the output language.

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

Every consultation includes a PDF report answering the client’s question, kept with the CV and requested documents in one `~/Downloads/<workspace-name>/` folder. Reuse one delivery folder across stages. Reports contain career analysis, evidence and relevant facts to confirm; tool diagnostics stay internal. Cover letters are on demand and mock interviews never start automatically. Delivery is incomplete until the PDF is generated and verified. [Supplementary sources](references/supplementary-sources.md) support official web, news, GitHub and public discussion research when relevant; logged-in Xiaohongshu/Douyin searches require explicit authorization for the current consultation.

Delivery uses `简历/` (resume) and `报告/` (report) subfolders, with names such as `简历.docx`, `简历.pdf` and `求职建议报告.pdf`; filenames exclude employer names and internal workspace identifiers.

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
