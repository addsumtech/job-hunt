# job-hunt

A Claude Code / Codex skill for the whole job hunt, in four modes:

| Mode | Question it answers | Gate |
|---|---|---|
| `discover` | what is out there worth looking at | `check_shortlist.py`, `check_no_write.py` |
| `assess` | is this posting worth applying to | `check_assessment.py` (composes six) |
| `apply` | how do I build and pressure-test the application | `check_apply.py` (composes the rest) |
| `interview` | how do I answer, and what did I get wrong | `check_mock.py` |

They do not auto-chain: finding thirty postings does not generate thirty CVs.

`apply` is the largest. It interviews the user, parses or builds a CV into a
canonical `profile.yaml`, extracts the target posting, tailors through honest
reframing (never fabrication), optionally drafts a motivation letter, and
pressure-tests the package through a review loop modelling the real hiring funnel
— an ATS Screener, a Recruiter/HR Screener and a Hiring Manager, three independent
judges, all of whom must pass. Outputs Markdown, .docx, and PDF (via LaTeX).

Two rules run through all four: **never fabricate** — honest reframing only — and
**never predict an interview or offer probability**, or any 0–100 score. Both are
enforced by scripts, not only by prose.

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
├── SKILL.md                        # Orchestrator instructions — layer 1, always in context; routes to a mode first
├── README.md
├── requirements.txt
├── Makefile                        # make check = tests + losslessness + conventions
├── .github/workflows/checks.yml    # the same three checks in CI
├── modes/                          # Layer 1.5 — exactly one is loaded, on mode entry
│   ├── discover.md                  # Layer 1.5 — find roles (read-only)
│   ├── assess.md                    # Layer 1.5 — judge one posting
│   ├── apply.md                     # Layer 1.5 — build and pressure-test the package
│   └── interview.md                 # Layer 1.5 — rehearse and debrief
├── references/                     # Layer 2 — read on demand
│   ├── candidate-situations.md      # Non-standard candidates (gap, switch, exec, military, intl)
│   ├── cv-craft.md                  # CV writing conventions (markets, links, bullets, ordering)
│   ├── discovery-sources.md         # Per-adapter catalogue for discover
│   ├── gap-analysis.md              # Gap analysis, tailoring methodology, claim provenance
│   ├── interview-prep.md            # Interview-readiness brief
│   ├── interview-shapes.md          # Round types, tags and bands for the mock interview
│   ├── job-posting-extraction.md   # How to parse a posting (+ fetch sanity, application type)
│   ├── motivation-letter.md         # Letter craft guide
│   ├── rirekisho.md                 # Japanese 履歴書 form guide
│   ├── risk-control-signals.yaml    # Platform stop-signals discover must obey
│   ├── role-families.md             # Non-tech / regulated role conventions (clinical, sales, legal…)
│   ├── source-policy.md             # What discover may and may not do to a platform
│   ├── structured-applications.md   # Competency-form applications (NHS, Civil Service)
│   └── market-conventions/         # nl / us / cn / uk / de tables + README
├── agents/                         # Three review judges (hiring funnel) + two mock assessors
│   ├── ats-screener.md             # Judge 1 of 3 — machine lens (keyword coverage)
│   ├── recruiter-screener.md       # Judge 2 of 3 — fast human screen (skim/logistics)
│   ├── hiring-manager.md           # Judge 3 of 3 — deep human lens (fit/credibility)
│   ├── mock-assessor-transcript.md  # interview pass 1 — what the answers did
│   └── mock-assessor-provenance.md  # interview pass 2 — where the facts came from
├── assets/
│   ├── profile.example.yaml        # canonical profile schema
│   └── claims.example.yaml         # the provenance ledger, with a retracted row
├── docs/                           # spec, plans, research — outside the skill corpus
└── scripts/
    ├── check_apply.py               # the composing gate: every receipt present, and about current bytes
    ├── check_assessment.py          # assess mode's composing gate (requires six upstream receipts)
    ├── check_claims.py              # claim provenance + master-profile immutability
    ├── check_conventions.py         # CI — market-convention table lint
    ├── check_evidence_refs.py       # evidence refs resolve; no block ids in reader prose
    ├── check_letter.py              # letter body constraints
    ├── check_mock.py                # interview mode's gate: quotes, tags, promotions, question log
    ├── check_no_write.py            # discover is read-only — a journaled write command fails
    ├── check_opencli_result.py      # adapter result classifier (wrapper, not a gate)
    ├── check_pages.py               # page count + the text actually inside the delivered PDF
    ├── check_personal_data.py       # Cluster-1 personal-data interlock
    ├── check_render_freshness.py    # the judges read the files still on disk
    ├── check_shortlist.py           # discover's gate: row provenance, caps, md↔yaml agreement
    ├── check_skill_lossless.py      # CI only — the migration moved content, did not delete it
    ├── check_word_limits.py         # supporting-statement per-criterion word limits
    ├── consistency.py               # contradictions between assessment fields — reports, never repairs
    ├── count_coverage.py            # the ONLY path that produces coverage counts
    ├── enter_mode.py                # mode entry + the mode file's content hash
    ├── evidence_blocks.py           # cuts posting and CV into addressable JD-nnn / CV-nnn blocks
    ├── journal.py                   # gate receipts in journal.jsonl (library)
    ├── lint_cv.py                   # clichés, weak openers, bullet length, repeated verbs
    ├── lint_no_prediction.py        # no probabilities, no 0–100 scores — EN + ZH
    ├── mock_blocks.py               # fail-closed parser for the assessor blocks (library)
    ├── mock_vocab.py                # the interview mode's closed vocabularies (library)
    ├── opencli_meta.py              # resolves an adapter command's published access: (library)
    ├── parse_verdicts.py            # PASS/REJECT parsing, fail-closed on AMBIGUOUS
    ├── paths.py                     # the one definition of the workspace shape (library)
    ├── render_cv.py                 # CV → md / docx / pdf(LaTeX)
    ├── render_letter.py             # motivation letter → md / docx / pdf
    ├── render_rirekisho.py          # Japanese 履歴書 form renderer
    ├── rounds.py                    # judge-round-<n>.json read/merge (library)
    ├── vocab.py                     # every closed vocabulary in the skill (library)
    ├── lossless-allowlist.json     # deliberate deletions, each with a written reason
    └── tests/
        ├── fixtures/
        ├── required_inline.json    # layer-1 rules that must stay inline, each with its why
        └── test_*.py               # one module per script above, plus the seam suites
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

## Evaluation — what `make check` does and does not prove

**No end-to-end behavioural evaluation has ever been run on this skill.** The
harness for it is specified (`docs/superpowers/plans/2026-08-09-5-eval-rebuild.md`,
twenty scenarios) and is **not built**: there is no `evals/` directory.

So `make check` green means exactly this: the unit tests agree with themselves,
the market tables lint, and no line of the pre-migration skill was lost. It does
**not** mean any mode was measured against a baseline arm, and no claim in this
repo should be read as saying otherwise.

The reason to state that plainly: `check_skill_lossless.py` proves the bytes
survived the layering, not that they arrive in context when they are needed. Only
a run proves the second thing, and nothing here runs one.
