# job-application

A Claude Code skill that takes a user from "I want this job" to a tailored, credible application package. It interviews the user, parses or builds a CV into a canonical `profile.yaml`, fetches and analyses the target job posting, tailors the CV through honest reframing (never fabrication), optionally drafts a motivation letter, and pressure-tests the package through a simulated recruiter review loop — iterating until the screener passes or reporting honestly if it cannot. Outputs Markdown, .docx, and PDF (via LaTeX).

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
7. **HR review loop** — dispatch a fresh `hr-screener` subagent each round; iterate until `PASS` or 3 rounds.
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
│   ├── cv-craft.md                 # CV writing conventions
│   ├── gap-analysis.md             # Gap analysis methodology
│   ├── job-posting-extraction.md   # How to parse a posting
│   └── motivation-letter.md        # Letter craft guide
├── agents/
│   └── hr-screener.md              # Simulated recruiter subagent
├── assets/
│   ├── profile.example.yaml        # Canonical profile schema
│   ├── cv/template.tex             # LaTeX CV template
│   └── letter/template.tex         # LaTeX letter template
└── scripts/
    ├── render_cv.py
    ├── render_letter.py
    └── tests/
        ├── fixtures/
        │   ├── sample_profile.yaml
        │   └── sample_letter.yaml
        └── test_render_cv.py
        └── test_render_letter.py
```

---

## Testing

```bash
cd scripts && python -m pytest tests/ -v
```

Expected: 10 tests, all passing.
