# job-hunt — find roles, judge them, apply, and rehearse, without inventing anything

<p align="center">
  <a href="README_CN.md"><strong>简体中文</strong></a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-supported-5b5bd6">
  <img alt="Codex" src="https://img.shields.io/badge/Codex-verified-111827">
  <img alt="Modes" src="https://img.shields.io/badge/modes-discover_·_assess_·_apply_·_interview-0f766e">
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="Release" src="https://img.shields.io/badge/release-v1.0.0-1f883d"></a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="A CV with five threads running from its lines out to the sources behind them — a paper, a notebook, a certificate, a keyboard key, a diploma">
</p>

> **A career coach that reads your real history, refuses to embellish it, tells you the
> things a recruiter would only say in private, and puts the finished package in front
> of three independent screeners before it hands it to you.**

Runs as a skill in Claude Code or Codex. You talk to it; it does the reading, the
tailoring, the rendering and the review, and leaves a `.md` and a `.pdf` in your
Downloads folder.

Most CV tools optimise for the sixty seconds after you paste a job link. This one
optimises for the interview four weeks later, where every line on the page has to be
something you can defend.

---

## What it will not do

Each of these is enforced by a script that fails the run, not by a paragraph asking
the model nicely.

**It will not invent anything.** No skill you have never used, no inflated title, no
adjusted date, no "improved performance by 40%" when you cannot name the number.
Every claim entering the CV traces to a line in your source profile, an answer you
gave this session, or a paper or repository of yours it actually read. Anything else
goes to a gaps list where you can see it. The failure this exists to stop is specific
and common: a model reads Kubernetes in the job description, writes it onto your CV,
and you find out in the technical screen.

**It will not predict your odds.** No "82% match", no interview probability, no 0–100
score. Those numbers are invented, they read as authoritative, and people make real
decisions on them. What you get instead is a count of must-haves with the evidence
reference printed beside each one, so you can argue with a single row rather than
with a number. A lint enforces this in English and Chinese.

**It will not grade its own homework.** The package goes to three separate reviewers
with fresh context: an ATS parser, a recruiter giving it the fifteen seconds a real
one gives a CV in a stack, and a hiring manager reading for credibility. All three
have to pass. When they do not and the gap is real, the loop stops and says the CV
cannot honestly close it. That is the correct answer. A tool that stuffs the keyword in instead has moved your rejection to
a later and more expensive round.

**It will not quietly guess your market.** Region is asked, as options, at the start
of every round that needs one, and never inferred from where you have worked. Your CV
records your experience; it says nothing about where you want to apply next.

---

## Four modes, and they do not chain

| Mode | The question it answers | What you get |
|---|---|---|
| **discover** | what is out there worth looking at | a shortlist where every row traces to a real posting, each with a provisional read |
| **assess** | is this one worth applying to | a row-by-row fit assessment, disqualifiers first, and an honest verdict |
| **apply** | how do I build a package that survives a screen | tailored CV, optional motivation letter, three-judge review, `.md` + `.pdf` |
| **interview** | how do I answer, and what did I get wrong | a mock round, then a debrief on the claims you could not defend |

Finding thirty postings does not generate thirty CVs. Each mode ends by offering the
next one and waiting for you to pick.

---

## Personal data is a trap, and the direction matters

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="A US CV with no photo or date of birth beside a German CV that keeps both">
</p>

A photo and a date of birth on a US application invite a discrimination claim and get
the CV binned by a compliance-trained recruiter. The same photo and date of birth are
ordinary on a German one, and leaving them off looks careless. Those two mistakes are
not symmetric, so the rule is not symmetric either. For the US, Canada, the UK,
Ireland, Australia and New Zealand the fields are stripped and the suppression is
stated out loud; for a market the skill has no table for, they are withheld and you
are told why.

Five convention tables ship with it, covering the United States, the United Kingdom,
Germany, the Netherlands and China: 38 entries, each carrying its source URL, the
date it was retrieved and the date it needs re-checking. Past that date the entry
still renders, under a banner saying it is stale. A convention card that goes out of
date silently is worse than one that admits it.

---

## What it produces

**CV** in Markdown, `.docx` and PDF (typeset through LaTeX; `tectonic` recommended).
**Motivation letter** in the same three. **Japanese 履歴書** through its own form
renderer. **UK NHS and Civil Service** competency forms get the branch they need: a
supporting statement written per criterion, inside the employer's own word limit,
which is the artifact those employers actually score.

Non-English output is a first-class path rather than a translation afterthought. CVs
render with the right personal-data block and the right section labels in Dutch,
German, French, Spanish, Italian, Chinese, Japanese and Korean, and the checks that
catch machine-sounding prose or a dropped `(in progress)` on a degree run in those
languages too.

Finished files land in `~/Downloads` as `<company>-<role>-<date>-cv.md` and `.pdf`,
with no folder to go hunting for.

---

## What was actually measured

Two numbers, answering different questions.

**`make check`: 3321 tests green.** The code does what its tests say. That is all it
means. Passing gates are not correct output, and this repository has caught itself
green-on-wrong often enough to say so on the tin.

**`evals/`: twenty scenarios, two arms.** The comparison is the part that matters,
because a behaviour both arms produce belongs to the model rather than to the skill.
In iteration 2 (2026-09-05/06), fifteen runs with the skill were matched one-to-one
against baseline runs of the same scenario. **Ten guards that discriminate between
the arms went FAIL on the baseline and PASS with the skill:** the personal-data
suppression being audible rather than silent, a blocked discover round carrying its
disclosure block instead of quietly returning fewer rows, the refusal floor holding
on inputs too thin to judge, the apply loop stopping honestly on a genuine gap, and
no hire verdict or invented score coming out of the interview mode.

**n = 1 per cell.** That says the skill reached the behaviour on one run each. It says
nothing about how often it does, and it is not a confidence interval. The scenario
list and the assertion list were both written by the people who wrote the skill,
which is why every assertion carries a written falsifier — what a failing output
would look like — recorded before the run. The full record, generated from the
grading files rather than typed, is in
[`evals/iterations/iteration-2-with-skill.md`](evals/iterations/iteration-2-with-skill.md).

---

## Install

Three paths. All of them need **Python 3.10+** and two packages; `doctor.py` at the
end sorts the rest out.

**One line, with [`npx skills`](https://github.com/vercel-labs/skills)** — simplest:

```bash
npx skills add addsumtech/job-hunt
```

It asks which agent and which scope. Add `-g` for every project, `-a claude-code`
or `-a codex` to skip the agent prompt, `-y` for a non-interactive run. The
repository root *is* the skill, so the whole directory is copied into your skills
folder.

**As a Claude Code plugin** — managed updates, and the only path that reaches cloud
sessions:

```text
/plugin marketplace add addsumtech/job-hunt
/plugin install job-hunt@job-hunt
/reload-plugins
```

Plugin skills are namespaced, so it is invoked as `/job-hunt:job-hunt`. Two things
worth knowing: if you also keep a manual copy in `~/.claude/skills/` you will see
the skill twice, because nothing de-duplicates them; and third-party marketplaces
do not auto-update, so `/plugin marketplace update job-hunt` is how you pick up a
new release.

**Clone and symlink** — best if you intend to edit it, since changes take effect
immediately and the plugin cache does not:

```bash
git clone https://github.com/addsumtech/job-hunt.git
ln -s "$(pwd)/job-hunt" ~/.claude/skills/job-hunt     # or ~/.codex/skills/job-hunt
```

Then, whichever path you took:

```bash
pip install -r requirements.txt              # PyYAML, python-docx
python3 scripts/doctor.py --install          # checks this machine, installs what pip can
```

`doctor.py` checks capabilities rather than binary names: it renders an actual PDF
instead of looking for `xelatex`. An earlier version did look for the binary, missed
the `tectonic` that was installed, and reported PDF output as broken while every PDF
rendered fine. It installs Python packages and never system binaries; for a LaTeX
engine it prints the one command for your platform and lets you run it.

## Then say what you want

```text
Use job-hunt. Find me MRI reconstruction roles in the Netherlands.
Use job-hunt. Here's a posting link and my CV — is this worth applying to?
Use job-hunt. Tailor my CV to this job and write the cover letter.
Use job-hunt. Run a mock interview for the role I just applied to.
```

It asks a short round of questions with concrete options: region first, then which
platforms that region actually has, then which of those need you to log in before it
can search. Answer them and it goes.

## On Codex and other agents

The enforcement half — every gate, the journal, the renderers, the coverage counts —
is plain Python with two dependencies, so it behaves identically wherever Python 3
runs. What differs between hosts is how you ask a question and how you open a fresh
context for a judge, and
[`references/portability.md`](references/portability.md) gives the substitution for
both. The three judge personas were run end to end through `codex exec` on
2026-09-06 against a real apply workspace, and the skill's own verdict parser
accepted all three and recorded a PASS. `gemini` and `cursor-agent` were on the same
machine and were not tested; nothing here claims they work.

---

Repository layout, the profile schema, the workspace shape, and the full test and
eval detail: [`REFERENCE.md`](REFERENCE.md). MIT licensed.
