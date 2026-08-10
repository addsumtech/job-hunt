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

## Skill flow

The skill executes these 8 steps (full detail in `SKILL.md`):

1. **Interview** — ask up to 4 questions: CV source, target market/language, output formats, motivation letter.
2. **CV acquisition** — parse an existing CV or build one from scratch into `profile.yaml`.
3. **Job posting** — fetch and extract structured requirements (must-haves, keywords, tone, red flags).
4. **Gap analysis** — AMPLIFY / REFRAME / KEYWORD-INSERT / HONEST-GAPS table against the posting.
5. **Tailor CV** — write a tailored copy; render in requested formats.
6. **Motivation letter** — draft `letter.yaml` and render if requested.
7. **Hiring-pipeline review loop** — dispatch three fresh judges in parallel each round (ATS machine lens → Recruiter/HR fast human screen → Hiring Manager deep human lens); iterate until **all three** `PASS` or 3 rounds.
8. **Finalize** — list output paths, summarize changes, note remaining gaps, confirm the master profile is saved.

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
job-application/
├── SKILL.md                        # Orchestrator instructions
├── README.md
├── requirements.txt
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
│   ├── profile.example.yaml        # Canonical profile schema
│   ├── cv/template.tex             # LaTeX CV template
│   └── letter/template.tex         # LaTeX letter template
└── scripts/
    ├── render_cv.py
    ├── render_letter.py
    ├── render_rirekisho.py         # Japanese 履歴書 form renderer
    └── tests/
        ├── fixtures/
        ├── test_render_cv.py
        ├── test_render_letter.py
        └── test_render_rirekisho.py
```

---

## Testing

```bash
cd scripts && python -m pytest tests/ -v
```

Expected: 41 tests, all passing.
