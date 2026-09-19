# job-hunt: find roles, create your CV, practise interviews

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
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="Release: v1.0.1" src="https://img.shields.io/badge/release-v1.0.1-1f883d"></a>
  <a href="https://skillhub.cn/skills/user_f486c577/best-job-hunt"><img alt="SkillHub: best-job-hunt" src="https://img.shields.io/badge/SkillHub-best--job--hunt-e8590c"></a>
  <a href="https://clawhub.ai/dong845/skills/job-hunt"><img alt="ClawHub: job-hunt" src="https://img.shields.io/badge/ClawHub-job--hunt-0f766e"></a>
</p>

<p align="center">
  <a href="CHANGELOG.md">Changelog (Chinese)</a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="Illustrated career workflow: find roles, assess fit, create a CV and practise interviews">
</p>

job-hunt is a career skill for Claude Code and Codex. It helps you find roles, decide where to apply, create a Chinese or English CV and application materials, and practise interviews.

Share your goals, experience or a posting link. The agent organizes the information, checks requirements, edits your documents and reviews their layout. Guidance covers new graduates, career changes, employment gaps, technical and research roles, and international applications.

## What it helps you do

| Feature | When to use it | What the agent does |
|---|---|---|
| **discover · Find roles** | You have a direction but need suitable openings | Searches by market and preferences, reads the full details of retained postings, and organizes links and advice |
| **assess · Decide whether to apply** | You want to evaluate a specific role | Compares requirements with your experience, identifying eligibility barriers, strengths, gaps and preparation effort |
| **apply · Create your CV and application** | You need a CV or materials tailored to a role | Builds a draft from your experience or edits an existing CV, then formats Word/PDF files and runs independent reviews |
| **interview · Practise interviews** | You want to rehearse answers and follow-up questions | Uses the role and CV to run a mock interview, record answers, and review delivery and factual support |

Use the features separately or connect them as needed. You choose the next step and submit the finished application yourself.

## First use

### 1. Install and set up

Choose an option in [Install](#install) below. Then tell the agent in Claude Code or Codex:

```text
Set up job-hunt and start my task using my everyday browser.
```

The agent checks and prepares dependencies, then explains any browser consent or site login you need to complete. No additional skill or browser extension is required.

### 2. Share what you have

For a search, give your target role, market and preferences. For an assessment, share the posting and your experience. For a CV, provide an existing document or your education, work and projects. A mock interview needs a posting and CV. The agent asks for missing information; you do not need to fill out a fixed template first.

### 3. Ask for the task you need

Each of these is a separate starting point:

```text
Use job-hunt to find AI product manager roles in Shanghai.
Use job-hunt. Here is a posting and my CV. Is this worth applying to?
Use job-hunt to turn this experience into Chinese and English CVs in Word and PDF.
Use job-hunt to run a mock interview based on this posting and my CV.
```

## What you receive

| Deliverable | What it contains |
|---|---|
| **Career consultation report (PDF)** | Posting links, fit analysis, strengths and gaps, application priorities or next steps relevant to your task |
| **Tailored CV (Word/PDF)** | An editable Word document and a typeset PDF, built from your experience or adapted to a role |
| **Additional application materials (on request)** | A cover letter, motivation letter, employer form or criterion-based supporting statement |
| **Interview preparation and feedback (on request)** | An interview brief, mock transcript, and independent assessments of answer quality and factual support |

Each consultation includes a report; other documents depend on the task you choose. Local and employer requirements determine the format, such as a Japanese rirekisho and career-history document, or an NHS/Civil Service supporting statement in the UK.

Delivery goes into one `~/Downloads/<workspace-name>/` folder, organized into `简历/` (CV) and `报告/` (report). Later stages use the same location so you can find the current documents.

## How the work is checked

### Full postings and real experience

A complete career report requires reading the full description of every retained posting. Search summaries are for initial screening. If a description genuinely cannot be accessed, the report explains why and marks it unresolved; it does not count as reviewed.

CV edits and advice use the experience you provide. The agent preserves your source profile, edits a copy, and lists missing evidence. It does not invent skills or performance figures, or predict hiring odds.

### Three independent AI CV reviews

| Review perspective | What it checks |
|---|---|
| **Applicant tracking system (ATS)** | Whether the CV can be parsed and its keywords reflect the role's requirements |
| **Recruiter** | Readability and basic eligibility |
| **Hiring manager** | Whether projects, responsibilities and experience support the role's requirements |

A standard CV is revised and reviewed for up to three rounds. Gaps that need more real experience or evidence remain explicit. Employer forms and criterion-based statements are checked against their own requirements.

### Layout and interview feedback

Before delivery, every Word/PDF page is checked against your template, fonts, alignment, spacing and pagination. Changes trigger another review; unresolved layout issues prevent completion.

After a mock interview, answer quality and factual support receive separate independent assessments, identifying details to add and CV wording to revise.

## CV and report examples

### English CV

This image is rendered from a fictional CV PDF. Names, institutions, employers, projects and figures are illustrative. The [Chinese README](README.md) shows the Chinese version.

<p align="center">
  <a href="docs/assets/examples/cv-en.png"><img src="docs/assets/examples/cv-en.png" width="680" alt="Fictional English CV with education, work experience, internships, projects and skills"></a>
</p>

### Career report excerpt

An anonymized English excerpt from a real search on 11 September 2026, showing role judgments and preparation. This historical snapshot retains some summary-only leads; current complete reports require each posting’s full details. The fictional CV was not used for these judgments. Click an image for full size.

<p align="center">
  <a href="docs/assets/examples/report-en-01.png"><img src="docs/assets/examples/report-en-01.png" width="49%" alt="Anonymized English career report with priorities and selected roles"></a>
  <a href="docs/assets/examples/report-en-02.png"><img src="docs/assets/examples/report-en-02.png" width="49%" alt="Anonymized English career report with role analysis, gaps and preparation"></a>
</p>

## Install

You need an agent environment that can run local commands and read and write files, plus **Python 3.10+**. Installation with `npx` also requires Node.js/npm. Choose one of the four paths below.

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

### Option 4: install from SkillHub or ClawHub

Open the job-hunt listing on [SkillHub](https://skillhub.cn/skills/user_f486c577/best-job-hunt) or [ClawHub](https://clawhub.ai/dong845/skills/job-hunt), then follow that platform's installation flow.

## Markets and languages

Sources include 51job, Indeed, LinkedIn and BOSS Zhipin, selected for your market and access conditions. China searches also consider preferences for large or smaller private firms, state-owned enterprises and foreign companies. Nowcoder provides interview and hiring-process context. See the [source catalogue](references/discovery-sources.md) and [source policy](references/source-policy.md).

CV headings and personal-data labels support English, Dutch, German, French, Spanish, Italian, Chinese, Japanese and Korean. Discovery and assessment reports support Chinese, English, Japanese, Korean and Spanish through the [report language templates](references/report-localization.md). Company and industry research can use official sites, news, WeChat public accounts and relevant GitHub projects as [supplementary sources](references/supplementary-sources.md).

The repository includes 5 market-convention tables with 38 sourced entries for the US, UK, Germany, the Netherlands and China, each with scope and review dates. Photos, personal details and application formats follow the target market and employer's requirements; outdated or missing information is flagged.

Standard CVs for the US, Canada, UK, Ireland, Australia and New Zealand omit photos and related personal information by default. Other recognized markets use supplied information according to their rules. These fields are omitted when the market is unknown.

## Setup and common questions

### Do I need to install search and layout tools myself?

After the skill is installed, the agent uses one setup entry to prepare Python packages, Node.js and OpenCLI with its CDP patches. The AnySearch client and browser reader are bundled; AnySearch uses an HTTP API without an API key. CV layout tools are prepared as needed. Reports use bundled fonts by default and honor explicitly selected fonts without silent substitution. See [environment setup](references/agent-setup.md).

### Why does the browser ask for consent?

The agent uses CDP, a remote debugging connection, to access your everyday Chrome or Edge and reuse its login state. On first use, you may need to enable remote debugging at `chrome://inspect/#remote-debugging` and accept the connection. The agent checks support and guides you through the steps. Connections are reused within the task, and independent sources are searched concurrently where possible. A separate browser is used only on your explicit request. See [browser connections](references/daily-browser.md).

### What if a site requires login or a posting cannot be read?

The agent pauses that source and asks you to complete the login or verification. Reply “done, continue” to resume. If access remains unavailable, you can provide the posting text or leave the lead unresolved.

The agent verifies OpenCLI first and uses the bundled CDP reader only after confirming incompatibility. The Indeed adapter currently connects to the US site; other markets use local sources first. Known Indeed and 51job patches target OpenCLI 1.8.7 and can be checked or reverted. The agent can also use the site's search box directly. See [compatibility troubleshooting](references/opencli-compat.md).

### Where are source profiles and working files stored?

This skill uses `~/.claude/job-profiles/` as its default shared store. It is not a built-in Claude Code or Codex directory; saving a profile creates it as needed. Both agents use the same location to reuse your data. Set `JOBHUNT_PROFILES_ROOT` to choose another directory. Source profiles can be stored by language, and applications have separate workspaces, apart from your delivered reports and CVs. Markdown, applicable `.tex` sources and check records support later edits and traceability. See [REFERENCE.md](REFERENCE.md) for the layout.

Files are stored locally; model calls and web access depend on your chosen agent and its service configuration.

## Verification and further reading

<details>
<summary>Developer checks, evaluation records and technical documentation</summary>

Automated checks cover evidence references, source-profile preservation, verdict parsing, personal-data handling, rendering, and mode handoffs:

```bash
python3 -m pip install pytest
make check
make eval-lint
```

`make check` runs Python tests, migration content-preservation checks and market-table checks. Tests that use external tools need those tools installed; local skill-installation checks are optional.

[`evals/`](evals/README.md) contains 20 behavioural scenarios. The second iteration (2026-09-05/06) ran 15 scenarios with and without the skill, once per group (n = 1). Ten behavioural checks changed from baseline `FAIL` to with-skill `PASS`. See the [evaluation record](evals/iterations/iteration-2-with-skill.md) for results, untested checks and the invalid scenario.

The three CV reviewers were tested through `codex exec` on 2026-09-06. See [agent portability](references/portability.md) for setup on other hosts and the scope of testing.

- [SKILL.md](SKILL.md): mode routing and core rules.
- [REFERENCE.md](REFERENCE.md): architecture, workspaces, data structures, and script usage.
- [Example profile](assets/profile.example.yaml) and [claim-provenance example](assets/claims.example.yaml): structured data formats.
- [Evaluation guide](evals/README.md): methods and limitations.

These technical references are currently written mainly in English. Released under the [MIT License](LICENSE).

</details>
