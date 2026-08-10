# job-application

A Claude Code skill that takes a user from "I want this job" to a tailored, credible application package. It interviews the user, parses or builds a CV into a canonical `profile.yaml`, fetches and analyses the target job posting, tailors the CV through honest reframing (never fabrication), optionally drafts a motivation letter, and pressure-tests the package through a review loop that models the real hiring funnel — three independent judges, an ATS Screener (machine lens), a Recruiter/HR Screener (fast human screen), and a Hiring Manager (deep human lens), must all pass — iterating until they do or reporting honestly if they cannot. Outputs Markdown, .docx, and PDF (via LaTeX).

---

## Install

```bash
pip install -r requirements.txt   # PyYAML, python-docx
```

**PDF output** requires a LaTeX engine. `tectonic` is recommended:

```bash
brew install tectonic   # macOS
```

Without a LaTeX engine, Markdown and .docx outputs still work normally. The renderer emits a `.tex` file and prints a warning so you can compile it later once a LaTeX engine is available.

---

## The `profile.yaml` model

`assets/profile.example.yaml` is the canonical schema. It is the single source of truth for everything the renderers produce. Key rules:

- **Tailoring always works on a copy** — the master profile is never mutated.
- Master profiles can be saved to `~/.claude/job-profiles/<name>/profile.yaml` and reused across multiple applications.
- See `assets/profile.example.yaml` for all supported fields (contact, summary, experience, education, skills, projects, etc.).

---

## How it runs

One pipeline, in one place. `SKILL.md` holds the rules that must be in context on
every run — the honesty rule, the NOT-ALLOWED table, the claim-provenance
checkpoint, the gate table, the self-check. `modes/apply.md` holds the apply
pipeline itself and is loaded unconditionally on entering the mode, with its
content hash written to the workspace journal so that "it was loaded" is a fact
rather than a hope.

A second copy of the pipeline was here until 2026-08-09 and had already drifted —
it listed eight steps and omitted the interview-readiness brief. Read `SKILL.md`.

---

## Manual renderer usage

```bash
# CV
python scripts/render_cv.py PROFILE.yaml --format md|docx|pdf --out OUTPUT_PATH

# Motivation letter
python scripts/render_letter.py LETTER.yaml --format md|docx|pdf --out OUTPUT_PATH
```

---

## Layout

```
job-hunt/
├── SKILL.md                        # Orchestrator instructions — layer 1, always in context
├── README.md
├── requirements.txt
├── Makefile                        # make check = tests + losslessness + conventions
├── .github/workflows/checks.yml    # the same three checks, for whenever this repo gains a remote
├── modes/
│   └── apply.md                    # Layer 1.5 — the apply pipeline, loaded on mode entry
├── references/
│   ├── cv-craft.md                 # CV writing conventions (markets, links, bullets, ordering)
│   ├── gap-analysis.md             # Gap analysis + tailoring methodology
│   ├── job-posting-extraction.md   # How to parse a posting (+ fetch sanity, application type)
│   ├── candidate-situations.md     # Non-standard candidates (gap, switch, exec, military, intl)
│   ├── role-families.md            # Non-tech / regulated role conventions (clinical, sales, legal…)
│   ├── structured-applications.md  # Competency-form applications (NHS, Civil Service)
│   ├── motivation-letter.md        # Letter craft guide
│   ├── interview-prep.md           # Interview-readiness brief
│   └── rirekisho.md                # Japanese 履歴書 form guide
├── agents/                         # Three review judges (hiring funnel)
│   ├── ats-screener.md             # Judge 1 of 3 — machine lens (keyword coverage)
│   ├── recruiter-screener.md       # Judge 2 of 3 — fast human screen (skim/logistics)
│   └── hiring-manager.md           # Judge 3 of 3 — deep human lens (fit/credibility)
├── assets/
│   └── profile.example.yaml        # Canonical profile schema
├── docs/                           # spec, plans, research — outside the skill corpus
└── scripts/
    ├── journal.py                  # gate receipts in journal.jsonl (library)
    ├── paths.py                    # the one definition of the workspace shape (library)
    ├── vocab.py                    # every closed vocabulary in the skill (library)
    ├── rounds.py                   # judge-round-<n>.json read/merge (library)
    ├── enter_mode.py               # mode entry + the mode file's content hash
    ├── check_personal_data.py      # Cluster-1 interlock
    ├── check_claims.py             # claim provenance + master-profile immutability
    ├── check_render_freshness.py   # the judges read the files still on disk
    ├── parse_verdicts.py           # PASS/REJECT parsing, fail-closed on AMBIGUOUS
    ├── lint_cv.py                  # clichés, weak openers, bullet length, repeated verbs
    ├── check_letter.py             # letter body constraints
    ├── check_pages.py              # page count of the artifact actually submitted
    ├── check_word_limits.py        # supporting-statement per-criterion word limits
    ├── check_apply.py              # the composing gate: every receipt present
    ├── check_skill_lossless.py     # CI only — the migration moved content, not deleted it
    ├── lossless-allowlist.json     # deliberate deletions, each with a written reason
    ├── render_cv.py
    ├── render_letter.py
    ├── render_rirekisho.py         # Japanese 履歴書 form renderer
    └── tests/
        ├── fixtures/
        ├── required_inline.json    # layer-1 rules that must stay inline, each with its why
        └── test_*.py               # one module per script above
```

### A workspace

Everything a single application produces lives in one directory whose **shape is
load-bearing**: the "resume an unfinished application" lookup finds a prior run by
that shape, so a run that invents its own layout orphans the previous workspace and
silently re-interviews the user from scratch. `scripts/paths.py` is the only place
it is defined.

```
~/.claude/job-profiles/<name>/
  profile.yaml                 master profile · never mutated by any mode
  search-preferences.yaml      target market/city/level/languages (written by discover)
  answer-bank.md               the one artifact that accumulates across applications

  applications/<company>-<role>-<YYYY-MM-DD>/
    posting.yaml               extracted requirements
    posting-source.txt         raw capture · never edited
    cv-source.txt              raw CV text the assessment was cut from (assess mode)
    evidence-blocks.json       derived · never hand-edited
    fit-assessment.{yaml,md}
    coverage.json              the single counting path (assess mode)
    claims.yaml                append-only · a withdrawal is marked `retracted`, not deleted
    master-fingerprint.json    sha256 + mtime of profile.yaml at mode entry, so a
                               mutated master is detectable rather than discovered
                               on the NEXT application
    tailored-profile.yaml
    cv.{md,docx,pdf,tex} · letter.* · supporting-statement.md
    judge-round-<n>.json       dispatch hashes + the three parsed verdicts
    interview-brief.md
    mock/                      transcripts, assessments, question log (interview mode)
    journal.jsonl              every gate receipt · the evidence a gate actually ran
```

---

## Testing

```bash
cd scripts && python -m pytest tests/ -v
```

Everything must pass. `make check` additionally runs the migration losslessness
check and the market-convention lint.
