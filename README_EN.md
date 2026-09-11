# job-hunt: find jobs, tailor your CV, practise interviews

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

job-hunt is a career skill for Claude Code and Codex. It helps you find roles, decide where to apply, prepare a CV and cover letter, and practise interviews.

Give the agent your goals, CV or a job link. It checks the requirements against your experience, edits and formats your documents, then reviews them. Guidance covers technical and research roles, career changes, employment gaps, new graduates and international applications.

## Start with the step you need

| Mode | When to use it | Main output |
|---|---|---|
| **discover** | You have a direction and want roles worth exploring | A shortlist with original posting links and initial advice |
| **assess** | You have a posting and want to decide whether to invest time | Requirements mapped to evidence, hard barriers, gaps, and application advice |
| **apply** | You have chosen a role and need targeted materials | A tailored CV, optional cover letter, review records, and an interview brief |
| **interview** | You have a posting and CV and want to practise | One mock round, a transcript, two independent assessment passes, and open questions |

Use each mode on its own. After a round, the agent suggests next steps and you choose whether to continue. You submit the finished application.

After installation, try:

```text
Use job-hunt. Find me MRI reconstruction roles in the Netherlands.
Use job-hunt. Here is a posting link and my CV. Is this worth applying to?
Use job-hunt. Tailor my CV to this role and write a cover letter.
Use job-hunt. Run a technical mock interview based on this posting and my CV.
```

The agent first confirms your task and target market, then asks for any missing materials or preferences.

## Preparing your application

The agent checks your experience against your profile, answers, papers and projects before editing the CV. It adjusts the order and wording, and lists claims that need more evidence. Edits use a copy of your profile; the original stays available.

For each role, the agent compares the requirements with your experience and shows which are met, partly met or missing evidence. Work authorisation, licences and other eligibility requirements come first, followed by application advice and any information you need to add.

A standard CV receives three independent AI reviews. The ATS reviewer checks keywords and file parsing. The recruiter reviewer checks readability and basic eligibility. The hiring manager reviewer checks experience and responsibilities. The agent edits and reviews again for up to three rounds, listing any gaps that need additional experience or evidence.

Before delivery, the agent reviews every Word/PDF page against any supplied template and your later changes: fonts and sizes, margins, heading rules, date alignment, spacing, content order and pagination. Unreviewed pages or unresolved layout differences prevent completion; changed files must be reviewed again.

After a mock interview, two independent assessments review the quality of your answers and their factual support. The feedback identifies details to add and CV wording to revise.

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

### First use: let the agent prepare the environment

After installation, say: "Set up job-hunt and start my task using my everyday browser."

Install only this skill. The AnySearch client and browser reader are bundled. A single setup entry lets the agent prepare Python packages, Node.js and OpenCLI with its CDP patches; no other skill or browser extension needs a separate installation. Consultation report PDFs use bundled fonts by default and honor explicitly selected fonts without silent substitution, while CV layout tools are prepared when needed. **Browser access uses CDP.** The agent verifies OpenCLI first and uses the bundled CDP reader only after diagnosing an incompatibility.


The agent connects to your everyday browser where supported and reuses its login state. On first use, you may need to enable remote debugging at `chrome://inspect/#remote-debugging` and accept Chrome's connection request. The agent checks support and explains any steps you need to take.

AnySearch searches through its HTTP API and works anonymously without an API key. Browser operations use your daily browser through CDP by default; a separate browser is used only when you explicitly request it. Independent sources are searched concurrently where possible to reduce waiting. You handle site logins, verification challenges and browser consent.

See [environment setup](references/agent-setup.md) and [browser connections and concurrent searches](references/daily-browser.md) for details.

### Trouble reading a job site

For known Indeed and 51job compatibility issues, the agent checks and applies the appropriate fix. Current patches target OpenCLI 1.8.7; other versions are checked separately.

You can also ask the agent to search through the job site's own search box. For troubleshooting, say "check job-site compatibility patches" or "revert compatibility patches". See the [check and revert instructions](references/opencli-compat.md).

## Markets, platforms, and languages

The agent selects sources for your target market and reads them through the browser or an available OpenCLI adapter. Sources include 51job, Indeed, LinkedIn and BOSS Zhipin. The Indeed adapter currently connects to the US site; searches in other markets use local sources first. The [source catalogue](references/discovery-sources.md) lists login requirements and uses; the [source policy](references/source-policy.md) explains access rules.

For China, the agent asks whether you prefer large private companies, small and medium private companies, state-owned enterprises or foreign companies, then uses your preferences to rank results. Nowcoder and 1point3acres provide interview experiences and hiring-process context.

When a site requires login or verification, the agent pauses that source and asks you to complete the step. Reply "done, continue" to resume. If access is still unavailable, you can try later, paste the posting or review the results already collected.

CV headings and personal-data labels support English, Dutch, German, French, Spanish, Italian, Chinese, Japanese and Korean. Discovery and assessment reports support Chinese, English, Japanese, Korean and Spanish through the [report language templates](references/report-localization.md). Some internal references remain in English. The agent checks PDF fonts during setup.

The project includes 5 market-convention tables with 38 entries for the US, UK, Germany, the Netherlands and China. Each entry includes its source, scope and review date. The agent flags outdated or missing information; the employer's requirements guide the application.

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="Repository rendering examples: a US-targeted CV omits personal data; a Germany-targeted CV retains a supplied photo and date of birth">
</p>

The target market determines how photos and personal details appear. Standard CVs for the US, Canada, UK, Ireland, Australia and New Zealand omit them by default. Other recognised markets follow their own rules using the information you provide. If the market is unknown, these fields are omitted.

## What you receive

| Material | Formats and details |
|---|---|
| Tailored CV | Markdown, Word (`.docx`), and PDF; PDF typesetting also preserves `.tex` |
| Cover or motivation letter | Optional; Markdown, Word, and PDF |
| Japanese rirekisho (履歴書) | A separate form renderer produces a Markdown preview and editable `.docx`; export the form to PDF through Word or LibreOffice |
| Structured supporting statement | Evidence organised by criterion, with word-limit checks, for applications such as NHS and Civil Service forms |
| Assessment and interview material | Shortlists, fit assessments, interview briefs, mock transcripts, and debriefs |

Structured applications review the supporting statement against the employer's criteria. If a standard CV is also required, it receives the three-reviewer check separately. A Japanese rirekisho is checked for form completeness; its companion career-history document follows the standard CV review process.

Every consultation produces a PDF report with career analysis, supporting sources and questions to resolve. It goes in `~/Downloads/<workspace-name>/` with your CV and other requested documents. Later stages use the same folder. Cover letters and mock interviews are available when you request them.

Delivery uses `简历/` (CV) and `报告/` (report) subfolders, with filenames such as `简历.docx`, `简历.pdf` and `求职建议报告.pdf`.

For company or industry research, the agent can consult official sites, news, WeChat public accounts and relevant GitHub projects through [supplementary sources](references/supplementary-sources.md).

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

`make check` runs Python tests, migration content-preservation checks and market-table checks. Tests that use external tools need those tools installed; local skill-installation checks are optional.

[`evals/`](evals/README.md) contains 20 behavioural scenarios. The second iteration (2026-09-05/06) ran 15 scenarios with and without the skill, once per group (n = 1). Ten behavioural checks changed from baseline `FAIL` to with-skill `PASS`. See the [evaluation record](evals/iterations/iteration-2-with-skill.md) for results, untested checks and the invalid scenario.

The three CV reviewers were tested through `codex exec` on 2026-09-06. See [agent portability](references/portability.md) for setup on other hosts and the scope of testing.

- [SKILL.md](SKILL.md): mode routing and core rules.
- [REFERENCE.md](REFERENCE.md): architecture, workspaces, data structures, and script usage.
- [Example profile](assets/profile.example.yaml) and [claim-provenance example](assets/claims.example.yaml): structured data formats.
- [Evaluation guide](evals/README.md): methods and limitations.

These technical references are currently written mainly in English. Released under the [MIT License](LICENSE).
