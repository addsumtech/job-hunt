# Interview Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `interview` mode of the `job-hunt` skill — a conversational mock interview run inline in the main conversation, assessed by two subagent passes with deliberately different inputs, gated by `check_mock.py`, and written back into `interview-brief.md` and `claims.yaml`.

**Architecture:** The interviewer is **inline** (a spawned subagent has no channel to ask a question and wait for the human — `agents/hiring-manager.md:21` pastes its inputs at dispatch time and `:97` requires it to end with a fixed block). After each round the transcript on disk is handed to **two** assessor subagents whose input packs are deliberately different: pass 1 sees `transcript-<n>.md` + `posting.yaml` + `cv.md` and therefore cannot credit the candidate for a source fact they never said out loud; pass 2 sees `transcript-<n>.md` + `claims.yaml` + `interview-brief.md` but not the rubric, and emits only `UNSOURCED-FACT` / `OVER-CLAIM` / `CONTRADICTED`. Both passes end in a strict, sentinel-delimited block that `scripts/check_mock.py` parses fail-closed.

**Tech Stack:** Python 3 (stdlib + PyYAML), pytest, Markdown skill files. No new dependencies.

## Global Constraints

- Repo root is the skill: `/Users/donghanglyu/code_project/job-hunt`. All paths below are relative to it.
- **Plan 1 must be landed first.** This plan imports `scripts/journal.py` (`append`, `receipt`, `sha256_file`, `read_receipts`) exactly as the shared contract fixes them. Do not re-create those files.
- Plan 2 owns `scripts/lint_no_prediction.py`. This plan consumes it through **one** adapter function and exits 2 (could not run) when it is absent — never skips the check silently.
- Every gate obeys: `python3 scripts/<name>.py --workspace <path> [args]`; exit 0 = pass, exit 1 = fail (findings to stdout, one per line, each prefixed with a stable UPPERCASE code), exit 2 = could not run (message to stderr). Exactly one receipt line appended to `<workspace>/journal.jsonl` before exiting.
- The ONE verdict vocabulary is not used in this mode — interview mode emits **bands**, never verdicts.
- Bands, verbatim and unnumbered: `not_present` | `asserted` | `instanced` | `held_under_probe`. Non-band flag: `contradicted`.
- Defect tags, closed set, verbatim: `UNSOURCED-FACT` | `OVER-CLAIM` | `CONTRADICTED` | `PROBE-COLLAPSE`.
- Today is **2026-08-09**. Every dated example in every file is that literal date. Never call an unstamped date helper in an example.
- Tests: `python3 -m pytest scripts/tests -q` from the repo root.
- Git: stage **named paths only** (never `git add -A`, never `git add .`), commit locally, **never push**, never pass `-c user.name` / `-c user.email`.

---

## Two closed vocabularies, and why there are two

The shared contract fixes the **defect-tag** closed set at four: `UNSOURCED-FACT`, `OVER-CLAIM`, `CONTRADICTED`, `PROBE-COLLAPSE`. Those four are the escalation tags — three of them make a walk-back mandatory, the fourth routes to `claims.yaml`.

The design research (`interview.md` §4e) also specifies eleven *answer-shape* observations (`NO-INSTANCE`, `NO-OUTCOME`, …). They are not defects of honesty; they are facts about the shape of an answer, and they are what makes the night-before artifact a scannable list instead of an essay. They are kept as a **second, separately named closed set** (`SHAPE_TAGS`) with its own column, its own gate check, and the same "no quote, no tag" rule. This does not reshape the contract's four — `DEFECT_TAGS` stays exactly four and it alone drives the walk-back requirement.

Both sets live in `scripts/mock_vocab.py` as the single source of truth, and a test asserts `references/interview-shapes.md` and that module cannot drift apart.

---

## File Structure

**Created by this plan**

| File | Responsibility |
|---|---|
| `scripts/mock_vocab.py` | The closed vocabularies: defect tags, answer-shape tags, bands, dimensions, round types, statuses, question sources, rejection reasons, the market/family conditionals, and the 12-month staleness constant. Data only, no logic. |
| `scripts/mock_blocks.py` | Strict, fail-closed parser for the two assessor output blocks, plus quote normalisation and quote-in-transcript matching. No file I/O, no policy. |
| `scripts/check_mock.py` | The gate. CLI, exit codes, journal receipt, and every check: closed tag sets, quote-required, quote-really-in-transcript, wrong-pass, band-vs-flag, `question-log.yaml` schema and scraped rules, `answer-bank.md` `source:` lines, banned vocabulary, walk-back completeness, `UNSOURCED-FACT` resolution. |
| `references/interview-shapes.md` | Market × role-family loop shapes with a visible source-quality label on every row; the four band descriptors; both closed tag tables. Layer 2 — backstopped by the doc/module parity test and by the fact that `assessment-<n>.md` cannot be written without the bands. |
| `agents/mock-assessor-transcript.md` | Assessor pass 1 (rubric + shape + `PROBE-COLLAPSE`). States what it is deliberately not given and why. Ends with `MOCK-ASSESSMENT-V1`. |
| `agents/mock-assessor-provenance.md` | Assessor pass 2 (three honesty tags only). States what it is deliberately not given and why. Ends with `MOCK-PROVENANCE-V1`. |
| `modes/interview.md` | Layer 1.5. The mode's flow, the pack split, one-round-per-dispatch, flush-after-every-answer, carry-forward, the scraped-material rules including the COUNTRY RULE, the `question-log.yaml` schema, the `answer-bank.md` entry schema, the walk-back format, the `claims.yaml` promotion row, and the published-employer-rubric exception. |
| `scripts/tests/mock_fixtures.py` | Builds a complete, **passing** workspace on disk. Every test starts from this quiet case and breaks exactly one thing. |
| `scripts/tests/test_mock_blocks.py` | Parser: shape, fail-closed behaviour, quote matching. |
| `scripts/tests/test_interview_shapes_doc.py` | Doc/module parity + source-label discipline in the reference. |
| `scripts/tests/test_mock_assessor_agents.py` | The example block inside each agent file parses. |
| `scripts/tests/test_check_mock_core.py` | Tag sets, quotes, bands, headers, receipts, exit codes. |
| `scripts/tests/test_check_mock_sources.py` | `question-log.yaml`, `answer-bank.md`, banned vocabulary, missing-dependency exit 2. |
| `scripts/tests/test_check_mock_walkback.py` | Walk-back completeness and `UNSOURCED-FACT` resolution. |
| `scripts/tests/test_mode_interview_doc.py` | The mode file's embedded examples are executable: they are extracted and run through the real validators. |
| `scripts/tests/test_skill_md_interview_blocks.py` | The anti-coaching rules and session mechanics are present in `SKILL.md`, exactly once. |
| `scripts/tests/test_mock_dryrun.py` | End-to-end: three-turn transcript with drift → gate demands the walk-back → resolved → gate passes. |
| `scripts/tests/fixtures/mock-dryrun/**` | The dry-run workspace fixture. |

**Modified by this plan**

| File | Change |
|---|---|
| `SKILL.md` | Append one section: the four anti-coaching rules + the tripwire + the mock-interview session mechanics. Nothing else in the file is touched. |

## Scope map

| Scope item | Task |
|---|---|
| T1 `references/interview-shapes.md` | Task 1 |
| T2 the two assessor agent files | Task 2 |
| T3 `check_mock.py` | Tasks 3, 4, 5 |
| T4 scraped-material rules + COUNTRY RULE | Task 6 (inside `modes/interview.md`) |
| T5 `modes/interview.md` | Task 6 |
| T6 write-backs (walk-back list, claims promotion) | Task 5 (mechanism) + Task 6 (procedure) |
| T7 anti-coaching rules into `SKILL.md` | Task 7 |
| T8 end-to-end dry run | Task 8 |

---

### Task 1: Closed vocabularies and the shapes reference

**Files:**
- Create: `scripts/mock_vocab.py`
- Create: `references/interview-shapes.md`
- Test: `scripts/tests/test_interview_shapes_doc.py`

**Interfaces:**
- Consumes: nothing.
- Produces (all module-level constants in `scripts/mock_vocab.py`):
  - `DEFECT_TAGS: tuple[str, ...]` — the four contract tags
  - `PROVENANCE_TAGS: tuple[str, ...]` — the three pass-2 tags
  - `WALKBACK_TAGS: tuple[str, ...]` — the three that force a walk-back
  - `SHAPE_TAGS: tuple[str, ...]` — the eleven answer-shape tags
  - `TRANSCRIPT_TAGS: tuple[str, ...]` — what pass 1 may emit
  - `ALL_TAGS: tuple[str, ...]` — `DEFECT_TAGS + SHAPE_TAGS`
  - `BANDS: tuple[str, ...]`, `NON_BAND_FLAG: str`
  - `DIMENSIONS: tuple[str, ...]`, `ROUND_TYPES: tuple[str, ...]`, `MARKET_KEYS: tuple[str, ...]`
  - `COVERAGE_STATUS: tuple[str, ...]`, `SHAPE_STATUS: tuple[str, ...]`
  - `QUESTION_SOURCES: tuple[str, ...]`, `REJECT_REASONS: tuple[str, ...]`
  - `MARKET_CONDITIONAL: dict[str, tuple[str, ...]]`, `FAMILY_CONDITIONAL: dict[str, tuple[str, ...]]`
  - `SCRAPED_SPECIFIC_MAX_AGE_DAYS: int`

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_interview_shapes_doc.py`:

    ```python
    import pathlib
    import re
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import mock_vocab as V

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    DOC = ROOT / "references" / "interview-shapes.md"

    LABEL = re.compile(r"^\[(F|C|S)\]$")


    def _section(heading: str) -> str:
        """The text under an H2 heading, up to the next H2."""
        text = DOC.read_text(encoding="utf-8")
        marks = [m for m in re.finditer(r"^## (.+)$", text, re.M)]
        for i, m in enumerate(marks):
            if m.group(1).strip() == heading:
                end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
                return text[m.end():end]
        raise AssertionError(f"references/interview-shapes.md has no '## {heading}' section")


    def _table_rows(section: str) -> list[list[str]]:
        rows = []
        for line in section.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):   # separator row
                continue
            rows.append(cells)
        return rows


    def _first_col_tokens(heading: str) -> set[str]:
        rows = _table_rows(_section(heading))
        return {r[0].strip("`") for r in rows[1:]}          # skip the header row


    def test_defect_tag_table_matches_the_module():
        assert _first_col_tokens("Defect tags (closed set)") == set(V.DEFECT_TAGS)


    def test_answer_shape_tag_table_matches_the_module():
        assert _first_col_tokens("Answer-shape tags (closed set)") == set(V.SHAPE_TAGS)


    def test_band_table_matches_the_module():
        assert _first_col_tokens("The four bands") == set(V.BANDS)


    def test_the_ceiling_is_stated_in_words():
        section = _section("The four bands")
        assert "held_under_probe is the ceiling" in section
        assert "not numbered" in section


    def test_the_flag_is_not_presented_as_a_band():
        assert V.NON_BAND_FLAG not in _first_col_tokens("The four bands")
        assert V.NON_BAND_FLAG in _section("The four bands")   # it is still explained there


    def test_every_shape_row_carries_a_source_label():
        for heading in ("Market shapes", "Role-family shapes"):
            rows = _table_rows(_section(heading))
            assert rows, f"{heading} has no table"
            for cells in rows[1:]:
                assert LABEL.match(cells[0]), (
                    f"{heading}: row {cells!r} does not start with a [F]/[C]/[S] source label"
                )


    def test_search_summary_material_is_barred_from_verbatim_questions():
        section = _section("Verbatim question material")
        assert "[S]" not in section.replace("[S] material", "")
        assert "may set SHAPE" in _section("How to read the source labels")


    def test_the_reference_points_at_its_neighbours_rather_than_copying_them():
        text = DOC.read_text(encoding="utf-8")
        assert "references/role-families.md" in text
        assert "references/interview-prep.md" in text
    ```

- [ ] **Step 2: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_interview_shapes_doc.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'mock_vocab'`

- [ ] **Step 3: Write `scripts/mock_vocab.py`**

    ```python
    """Closed vocabularies for the interview mode — the single source of truth.

    `references/interview-shapes.md` documents these tables for the model;
    `scripts/tests/test_interview_shapes_doc.py` asserts the document and this module
    cannot drift apart. Nothing in the mode may invent a tag: a tag outside these sets is
    a finding no one can audit, and an unauditable finding is indistinguishable from an
    opinion.
    """

    # The contract's four. Do not extend — three of them force a walk-back and the fourth
    # routes to claims.yaml, so adding a fifth silently changes what the gate demands.
    DEFECT_TAGS = ("UNSOURCED-FACT", "OVER-CLAIM", "CONTRADICTED", "PROBE-COLLAPSE")

    # Pass 2 holds claims.yaml and interview-brief.md, so it is the only pass that can
    # decide these three.
    PROVENANCE_TAGS = ("UNSOURCED-FACT", "OVER-CLAIM", "CONTRADICTED")

    # Firing any of these makes a "## Walk-back list" section mandatory (spec 5.4 gate).
    # UNSOURCED-FACT is deliberately NOT here: its honest route is usually claims.yaml
    # ("true, just not on my CV"), not a change to the CV.
    WALKBACK_TAGS = ("PROBE-COLLAPSE", "OVER-CLAIM", "CONTRADICTED")

    # Answer-shape observations. Facts about the shape of an answer, never about the
    # person. Second closed set, its own column; see the plan's "Two closed vocabularies".
    SHAPE_TAGS = (
        "NO-INSTANCE",
        "NO-OUTCOME",
        "VAGUE-OUTCOME",
        "NO-ACTOR",
        "PREAMBLE-HEAVY",
        "DRIFT",
        "NO-REFLECTION",
        "NO-TRADEOFF",
        "JARGON-UNGLOSSED",
        "NO-NEXT-STEP",
        "CLINICAL-DRIFT",
    )

    # PROBE-COLLAPSE is visible in the transcript alone, so pass 1 owns it.
    TRANSCRIPT_TAGS = SHAPE_TAGS + ("PROBE-COLLAPSE",)
    ALL_TAGS = DEFECT_TAGS + SHAPE_TAGS

    # Unnumbered on purpose: a numbered band would be averaged, and an average of four
    # observations about four different answers is a number with no referent.
    BANDS = ("not_present", "asserted", "instanced", "held_under_probe")
    NON_BAND_FLAG = "contradicted"

    # Pass 1 bands five dimensions. The sixth dimension in the design research
    # (provenance) is NOT here: pass 1 does not hold interview-brief.md or claims.yaml,
    # so it cannot decide provenance. Pass 2's three tags are the provenance dimension.
    DIMENSIONS = ("instance", "completeness", "ownership", "outcome", "probe")

    ROUND_TYPES = ("behavioural", "technical", "design", "hr")
    MARKET_KEYS = ("cn", "nl", "de", "uk", "us", "other")

    COVERAGE_STATUS = ("evidenced", "asked_thin", "not_asked")
    SHAPE_STATUS = ("rehearsed", "partial", "not_attempted", "cannot_simulate")

    QUESTION_SOURCES = ("generated", "scraped", "judge-supplementary")
    REJECT_REASONS = (
        "wrong_country",
        "stale_specific",
        "advertising",
        "needs_login",
        "answer_included",
    )

    # Conditional tags: firing one outside its market/family is a miscalibrated mock, not
    # a finding. NO-REFLECTION is Dutch STARR (carrieretijger, [F]) — it is not a defect
    # in a US loop.
    MARKET_CONDITIONAL = {"NO-REFLECTION": ("nl",)}
    FAMILY_CONDITIONAL = {"NO-NEXT-STEP": ("sales",), "CLINICAL-DRIFT": ("clinical",)}

    # Scraped material older than this may set SHAPE only, never be quoted as a specific
    # technical question. Measured need: one nowcoder result set held posts 3 days and
    # 9.5 months old, and `search` has no date parameter at all.
    SCRAPED_SPECIFIC_MAX_AGE_DAYS = 365
    ```

- [ ] **Step 4: Write `references/interview-shapes.md`**

    ```markdown
    # Interview shapes, bands, and the closed tag sets

    Read this **every time** you enter interview mode, before the first question — `modes/interview.md` §0 and the SKILL.md self-check both name it. It holds three things you cannot write `mock/assessment-<n>.md` without: the loop shapes, the four bands, and the two closed tag sets.

    It **extends** two existing files and duplicates neither:
    - `references/role-families.md` is a *CV-layout* document (what to lead with, what counts as evidence). Interviews need a different axis — what artifact the candidate must produce live. That axis is the role-family table below; the layout recipes stay where they are.
    - `references/interview-prep.md` produces the thin defence brief (`interview-brief.md`) from data the pipeline already holds. This mode consumes that brief and writes back into it; it does not replace it.

    ## How to read the source labels

    | Label | Meaning | What it may be used for |
    |---|---|---|
    | `[F]` | A primary page that was fetched and read | Shape **and** specific questions |
    | `[C]` | A command run in-session, output quoted | Shape **and** specific questions, subject to the scraped-material rules in `modes/interview.md` |
    | `[S]` | A search-result summary only; the page was never opened | **Shape only.** `[S]` material may set round count, order, and ritual names. It may never be quoted to the candidate as a specific technical question |
    | `[U]` | Could not source | Do not state it at all |

    Every row in the two shape tables begins with its label. A row without one is a claim with no provenance, and the doc test fails the build on it.

    ## Market shapes

    ### China (tech / campus)

    | Source | Shape fact |
    |---|---|
    | `[F]` | The pipeline is 简历初筛 → 笔试 → 技术一面 → 技术二面 → 技术三面 → HR面 → offer, with elimination possible at every stage |
    | `[F]` | 笔试 is a coding assessment before any interview; most require ACM-style input/output |
    | `[F]` | 技术一面 is four parts in one round: 基础知识 + 项目 + 开放性问题 + 手撕算法 |
    | `[F]` | 技术二面 goes into project depth and architecture; 技术三面 is often leadership-level, covering research direction and career plans |
    | `[F]` | Rounds run 30–45 minutes. Formats: 一对一, 一对多 (common at state enterprises and banks), 多对一 / 群面 |
    | `[S]` | 交叉面 exists at large firms: same-level interviewers from a different business department, no fixed round count, used to give the main interviewer an outside read |

    Register notes. **八股文 is a register, not a topic** — rapid rote recall of canonical fundamentals, where the pressure is volume and speed. Running it as three thoughtful discussion questions misses the round entirely. **手撕代码 cannot be simulated here** — there is no shared editor and no watching interviewer; say so and run the verbal half instead (state the approach before coding, the complexity, what breaks on empty input).

    ### United States (tech)

    | Source | Shape fact |
    |---|---|
    | `[F]` | Amazon publishes: Application → Initial screening → Interview loop → Post-interview and follow-up; the loop is "four to six intensive interviews lasting 45-60 minutes each" |
    | `[F]` | Amazon's Bar Raiser is "an objective interviewer from outside the hiring team who ensures Amazon's high hiring standards are maintained" |
    | `[F]` | Amazon's published pronoun guidance: use "I" statements — "Instead of saying 'we improved customer satisfaction,' say 'I implemented a new feedback system…'" |
    | `[F]` | Google documents "with illustrative examples what a poor, borderline, solid, and outstanding answer would cover", and interviewers "take detailed notes of applicant responses" |
    | `[S]` | The generic sequence (recruiter screen → technical phone → onsite loop → sometimes a take-home) is repeated everywhere but no primary source states it canonically |

    ### United Kingdom and EU public / academic sector

    | Source | Shape fact |
    |---|---|
    | `[F]` | UK Civil Service Success Profiles has five elements: Behaviours, Strengths, Ability, Experience, Technical |
    | `[F]` | Nine named behaviours, defined across seven grade groupings; the published document gives **positive examples only** ("Examples of [behaviour] at [grade] are when you:") |
    | `[F]` | The published scale runs 1 Not Demonstrated → 7 Outstanding Demonstration, and every descriptor is a statement about the evidence, not about the person |
    | `[F]` | Published pass bar: "A minimum score of 4 is required across all behaviours. However, candidates may score a single 3 where all other behaviour scores are high." |
    | `[F]` | STAR, UK National Careers Service: Result = "what happened as a result of your action **and what you learned from the experience**" |
    | `[F]` | Academic (MIT CAPD): screening interview 20–40 min; campus visit 1–2 days; job talk 45 min–1 hour; a chalk talk on future research plans; sometimes a teaching demo |
    | `[S]` | UK academic panels score against the person specification as "the only basis for scoring", marks per criterion fixed at the outset, panel of three or more reaching consensus |
    | `[S]` | EPSO uses eight general competencies composed of observable "anchors"; the list itself is only in PDFs that could not be decoded |

    The academic loop's **meal and hallway are scored informally**. A module that rehearses only the job-talk Q&A misses the failure mode that actually sinks candidates.

    ### Netherlands

    | Source | Shape fact |
    |---|---|
    | `[F]` | Multiple interviews are normal: hiring manager, then the team, then possibly leadership |
    | `[F]` | Directness is the house style — anything questionable on the CV will be asked about without preamble; vague answers are penalised, data and concrete results expected |
    | `[F]` | Non-hierarchical workplaces: teamwork evidence is load-bearing |
    | `[F]` | The local method is **STARR** — Situatie, Taak, Actie, Resultaat, **Reflectie** (what did you learn, what would you do differently, what feedback did you get); **STARRT** adds Transfer, how you will apply it |
    | `[S]` | A case *opdracht* may precede the first or second interview; psychometric assessment scales with seniority; the process closes with an *arbeidsvoorwaardengesprek* held after the decision and before signature |

    The reflectie step **is a scored element, not politeness.** A perfect STAR that stops at Resultaat is an incomplete Dutch answer. That is the single cheapest high-value correction this mode makes for an NL target, and a US-calibrated mock never surfaces it.

    ### Germany

    | Source | Shape fact |
    |---|---|
    | `[F]` | Five phases: greeting/small talk, application questions and self-presentation, company presentation, candidate questions, farewell |
    | `[F]` | 45–60 minutes (Robert Half: 30–60), with "kein Jobinterview gleicht dem anderen" |
    | `[F]` | The interviewer may come from Geschäftsführung, Personalabteilung, or Fachabteilung depending on company size |
    | `[F]` | Legally impermissible questions are listed (family planning, sexual orientation, health, religion, political beliefs, union membership, finances) and the candidate "muss nicht ausweichen oder sich rechtfertigen" |
    | `[U]` | Whether German private-sector hiring normally runs multiple rounds. Two fetched sources describe a single five-phase interview and neither states a round count. **Do not assert a German multi-round loop.** |

    For DE/AT/CH targets the prohibited-question list is a rehearsal item **in the opposite direction**: what the candidate needs is a prepared polite refusal, not a prepared answer.

    ## Role-family shapes

    Keyed on what the candidate must produce live. This is the interview axis; `references/role-families.md` keeps the CV axis.

    | Source | Live artifact demanded | Families | Can this mode run it? |
    |---|---|---|---|
    | `[F]` | Working code, watched | SWE, ML eng, quant | **Partly** — the verbal half only. No shared editor exists; say so rather than faking it |
    | `[S]` | A design argued aloud | SWE system design, ML system design, data experiment design | **Yes** — text-native, the strongest mode here |
    | `[F]` | A prepared talk | research scientist, academic, senior clinical, some PM | **Yes, via file** — the candidate outlines, you play the Q&A |
    | `[S]` | A defended past artifact | research scientist, PhD track, legal, creative | **Yes** — deep-dive on a real paper, repo, or matter the candidate names |
    | `[S]` | A live role-play with a counterpart | sales, clinical comms, teaching, hospitality, consulting | **Yes** — you play the counterpart |
    | `[F]` | Structured evidence against named criteria | UK/EU public sector, NHS, academic, EU institutions | **Yes** — and the criteria are published, so the rubric is not invented |
    | `[F]` | Rote recall at speed | China tech 八股文, some licensing exams | **Yes** — but as volume, not as three questions |
    | `[S]` | Values scenarios, deliberately non-clinical | NHS and other regulated professions (MMI) | **Yes** — and the classic failure is answering with clinical knowledge |

    For a family not listed, ask one question that resolves the whole shape: **"In your field, what does the employer make you do live — talk, demonstrate, be scored against written criteria, or be role-played at?"** The answer picks a row above and everything else follows.

    ## The four bands

    Bands are **not numbered**, so they cannot be averaged into a score that has no referent. They are worded as evidence-presence, in the style of the one published scale that does this honestly: every COPFS descriptor is a statement about what appeared in the room, not about the person.

    | Band | Descriptor |
    |---|---|
    | `not_present` | Nothing in the answer addresses this. Quote the closest thing the candidate did say |
    | `asserted` | The candidate stated it but gave no occasion, no object, and no detail that could be checked ("I'm good at stakeholder management") |
    | `instanced` | A specific, dated-or-datable occasion with named people, systems, or numbers, volunteered unprompted |
    | `held_under_probe` | Instanced, **and** the candidate supplied a further concrete detail when asked for one they had not already given |

    **`held_under_probe` is the ceiling, and that is deliberate.** The published Civil Service scale has a 6 and a 7 for "exceeds expectations at this level" — awarding those requires knowing what that level expects, and this mode does not know. What was observed is that an answer survived one real dig. That is what the top band says.

    `contradicted` is **not a fifth band.** It is an orthogonal flag: the answer conflicts with the CV, with `interview-brief.md`, or with an earlier answer this session. It is never scored — it is emitted as `tag=CONTRADICTED` by the provenance pass and it escalates to the walk-back list.

    Bands are emitted per question against five dimensions: `instance`, `completeness`, `ownership`, `outcome`, `probe`. There is no `provenance` dimension — provenance is decided by pass 2, which is the only pass holding the provenance map.

    ## Defect tags (closed set)

    Emitted **with the verbatim line that triggered them**. No quote, no tag — `check_mock.py` fails on a tag whose `quote=` is empty or does not appear in the transcript.

    | Tag | Fires when | Emitted by |
    |---|---|---|
    | `PROBE-COLLAPSE` | Under follow-up the candidate withdrew, hedged away from, or contradicted their own original claim | pass 1 |
    | `UNSOURCED-FACT` | A figure, tool, employer, title, or scope appears in the answer that is in neither the profile, nor `interview-brief.md`, nor an earlier answer this session | pass 2 |
    | `OVER-CLAIM` | The stated scope or credit exceeds the source fact recorded in `interview-brief.md` | pass 2 |
    | `CONTRADICTED` | The answer conflicts with the CV, with `interview-brief.md`, or with an earlier answer this session. Quote both sides | pass 2 |

    `PROBE-COLLAPSE`, `OVER-CLAIM`, and `CONTRADICTED` make a `## Walk-back list` section mandatory. `UNSOURCED-FACT` does not: its usual honest resolution is "true, just not on my CV", which is a `claims.yaml` entry, not a CV edit.

    ## Answer-shape tags (closed set)

    Facts about the shape of the answer. Same rule: no quote, no tag.

    | Tag | Fires when |
    |---|---|
    | `NO-INSTANCE` | A general practice, not a specific time ("I always make sure to…") |
    | `NO-OUTCOME` | The answer ends without saying what changed |
    | `VAGUE-OUTCOME` | An outcome word with no object ("it went really well", "it was a success") |
    | `NO-ACTOR` | "We" throughout; the candidate's own action is not separable |
    | `PREAMBLE-HEAVY` | More than half the answer elapses before the first action the candidate took |
    | `DRIFT` | The answer finishes on a different question than the one asked |
    | `NO-REFLECTION` | **NL targets only** — no reflectie step, which STARR treats as a required element |
    | `NO-TRADEOFF` | A design or decision answer presents one option and no alternative considered |
    | `JARGON-UNGLOSSED` | A domain term used undefined to an interviewer the candidate was told is non-expert |
    | `NO-NEXT-STEP` | **Sales role-play only** — the call ended without asking for a next step |
    | `CLINICAL-DRIFT` | **Regulated/values interview only** — a values scenario answered with clinical knowledge |

    ## Verbatim question material

    Only `[F]` and `[C]` material may be quoted to the candidate as a specific question. This section holds what has been read directly and may be used as-is:

    - `[F]` The Civil Service scale wording, quoted and attributed, as a checklist of what the panel is told to look for — never as a prediction of the mark.
    - `[F]` The STAR / STARR element definitions, including the Dutch reflectie and transfer steps.
    - `[F]` Amazon's published "I" vs "we" instruction, used to explain what the Ownership dimension is looking for.
    - `[C]` Any question opened with `opencli nowcoder detail <id>`, subject to every rule in `modes/interview.md` (date stamp shown, country rule, 12-month rule, answers never pasted).

    Everything else in this file is shape. Search-summary material sets round count, order, and ritual names, and stops there.
    ```

- [ ] **Step 5: Run test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_interview_shapes_doc.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 6: Commit**

    ```bash
    git add scripts/mock_vocab.py references/interview-shapes.md scripts/tests/test_interview_shapes_doc.py
    git commit -m "feat(interview): closed vocabularies + interview-shapes reference, parity-tested"
    ```

---

### Task 2: The assessor output-block parser and the two agent files

**Files:**
- Create: `scripts/mock_blocks.py`
- Create: `agents/mock-assessor-transcript.md`
- Create: `agents/mock-assessor-provenance.md`
- Test: `scripts/tests/test_mock_blocks.py`
- Test: `scripts/tests/test_mock_assessor_agents.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces, in `scripts/mock_blocks.py`:
  - `ASSESSMENT: str = "MOCK-ASSESSMENT-V1"`, `PROVENANCE: str = "MOCK-PROVENANCE-V1"`, `BLOCK_KINDS: tuple[str, str]`
  - `class BlockParseError(ValueError)`
  - `@dataclass(frozen=True) class Record: kind: str; fields: dict; line_no: int`
  - `@dataclass(frozen=True) class Block: kind: str; header: dict; records: tuple; findings_none: bool`
  - `def extract_block(text: str, kind: str) -> list[str]`
  - `def parse_block(text: str, kind: str) -> Block`
  - `def collapse_ws(s: str) -> str`
  - `def normalize_quote(s: str) -> str`
  - `def quote_segments(quote: str) -> list[str]`
  - `def quote_is_in(quote: str, haystack: str) -> bool`
  - `HEADER_KEYS: dict[str, tuple[str, ...]]`, `RECORD_FIELDS: dict[str, tuple[str, ...]]`, `ALLOWED_RECORDS: dict[str, tuple[str, ...]]`, `NONE_MARKER: str`

- [ ] **Step 1: Write the failing parser test**

    Create `scripts/tests/test_mock_blocks.py`:

    ```python
    import pathlib
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import mock_blocks as MB

    GOOD = """prose before the block is fine

    MOCK-ASSESSMENT-V1
    ROUND: 2
    ROUND-TYPE: technical
    MARKET: nl
    FAMILY: ml-engineering
    FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
    BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
    COVERAGE: status=evidenced | must_have=MRI reconstruction | pipelines, clinical
    SHAPE: status=rehearsed | round_name=technisch gesprek
    END-MOCK-ASSESSMENT-V1

    prose after is fine too
    """


    def test_parses_a_well_formed_block():
        block = MB.parse_block(GOOD, MB.ASSESSMENT)
        assert block.header["ROUND"] == "2"
        assert block.header["FAMILY"] == "ml-engineering"
        assert [r.kind for r in block.records] == ["FINDING", "BAND", "COVERAGE", "SHAPE"]
        assert block.findings_none is False


    def test_the_last_field_keeps_its_pipes():
        block = MB.parse_block(GOOD, MB.ASSESSMENT)
        coverage = [r for r in block.records if r.kind == "COVERAGE"][0]
        assert coverage.fields["must_have"] == "MRI reconstruction | pipelines, clinical"


    def test_quote_field_keeps_its_pipes_too():
        text = GOOD.replace(
            "quote=It went really well after that.",
            "quote=we shipped it | then it broke | then we fixed it",
        )
        block = MB.parse_block(text, MB.ASSESSMENT)
        finding = [r for r in block.records if r.kind == "FINDING"][0]
        assert finding.fields["quote"] == "we shipped it | then it broke | then we fixed it"


    def test_a_missing_sentinel_is_a_parse_error():
        with pytest.raises(MB.BlockParseError, match="exactly one start and one end"):
            MB.parse_block(GOOD.replace("END-MOCK-ASSESSMENT-V1", ""), MB.ASSESSMENT)


    def test_two_blocks_of_the_same_kind_are_a_parse_error():
        with pytest.raises(MB.BlockParseError, match="exactly one start and one end"):
            MB.parse_block(GOOD + GOOD, MB.ASSESSMENT)


    def test_an_unknown_record_key_is_a_parse_error():
        text = GOOD.replace("SHAPE: status=", "SHAPES: status=")
        with pytest.raises(MB.BlockParseError, match="unknown record"):
            MB.parse_block(text, MB.ASSESSMENT)


    def test_a_missing_header_line_is_a_parse_error():
        text = GOOD.replace("MARKET: nl\n", "")
        with pytest.raises(MB.BlockParseError, match="missing header line"):
            MB.parse_block(text, MB.ASSESSMENT)


    def test_a_record_with_the_wrong_field_order_is_a_parse_error():
        text = GOOD.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 |", "FINDING: ref=Q2 | tag=VAGUE-OUTCOME |"
        )
        with pytest.raises(MB.BlockParseError, match="expected field 'tag'"):
            MB.parse_block(text, MB.ASSESSMENT)


    def test_a_record_missing_a_field_is_a_parse_error():
        text = GOOD.replace(" | quote=It went really well after that.", "", 1)
        with pytest.raises(MB.BlockParseError, match="must have fields"):
            MB.parse_block(text, MB.ASSESSMENT)


    def test_findings_and_the_none_marker_together_are_a_parse_error():
        text = GOOD.replace("SHAPE: status=rehearsed | round_name=technisch gesprek",
                            "FINDINGS: none")
        with pytest.raises(MB.BlockParseError, match="never both and never neither"):
            MB.parse_block(text, MB.ASSESSMENT)


    def test_neither_findings_nor_the_none_marker_is_a_parse_error():
        """Fail-closed: silence is not the same as 'nothing found'."""
        lines = [ln for ln in GOOD.splitlines() if not ln.startswith("FINDING:")]
        with pytest.raises(MB.BlockParseError, match="never both and never neither"):
            MB.parse_block("\n".join(lines), MB.ASSESSMENT)


    def test_the_none_marker_alone_parses():
        text = "\n".join(
            ln for ln in GOOD.splitlines()
            if not ln.startswith(("FINDING:", "BAND:", "COVERAGE:", "SHAPE:"))
        ).replace("FAMILY: ml-engineering", "FAMILY: ml-engineering\nFINDINGS: none")
        block = MB.parse_block(text, MB.ASSESSMENT)
        assert block.findings_none is True
        assert block.records == ()


    def test_the_provenance_block_refuses_assessment_records():
        text = """MOCK-PROVENANCE-V1
    ROUND: 2
    BAND: dimension=outcome | value=asserted | ref=Q2 | quote=whatever it was
    END-MOCK-PROVENANCE-V1"""
        with pytest.raises(MB.BlockParseError, match="unknown record 'BAND'"):
            MB.parse_block(text, MB.PROVENANCE)


    def test_quote_matching_ignores_wrapping_and_whitespace():
        transcript = "**Candidate:** It went\n  really well  after that."
        assert MB.quote_is_in('"It went really well after that."', transcript)


    def test_quote_matching_tolerates_an_ellipsis():
        transcript = "I ran the benchmark myself on the department cluster last spring."
        assert MB.quote_is_in("I ran the benchmark ... on the department cluster", transcript)


    def test_quote_matching_rejects_an_invented_quote():
        transcript = "I ran the benchmark myself on the department cluster."
        assert not MB.quote_is_in("I ran it on 200 patient scans", transcript)


    def test_a_short_quote_still_matches():
        assert MB.quote_is_in("we did", "and then we did, eventually")
    ```

- [ ] **Step 2: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_mock_blocks.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'mock_blocks'`

- [ ] **Step 3: Write `scripts/mock_blocks.py`**

    ```python
    """Strict parser for the two mock-assessor output blocks.

    Fail-closed, for the same reason parse_verdicts.py is: a block we can only partly read
    is not a block with a few odd lines, it is an assessment that did not happen. The
    caller re-dispatches the pass rather than accepting a half-read one — and in
    particular, a block with neither FINDING lines nor the explicit "FINDINGS: none"
    marker is an error, because silence and "nothing found" must not look the same.
    """
    from __future__ import annotations

    import re
    from dataclasses import dataclass

    ASSESSMENT = "MOCK-ASSESSMENT-V1"
    PROVENANCE = "MOCK-PROVENANCE-V1"
    BLOCK_KINDS = (ASSESSMENT, PROVENANCE)

    HEADER_KEYS = {
        ASSESSMENT: ("ROUND", "ROUND-TYPE", "MARKET", "FAMILY"),
        PROVENANCE: ("ROUND",),
    }
    ALLOWED_RECORDS = {
        ASSESSMENT: ("FINDING", "BAND", "COVERAGE", "SHAPE"),
        PROVENANCE: ("FINDING",),
    }
    # Exactly one free-text field per record, and it is always last, so it may contain
    # the pipe character a real quote sometimes contains.
    RECORD_FIELDS = {
        "FINDING": ("tag", "ref", "quote"),
        "BAND": ("dimension", "value", "ref", "quote"),
        "COVERAGE": ("status", "must_have"),
        "SHAPE": ("status", "round_name"),
    }
    NONE_MARKER = "FINDINGS: none"


    class BlockParseError(ValueError):
        """The block is not exactly the contracted shape."""


    @dataclass(frozen=True)
    class Record:
        kind: str
        fields: dict
        line_no: int


    @dataclass(frozen=True)
    class Block:
        kind: str
        header: dict
        records: tuple
        findings_none: bool


    def extract_block(text: str, kind: str) -> list[str]:
        if kind not in BLOCK_KINDS:
            raise ValueError(f"unknown block kind {kind!r}")
        lines = text.splitlines()
        starts = [i for i, ln in enumerate(lines) if ln.strip() == kind]
        ends = [i for i, ln in enumerate(lines) if ln.strip() == "END-" + kind]
        if len(starts) != 1 or len(ends) != 1:
            raise BlockParseError(
                f"{kind}: expected exactly one start and one end sentinel, "
                f"found {len(starts)} start and {len(ends)} end"
            )
        if ends[0] < starts[0]:
            raise BlockParseError(f"{kind}: END sentinel appears before the start sentinel")
        return lines[starts[0] + 1:ends[0]]


    def _parse_record(key: str, payload: str, line_no: int) -> Record:
        names = RECORD_FIELDS[key]
        parts = payload.split(" | ", len(names) - 1)
        if len(parts) != len(names):
            raise BlockParseError(
                f"line {line_no}: {key} must have fields "
                + " | ".join(n + "=" for n in names)
            )
        fields = {}
        for position, (name, part) in enumerate(zip(names, parts), start=1):
            prefix = name + "="
            if not part.startswith(prefix):
                raise BlockParseError(
                    f"line {line_no}: expected field {name!r} at position {position}, "
                    f"got {part[:24]!r}"
                )
            fields[name] = part[len(prefix):].strip()
        return Record(key, fields, line_no)


    def parse_block(text: str, kind: str) -> Block:
        body = extract_block(text, kind)
        header: dict = {}
        records: list = []
        findings_none = False
        for offset, raw in enumerate(body, start=1):
            line = raw.strip()
            if not line:
                continue
            if line == NONE_MARKER:
                findings_none = True
                continue
            if ":" not in line:
                raise BlockParseError(f"line {offset}: not a record: {line[:40]!r}")
            key, payload = line.split(":", 1)
            key, payload = key.strip(), payload.strip()
            if key in HEADER_KEYS[kind]:
                if key in header:
                    raise BlockParseError(f"line {offset}: duplicate header {key}")
                header[key] = payload
                continue
            if key in ALLOWED_RECORDS[kind]:
                records.append(_parse_record(key, payload, offset))
                continue
            raise BlockParseError(
                f"line {offset}: unknown record {key!r} in {kind} (allowed: "
                + ", ".join(HEADER_KEYS[kind] + ALLOWED_RECORDS[kind])
                + ")"
            )
        missing = [k for k in HEADER_KEYS[kind] if k not in header]
        if missing:
            raise BlockParseError(f"{kind}: missing header line(s) {', '.join(missing)}")
        has_findings = any(r.kind == "FINDING" for r in records)
        if has_findings == findings_none:
            raise BlockParseError(
                f"{kind}: emit either FINDING lines or the single line '{NONE_MARKER}' "
                "— never both and never neither"
            )
        return Block(kind, header, tuple(records), findings_none)


    _WS = re.compile(r"\s+")
    _ELLIPSIS = re.compile(r"\.\.\.|…|\[\.\.\.\]")
    MIN_SEGMENT = 8


    def collapse_ws(s: str) -> str:
        return _WS.sub(" ", s).strip()


    def normalize_quote(s: str) -> str:
        """Collapse whitespace and strip one layer of surrounding quotation marks."""
        s = collapse_ws(s)
        if len(s) >= 2 and s[0] in "\"“'‘" and s[-1] in "\"”'’":
            s = collapse_ws(s[1:-1])
        return s


    def quote_segments(quote: str) -> list[str]:
        whole = normalize_quote(quote)
        segments = [collapse_ws(p) for p in _ELLIPSIS.split(whole)]
        long_enough = [s for s in segments if len(s) >= MIN_SEGMENT]
        if long_enough:
            return long_enough
        return [whole] if whole else []


    def quote_is_in(quote: str, haystack: str) -> bool:
        """True when every substantial segment of the quote appears in the haystack.

        Tolerant of line wrapping, of one layer of quotation marks, and of an elision the
        assessor put in the middle of a long quote — intolerant of an invented quote,
        which is the thing worth catching.
        """
        segments = quote_segments(quote)
        if not segments:
            return False
        hay = collapse_ws(haystack)
        return all(seg in hay for seg in segments)
    ```

- [ ] **Step 4: Run test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_mock_blocks.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 5: Write the failing agent-file test**

    Create `scripts/tests/test_mock_assessor_agents.py`:

    ```python
    import pathlib
    import re
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import mock_blocks as MB
    import mock_vocab as V

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    PASS1 = ROOT / "agents" / "mock-assessor-transcript.md"
    PASS2 = ROOT / "agents" / "mock-assessor-provenance.md"


    def _example(path: pathlib.Path, kind: str) -> str:
        """The fenced example block under '## Example output block'."""
        text = path.read_text(encoding="utf-8")
        after = text.split("## Example output block", 1)
        assert len(after) == 2, f"{path.name} has no '## Example output block' section"
        fenced = re.findall(r"```\n(.*?)```", after[1], re.S)
        assert fenced, f"{path.name}: the example section has no fenced block"
        for candidate in fenced:
            if kind in candidate:
                return candidate
        raise AssertionError(f"{path.name}: no fenced example containing {kind}")


    def test_pass1_example_block_parses():
        block = MB.parse_block(_example(PASS1, MB.ASSESSMENT), MB.ASSESSMENT)
        assert block.header["ROUND-TYPE"] in V.ROUND_TYPES
        assert block.header["MARKET"] in V.MARKET_KEYS


    def test_pass2_example_block_parses():
        block = MB.parse_block(_example(PASS2, MB.PROVENANCE), MB.PROVENANCE)
        assert block.header["ROUND"].isdigit()


    def test_pass1_example_uses_only_tags_pass1_may_emit():
        block = MB.parse_block(_example(PASS1, MB.ASSESSMENT), MB.ASSESSMENT)
        for record in block.records:
            if record.kind == "FINDING":
                assert record.fields["tag"] in V.TRANSCRIPT_TAGS


    def test_pass2_example_uses_only_tags_pass2_may_emit():
        block = MB.parse_block(_example(PASS2, MB.PROVENANCE), MB.PROVENANCE)
        for record in block.records:
            if record.kind == "FINDING":
                assert record.fields["tag"] in V.PROVENANCE_TAGS


    def test_every_example_record_carries_a_quote():
        for path, kind in ((PASS1, MB.ASSESSMENT), (PASS2, MB.PROVENANCE)):
            block = MB.parse_block(_example(path, kind), kind)
            for record in block.records:
                if record.kind in ("FINDING", "BAND"):
                    assert MB.normalize_quote(record.fields["quote"]), (
                        f"{path.name}: {record.kind} on line {record.line_no} has no quote"
                    )


    @pytest.mark.parametrize(
        "path, must_not_see",
        [(PASS1, ("interview-brief.md", "claims.yaml")), (PASS2, ("rubric",))],
    )
    def test_each_agent_states_what_it_is_not_given(path, must_not_see):
        text = path.read_text(encoding="utf-8")
        assert "## What you are deliberately NOT given, and why" in text
        section = text.split("## What you are deliberately NOT given, and why", 1)[1]
        section = section.split("\n## ", 1)[0]
        for item in must_not_see:
            assert item in section, f"{path.name} does not name {item!r} as withheld"


    def test_pass1_is_told_it_may_not_emit_the_provenance_tags():
        text = PASS1.read_text(encoding="utf-8")
        for tag in V.PROVENANCE_TAGS:
            assert tag in text
        assert "WRONG_PASS" in text


    def test_neither_agent_is_allowed_to_number_the_bands():
        for path in (PASS1, PASS2):
            text = path.read_text(encoding="utf-8")
            assert "do not average" in text.lower() or "cannot be averaged" in text.lower()
    ```

- [ ] **Step 6: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_mock_assessor_agents.py -q`
    Expected: FAIL with `FileNotFoundError: ... agents/mock-assessor-transcript.md`

- [ ] **Step 7: Write `agents/mock-assessor-transcript.md`**

    ````markdown
    # Mock Assessor — Transcript Pass (assessment pass 1 of 2)

    ## Role

    You assess **one round of a mock interview transcript**. You are one of two independent
    assessors run on the same transcript with **deliberately different inputs**. You never
    see the other pass's output, and it never sees yours.

    Your job: report what is in the transcript. Never report what a human would conclude
    from it. "Your answer to Q3 never named what changed as a result" is a fact about a
    text file. "That was a solid answer" is a guess about a stranger's judgement, and "you
    would probably pass" is an invented number wearing words. The first is always
    available; the other two never are.

    ## Inputs (pasted directly below this prompt when you are dispatched)

    1. `mock/transcript-<n>.md` — the full round, verbatim.
    2. `posting.yaml` — the extracted posting, for the must-have list.
    3. `cv.md` — the tailored CV as the candidate submitted it.

    ## What you are deliberately NOT given, and why

    You are **not** given `interview-brief.md` and **not** given `claims.yaml`.

    Those two files hold the provenance map: the real source fact behind every tailored CV
    claim. If you held them, you would hear the answer the candidate *meant* instead of the
    one they gave, and you would credit them for a source fact they never said out loud.
    That leniency would be invisible in your output — it looks exactly like a generous
    reading. Withholding those files is the mechanism that makes your assessment honest,
    not a limitation to work around.

    So: if you find yourself wanting to know "what was the real number", that is the
    boundary doing its job. Report what the transcript says.

    Consequently you **may not emit** `UNSOURCED-FACT`, `OVER-CLAIM`, or `CONTRADICTED`.
    You do not hold the inputs that decide them; the provenance pass does. `check_mock.py`
    fails your block with `WRONG_PASS` if one of those tags appears in it.

    ## What you emit

    **Findings.** Zero or more, from this closed set and no other. A tag outside it fails
    the gate with `UNKNOWN_TAG`.

    | Tag | Fires when |
    |---|---|
    | `NO-INSTANCE` | A general practice, not a specific time ("I always make sure to…") |
    | `NO-OUTCOME` | The answer ends without saying what changed |
    | `VAGUE-OUTCOME` | An outcome word with no object ("it went really well") |
    | `NO-ACTOR` | "We" throughout; the candidate's own action is not separable |
    | `PREAMBLE-HEAVY` | More than half the answer elapses before the first action they took |
    | `DRIFT` | The answer finishes on a different question than the one asked |
    | `NO-REFLECTION` | **MARKET: nl only** — no reflectie step (STARR treats it as required) |
    | `NO-TRADEOFF` | A design or decision answer presents one option, no alternative |
    | `JARGON-UNGLOSSED` | A domain term left undefined to a non-expert interviewer |
    | `NO-NEXT-STEP` | **FAMILY: sales only** — the call ended without asking for a next step |
    | `CLINICAL-DRIFT` | **FAMILY: clinical only** — a values scenario answered with clinical knowledge |
    | `PROBE-COLLAPSE` | Under follow-up the candidate withdrew, hedged away from, or contradicted their own original claim |

    **Every finding carries the verbatim line that triggered it.** No quote, no tag — the
    gate fails an empty `quote=` with `NO_QUOTE`, and a quote that does not appear in the
    transcript with `QUOTE_NOT_IN_TRANSCRIPT`. Copy the words; do not paraphrase them.

    **Bands.** One `BAND` line per question per dimension you can decide, on five
    dimensions: `instance`, `completeness`, `ownership`, `outcome`, `probe`. Four values,
    and **they are not numbered on purpose — do not average, total, rank, or convert them**:

    | Band | Meaning |
    |---|---|
    | `not_present` | Nothing in the answer addresses this. Quote the closest thing they did say |
    | `asserted` | Stated, with no occasion, no object, and no checkable detail |
    | `instanced` | A specific, dated-or-datable occasion with named people, systems, or numbers, volunteered unprompted |
    | `held_under_probe` | Instanced, **and** a further concrete detail supplied when asked for one not already given |

    `held_under_probe` is the ceiling. There is no higher band, because a higher band would
    require knowing what this employer expects at this level, and you do not.

    `contradicted` is **not a band value** — it is a flag owned by the provenance pass. The
    gate fails `value=contradicted` with `NOT_A_BAND`.

    **Coverage.** One `COVERAGE` line per must-have in `posting.yaml`, with
    `status=evidenced|asked_thin|not_asked`. This is the **session's** coverage, not the
    candidate's competence.

    **Shape.** One `SHAPE` line per round the target market and family actually runs, with
    `status=rehearsed|partial|not_attempted|cannot_simulate`. Use `cannot_simulate`
    honestly — 手撕代码 under a watching interviewer, an in-person MMI circuit, and a
    whiteboard chalk talk cannot be run here, and saying so is more useful than pretending.

    ## Vocabulary you must not use

    No score, grade, percentage, or "X out of Y" of your own invention. No probability,
    likelihood, odds, or "chance of". No "you would pass / fail / they would hire you". No
    "strong candidate", "weak candidate", "hire", "no-hire", "leaning hire". No comparison
    to other candidates, real or imagined. No claim about what the interviewer thought,
    felt, or would conclude. No rating on a scale the employer did not publish.

    Where the employer publishes its own rubric, you may quote it, attributed, as a
    checklist of what the panel is told to look for. Quoting an employer's scale is
    reporting; applying it as a verdict is fabrication.

    ## Required output format

    You MUST end your response with EXACTLY the following block. Nothing after it. The
    gate parses it programmatically and fails closed — a block it cannot read exactly is
    treated as an assessment that did not happen, and the round is re-dispatched.

    ```
    MOCK-ASSESSMENT-V1
    ROUND: <integer>
    ROUND-TYPE: behavioural | technical | design | hr
    MARKET: cn | nl | de | uk | us | other
    FAMILY: <role-family slug, e.g. ml-engineering>
    FINDING: tag=<TAG> | ref=<Qn> | quote=<verbatim, to end of line>
    BAND: dimension=<dimension> | value=<band> | ref=<Qn> | quote=<verbatim, to end of line>
    COVERAGE: status=<status> | must_have=<text, to end of line>
    SHAPE: status=<status> | round_name=<text, to end of line>
    END-MOCK-ASSESSMENT-V1
    ```

    Rules for the block:

    - Fields are separated by ` | ` (space pipe space) and appear in the order shown.
    - **The last field of each record is free text and may contain pipes.** No other field may.
    - If you found no defects at all, emit the single line `FINDINGS: none` and no
      `FINDING:` lines. Emitting neither is a parse error, and so is emitting both —
      silence must not be readable as "nothing found".
    - `ref=` must name a question heading that exists in the transcript (`## Q3 — …`).
    - Do not add fields. Do not omit header lines.

    ## Example output block

    ```
    MOCK-ASSESSMENT-V1
    ROUND: 2
    ROUND-TYPE: technical
    MARKET: nl
    FAMILY: ml-engineering
    FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
    FINDING: tag=NO-REFLECTION | ref=Q2 | quote=I replaced the per-slice loop with a batched GPU implementation.
    BAND: dimension=instance | value=instanced | ref=Q1 | quote=At the university hospital I owned the offline recon pipeline for a 3T scanner study
    BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
    BAND: dimension=probe | value=held_under_probe | ref=Q3 | quote=I would run the profiler first next time
    COVERAGE: status=evidenced | must_have=MRI reconstruction pipelines in a clinical setting
    COVERAGE: status=not_asked | must_have=Experience with regulatory documentation (MDR)
    SHAPE: status=rehearsed | round_name=technisch gesprek met de vakinhoudelijke manager
    SHAPE: status=not_attempted | round_name=gesprek met het team
    END-MOCK-ASSESSMENT-V1
    ```
    ````

    > **Note for the implementer:** the file above ends with a fenced block inside a fenced
    > block. When you write the real file, the outer fence shown here is not part of it —
    > the file starts at `# Mock Assessor — Transcript Pass` and its last line is the
    > closing fence of the example block.

- [ ] **Step 8: Write `agents/mock-assessor-provenance.md`**

    ````markdown
    # Mock Assessor — Provenance Pass (assessment pass 2 of 2)

    ## Role

    You have exactly one job: decide whether anything the candidate said in this round is
    **not traceable** to a source the pipeline already holds. You do not assess quality.
    You do not grade. You emit three tags and nothing else.

    You are one of two independent assessors run on the same transcript with **deliberately
    different inputs**. You never see the other pass's output, and it never sees yours.

    ## Inputs (pasted directly below this prompt when you are dispatched)

    1. `mock/transcript-<n>.md` — the full round, verbatim.
    2. `claims.yaml` — every claim that entered the tailored CV, with its source.
    3. `interview-brief.md` — the defence brief: each tailored claim and the real source
       fact behind it, the honest gaps, and the questions the CV judges already raised.

    ## What you are deliberately NOT given, and why

    You are **not** given the rubric — not the band descriptors, not the answer-shape tag
    set, not the coverage tables.

    If you held the rubric you would drift into grading, and a grader who *also* holds the
    provenance map is exactly the lenient assessor that pass 1 exists to prevent: it would
    hear the answer the candidate meant, credit the source fact they never said, and score
    it well. Two passes with different inputs is what turns the honesty tripwire from an
    intention into a mechanism. Keeping you rubric-blind is half of that mechanism.

    So do not comment on how good an answer was, how it was structured, or what it was
    missing. That is pass 1's work and it is being done in parallel.

    ## What you emit

    Three tags, and no others. A tag outside this set fails the gate with `UNKNOWN_TAG`.

    | Tag | Fires when |
    |---|---|
    | `UNSOURCED-FACT` | A figure, tool, employer, title, or scope appears in the answer that is in **neither** the profile/CV material in `claims.yaml`, **nor** `interview-brief.md`, **nor** an earlier answer in this same transcript |
    | `OVER-CLAIM` | The scope or credit the candidate stated **exceeds** the source fact recorded in `interview-brief.md`. Quote the answer; name the brief's line in the note position of the quote if it helps |
    | `CONTRADICTED` | The answer conflicts with the CV, with `interview-brief.md`, or with an earlier answer in this transcript. Quote **both** sides — emit two FINDING lines with the same tag, one per side |

    **Every finding carries the verbatim line that triggered it.** No quote, no tag. The
    gate fails an empty `quote=` with `NO_QUOTE`, and a quote that does not appear in the
    transcript with `QUOTE_NOT_IN_TRANSCRIPT`. Copy the words exactly.

    **You do not resolve anything.** An `UNSOURCED-FACT` is usually "it's true, it's just
    not on my CV" — that is a real finding and it belongs on the CV, but *you* do not
    decide that. You report it; the main conversation asks the candidate where it came
    from. Silently keeping an unsourced fact is worse than having no answer bank at all,
    because the candidate will say it out loud in the real interview believing it was
    vetted.

    ## Vocabulary you must not use

    No score, grade, percentage, or "X out of Y". No probability, likelihood, or odds. No
    "you would pass / fail". No "strong candidate" or "weak candidate". No comparison to
    other candidates. No claim about what an interviewer thought or would conclude. The
    bands are not yours to use and **cannot be averaged** in any case — do not average,
    total, or rank anything.

    ## Required output format

    You MUST end your response with EXACTLY the following block. Nothing after it. The gate
    parses it programmatically and fails closed.

    ```
    MOCK-PROVENANCE-V1
    ROUND: <integer>
    FINDING: tag=<UNSOURCED-FACT | OVER-CLAIM | CONTRADICTED> | ref=<Qn> | quote=<verbatim, to end of line>
    END-MOCK-PROVENANCE-V1
    ```

    Rules for the block:

    - Fields are separated by ` | ` and appear in the order shown. `quote=` is last and may
      contain pipes; no other field may.
    - If nothing is unsourced, over-claimed, or contradicted, emit the single line
      `FINDINGS: none` and no `FINDING:` lines. Emitting neither is a parse error, and so
      is emitting both — a clean round must be stated, not implied by silence.
    - `ref=` must name a question heading that exists in the transcript (`## Q3 — …`).

    ## Example output block

    ```
    MOCK-PROVENANCE-V1
    ROUND: 2
    FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=We benchmarked the new pipeline against the old one on about 200 patient scans
    FINDING: tag=OVER-CLAIM | ref=Q1 | quote=it came out roughly 40% faster end to end
    END-MOCK-PROVENANCE-V1
    ```
    ````

    > **Note for the implementer:** as with pass 1, the outer fence shown here is not part
    > of the real file.

- [ ] **Step 9: Run test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_mock_assessor_agents.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 10: Commit**

    ```bash
    git add scripts/mock_blocks.py agents/mock-assessor-transcript.md agents/mock-assessor-provenance.md scripts/tests/test_mock_blocks.py scripts/tests/test_mock_assessor_agents.py
    git commit -m "feat(interview): fail-closed assessor block parser + the two assessor agents"
    ```

---

### Task 3: `check_mock.py` — the gate core (tags, quotes, bands, receipts, exit codes)

**Files:**
- Create: `scripts/check_mock.py`
- Create: `scripts/tests/mock_fixtures.py`
- Test: `scripts/tests/test_check_mock_core.py`

**Interfaces:**
- Consumes:
  - `scripts/journal.py` (Plan 1): `append(workspace, record)`, `receipt(workspace, gate, input_hashes, verdict, findings=None) -> dict`, `sha256_file(path) -> str`, `read_receipts(workspace, gate=None) -> list[dict]`
  - `scripts/mock_blocks.py` (Task 2): `ASSESSMENT`, `PROVENANCE`, `BlockParseError`, `parse_block`, `collapse_ws`, `normalize_quote`, `quote_is_in`
  - `scripts/mock_vocab.py` (Task 1): every constant
- Produces, in `scripts/check_mock.py`:
  - `class InputMissing(RuntimeError)` — raised when a required *input* is absent → exit 2
  - `class MissingDependency(RuntimeError)` — raised when a cross-plan module is absent → exit 2
  - `def transcript_refs(text: str) -> set[str]`
  - `def check_assessment(assessment_text: str, transcript_text: str, round_no: int) -> tuple[dict, list[str]]` — returns `({block_kind: Block}, findings)`
  - `def run(workspace: pathlib.Path, round_no: int, answer_bank: pathlib.Path | None = None, today: datetime.date | None = None, vocab_scanner=_AUTO) -> list[str]`
  - `def main(argv: list[str] | None = None) -> int`
- Produces, in `scripts/tests/mock_fixtures.py`:
  - `def build(tmp_path, *, round_no=2, transcript=None, assessment=None, question_log=None, answer_bank=None, brief=None, claims=None) -> pathlib.Path` — returns the workspace path
  - `def no_vocab(text: str, source: str) -> list[str]` — the stub banned-vocabulary scanner
  - module constants `TRANSCRIPT`, `ASSESSMENT`, `QUESTION_LOG`, `ANSWER_BANK`, `BRIEF`, `CLAIMS`

- [ ] **Step 1: Write the fixture builder**

    Create `scripts/tests/mock_fixtures.py`. This is the **quiet case**: a complete workspace
    that every check must pass in silence. Every test below starts here and breaks exactly
    one thing, so a check that cries wolf on ordinary output fails a test immediately.

    ```python
    """A complete, PASSING interview workspace, built on disk.

    Every test starts from this quiet case and breaks exactly one thing. A check that fires
    on ordinary output therefore fails a test on its first run, which is the only way to
    keep the gate from becoming the line everyone learns to skip.
    """
    import pathlib

    TRANSCRIPT = """# Mock transcript — round 2
    Round type: technical
    Market: nl
    Family: ml-engineering
    Persona: Sanne de Vries, MR reconstruction team lead — direct, asks for numbers

    ## Q1 — Walk me through the reconstruction pipeline you owned.
    **Interviewer:** Walk me through the reconstruction pipeline you owned.
    **Candidate:** At the university hospital I owned the offline recon pipeline for a 3T scanner study: raw k-space came off the scanner, I ran coil compression, then a variational-network model, then wrote DICOMs back to the PACS.

    ## Q2 — What did you change about it, and what happened as a result?
    **Interviewer:** What did you change about it, and what happened as a result?
    **Candidate:** I replaced the per-slice loop with a batched GPU implementation. It went really well after that.

    ## Q3 — What did you learn from that, and what would you do differently?
    **Interviewer:** What did you learn from that, and what would you do differently?
    **Candidate:** I learned to profile before optimising. I would run the profiler first next time and write down the baseline before touching anything.
    """

    ASSESSMENT = """# Mock assessment — round 2

    Two passes ran on this transcript with deliberately different inputs. Neither saw the
    other's output. The blocks below are the assessors' own words, unedited.

    MOCK-ASSESSMENT-V1
    ROUND: 2
    ROUND-TYPE: technical
    MARKET: nl
    FAMILY: ml-engineering
    FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
    BAND: dimension=instance | value=instanced | ref=Q1 | quote=At the university hospital I owned the offline recon pipeline for a 3T scanner study
    BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
    BAND: dimension=probe | value=held_under_probe | ref=Q3 | quote=I would run the profiler first next time
    BAND: dimension=completeness | value=instanced | ref=Q3 | quote=I learned to profile before optimising.
    COVERAGE: status=evidenced | must_have=MRI reconstruction pipelines in a clinical setting
    COVERAGE: status=not_asked | must_have=Regulatory documentation (MDR)
    SHAPE: status=rehearsed | round_name=technisch gesprek met de vakinhoudelijke manager
    SHAPE: status=not_attempted | round_name=gesprek met het team
    END-MOCK-ASSESSMENT-V1

    MOCK-PROVENANCE-V1
    ROUND: 2
    FINDINGS: none
    END-MOCK-PROVENANCE-V1
    """

    QUESTION_LOG = """round: 2
    posting_country: NL
    questions:
      - id: Q1
        text: Walk me through the reconstruction pipeline you owned.
        source: generated
        asked: true
      - id: Q2
        text: What did you change about it, and what happened as a result?
        source: generated
        asked: true
      - id: Q3
        text: What did you learn from that, and what would you do differently?
        source: generated
        asked: true
rejected:
      - id: R1
        text: "ASML 宣讲会 + 笔试 timeline"
        source: scraped
        source_site: nowcoder
        source_id: "057523b2ca9d"
        source_time: "2026-08-06T11:06:49"
        entity_country: CN
        reason: wrong_country
    """

    ANSWER_BANK = """# Answer bank

    ## Batched GPU reconstruction on the 3T study
    - serves: "tell me about an optimisation you made"; round 2 Q2
    - source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
    - session: 2026-08-09 — applications/asml-mr-recon-engineer-2026-08-09/mock/transcript-2.md#Q2
    - S: offline recon for a 3T scanner study at the university hospital
    - T: the per-slice loop was the bottleneck in the nightly batch
    - A: replaced the per-slice loop with a batched GPU implementation
    - R: open loop — the measured change was not stated in the room; see open-loops.md
    - R2 (reflectie): profile before optimising, and write the baseline down first
    """

    BRIEF = """# Interview-readiness brief

    ## 1. Be ready to explain (your tailored claims)
    - CV says: "Rewrote the offline reconstruction loop for GPU batching."
      Source: profile.yaml:experience[0].bullets[2].
      Be ready to: name the before and after timings and how they were measured.

    ## 2. Honest gaps — your answer if asked
    - No MDR regulatory documentation experience. Honest framing: research-side validation
      work, learning the regulatory side deliberately.
    """

    CLAIMS = """- term: GPU batching
      where: tailored-profile.yaml:experience[0].bullets[2]
      source_kind: profile-line
      source_ref: profile.yaml:experience[0].bullets[2]
      session_date: "2026-08-09"
      retracted: null
    """


    def build(tmp_path, *, round_no=2, transcript=None, assessment=None, question_log=None,
              answer_bank=None, brief=None, claims=None):
        """Write the quiet-case workspace under tmp_path and return the workspace path."""
        profile = pathlib.Path(tmp_path) / "job-profiles" / "demo"
        workspace = profile / "applications" / "asml-mr-recon-engineer-2026-08-09"
        (workspace / "mock").mkdir(parents=True, exist_ok=True)

        def w(path, text):
            path.write_text(text, encoding="utf-8")

        w(workspace / "mock" / f"transcript-{round_no}.md",
          TRANSCRIPT if transcript is None else transcript)
        w(workspace / "mock" / f"assessment-{round_no}.md",
          ASSESSMENT if assessment is None else assessment)
        w(workspace / "mock" / "question-log.yaml",
          QUESTION_LOG if question_log is None else question_log)
        w(workspace / "interview-brief.md", BRIEF if brief is None else brief)
        w(workspace / "claims.yaml", CLAIMS if claims is None else claims)
        w(profile / "answer-bank.md", ANSWER_BANK if answer_bank is None else answer_bank)
        return workspace


    def no_vocab(text, source):
        """Stub for scripts/lint_no_prediction.py (Plan 2): finds nothing, quietly."""
        return []
    ```

    > **Indentation warning:** the triple-quoted constants above are shown indented to sit
    > inside this plan's fenced block. In the real file they start at column 0 — the YAML in
    > `QUESTION_LOG` in particular must be written with no leading spaces on `round:`,
    > `posting_country:`, `questions:` and `rejected:`, and two-space indents beneath them.
    > After writing the file, verify with:
    > `python3 -c "import yaml,sys;sys.path.insert(0,'scripts/tests');import mock_fixtures as m;print(yaml.safe_load(m.QUESTION_LOG)['posting_country'])"`
    > which must print `NL`.

- [ ] **Step 2: Write the failing core test**

    Create `scripts/tests/test_check_mock_core.py`:

    ```python
    import json
    import pathlib
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import check_mock
    import mock_fixtures as F


    def run(workspace, **kw):
        kw.setdefault("vocab_scanner", F.no_vocab)
        return check_mock.run(workspace, 2, **kw)


    # ---------------------------------------------------------------- the quiet case

    def test_a_clean_workspace_produces_no_findings(tmp_path):
        assert run(F.build(tmp_path)) == []


    def test_a_clean_workspace_exits_zero_and_prints_nothing(tmp_path, capsys, monkeypatch):
        ws = F.build(tmp_path)
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        code = check_mock.main(["--workspace", str(ws), "--round", "2",
                                "--today", "2026-08-09"])
        assert code == 0
        assert capsys.readouterr().out == ""


    def test_a_clean_run_writes_exactly_one_pass_receipt(tmp_path, monkeypatch):
        ws = F.build(tmp_path)
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        check_mock.main(["--workspace", str(ws), "--round", "2", "--today", "2026-08-09"])
        lines = (ws / "journal.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["gate"] == "check_mock"
        assert record["verdict"] == "pass"
        assert "mock/assessment-2.md" in record["input_hashes"]
        assert "mock/transcript-2.md" in record["input_hashes"]


    # ---------------------------------------------------------------- missing inputs

    def test_a_missing_assessment_is_exit_2_not_a_failure(tmp_path, capsys, monkeypatch):
        ws = F.build(tmp_path)
        (ws / "mock" / "assessment-2.md").unlink()
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        code = check_mock.main(["--workspace", str(ws), "--round", "2",
                                "--today", "2026-08-09"])
        assert code == 2
        assert "assessment-2.md" in capsys.readouterr().err


    def test_a_missing_input_still_writes_a_receipt(tmp_path, monkeypatch):
        ws = F.build(tmp_path)
        (ws / "mock" / "transcript-2.md").unlink()
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        check_mock.main(["--workspace", str(ws), "--round", "2", "--today", "2026-08-09"])
        record = json.loads((ws / "journal.jsonl").read_text(encoding="utf-8").strip())
        assert record["verdict"] == "could_not_run"


    # ---------------------------------------------------------------- fail-closed parsing

    def test_a_missing_provenance_block_is_reported_as_a_pass_that_never_ran(tmp_path):
        text = F.ASSESSMENT.split("MOCK-PROVENANCE-V1")[0]
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("MISSING_BLOCK: MOCK-PROVENANCE-V1") for f in findings)


    def test_an_unreadable_block_is_a_parse_fail_not_a_silent_pass(tmp_path):
        text = F.ASSESSMENT.replace("ROUND-TYPE: technical", "ROUND-TYPE: technical | oops")
        text = text.replace("MARKET: nl\n", "")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("PARSE_FAIL:") for f in findings)


    # ---------------------------------------------------------------- the closed tag sets

    def test_an_invented_tag_fails(tmp_path):
        text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=WEAK-ANSWER")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_TAG:") and "WEAK-ANSWER" in f for f in findings)


    def test_a_provenance_tag_in_the_transcript_pass_fails(tmp_path):
        """Pass 1 does not hold interview-brief.md, so it cannot have decided this."""
        text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=UNSOURCED-FACT")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("WRONG_PASS:") and "UNSOURCED-FACT" in f for f in findings)


    def test_a_shape_tag_in_the_provenance_pass_fails(tmp_path):
        text = F.ASSESSMENT.replace(
            "MOCK-PROVENANCE-V1\nROUND: 2\nFINDINGS: none",
            "MOCK-PROVENANCE-V1\nROUND: 2\n"
            "FINDING: tag=NO-OUTCOME | ref=Q2 | quote=It went really well after that.",
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("WRONG_PASS:") and "NO-OUTCOME" in f for f in findings)


    def test_all_four_contract_tags_are_accepted_in_their_own_pass(tmp_path):
        text = F.ASSESSMENT.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
            "FINDING: tag=PROBE-COLLAPSE | ref=Q2 | quote=It went really well after that.",
        ).replace(
            "MOCK-PROVENANCE-V1\nROUND: 2\nFINDINGS: none",
            "MOCK-PROVENANCE-V1\nROUND: 2\n"
            "FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=then wrote DICOMs back to the PACS\n"
            "FINDING: tag=OVER-CLAIM | ref=Q1 | quote=I owned the offline recon pipeline\n"
            "FINDING: tag=CONTRADICTED | ref=Q3 | quote=I learned to profile before optimising.",
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert not [f for f in findings if f.startswith(("UNKNOWN_TAG:", "WRONG_PASS:"))]


    # ---------------------------------------------------------------- conditional tags

    def test_a_dutch_only_tag_outside_the_dutch_market_fails(tmp_path):
        text = F.ASSESSMENT.replace("MARKET: nl", "MARKET: us").replace(
            "tag=VAGUE-OUTCOME", "tag=NO-REFLECTION")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("TAG_NOT_APPLICABLE:") and "NO-REFLECTION" in f
                   for f in findings)


    def test_the_same_tag_in_the_dutch_market_is_quiet(tmp_path):
        text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=NO-REFLECTION")
        findings = run(F.build(tmp_path, assessment=text))
        assert not [f for f in findings if f.startswith("TAG_NOT_APPLICABLE:")]


    def test_a_sales_only_tag_outside_sales_fails(tmp_path):
        text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=NO-NEXT-STEP")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("TAG_NOT_APPLICABLE:") and "NO-NEXT-STEP" in f
                   for f in findings)


    # ---------------------------------------------------------------- no quote, no tag

    def test_a_tag_without_a_quote_fails(tmp_path):
        text = F.ASSESSMENT.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=",
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("NO_QUOTE:") for f in findings)


    def test_a_band_without_a_quote_fails(tmp_path):
        text = F.ASSESSMENT.replace(
            "BAND: dimension=outcome | value=asserted | ref=Q2 | "
            "quote=It went really well after that.",
            "BAND: dimension=outcome | value=asserted | ref=Q2 | quote=   ",
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("NO_QUOTE:") for f in findings)


    def test_an_invented_quote_fails(tmp_path):
        text = F.ASSESSMENT.replace(
            "quote=It went really well after that.",
            "quote=we cut the reconstruction time by 40 percent",
            1,
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("QUOTE_NOT_IN_TRANSCRIPT:") for f in findings)


    def test_a_rewrapped_quote_is_quiet(tmp_path):
        """The transcript wraps; the assessor's copy of the line must still count."""
        transcript = F.TRANSCRIPT.replace(
            "I replaced the per-slice loop with a batched GPU implementation. "
            "It went really well after that.",
            "I replaced the per-slice loop with a batched GPU implementation.\n"
            "It went really\n  well after that.",
        )
        findings = run(F.build(tmp_path, transcript=transcript))
        assert not [f for f in findings if f.startswith("QUOTE_NOT_IN_TRANSCRIPT:")]


    def test_an_elided_quote_is_quiet(tmp_path):
        text = F.ASSESSMENT.replace(
            "quote=At the university hospital I owned the offline recon pipeline "
            "for a 3T scanner study",
            "quote=At the university hospital I owned ... for a 3T scanner study",
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert not [f for f in findings if f.startswith("QUOTE_NOT_IN_TRANSCRIPT:")]


    def test_a_reference_to_a_question_that_was_never_asked_fails(tmp_path):
        text = F.ASSESSMENT.replace("ref=Q2 | quote=It went", "ref=Q9 | quote=It went")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_REF:") and "Q9" in f for f in findings)


    # ---------------------------------------------------------------- bands

    def test_the_flag_is_rejected_as_a_band_value(tmp_path):
        text = F.ASSESSMENT.replace("value=asserted", "value=contradicted")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("NOT_A_BAND:") for f in findings)
        assert any("tag=CONTRADICTED" in f for f in findings)


    def test_an_invented_band_fails(tmp_path):
        text = F.ASSESSMENT.replace("value=asserted", "value=excellent")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_BAND:") for f in findings)


    def test_a_numeric_band_fails(tmp_path):
        text = F.ASSESSMENT.replace("value=asserted", "value=3")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_BAND:") for f in findings)


    def test_an_invented_dimension_fails(tmp_path):
        text = F.ASSESSMENT.replace("dimension=outcome", "dimension=charisma")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_DIMENSION:") for f in findings)


    def test_a_provenance_dimension_fails_because_pass_1_cannot_decide_it(tmp_path):
        text = F.ASSESSMENT.replace("dimension=outcome", "dimension=provenance")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_DIMENSION:") for f in findings)


    # ---------------------------------------------------------------- headers

    def test_a_round_mismatch_fails(tmp_path):
        text = F.ASSESSMENT.replace("ROUND: 2\nROUND-TYPE", "ROUND: 3\nROUND-TYPE")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("ROUND_MISMATCH:") for f in findings)


    def test_an_invented_round_type_fails(tmp_path):
        text = F.ASSESSMENT.replace("ROUND-TYPE: technical", "ROUND-TYPE: culture-fit")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_ROUND_TYPE:") for f in findings)


    def test_an_unknown_market_fails(tmp_path):
        text = F.ASSESSMENT.replace("MARKET: nl", "MARKET: benelux")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_MARKET:") for f in findings)


    def test_an_unknown_status_fails(tmp_path):
        text = F.ASSESSMENT.replace("status=evidenced", "status=covered")
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("UNKNOWN_STATUS:") for f in findings)


    # ---------------------------------------------------------------- exit codes

    def test_a_failing_workspace_exits_1_and_prints_one_finding_per_line(
        tmp_path, capsys, monkeypatch
    ):
        ws = F.build(tmp_path, assessment=F.ASSESSMENT.replace(
            "tag=VAGUE-OUTCOME", "tag=WEAK-ANSWER"))
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        code = check_mock.main(["--workspace", str(ws), "--round", "2",
                                "--today", "2026-08-09"])
        out = capsys.readouterr().out.strip().splitlines()
        assert code == 1
        assert out and all(line.split(":")[0].isupper() for line in out)
    ```

- [ ] **Step 3: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_mock_core.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_mock'`

- [ ] **Step 4: Write `scripts/check_mock.py`**

    ```python
    #!/usr/bin/env python3
    """Gate for the interview mode.

    Usage:
        python3 scripts/check_mock.py --workspace <application dir> --round <n>
                                      [--answer-bank <path>] [--today YYYY-MM-DD]

    exit 0 — the round holds up.
    exit 1 — findings printed to stdout, one per line, each with a stable UPPERCASE code.
    exit 2 — could not run (a required input is missing, or a cross-plan module is absent);
             message to stderr. Never a silent skip: a check that did not run must not look
             like a check that passed.

    Required *inputs* are the transcript and the assessment. Everything else this gate reads
    (question-log.yaml, answer-bank.md, interview-brief.md, claims.yaml) is a required
    *output* of the mode — its absence is the defect, so it is a finding, not an exit 2.
    """
    from __future__ import annotations

    import argparse
    import datetime
    import pathlib
    import re
    import sys

    import journal
    import mock_blocks as MB
    import mock_vocab as V

    GATE = "check_mock"
    _AUTO = object()


    class InputMissing(RuntimeError):
        """A required input file is absent — the gate has nothing to check."""


    class MissingDependency(RuntimeError):
        """A cross-plan module is absent — the gate cannot honestly claim to have run."""


    # ----------------------------------------------------------------- transcript helpers

    _Q_HEADING = re.compile(r"^##\s+(Q\d+)\b", re.M)


    def transcript_refs(text: str) -> set:
        return set(_Q_HEADING.findall(text))


    # ----------------------------------------------------------------- assessment checks

    def _check_headers(block, round_no: int, findings: list) -> None:
        label = block.kind
        raw = block.header.get("ROUND", "")
        if not raw.isdigit():
            findings.append(f"BAD_ROUND: {label}: ROUND: {raw!r} is not an integer")
        elif int(raw) != round_no:
            findings.append(
                f"ROUND_MISMATCH: {label}: ROUND: {raw}, but the gate was run with "
                f"--round {round_no} — one of the two is looking at the wrong round"
            )
        if block.kind != MB.ASSESSMENT:
            return
        round_type = block.header.get("ROUND-TYPE", "")
        if round_type not in V.ROUND_TYPES:
            findings.append(
                f"UNKNOWN_ROUND_TYPE: {round_type!r} is not one of "
                + " | ".join(V.ROUND_TYPES)
            )
        market = block.header.get("MARKET", "")
        if market not in V.MARKET_KEYS:
            findings.append(
                f"UNKNOWN_MARKET: {market!r} is not one of " + " | ".join(V.MARKET_KEYS)
            )
        if not block.header.get("FAMILY", "").strip():
            findings.append("NO_FAMILY: the assessment block has an empty FAMILY line")


    def _check_quote(record, label: str, transcript: str, refs: set, findings: list) -> None:
        what = record.fields.get("tag") or record.fields.get("dimension") or record.kind
        quote = record.fields.get("quote", "")
        if not MB.normalize_quote(quote):
            findings.append(
                f"NO_QUOTE: {label} line {record.line_no}: {record.kind} {what} has an "
                "empty quote= — no quote, no tag"
            )
        elif not MB.quote_is_in(quote, transcript):
            findings.append(
                f"QUOTE_NOT_IN_TRANSCRIPT: {label} line {record.line_no}: "
                f"{MB.normalize_quote(quote)[:70]!r} does not appear in the transcript"
            )
        ref = record.fields.get("ref", "")
        if refs and ref not in refs:
            findings.append(
                f"UNKNOWN_REF: {label} line {record.line_no}: {ref!r} is not a question "
                "heading in the transcript"
            )


    def _check_tag(record, block, findings: list) -> None:
        label = block.kind
        tag = record.fields["tag"]
        allowed = V.TRANSCRIPT_TAGS if label == MB.ASSESSMENT else V.PROVENANCE_TAGS
        if tag not in V.ALL_TAGS:
            findings.append(
                f"UNKNOWN_TAG: {label} line {record.line_no}: {tag!r} is not in the closed "
                "set — see references/interview-shapes.md"
            )
            return
        if tag not in allowed:
            findings.append(
                f"WRONG_PASS: {label} line {record.line_no}: {tag} may only be emitted by "
                + ("the provenance pass" if label == MB.ASSESSMENT else "the transcript pass")
                + " — that pass holds the inputs this tag is decided from"
            )
            return
        if label != MB.ASSESSMENT:
            return
        market = block.header.get("MARKET", "")
        family = block.header.get("FAMILY", "").strip().lower()
        markets = V.MARKET_CONDITIONAL.get(tag)
        if markets and market not in markets:
            findings.append(
                f"TAG_NOT_APPLICABLE: {label} line {record.line_no}: {tag} applies only in "
                f"market(s) {', '.join(markets)}, this round is MARKET: {market}"
            )
        families = V.FAMILY_CONDITIONAL.get(tag)
        if families and family not in families:
            findings.append(
                f"TAG_NOT_APPLICABLE: {label} line {record.line_no}: {tag} applies only to "
                f"family {', '.join(families)}, this round is FAMILY: {family}"
            )


    def _check_band(record, label: str, findings: list) -> None:
        dimension = record.fields["dimension"]
        value = record.fields["value"]
        if dimension not in V.DIMENSIONS:
            findings.append(
                f"UNKNOWN_DIMENSION: {label} line {record.line_no}: {dimension!r} is not "
                "one of " + " | ".join(V.DIMENSIONS)
            )
        if value == V.NON_BAND_FLAG:
            findings.append(
                f"NOT_A_BAND: {label} line {record.line_no}: {V.NON_BAND_FLAG!r} is a flag, "
                "not a band — emit it as tag=CONTRADICTED from the provenance pass"
            )
        elif value not in V.BANDS:
            findings.append(
                f"UNKNOWN_BAND: {label} line {record.line_no}: {value!r} is not one of "
                + " | ".join(V.BANDS)
                + " (the bands are unnumbered on purpose)"
            )


    def check_assessment(assessment_text: str, transcript_text: str, round_no: int):
        """Returns ({block kind: Block}, findings)."""
        findings: list = []
        blocks: dict = {}
        for kind in (MB.ASSESSMENT, MB.PROVENANCE):
            if kind not in assessment_text:
                findings.append(
                    f"MISSING_BLOCK: {kind} — that assessment pass did not run, or its "
                    "block was not copied into the file verbatim"
                )
                continue
            try:
                blocks[kind] = MB.parse_block(assessment_text, kind)
            except MB.BlockParseError as exc:
                findings.append(
                    f"PARSE_FAIL: {exc} — the round is void; re-dispatch that pass rather "
                    "than hand-editing its block"
                )
        refs = transcript_refs(transcript_text)
        for kind, block in blocks.items():
            _check_headers(block, round_no, findings)
            for record in block.records:
                if record.kind == "FINDING":
                    _check_tag(record, block, findings)
                    _check_quote(record, kind, transcript_text, refs, findings)
                elif record.kind == "BAND":
                    _check_band(record, kind, findings)
                    _check_quote(record, kind, transcript_text, refs, findings)
                elif record.kind == "COVERAGE":
                    if record.fields["status"] not in V.COVERAGE_STATUS:
                        findings.append(
                            f"UNKNOWN_STATUS: {kind} line {record.line_no}: COVERAGE "
                            f"status {record.fields['status']!r} is not one of "
                            + " | ".join(V.COVERAGE_STATUS)
                        )
                elif record.kind == "SHAPE":
                    if record.fields["status"] not in V.SHAPE_STATUS:
                        findings.append(
                            f"UNKNOWN_STATUS: {kind} line {record.line_no}: SHAPE status "
                            f"{record.fields['status']!r} is not one of "
                            + " | ".join(V.SHAPE_STATUS)
                        )
        return blocks, findings


    # ----------------------------------------------------------------- banned vocabulary

    def _default_scanner():
        """scripts/lint_no_prediction.py is Plan 2's. This is the ONLY adapter point —
        if its function is named differently there, change it here and nowhere else."""
        try:
            import lint_no_prediction
        except ImportError:
            return None
        return lint_no_prediction.scan_text


    # ----------------------------------------------------------------- receipts

    def _receipt(workspace: pathlib.Path, inputs: dict, verdict: str, findings: list) -> None:
        hashes = {}
        for label, path in inputs.items():
            if path.exists():
                hashes[label] = journal.sha256_file(path)
        try:
            journal.receipt(workspace, GATE, hashes, verdict, findings)
        except OSError as exc:
            print(f"WARNING: could not write the journal receipt: {exc}", file=sys.stderr)


    # ----------------------------------------------------------------- orchestration

    def _answer_bank_default(workspace: pathlib.Path) -> pathlib.Path:
        try:
            return workspace.parents[1] / "answer-bank.md"
        except IndexError:
            return workspace / "answer-bank.md"


    def _inputs(workspace: pathlib.Path, round_no: int, answer_bank: pathlib.Path) -> dict:
        return {
            f"mock/assessment-{round_no}.md": workspace / "mock" / f"assessment-{round_no}.md",
            f"mock/transcript-{round_no}.md": workspace / "mock" / f"transcript-{round_no}.md",
            "mock/question-log.yaml": workspace / "mock" / "question-log.yaml",
            "interview-brief.md": workspace / "interview-brief.md",
            "claims.yaml": workspace / "claims.yaml",
            "answer-bank.md": answer_bank,
        }


    def run(workspace, round_no: int, answer_bank=None, today=None, vocab_scanner=_AUTO):
        workspace = pathlib.Path(workspace)
        answer_bank = pathlib.Path(answer_bank) if answer_bank else _answer_bank_default(workspace)
        assessment_path = workspace / "mock" / f"assessment-{round_no}.md"
        transcript_path = workspace / "mock" / f"transcript-{round_no}.md"
        for path in (assessment_path, transcript_path):
            if not path.exists():
                raise InputMissing(f"{path} is missing — nothing to check")

        assessment_text = assessment_path.read_text(encoding="utf-8")
        transcript_text = transcript_path.read_text(encoding="utf-8")

        blocks, findings = check_assessment(assessment_text, transcript_text, round_no)
        return findings


    def main(argv=None) -> int:
        parser = argparse.ArgumentParser(description="Gate for one mock-interview round.")
        parser.add_argument("--workspace", required=True, type=pathlib.Path)
        parser.add_argument("--round", required=True, type=int)
        parser.add_argument("--answer-bank", type=pathlib.Path, default=None)
        parser.add_argument(
            "--today",
            default=None,
            help="ISO date used for staleness arithmetic; defaults to the system date",
        )
        args = parser.parse_args(argv)

        today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
        answer_bank = args.answer_bank or _answer_bank_default(args.workspace)
        inputs = _inputs(args.workspace, args.round, answer_bank)

        try:
            findings = run(
                args.workspace,
                args.round,
                answer_bank=answer_bank,
                today=today,
                vocab_scanner=_AUTO,
            )
        except (InputMissing, MissingDependency) as exc:
            print(str(exc), file=sys.stderr)
            _receipt(args.workspace, inputs, "could_not_run", [str(exc)])
            return 2

        verdict = "fail" if findings else "pass"
        _receipt(args.workspace, inputs, verdict, findings)
        for finding in findings:
            print(finding)
        return 1 if findings else 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

- [ ] **Step 5: Run test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_check_mock_core.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 6: Commit**

    ```bash
    git add scripts/check_mock.py scripts/tests/mock_fixtures.py scripts/tests/test_check_mock_core.py
    git commit -m "feat(interview): check_mock core — closed tag sets, quote-required, fail-closed parse"
    ```

---

### Task 4: `check_mock.py` — source integrity (question log, answer bank, banned vocabulary)

**Files:**
- Modify: `scripts/check_mock.py` (add three check functions and the vocabulary adapter; replace `run()`)
- Test: `scripts/tests/test_check_mock_sources.py`

**Interfaces:**
- Consumes: everything Task 3 produced, plus `scripts/lint_no_prediction.py` (Plan 2) through exactly one adapter — `_default_scanner()` returns a callable with the signature `scan_text(text: str, source: str) -> list[str]` returning finding strings that already carry their own UPPERCASE prefix. **If Plan 2 named it differently, change `_default_scanner()` and nothing else.**
- Produces, in `scripts/check_mock.py`:
  - `def check_question_log(path: pathlib.Path, today: datetime.date) -> list[str]`
  - `def check_answer_bank(path: pathlib.Path) -> list[str]`
  - `def check_vocabulary(paths: list[pathlib.Path], scanner) -> list[str]` — raises `MissingDependency` when `scanner is None`
  - `def _parse_stamp(raw: str) -> datetime.date | None`
  - a `run()` that calls all four check families

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_check_mock_sources.py`:

    ```python
    import datetime
    import pathlib
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import check_mock
    import mock_fixtures as F

    TODAY = datetime.date(2026, 8, 9)


    def run(workspace, **kw):
        kw.setdefault("vocab_scanner", F.no_vocab)
        kw.setdefault("today", TODAY)
        return check_mock.run(workspace, 2, **kw)


    SCRAPED = """  - id: Q4
    text: 讲一下 variational network 的展开步数怎么定的
    source: scraped
    source_site: nowcoder
    source_id: "ce23c4da4205"
    source_url: https://www.nowcoder.com/discuss/ce23c4da4205
    source_time: "2026-08-03T11:12:22"
    entity_country: NL
    country_named_in_post: true
    use: question
    asked: false
"""


    def with_scraped(**overrides):
        """The quiet question log plus one well-formed scraped row, then edits."""
        text = F.QUESTION_LOG.replace("rejected:", SCRAPED + "rejected:")
        for old, new in overrides.items():
            text = text.replace(old.replace("__", " "), new)
        return text


    # ---------------------------------------------------------------- the quiet case

    def test_a_well_formed_scraped_row_is_quiet(tmp_path):
        findings = run(F.build(tmp_path, question_log=with_scraped()))
        assert findings == []


    def test_a_generated_question_needs_no_source_id(tmp_path):
        """Cry-wolf guard: the scraped rules must not fire on generated questions."""
        findings = run(F.build(tmp_path))
        assert not [f for f in findings if f.startswith(("NO_SOURCE_ID:", "NO_SOURCE_TIME:"))]


    # ---------------------------------------------------------------- question-log.yaml

    def test_a_missing_question_log_is_a_finding_not_an_exit_2(tmp_path):
        ws = F.build(tmp_path)
        (ws / "mock" / "question-log.yaml").unlink()
        findings = run(ws)
        assert any(f.startswith("NO_QUESTION_LOG:") for f in findings)


    def test_a_scraped_question_without_a_source_id_fails(tmp_path):
        text = with_scraped().replace('    source_id: "ce23c4da4205"\n', "")
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("NO_SOURCE_ID:") and "Q4" in f for f in findings)


    def test_a_scraped_question_without_a_time_fails(tmp_path):
        text = with_scraped().replace('    source_time: "2026-08-03T11:12:22"\n', "")
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("NO_SOURCE_TIME:") and "Q4" in f for f in findings)


    def test_an_unparseable_time_fails(tmp_path):
        text = with_scraped().replace('"2026-08-03T11:12:22"', '"last spring"')
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("BAD_SOURCE_TIME:") for f in findings)


    def test_a_year_old_post_may_not_be_quoted_as_a_specific_question(tmp_path):
        text = with_scraped().replace('"2026-08-03T11:12:22"', '"2025-01-04T09:30:27"')
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("STALE_SPECIFIC:") and "Q4" in f for f in findings)


    def test_the_same_year_old_post_used_for_shape_is_quiet(tmp_path):
        text = with_scraped().replace('"2026-08-03T11:12:22"', '"2025-01-04T09:30:27"')
        text = text.replace("    use: question\n", "    use: shape\n")
        findings = run(F.build(tmp_path, question_log=text))
        assert not [f for f in findings if f.startswith("STALE_SPECIFIC:")]


    def test_the_country_rule_fires_on_a_same_name_different_entity_post(tmp_path):
        """The ASML case: company matches, content is real, the process is the wrong one."""
        text = with_scraped().replace("    entity_country: NL\n", "    entity_country: CN\n")
        text = text.replace("    country_named_in_post: true\n",
                            "    country_named_in_post: false\n")
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("WRONG_COUNTRY:") and "Q4" in f for f in findings)


    def test_a_post_that_names_the_posting_country_itself_is_quiet(tmp_path):
        text = with_scraped().replace("    entity_country: NL\n", "    entity_country: CN\n")
        findings = run(F.build(tmp_path, question_log=text))
        assert not [f for f in findings if f.startswith("WRONG_COUNTRY:")]


    def test_a_missing_entity_country_fails(tmp_path):
        text = with_scraped().replace("    entity_country: NL\n", "")
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("NO_ENTITY_COUNTRY:") for f in findings)


    def test_a_missing_posting_country_fails(tmp_path):
        text = F.QUESTION_LOG.replace("posting_country: NL\n", "")
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("NO_POSTING_COUNTRY:") for f in findings)


    def test_an_unknown_question_source_fails(tmp_path):
        text = F.QUESTION_LOG.replace("source: generated", "source: invented", 1)
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("UNKNOWN_QUESTION_SOURCE:") for f in findings)


    def test_an_unknown_rejection_reason_fails(tmp_path):
        text = F.QUESTION_LOG.replace("reason: wrong_country", "reason: seemed_off")
        findings = run(F.build(tmp_path, question_log=text))
        assert any(f.startswith("UNKNOWN_REJECT_REASON:") for f in findings)


    def test_the_advertising_rejection_reason_is_accepted(tmp_path):
        """Two posts in the source probe were commercial pitches dressed as 面经."""
        text = F.QUESTION_LOG.replace("reason: wrong_country", "reason: advertising")
        findings = run(F.build(tmp_path, question_log=text))
        assert not [f for f in findings if f.startswith("UNKNOWN_REJECT_REASON:")]


    def test_unreadable_yaml_is_reported_not_crashed(tmp_path):
        findings = run(F.build(tmp_path, question_log="questions: [unclosed\n"))
        assert any(f.startswith("QUESTION_LOG_UNPARSEABLE:") for f in findings)


    # ---------------------------------------------------------------- answer-bank.md

    def test_an_answer_bank_entry_without_a_source_line_fails(tmp_path):
        text = F.ANSWER_BANK.replace(
            '- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"\n',
            "",
        )
        findings = run(F.build(tmp_path, answer_bank=text))
        assert any(f.startswith("ANSWER_NO_SOURCE:") for f in findings)


    def test_an_empty_source_line_fails(tmp_path):
        text = F.ANSWER_BANK.replace(
            '- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"',
            "- source:",
        )
        findings = run(F.build(tmp_path, answer_bank=text))
        assert any(f.startswith("ANSWER_NO_SOURCE:") for f in findings)


    def test_a_session_answer_source_is_accepted(tmp_path):
        text = F.ANSWER_BANK.replace(
            '- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"',
            "- source: session-answer 2026-08-09 — mock/transcript-2.md#Q2",
        )
        findings = run(F.build(tmp_path, answer_bank=text))
        assert not [f for f in findings if f.startswith("ANSWER_NO_SOURCE:")]


    def test_a_missing_answer_bank_fails(tmp_path):
        ws = F.build(tmp_path)
        (ws.parents[1] / "answer-bank.md").unlink()
        findings = run(ws)
        assert any(f.startswith("NO_ANSWER_BANK:") for f in findings)


    def test_an_explicit_answer_bank_path_is_honoured(tmp_path):
        ws = F.build(tmp_path)
        elsewhere = tmp_path / "elsewhere.md"
        elsewhere.write_text(F.ANSWER_BANK, encoding="utf-8")
        (ws.parents[1] / "answer-bank.md").unlink()
        assert run(ws, answer_bank=elsewhere) == []


    # ---------------------------------------------------------------- banned vocabulary

    def test_banned_vocabulary_findings_are_passed_through(tmp_path):
        def scanner(text, source):
            return [f"BANNED_VOCAB: {source}: 'strong candidate'"] if "assessment" in source else []

        findings = check_mock.run(F.build(tmp_path), 2, today=TODAY, vocab_scanner=scanner)
        assert any(f.startswith("BANNED_VOCAB:") for f in findings)


    def test_the_vocabulary_scanner_sees_the_candidate_facing_files(tmp_path):
        seen = []

        def scanner(text, source):
            seen.append(pathlib.Path(source).name)
            return []

        ws = F.build(tmp_path)
        (ws / "mock" / "cheatsheet.md").write_text("# Cheatsheet\n", encoding="utf-8")
        check_mock.run(ws, 2, today=TODAY, vocab_scanner=scanner)
        assert "assessment-2.md" in seen
        assert "cheatsheet.md" in seen


    def test_an_absent_lint_module_is_exit_2_never_a_silent_skip(tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: None)
        ws = F.build(tmp_path)
        code = check_mock.main(["--workspace", str(ws), "--round", "2",
                                "--today", "2026-08-09"])
        assert code == 2
        assert "lint_no_prediction" in capsys.readouterr().err


    def test_run_resolves_the_scanner_itself_when_not_injected(tmp_path, monkeypatch):
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        assert check_mock.run(F.build(tmp_path), 2, today=TODAY) == []
    ```

- [ ] **Step 2: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_mock_sources.py -q`
    Expected: FAIL with `AttributeError: module 'check_mock' has no attribute 'check_question_log'` (and, before that, `test_a_missing_question_log_is_a_finding_not_an_exit_2` failing because `run()` returns `[]`)

- [ ] **Step 3: Add the source checks to `scripts/check_mock.py`**

    Add `import yaml` to the imports, and insert these functions after `check_assessment`:

    ```python
    # ----------------------------------------------------------------- question-log.yaml

    def _parse_stamp(raw: str):
        """`opencli nowcoder detail` returns an ISO-8601 timestamp; accept a bare date too."""
        text = str(raw).strip().replace("Z", "")
        for cut in (len(text), 19, 10):
            try:
                return datetime.datetime.fromisoformat(text[:cut]).date()
            except ValueError:
                continue
        return None


    def check_question_log(path: pathlib.Path, today: datetime.date) -> list:
        if not path.exists():
            return [
                f"NO_QUESTION_LOG: {path} is missing — modes/interview.md requires the log "
                "seeded before the round, and it is the only record of where a question came from"
            ]
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            return [f"QUESTION_LOG_UNPARSEABLE: {path}: {exc}"]
        if not isinstance(data, dict):
            return [f"QUESTION_LOG_UNPARSEABLE: {path}: top level is not a mapping"]

        findings: list = []
        posting_country = str(data.get("posting_country") or "").strip().upper()
        if not posting_country:
            findings.append(
                "NO_POSTING_COUNTRY: question-log.yaml must record posting_country: <ISO-2>. "
                "Without it the country rule cannot fire, and a same-name different-entity "
                "post looks exactly like a right one"
            )
        questions = data.get("questions") or []
        if not isinstance(questions, list) or not questions:
            findings.append(f"QUESTION_LOG_EMPTY: {path} has no questions: list")
            questions = []

        for entry in questions:
            if not isinstance(entry, dict):
                findings.append(f"QUESTION_LOG_UNPARSEABLE: {path}: a questions: row is not a mapping")
                continue
            qid = entry.get("id", "?")
            source = entry.get("source")
            if source not in V.QUESTION_SOURCES:
                findings.append(
                    f"UNKNOWN_QUESTION_SOURCE: {qid}: {source!r} is not one of "
                    + " | ".join(V.QUESTION_SOURCES)
                )
            if source != "scraped":
                continue
            if not str(entry.get("source_id") or "").strip():
                findings.append(
                    f"NO_SOURCE_ID: {qid}: a scraped question needs the id that "
                    "`opencli nowcoder detail <id>` was called with"
                )
            use = str(entry.get("use") or "").strip()
            if use not in ("shape", "question"):
                findings.append(f"UNKNOWN_USE: {qid}: use: must be 'shape' or 'question'")
            stamp = str(entry.get("source_time") or "").strip()
            if not stamp:
                findings.append(
                    f"NO_SOURCE_TIME: {qid}: copy the `time` field from `detail` — a search "
                    "row is elided and undated, and one result set held posts 3 days and "
                    "9.5 months old"
                )
            else:
                when = _parse_stamp(stamp)
                if when is None:
                    findings.append(f"BAD_SOURCE_TIME: {qid}: {stamp!r} is not an ISO-8601 timestamp")
                elif (today - when).days > V.SCRAPED_SPECIFIC_MAX_AGE_DAYS and use == "question":
                    findings.append(
                        f"STALE_SPECIFIC: {qid}: {stamp} is {(today - when).days} days old — "
                        "it may set shape only, never be quoted as a specific question"
                    )
            entity = str(entry.get("entity_country") or "").strip().upper()
            if not entity:
                findings.append(
                    f"NO_ENTITY_COUNTRY: {qid}: record which country's entity the post "
                    "describes; the company name matching is not evidence that the process does"
                )
            elif posting_country and entity != posting_country and not entry.get("country_named_in_post"):
                findings.append(
                    f"WRONG_COUNTRY: {qid}: the source describes the {entity} entity and the "
                    f"posting is {posting_country} — move it to rejected: with "
                    "reason: wrong_country unless the post itself names the posting's country"
                )

        for entry in data.get("rejected") or []:
            if not isinstance(entry, dict):
                continue
            reason = str(entry.get("reason") or "")
            if reason not in V.REJECT_REASONS:
                findings.append(
                    f"UNKNOWN_REJECT_REASON: {entry.get('id', '?')}: {reason!r} is not one of "
                    + " | ".join(V.REJECT_REASONS)
                )
        return findings


    # ----------------------------------------------------------------- answer-bank.md

    _AB_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)
    _AB_SOURCE = re.compile(r"^\s*-\s*source:\s*\S+", re.M)


    def check_answer_bank(path: pathlib.Path) -> list:
        if not path.exists():
            return [
                f"NO_ANSWER_BANK: {path} is missing — the answer bank is the only artifact "
                "that compounds across applications, and modes/interview.md requires one "
                "entry per story banked this round (--answer-bank to point elsewhere)"
            ]
        text = path.read_text(encoding="utf-8")
        marks = list(_AB_HEADING.finditer(text))
        if not marks:
            return [f"NO_ANSWER_BANK_ENTRIES: {path} has no '## ' entries"]
        findings = []
        for index, mark in enumerate(marks):
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            body = text[mark.end():end]
            if not _AB_SOURCE.search(body):
                findings.append(
                    f"ANSWER_NO_SOURCE: answer-bank.md entry {mark.group(1)!r} has no "
                    "'- source:' line — an entry whose fact cannot be traced is worse than "
                    "no entry, because the candidate will say it out loud believing it was vetted"
                )
        return findings


    # ----------------------------------------------------------------- banned vocabulary

    def check_vocabulary(paths: list, scanner) -> list:
        if scanner is None:
            raise MissingDependency(
                "scripts/lint_no_prediction.py (Plan 2) is not importable — refusing to "
                "report a vocabulary check that did not run"
            )
        findings = []
        for path in paths:
            if path.exists():
                findings.extend(scanner(path.read_text(encoding="utf-8"), str(path)))
        return findings
    ```

- [ ] **Step 4: Replace `run()` with the version that calls all three**

    Replace the whole `run()` function body written in Task 3 with:

    ```python
    def run(workspace, round_no: int, answer_bank=None, today=None, vocab_scanner=_AUTO):
        workspace = pathlib.Path(workspace)
        answer_bank = pathlib.Path(answer_bank) if answer_bank else _answer_bank_default(workspace)
        today = today or datetime.date.today()
        scanner = _default_scanner() if vocab_scanner is _AUTO else vocab_scanner

        assessment_path = workspace / "mock" / f"assessment-{round_no}.md"
        transcript_path = workspace / "mock" / f"transcript-{round_no}.md"
        for path in (assessment_path, transcript_path):
            if not path.exists():
                raise InputMissing(f"{path} is missing — nothing to check")

        assessment_text = assessment_path.read_text(encoding="utf-8")
        transcript_text = transcript_path.read_text(encoding="utf-8")

        blocks, findings = check_assessment(assessment_text, transcript_text, round_no)
        findings += check_question_log(workspace / "mock" / "question-log.yaml", today)
        findings += check_answer_bank(answer_bank)
        findings += check_vocabulary(
            [
                assessment_path,
                workspace / "mock" / "open-loops.md",
                workspace / "mock" / "cheatsheet.md",
            ],
            scanner,
        )
        return findings
    ```

- [ ] **Step 5: Run both check_mock test files to verify they pass**

    Run: `python3 -m pytest scripts/tests/test_check_mock_core.py scripts/tests/test_check_mock_sources.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 6: Commit**

    ```bash
    git add scripts/check_mock.py scripts/tests/test_check_mock_sources.py
    git commit -m "feat(interview): check_mock source integrity — question log, answer bank, vocabulary"
    ```

---

### Task 5: `check_mock.py` — the write-back mechanism (walk-back list, claims promotion)

This is the task that makes `references/interview-prep.md:39` — "if preparing the brief
surfaces a claim the candidate cannot truthfully defend, treat it as a tailoring error and
walk the claim back on the CV" — into something that actually fires. The three CV judges
read a page, and the page does not stammer. The transcript does.

**Files:**
- Modify: `scripts/check_mock.py` (add the walk-back and claims checks; extend `run()`)
- Test: `scripts/tests/test_check_mock_walkback.py`

**Interfaces:**
- Consumes: `check_assessment` returning `(blocks, findings)` from Task 3; `mock_blocks.quote_is_in`, `mock_blocks.normalize_quote`; `mock_vocab.WALKBACK_TAGS`.
- Produces, in `scripts/check_mock.py`:
  - `def walkback_entries(brief_text: str) -> list[dict]` — each dict has `id`, `claim`, `quote`, `softened`, `defect`, `transcript`
  - `def check_walkback(blocks: dict, brief_path: pathlib.Path, claims_path: pathlib.Path, transcript_name: str) -> list[str]`
  - a `run()` that calls it

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_check_mock_walkback.py`:

    ```python
    import datetime
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import check_mock
    import mock_fixtures as F

    TODAY = datetime.date(2026, 8, 9)

    COLLAPSE = (
        "FINDING: tag=PROBE-COLLAPSE | ref=Q2 | quote=It went really well after that."
    )
    OVERCLAIM = (
        "FINDING: tag=OVER-CLAIM | ref=Q1 | quote=I owned the offline recon pipeline"
    )
    UNSOURCED = (
        "FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=then wrote DICOMs back to the PACS"
    )

    WALKBACK = """
## Walk-back list

### WB-1 — "Rewrote the offline reconstruction loop for GPU batching."
- transcript: mock/transcript-2.md — Q2
- quote: It went really well after that.
- defect: PROBE-COLLAPSE
- softened: "Rewrote the offline reconstruction loop for GPU batching (timings not retained)."
- status: proposed
"""

    PROMOTED = """- term: PACS export
      where: tailoring-plan.md:promoted-from-mock
      source_kind: session-answer
      source_ref: mock/transcript-2.md#Q1
      session_date: "2026-08-09"
      retracted: null
"""


    def run(workspace, **kw):
        kw.setdefault("vocab_scanner", F.no_vocab)
        kw.setdefault("today", TODAY)
        return check_mock.run(workspace, 2, **kw)


    def assessment_with(*findings):
        return F.ASSESSMENT.replace(
            "MOCK-PROVENANCE-V1\nROUND: 2\nFINDINGS: none",
            "MOCK-PROVENANCE-V1\nROUND: 2\n" + "\n".join(findings),
        )


    # ---------------------------------------------------------------- the quiet case

    def test_no_walkback_is_demanded_when_no_walkback_tag_fired(tmp_path):
        """Cry-wolf guard: an ordinary round with shape findings needs no walk-back."""
        findings = run(F.build(tmp_path))
        assert not [f for f in findings if f.startswith("WALKBACK")]


    def test_a_walkback_section_present_without_any_tag_is_not_penalised(tmp_path):
        findings = run(F.build(tmp_path, brief=F.BRIEF + WALKBACK))
        assert not [f for f in findings if f.startswith("WALKBACK")]


    # ---------------------------------------------------------------- the demand

    def test_a_probe_collapse_demands_the_walkback_section(tmp_path):
        text = F.ASSESSMENT.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
            COLLAPSE,
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("WALKBACK_MISSING:") for f in findings)


    def test_an_over_claim_demands_the_walkback_section(tmp_path):
        findings = run(F.build(tmp_path, assessment=assessment_with(OVERCLAIM)))
        assert any(f.startswith("WALKBACK_MISSING:") for f in findings)


    def test_a_contradiction_demands_the_walkback_section(tmp_path):
        text = assessment_with(
            "FINDING: tag=CONTRADICTED | ref=Q2 | quote=It went really well after that."
        )
        findings = run(F.build(tmp_path, assessment=text))
        assert any(f.startswith("WALKBACK_MISSING:") for f in findings)


    def test_an_unsourced_fact_alone_does_not_demand_a_walkback(tmp_path):
        """Its honest route is usually claims.yaml — 'true, just not on my CV'."""
        findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED)))
        assert not [f for f in findings if f.startswith("WALKBACK_MISSING:")]


    # ---------------------------------------------------------------- per-finding matching

    def test_a_walkback_section_that_misses_this_finding_fails(tmp_path):
        findings = run(
            F.build(tmp_path, assessment=assessment_with(OVERCLAIM), brief=F.BRIEF + WALKBACK)
        )
        assert any(f.startswith("WALKBACK_NO_ENTRY:") and "OVER-CLAIM" in f for f in findings)


    def test_the_matching_entry_satisfies_it(tmp_path):
        text = F.ASSESSMENT.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
            COLLAPSE,
        )
        findings = run(F.build(tmp_path, assessment=text, brief=F.BRIEF + WALKBACK))
        assert not [f for f in findings if f.startswith("WALKBACK")]


    def test_an_entry_without_softened_wording_fails(tmp_path):
        brief = F.BRIEF + WALKBACK.replace('- softened: "Rewrote the offline '
                                           'reconstruction loop for GPU batching '
                                           '(timings not retained)."\n', "")
        text = F.ASSESSMENT.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
            COLLAPSE,
        )
        findings = run(F.build(tmp_path, assessment=text, brief=brief))
        assert any(f.startswith("WALKBACK_INCOMPLETE:") and "softened" in f for f in findings)


    def test_an_entry_with_a_tag_outside_the_walkback_set_fails(tmp_path):
        brief = F.BRIEF + WALKBACK.replace("- defect: PROBE-COLLAPSE", "- defect: NO-OUTCOME")
        text = F.ASSESSMENT.replace(
            "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
            COLLAPSE,
        )
        findings = run(F.build(tmp_path, assessment=text, brief=brief))
        assert any(f.startswith("WALKBACK_BAD_DEFECT:") for f in findings)


    # ---------------------------------------------------------------- claims promotion

    def test_an_unsourced_fact_must_be_resolved_somewhere(tmp_path):
        findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED)))
        assert any(f.startswith("UNRESOLVED_FACT:") for f in findings)


    def test_promotion_to_claims_resolves_it(tmp_path):
        findings = run(
            F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=F.CLAIMS + PROMOTED)
        )
        assert not [f for f in findings if f.startswith("UNRESOLVED_FACT:")]


    def test_a_promotion_row_pointing_at_another_round_does_not_resolve_it(tmp_path):
        claims = F.CLAIMS + PROMOTED.replace("transcript-2.md", "transcript-1.md")
        findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=claims))
        assert any(f.startswith("UNRESOLVED_FACT:") for f in findings)


    def test_a_promotion_row_missing_a_contract_field_fails(tmp_path):
        claims = F.CLAIMS + PROMOTED.replace('      session_date: "2026-08-09"\n', "")
        findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=claims))
        assert any(f.startswith("CLAIM_ROW_INCOMPLETE:") and "session_date" in f
                   for f in findings)


    def test_walking_the_fact_back_also_resolves_it(tmp_path):
        """Drift under pressure is not promoted to the CV — it is walked back."""
        walkback = WALKBACK.replace(
            "- quote: It went really well after that.",
            "- quote: then wrote DICOMs back to the PACS",
        ).replace("- defect: PROBE-COLLAPSE", "- defect: CONTRADICTED")
        findings = run(
            F.build(tmp_path, assessment=assessment_with(UNSOURCED), brief=F.BRIEF + walkback)
        )
        assert not [f for f in findings if f.startswith("UNRESOLVED_FACT:")]


    def test_the_ordinary_claims_file_is_not_flagged(tmp_path):
        """Cry-wolf guard: profile-line rows are not promotion rows and are not checked."""
        findings = run(F.build(tmp_path))
        assert not [f for f in findings if f.startswith("CLAIM_ROW_INCOMPLETE:")]
    ```

- [ ] **Step 2: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_mock_walkback.py -q`
    Expected: FAIL — `test_a_probe_collapse_demands_the_walkback_section` fails on `assert any(...)` over an empty list, because nothing checks the walk-back yet

- [ ] **Step 3: Add the walk-back and claims checks to `scripts/check_mock.py`**

    Insert after `check_vocabulary`:

    ```python
    # ----------------------------------------------------------------- write-backs

    _WB_SECTION = "## Walk-back list"
    _WB_HEADING = re.compile(r"^###\s+(WB-\d+)\s*(.*)$", re.M)
    _CLAIM_FIELDS = ("term", "where", "source_kind", "source_ref", "session_date", "retracted")


    def walkback_entries(brief_text: str) -> list:
        if _WB_SECTION not in brief_text:
            return []
        body = brief_text.split(_WB_SECTION, 1)[1]
        following = re.search(r"^##\s+", body, re.M)
        if following:
            body = body[:following.start()]
        marks = list(_WB_HEADING.finditer(body))
        entries = []
        for index, mark in enumerate(marks):
            end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
            chunk = body[mark.end():end]
            entry = {"id": mark.group(1), "claim": mark.group(2).strip(" —-")}
            for field in ("quote", "softened", "defect", "transcript"):
                found = re.search(rf"^\s*-\s*{field}:\s*(.+)$", chunk, re.M)
                entry[field] = found.group(1).strip() if found else ""
            entries.append(entry)
        return entries


    def check_walkback(blocks: dict, brief_path: pathlib.Path, claims_path: pathlib.Path,
                       transcript_name: str) -> list:
        records = [
            record
            for block in blocks.values()
            for record in block.records
            if record.kind == "FINDING"
        ]
        fired = [r for r in records if r.fields["tag"] in V.WALKBACK_TAGS]
        unsourced = [r for r in records if r.fields["tag"] == "UNSOURCED-FACT"]
        if not fired and not unsourced:
            return []

        brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
        entries = walkback_entries(brief_text)

        findings = []
        if fired and _WB_SECTION not in brief_text:
            findings.append(
                "WALKBACK_MISSING: "
                + ", ".join(sorted({r.fields["tag"] for r in fired}))
                + f" fired, but {brief_path.name} has no '{_WB_SECTION}' section — a claim "
                "the candidate cannot defend under one follow-up is a tailoring error, not "
                "a rehearsal topic"
            )
        else:
            for record in fired:
                quote = record.fields["quote"]
                if not any(MB.quote_is_in(quote, e["quote"]) for e in entries):
                    findings.append(
                        f"WALKBACK_NO_ENTRY: {record.fields['tag']} at "
                        f"{record.fields['ref']} has no '### WB-' entry quoting "
                        f"{MB.normalize_quote(quote)[:60]!r}"
                    )

        for entry in entries:
            for field in ("quote", "softened", "defect"):
                if not entry[field]:
                    findings.append(
                        f"WALKBACK_INCOMPLETE: {entry['id']} is missing its '- {field}:' line"
                    )
            # Any of the four defect tags may land here: the three that *demand* the
            # section, plus an UNSOURCED-FACT the candidate could not stand behind, which
            # is walked back rather than promoted to claims.yaml.
            if entry["defect"] and entry["defect"] not in V.DEFECT_TAGS:
                findings.append(
                    f"WALKBACK_BAD_DEFECT: {entry['id']}: defect: {entry['defect']!r} must "
                    "be one of " + " | ".join(V.DEFECT_TAGS)
                )

        promoted = []
        if claims_path.exists():
            try:
                rows = yaml.safe_load(claims_path.read_text(encoding="utf-8")) or []
            except yaml.YAMLError as exc:
                findings.append(f"CLAIMS_UNPARSEABLE: {claims_path}: {exc}")
                rows = []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict) or row.get("source_kind") != "session-answer":
                    continue
                if transcript_name not in str(row.get("source_ref", "")):
                    continue
                promoted.append(row)
                missing = [f for f in _CLAIM_FIELDS if f not in row]
                if missing:
                    findings.append(
                        f"CLAIM_ROW_INCOMPLETE: the promotion row for "
                        f"{row.get('term', '?')!r} is missing {', '.join(missing)}"
                    )

        for record in unsourced:
            quote = MB.normalize_quote(record.fields["quote"])
            walked = any(MB.quote_is_in(record.fields["quote"], e["quote"]) for e in entries)
            claimed = any(
                str(row.get("term", "")).strip()
                and MB.collapse_ws(str(row["term"])).lower() in quote.lower()
                for row in promoted
            )
            if not (walked or claimed):
                findings.append(
                    f"UNRESOLVED_FACT: UNSOURCED-FACT at {record.fields['ref']} "
                    f"({quote[:50]!r}) is neither promoted to claims.yaml "
                    f"(source_kind: session-answer, source_ref naming {transcript_name}) nor "
                    "walked back — ask the candidate where it came from before it enters the "
                    "answer bank"
                )
        return findings
    ```

- [ ] **Step 4: Extend `run()` to call it**

    In `run()`, immediately after the `check_vocabulary(...)` call and before `return findings`, insert:

    ```python
        findings += check_walkback(
            blocks,
            workspace / "interview-brief.md",
            workspace / "claims.yaml",
            f"transcript-{round_no}.md",
        )
    ```

- [ ] **Step 5: Run the whole check_mock suite to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_check_mock_core.py scripts/tests/test_check_mock_sources.py scripts/tests/test_check_mock_walkback.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 6: Commit**

    ```bash
    git add scripts/check_mock.py scripts/tests/test_check_mock_walkback.py
    git commit -m "feat(interview): check_mock write-backs — walk-back list and claims promotion"
    ```

---

### Task 6: `modes/interview.md` — the layer-1.5 mode file

This file is the only definition of `question-log.yaml`'s schema, of `answer-bank.md`'s
`source:` line, of the walk-back entry format, and of the promotion row — all four of which
`check_mock.py` requires and nothing else describes. Its embedded examples are extracted by
the test and run through the real validators, so the schema documentation cannot drift away
from the gate that enforces it.

**Files:**
- Create: `modes/interview.md`
- Test: `scripts/tests/test_mode_interview_doc.py`

**Interfaces:**
- Consumes: `check_mock.check_question_log(path, today)` and `check_mock.check_answer_bank(path)` (Task 4); the block grammar from Task 2; `references/interview-shapes.md` (Task 1).
- Produces: no code. The contract it fixes for the gate: `question-log.yaml` keys `round`, `posting_country`, `questions[].{id,text,source,asked,source_site,source_id,source_url,source_time,entity_country,country_named_in_post,use}`, `rejected[].{id,text,source_id,reason}`; `answer-bank.md` entries as `## <title>` with a `- source:` line; walk-back entries as `### WB-<n>` with `- quote:`, `- softened:`, `- defect:`, `- transcript:`; the promotion row's six `claims.yaml` fields.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_mode_interview_doc.py`:

    ```python
    import datetime
    import pathlib
    import re
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import check_mock
    import mock_blocks as MB

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    MODE = ROOT / "modes" / "interview.md"
    TODAY = datetime.date(2026, 8, 9)


    def _example(anchor: str) -> str:
        text = MODE.read_text(encoding="utf-8")
        marker = f"<!-- example: {anchor} -->"
        assert marker in text, f"modes/interview.md has no {marker}"
        fence = re.search(r"```[a-z]*\n(.*?)```", text[text.index(marker):], re.S)
        assert fence, f"{marker} is not followed by a fenced block"
        return fence.group(1)


    # --------------------------------------------- the schemas are executable, not prose

    def test_the_question_log_example_passes_the_real_validator(tmp_path):
        path = tmp_path / "question-log.yaml"
        path.write_text(_example("question-log.yaml"), encoding="utf-8")
        assert check_mock.check_question_log(path, TODAY) == []


    def test_the_answer_bank_example_passes_the_real_validator(tmp_path):
        path = tmp_path / "answer-bank.md"
        path.write_text(_example("answer-bank.md"), encoding="utf-8")
        assert check_mock.check_answer_bank(path) == []


    def test_the_walkback_example_parses_into_a_complete_entry():
        entries = check_mock.walkback_entries(_example("walk-back list"))
        assert entries, "the walk-back example yields no entries"
        for entry in entries:
            assert entry["quote"] and entry["softened"] and entry["defect"]


    def test_the_transcript_example_carries_parseable_question_headings():
        assert check_mock.transcript_refs(_example("transcript-<n>.md"))


    def test_the_assessment_example_parses_as_both_blocks():
        text = _example("assessment-<n>.md")
        MB.parse_block(text, MB.ASSESSMENT)
        MB.parse_block(text, MB.PROVENANCE)


    # --------------------------------------------- rules that must be stated in words

    @pytest.mark.parametrize(
        "phrase",
        [
            "FLUSH THE TRANSCRIPT AFTER EVERY ANSWER",
            "one round per dispatch",
            "COUNTRY RULE",
            "never quoted as a specific technical question",
            "Never paste a scraped post's ANSWER",
            "Do not log in to work around it",
            "open-loops summary",
            "references/interview-shapes.md",
            "agents/mock-assessor-transcript.md",
            "agents/mock-assessor-provenance.md",
            "scripts/check_mock.py",
        ],
    )
    def test_the_mode_file_states(phrase):
        assert phrase in MODE.read_text(encoding="utf-8")


    def test_the_pack_split_names_what_pass_1_is_not_given():
        text = MODE.read_text(encoding="utf-8")
        table = text.split("## 4.")[1].split("## 5.")[0]
        assert "interview-brief.md" in table and "claims.yaml" in table
        assert "NOT" in table or "not given" in table


    def test_the_published_rubric_exception_is_bounded():
        text = MODE.read_text(encoding="utf-8")
        section = text.split("## Published employer rubric")[1]
        assert "attribut" in section.lower()
        assert "never as a prediction" in section.lower()


    def test_the_twelve_month_rule_is_stated_with_its_reason():
        text = MODE.read_text(encoding="utf-8")
        assert "12 months" in text
        assert "shape" in text.lower()


    def test_the_country_rule_names_the_measured_case():
        text = MODE.read_text(encoding="utf-8")
        assert "ASML" in text and "宣讲会" in text
    ```

- [ ] **Step 2: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_mode_interview_doc.py -q`
    Expected: FAIL with `FileNotFoundError: ... modes/interview.md`

- [ ] **Step 3: Write `modes/interview.md`**

    ````markdown
    # Mode: interview

    **Entry:** the workspace holds an application package, **or** the user has a posting plus
    a CV and says they have an interview.

    **Reads:** `posting.yaml`, `cv.md`, `tailored-profile.yaml`, `fit-assessment.*`,
    `interview-brief.md`, `claims.yaml`.
    **Writes (exclusively):** `mock/`. Plus two append-only write-backs: a `## Walk-back list`
    section on `interview-brief.md`, and `source_kind: session-answer` rows on `claims.yaml`.
    Nothing else in the workspace is modified, and `profile.yaml` is never touched.

    ## 0. Before the first question

    Read `references/interview-shapes.md` in full. It holds the market × family loop shapes,
    the four band descriptors, and both closed tag sets — you cannot write
    `mock/assessment-<n>.md` without them, and you cannot pick a realistic round order without
    the shapes.

    Then confirm three things with the user, in one message:

    1. **Market** — ask; never infer it from a place name. `cn | nl | de | uk | us | other`.
    2. **Role family** — from `references/role-families.md`. If it is not one of the nine, ask
       the one question that resolves the shape: *"In your field, what does the employer make
       you do live — talk, demonstrate, be scored against written criteria, or be role-played
       at?"*
    3. **Round type for this session** — `behavioural | technical | design | hr`. One per
       session; see §3.

    ## 1. Fix the shape

    From `references/interview-shapes.md`, state the loop the candidate is walking into: the
    rounds, in the local vocabulary, with who is in the room. Say plainly which rounds this
    mode **cannot** simulate (手撕代码 under a watching interviewer, an in-person MMI circuit,
    a whiteboard chalk talk) rather than running a thin imitation of them.

    Give the interviewer a **named persona** drawn from that shape — a 交叉面 interviewer from
    another department who has not read the CV closely; a Bar Raiser from outside the team; a
    panel member scoring one named Success Profiles behaviour at the grade in the advert; a
    Dutch hiring manager who will ask about anything questionable on the CV without preamble.
    The persona costs nothing and is most of what makes a text interview feel like anything.

    ## 2. Seed `mock/question-log.yaml`

    Questions come from three places, and each row records which: `generated`, `scraped`, or
    `judge-supplementary` (carried over from the CV judges'
    `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`).

    **Generated questions are the high-value ones.** *"You wrote that you cut deploy time 40% —
    how did you measure that?"* exists in no archive, and it is the question that catches an
    over-tailoring the three CV judges passed. Build the generated set to cover every must-have
    in `posting.yaml`.

    **Scraped material sets SHAPE; generated material sets CONTENT.** They are not competing
    sources of the same thing. Reach for a scraped item when you need a fact about the
    employer's process you cannot derive from the posting: a named ritual (交叉面, HRBP面, Bar
    Raiser, 宣讲会, 群面, a specific take-home), the round count and order, who is in the room,
    the pacing.

    ### Scraped material — the rules

    ```
    Every scraped item is (a) opened with `detail` for untruncated text — a `search` row is
      elided and must never be quoted, (b) stamped with its `time` in question-log.yaml, and
      (c) shown to the candidate with that date.
    Anything older than ~12 months may be used for SHAPE (round count, order, ritual names)
      but is never quoted as a specific technical question.
    COUNTRY RULE. Never use a scraped item whose company entity sits in a different country
      from the posting, unless the post itself names that country. Log it under `rejected:`
      with `reason: wrong_country` so the filter is visible.
    Never paste a scraped post's ANSWER to the candidate — questions only. A 面经 that
      includes the poster's own answer is a script, and handing over a script is the exact
      thing the anti-coaching rules forbid.
    Filter advertising. Posts that open with a course pitch, a 辅导 offer, or a contact email
      are commercial material wearing a 面经 costume. Log them `reason: advertising`.
    If the adapter returns 403 or "need login", report the source as unavailable and generate
      instead. Do not log in to work around it.
    1point3acres is unavailable: every read command 403s anonymously, including the
      `browser: false` ones, and `search` is documented as requiring login.
    `nowcoder papers --company/--job` filters are inert (verified: three different filter
      values returned byte-identical rows). Use `papers` as a company/role index only.
    ```

    **Why the COUNTRY RULE is first among equals.** `opencli nowcoder search "ASML 面试"`
    returns three real posts, all describing that company's **China entity** — 宣讲会, 笔试,
    then 二面 and an HR call. That is not the Veldhoven loop. The company name matches, the
    content is genuine, the process is the wrong one, and **nothing about it looks wrong.** The
    same held for Philips. This is the most dangerous failure available in this source.

    ### `mock/question-log.yaml`

    `check_mock.py` reads this file. Keys marked **scraped-only** are required on any row with
    `source: scraped` and ignored elsewhere.

    | Key | Meaning |
    |---|---|
    | `round` | integer, the round this log belongs to |
    | `posting_country` | ISO-2 country of the **posting** — without it the country rule cannot fire |
    | `questions[].id` | `Q1`, `Q2`, … — must match the transcript's `## Q<n>` headings |
    | `questions[].text` | the question as it will be asked |
    | `questions[].source` | `generated` \| `scraped` \| `judge-supplementary` |
    | `questions[].asked` | whether it was actually put to the candidate |
    | `questions[].source_site` | **scraped-only** — e.g. `nowcoder` |
    | `questions[].source_id` | **scraped-only** — the id `detail` was called with |
    | `questions[].source_url` | **scraped-only** |
    | `questions[].source_time` | **scraped-only** — the ISO timestamp from `detail`, verbatim |
    | `questions[].entity_country` | **scraped-only** — ISO-2 of the entity the post describes |
    | `questions[].country_named_in_post` | **scraped-only** — true only if the post itself names the posting's country |
    | `questions[].use` | **scraped-only** — `question` (may be quoted) or `shape` (structure only) |
    | `rejected[].reason` | `wrong_country` \| `stale_specific` \| `advertising` \| `needs_login` \| `answer_included` |

    <!-- example: question-log.yaml -->
    ```yaml
    round: 2
    posting_country: NL
    questions:
      - id: Q1
        text: Walk me through the reconstruction pipeline you owned.
        source: generated
        asked: true
      - id: Q2
        text: You wrote that you rewrote the recon loop for GPU batching — how did you measure the change?
        source: judge-supplementary
        asked: true
      - id: Q3
        text: 讲一下 variational network 的展开步数怎么定的
        source: scraped
        source_site: nowcoder
        source_id: "ce23c4da4205"
        source_url: https://www.nowcoder.com/discuss/ce23c4da4205
        source_time: "2026-08-03T11:12:22"
        entity_country: NL
        country_named_in_post: true
        use: question
        asked: true
    rejected:
      - id: R1
        text: "ASML 宣讲会 → 笔试 → 二面 → HR 电话面 timeline"
        source: scraped
        source_site: nowcoder
        source_id: "057523b2ca9d"
        source_time: "2026-08-06T11:06:49"
        entity_country: CN
        reason: wrong_country
      - id: R2
        text: "27届秋招…可以了解下算法项目辅导"
        source: scraped
        source_site: nowcoder
        source_id: "a1b2c3d4e5f6"
        source_time: "2026-07-30T08:00:00"
        entity_country: CN
        reason: advertising
    ```

    ## 3. Run ONE round, inline

    **The interviewer is you, in this conversation.** A spawned subagent has no channel to ask
    a question and wait for the human — `agents/hiring-manager.md:21` pastes its inputs at
    dispatch time and `:97` requires it to end with a fixed block. That is a mechanical fact,
    not a preference, and it decides the architecture before any trade-off analysis.

    **One round per dispatch.** Finish the round, assess it, write the artifacts, and stop.
    Round n+1 starts fresh.

    **FLUSH THE TRANSCRIPT AFTER EVERY ANSWER.** Append the question and the answer to
    `mock/transcript-<n>.md` the moment the candidate finishes speaking — not at the end of the
    round. This buys pause/resume for free, keeps the assessors reading a *file* rather than
    this conversation, and means a crashed session loses one answer instead of a round. The
    transcript is a raw capture: **never edit it.** Every downstream claim's source chain
    terminates here.

    Ask from the log, then go where the answer leads. The log is seed material — its coverage
    value is realised by **auditing it after the round**, not by reading from it during. A
    question bank cannot follow up on an answer it did not anticipate, and "held under probe"
    is the only band above `asserted` that means anything.

    While you interview, the anti-coaching rules in SKILL.md bind on every turn: never write an
    answer for the candidate, never ask a leading question, never build a question on a premise
    the CV does not support, and never rehearse a gap into a non-gap.

    <!-- example: transcript-<n>.md -->
    ```markdown
    # Mock transcript — round 2
    Round type: technical
    Market: nl
    Family: ml-engineering
    Persona: Sanne de Vries, MR reconstruction team lead — direct, asks for numbers

    ## Q1 — Walk me through the reconstruction pipeline you owned.
    **Interviewer:** Walk me through the reconstruction pipeline you owned.
    **Candidate:** At the university hospital I owned the offline recon pipeline for a 3T scanner study.

    ## Q2 — What did you change about it, and what happened as a result?
    **Interviewer:** What did you change about it, and what happened as a result?
    **Candidate:** I replaced the per-slice loop with a batched GPU implementation.
    ```

    ## 4. Assess — two passes, deliberately different inputs

    Dispatch **both** assessors in one message (two `Agent` calls, in parallel). Each gets
    exactly the files in its row and nothing else:

    | Pass | Agent file | Given | **Deliberately NOT given** |
    |---|---|---|---|
    | 1 — transcript | `agents/mock-assessor-transcript.md` | `mock/transcript-<n>.md`, `posting.yaml`, `cv.md` | `interview-brief.md`, `claims.yaml` — so it cannot credit the candidate for a source fact they never said out loud |
    | 2 — provenance | `agents/mock-assessor-provenance.md` | `mock/transcript-<n>.md`, `claims.yaml`, `interview-brief.md` | the rubric — so it cannot drift into grading, which is what makes a provenance-holding assessor lenient |

    Two passes fed different inputs is what turns the honesty tripwire from an intention into a
    mechanism. Do not "helpfully" hand pass 1 the brief.

    Then assemble `mock/assessment-<n>.md`: **both output blocks copied in verbatim**, plus a
    short human-readable summary above them. Never hand-edit an assessor's block. If
    `scripts/check_mock.py` reports `PARSE_FAIL` or `MISSING_BLOCK`, that pass did not produce a
    readable assessment — re-dispatch it.

    <!-- example: assessment-<n>.md -->
    ```markdown
    # Mock assessment — round 2

    Two passes ran on this transcript with deliberately different inputs.

    MOCK-ASSESSMENT-V1
    ROUND: 2
    ROUND-TYPE: technical
    MARKET: nl
    FAMILY: ml-engineering
    FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
    BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
    COVERAGE: status=evidenced | must_have=MRI reconstruction pipelines in a clinical setting
    SHAPE: status=rehearsed | round_name=technisch gesprek met de vakinhoudelijke manager
    END-MOCK-ASSESSMENT-V1

    MOCK-PROVENANCE-V1
    ROUND: 2
    FINDINGS: none
    END-MOCK-PROVENANCE-V1
    ```

    ## 5. Write the session artifacts

    **`~/.claude/job-profiles/<name>/answer-bank.md`** — the profile-level file, not a
    per-application one. It is the only artifact that compounds across applications. One entry
    per real story, in the candidate's **own words as actually spoken**, with a `- source:` line
    that traces the load-bearing fact to `profile.yaml`, to `interview-brief.md`'s provenance
    map, or to a session answer with its date. `check_mock.py` fails an entry with no
    `- source:` line: an entry the candidate cannot trace is worse than no entry, because they
    will say it out loud in the real room believing it was vetted.

    <!-- example: answer-bank.md -->
    ```markdown
    # Answer bank

    ## Batched GPU reconstruction on the 3T study
    - serves: "tell me about an optimisation you made"; round 2 Q2
    - source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
    - session: 2026-08-09 — applications/asml-mr-recon-engineer-2026-08-09/mock/transcript-2.md#Q2
    - S: offline recon for a 3T scanner study at the university hospital
    - T: the per-slice loop was the bottleneck in the nightly batch
    - A: replaced the per-slice loop with a batched GPU implementation
    - R: open loop — the measured change was not stated in the room
    - R2 (reflectie): profile before optimising, and write the baseline down first
    ```

    **`mock/open-loops.md`** — every question the candidate could not answer, in **three
    buckets**, because they have three completely different actions:

    1. **a fact you have but did not recall** → go and find it before the real interview;
    2. **a genuine gap** → use the honest framing already chosen in `interview-brief.md`;
    3. **a tailoring error** → the claim comes off the CV (this bucket feeds §6).

    Merging them into one "weak areas" list destroys the artifact.

    **`mock/cheatsheet.md`** — one page. The stories, one line each; the 2–4 honest gaps with
    their exact framing; the questions still unanswered; the candidate's questions for them;
    the loop shape with round names in the local vocabulary. If it exceeds one page it has
    failed.

    ## 6. Write-backs

    **(a) Walk-back list.** Append a `## Walk-back list` section to `interview-brief.md` for
    every CV claim that collapsed under **one** follow-up. Then **offer to re-run the tailoring
    edit and re-render** — that is the point of the section; a list nobody acts on is a note.

    An undefendable claim is a **CV bug, not a rehearsal topic.** This is the mechanism that
    fires `references/interview-prep.md`'s over-reach rule, which until now had no trigger: the
    three CV judges read a page, and the page does not stammer.

    <!-- example: walk-back list -->
    ```markdown
    ## Walk-back list

    ### WB-1 — "Rewrote the offline reconstruction loop for GPU batching, cutting runtime 40%."
    - transcript: mock/transcript-2.md — Q3
    - quote: Honestly it might have been closer to a third, I am not sure any more.
    - defect: PROBE-COLLAPSE
    - softened: "Rewrote the offline reconstruction loop for GPU batching (measured speed-up; exact figure not retained)."
    - status: proposed
    ```

    `check_mock.py` requires this section whenever `PROBE-COLLAPSE`, `OVER-CLAIM`, or
    `CONTRADICTED` fired, and requires an entry quoting **each** such finding.

    **(b) Promote a confirmed-but-absent fact.** An `UNSOURCED-FACT` usually resolves to "it's
    true, it's just not on my CV". Ask the candidate where it came from **before** it enters the
    answer bank. If the answer is that it is real, that is a genuine gap-analysis finding: append
    a row to `claims.yaml` with `source_kind: session-answer` — an already-permitted provenance
    — and route it back into the tailoring plan.

    ```yaml
    - term: PACS export
      where: tailoring-plan.md:promoted-from-mock
      source_kind: session-answer
      source_ref: mock/transcript-2.md#Q1
      session_date: "2026-08-09"
      retracted: null
    ```

    If instead it was drift under pressure, it goes on the walk-back list. Either way it is
    resolved, never silently kept.

    ## 7. Gate

    Run:

    ```
    python3 scripts/check_mock.py --workspace <workspace> --round <n>
    ```

    Exit 0 = the round holds up. Exit 1 = findings on stdout, one per line. Exit 2 = it could
    not run — fix the input, never proceed. **Do not report the round as complete without
    quoting the `check_mock` receipt from `<workspace>/journal.jsonl`.** A gate that was skipped
    produces no output, and that looks exactly like a gate that passed.

    ## 8. Round n+1

    Carry forward an **open-loops summary** only — the unresolved probes and the questions that
    wobbled — not the full transcript. The transcript is on disk; the assessors read it there.
    That is the context-cost mitigation, and it is why the transcript is flushed after every
    answer rather than held in this conversation.

    ## Published employer rubric — the one place a number is honest

    Where the employer publishes its own scale — UK Civil Service Success Profiles behaviours at
    the grade named in the advert, an NHS values framework, a university person specification —
    you may walk the candidate through **that** scale, in the employer's own wording, **attributed**,
    as a checklist of what the panel is told to look for:

    > the Civil Service scale used here reads: 4 = "Adequate positive evidence and any negative
    > evidence would not cause concern"

    **Never as a prediction of the mark.** Quoting an employer's scale is reporting; applying it
    as a verdict is fabrication. Everywhere else, no score, no percentage, no probability, no
    "strong candidate", no invented scale — see the banned-vocabulary block in SKILL.md.

    ## Self-check before reporting the session complete

    - [ ] `references/interview-shapes.md` was read this session
    - [ ] `mock/transcript-<n>.md` was appended to after **every** answer, and never edited
    - [ ] both assessors were dispatched, each with exactly its own pack (`agents/mock-assessor-transcript.md`, `agents/mock-assessor-provenance.md`)
    - [ ] `mock/assessment-<n>.md` contains both blocks verbatim
    - [ ] `mock/question-log.yaml`, `mock/open-loops.md`, `mock/cheatsheet.md` and the profile-level `answer-bank.md` are written
    - [ ] every walk-back and every promoted claim from §6 is on disk
    - [ ] `scripts/check_mock.py` exited 0 and its receipt is in `journal.jsonl`
    ````

- [ ] **Step 4: Run test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_mode_interview_doc.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 5: Commit**

    ```bash
    git add modes/interview.md scripts/tests/test_mode_interview_doc.py
    git commit -m "feat(interview): modes/interview.md with executable schema examples"
    ```

---

### Task 7: The anti-coaching rules in `SKILL.md` (layer 1)

These belong in layer 1 and nowhere else. **Nothing fires if they are skipped** — no build
breaks, no lint complains; the session just quietly coaches the candidate into a sentence
they cannot defend in the real room. That is the exact class the owner's layering rule says
must stay inline however bulky.

**Files:**
- Modify: `SKILL.md` (append one section; touch nothing else)
- Test: `scripts/tests/test_skill_md_interview_blocks.py`

**Interfaces:**
- Consumes: nothing.
- Produces: no code. The section heading `## Mock interview — the anti-coaching line` is the anchor other plans and the self-check may reference.

**Coordination:** Plan 1 owns the rest of `SKILL.md` — its gate table, its self-check list,
and the global banned-vocabulary list. **Append** this section at the end of the file; do not
restructure anything above it, and do not add a second copy of a banned-vocabulary list if
Plan 1 already wrote one (this section extends it for the interviewer and assessors). If
`SKILL.md` does not exist yet, create it with a single `# job-hunt` heading line and then
append.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_skill_md_interview_blocks.py`:

    ```python
    import pathlib
    import re

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    SKILL = ROOT / "SKILL.md"

    HEADING = "## Mock interview — the anti-coaching line"

    REQUIRED = [
        # The line itself
        "A mock interview may help the candidate FIND, ORDER, and COMPRESS a true story they",
        "It may not help them ACQUIRE one.",
        "it is fabrication, however plausible, and it stays fabrication after the candidate agrees",
        # Rule 1
        "**Never write an answer for the candidate.**",
        "Naming a gap is feedback; filling it is ghostwriting a lie.",
        # Rule 2
        "**A leading question is a fabrication vector.**",
        "never build a question on a premise the CV does not support",
        # Rule 3
        "**An undefendable claim is a CV bug, not a story to drill.**",
        "the three CV judges only read the page and the page does not stammer",
        # Rule 4
        "**Never rehearse a gap into a non-gap.**",
        '"I haven\'t done X" must survive rehearsal intact',
        # The tripwire
        "**The tripwire.**",
        "`UNSOURCED-FACT`",
        "before it may enter the answer bank",
        "an answer-bank entry containing an unsourced fact is worse than no answer bank",
        # Session mechanics
        "one round per dispatch",
        "flush the transcript after every answer",
        "the first assessment pass does not see `interview-brief.md` or `claims.yaml`",
    ]


    def test_the_section_exists_exactly_once():
        text = SKILL.read_text(encoding="utf-8")
        assert text.count(HEADING) == 1


    def test_every_load_bearing_sentence_survives():
        text = SKILL.read_text(encoding="utf-8")
        missing = [phrase for phrase in REQUIRED if phrase not in text]
        assert not missing, f"SKILL.md is missing: {missing}"


    def test_the_four_rules_are_numbered_rules():
        text = SKILL.read_text(encoding="utf-8")
        section = text.split(HEADING, 1)[1]
        numbers = re.findall(r"^(\d)\. \*\*", section, re.M)
        assert numbers[:4] == ["1", "2", "3", "4"]


    def test_the_section_does_not_smuggle_in_a_score():
        section = SKILL.read_text(encoding="utf-8").split(HEADING, 1)[1]
        assert "%" not in section
        assert not re.search(r"\b\d+\s*/\s*\d+\b", section)
    ```

- [ ] **Step 2: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_skill_md_interview_blocks.py -q`
    Expected: FAIL with `FileNotFoundError: ... SKILL.md` (or, if Plan 1 has landed, `AssertionError: assert 0 == 1` on the heading count)

- [ ] **Step 3: Append the section to `SKILL.md`**

    Append exactly this, at the end of the file:

    ```markdown
    ## Mock interview — the anti-coaching line

    ### Rehearse retrieval, never rehearse content

    A mock interview may help the candidate FIND, ORDER, and COMPRESS a true story they
    already lived. It may not help them ACQUIRE one. The test is where the fact came from:

    - If a detail traces to the profile, to the provenance map in `interview-brief.md`, or to
      something the candidate told you earlier in this session — helping them say it better is
      preparation.
    - If a detail first appears in YOUR mouth — a number, a tool, a scope, a motive, a
      result — it is fabrication, however plausible, and it stays fabrication after the candidate
      agrees with it.

    **Four hard rules.**

    1. **Never write an answer for the candidate.** You may name what is missing ("your answer
       never said what changed as a result"). You may not supply the missing part. Naming a gap
       is feedback; filling it is ghostwriting a lie.

    2. **A leading question is a fabrication vector.** "So you'd say you owned the migration?"
       hands the candidate an over-claim they will repeat in the real room and will not be able
       to defend. Ask "who owned the migration?" — open, and let the answer be whatever it is.
       This applies to your interview questions too: never build a question on a premise the CV
       does not support ("when you led that team of twelve").

    3. **An undefendable claim is a CV bug, not a story to drill.** If the candidate cannot
       truthfully support a CV claim under ONE follow-up, that is a tailoring error. Log it to
       the walk-back list and change the CV. This is `references/interview-prep.md`'s over-reach
       rule — the mock interview is the stage where it actually fires, because the three CV
       judges only read the page and the page does not stammer.

    4. **Never rehearse a gap into a non-gap.** For an HONEST-GAP the only preparation is the
       truthful framing already chosen in the tailoring plan. Do not produce a smoother version
       that implies experience the candidate lacks. "I haven't done X" must survive rehearsal
       intact; only the sentence around it may improve.

    **The tripwire.** Any figure, tool, employer, title, or scope that appears in the
    candidate's answer and is in NEITHER the profile, NOR `interview-brief.md`, NOR an earlier
    answer this session, is tagged `UNSOURCED-FACT` (or `OVER-CLAIM` if it exceeds a recorded
    source fact) and the candidate is asked where it came from BEFORE it may enter the answer
    bank. Usually the answer is "it's true, it's just not on my CV" — that is a real finding and
    it should probably go on the CV. Sometimes it is drift under pressure. Either way it gets
    resolved, never silently kept: an answer-bank entry containing an unsourced fact is worse
    than no answer bank, because the candidate will say it out loud in the real interview
    believing you vetted it.

    ### Mock-interview session mechanics

    - **Information isolation.** The interviewer is inline and sees everything. The first
      assessment pass sees the transcript, `posting.yaml` and `cv.md` — **the first assessment
      pass does not see `interview-brief.md` or `claims.yaml`**, so it cannot credit the
      candidate for a source fact they never said out loud. The second pass sees the transcript,
      `claims.yaml` and `interview-brief.md` but not the rubric, and emits only
      `UNSOURCED-FACT` / `OVER-CLAIM` / `CONTRADICTED`. Feeding the two passes different inputs
      is what turns the honesty tripwire from an intention into a mechanism.
    - **One round per dispatch.** Assess, write the artifacts, stop. Round n+1 carries an
      open-loops summary, never the full transcript.
    - **Flush the transcript after every answer**, not at the end of the round. A crashed
      session then loses one answer instead of a round, and the assessors read a file rather
      than this conversation.
    - **Bands, not scores.** `not_present` / `asserted` / `instanced` / `held_under_probe`, plus
      the non-band flag `contradicted`. They are unnumbered so they cannot be averaged, and
      `held_under_probe` is the ceiling on purpose: a higher band would require knowing what
      this employer expects at this level, and this skill does not.
    - **The interviewer and both assessors may not emit** a score, grade, percentage or invented
      "X out of Y"; a probability, likelihood or odds; "you would pass / fail / they would hire
      you"; "strong candidate" / "weak candidate" / "hire" / "no-hire"; any comparison to other
      candidates; any claim about what the interviewer thought or would conclude; or a rating on
      a scale the employer did not publish. **The one exception**: where the employer publishes
      its own rubric, you may walk the candidate through that published scale in the employer's
      own wording, attributed, as a checklist of what the panel is told to look for. Quoting an
      employer's scale is reporting; applying it as a verdict is fabrication.
    ```

- [ ] **Step 4: Run test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_skill_md_interview_blocks.py -q`
    Expected: PASS — every test in the file(s) just run, 0 failed

- [ ] **Step 5: Commit**

    ```bash
    git add SKILL.md scripts/tests/test_skill_md_interview_blocks.py
    git commit -m "feat(interview): anti-coaching rules and session mechanics in SKILL.md"
    ```

---

### Task 8: End-to-end dry run — drift, tagged, demanded, resolved

The three preceding tasks each test one check. This one runs the whole mode's disk state
through the real CLI, in the order a real session produces it: a three-turn round in which
the candidate drifts into an unsourced fact and then collapses under the probe; the
provenance pass tags it with the quote; the gate refuses the round until the walk-back
exists and the promoted fact is on `claims.yaml`; and then — the half that matters just as
much — the gate goes quiet.

**Files:**
- Create: `scripts/tests/fixtures/mock-dryrun/job-profiles/demo/answer-bank.md`
- Create: `scripts/tests/fixtures/mock-dryrun/job-profiles/demo/applications/asml-mr-recon-engineer-2026-08-09/cv.md`
- Create: `.../asml-mr-recon-engineer-2026-08-09/interview-brief.md`
- Create: `.../asml-mr-recon-engineer-2026-08-09/claims.yaml`
- Create: `.../asml-mr-recon-engineer-2026-08-09/mock/transcript-2.md`
- Create: `.../asml-mr-recon-engineer-2026-08-09/mock/assessment-2.md`
- Create: `.../asml-mr-recon-engineer-2026-08-09/mock/question-log.yaml`
- Create: `.../asml-mr-recon-engineer-2026-08-09/mock/open-loops.md`
- Create: `scripts/tests/fixtures/mock-dryrun/fixes/walkback.md`
- Create: `scripts/tests/fixtures/mock-dryrun/fixes/claims-promotion.yaml`
- Test: `scripts/tests/test_mock_dryrun.py`

**Interfaces:**
- Consumes: `check_mock.main(argv) -> int`, `check_mock._default_scanner`, `journal.read_receipts(workspace, gate)`.
- Produces: no code.

**One cross-plan note the implementer must not skip.** A verbatim quote of a candidate can
legitimately contain a percentage, and `check_mock.py` runs the banned-vocabulary scanner
over `assessment-<n>.md`, which is full of verbatim quotes. This fixture writes speech as
"40 percent" so the two never collide, but that is a dodge, not a fix. **Raise it against
Plan 2:** `lint_no_prediction.py` needs an exemption for text inside a `quote=` field of a
`MOCK-*-V1` block, or honest transcripts will fail this gate. Do not weaken `check_mock.py`
to work around it — the scanner must keep seeing the prose the model wrote.

- [ ] **Step 1: Write the fixture workspace**

    `scripts/tests/fixtures/mock-dryrun/job-profiles/demo/applications/asml-mr-recon-engineer-2026-08-09/mock/transcript-2.md`:

    ```markdown
    # Mock transcript — round 2
    Round type: technical
    Market: nl
    Family: ml-engineering
    Persona: Sanne de Vries, MR reconstruction team lead — direct, asks for numbers

    ## Q1 — Your CV says you cut reconstruction time by a third. Walk me through how you measured that.
    **Interviewer:** Your CV says you cut reconstruction time by a third. Walk me through how you measured that.
    **Candidate:** We benchmarked the new pipeline against the old one on about 200 patient scans and it came out roughly 40 percent faster end to end.

    ## Q2 — Who ran that benchmark, and where did the 200 scans come from?
    **Interviewer:** Who ran that benchmark, and where did the 200 scans come from?
    **Candidate:** I ran it myself on the department cluster. The 200 is from memory, it might have been fewer.

    ## Q3 — Take the speed-up specifically. What was the before number and the after number?
    **Interviewer:** Take the speed-up specifically. What was the before number and the after number?
    **Candidate:** I do not have the before and after in front of me. Honestly it might have been closer to a third, I am not sure any more.
    ```

    `.../mock/assessment-2.md`:

    ```markdown
    # Mock assessment — round 2

    Two passes ran on this transcript with deliberately different inputs. Neither saw the
    other's output. The blocks below are the assessors' own words, unedited.

    MOCK-ASSESSMENT-V1
    ROUND: 2
    ROUND-TYPE: technical
    MARKET: nl
    FAMILY: ml-engineering
    FINDING: tag=NO-ACTOR | ref=Q1 | quote=We benchmarked the new pipeline against the old one
    FINDING: tag=PROBE-COLLAPSE | ref=Q3 | quote=Honestly it might have been closer to a third, I am not sure any more.
    BAND: dimension=ownership | value=asserted | ref=Q1 | quote=We benchmarked the new pipeline against the old one
    BAND: dimension=outcome | value=asserted | ref=Q1 | quote=it came out roughly 40 percent faster end to end
    BAND: dimension=probe | value=not_present | ref=Q3 | quote=I do not have the before and after in front of me.
    COVERAGE: status=asked_thin | must_have=Measured performance work on reconstruction pipelines
    SHAPE: status=rehearsed | round_name=technisch gesprek met de vakinhoudelijke manager
    END-MOCK-ASSESSMENT-V1

    MOCK-PROVENANCE-V1
    ROUND: 2
    FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=on about 200 patient scans
    FINDING: tag=OVER-CLAIM | ref=Q1 | quote=it came out roughly 40 percent faster end to end
    FINDING: tag=UNSOURCED-FACT | ref=Q2 | quote=I ran it myself on the department cluster
    END-MOCK-PROVENANCE-V1
    ```

    `.../mock/question-log.yaml`:

    ```yaml
    round: 2
    posting_country: NL
    questions:
      - id: Q1
        text: Your CV says you cut reconstruction time by a third. Walk me through how you measured that.
        source: judge-supplementary
        asked: true
      - id: Q2
        text: Who ran that benchmark, and where did the 200 scans come from?
        source: generated
        asked: true
      - id: Q3
        text: Take the speed-up specifically. What was the before number and the after number?
        source: generated
        asked: true
    rejected:
      - id: R1
        text: "ASML 宣讲会 → 笔试 → 二面 → HR 电话面 timeline"
        source: scraped
        source_site: nowcoder
        source_id: "057523b2ca9d"
        source_time: "2026-08-06T11:06:49"
        entity_country: CN
        reason: wrong_country
    ```

    `.../mock/open-loops.md`:

    ```markdown
    # Open loops — round 2

    ## (i) A fact you have but did not recall
    - The before/after timings for the batched GPU rewrite. Find them in the lab notebook or
      the commit history before the real interview.

    ## (ii) A genuine gap
    - No MDR regulatory documentation experience. Use the framing in interview-brief.md §2.

    ## (iii) A tailoring error
    - The "cut reconstruction time by a third" bullet did not survive one follow-up. See the
      walk-back list on interview-brief.md.
    ```

    `.../interview-brief.md`:

    ```markdown
    # Interview-readiness brief

    ## 1. Be ready to explain (your tailored claims)
    - CV says: "Rewrote the offline reconstruction loop for GPU batching, cutting runtime by a third."
      Source: profile.yaml:experience[0].bullets[2] — the measured change was on the model
      forward pass on the dev set, not end to end.
      Be ready to: give the before and after timings and say how they were measured.

    ## 2. Honest gaps — your answer if asked
    - No MDR regulatory documentation experience. Honest framing: research-side validation
      work, learning the regulatory side deliberately.
    ```

    `.../claims.yaml`:

    ```yaml
    - term: GPU batching
      where: tailored-profile.yaml:experience[0].bullets[2]
      source_kind: profile-line
      source_ref: profile.yaml:experience[0].bullets[2]
      session_date: "2026-08-09"
      retracted: null
    ```

    `.../cv.md` (short, only so the fixture reads like a real workspace):

    ```markdown
    # Demo Candidate
    MR reconstruction engineer

    ## Experience
    **Research engineer, University Hospital — 2023–2026**
    - Rewrote the offline reconstruction loop for GPU batching, cutting runtime by a third.
    ```

    `scripts/tests/fixtures/mock-dryrun/job-profiles/demo/answer-bank.md`:

    ```markdown
    # Answer bank

    ## Batched GPU reconstruction on the 3T study
    - serves: "tell me about an optimisation you made"; round 2 Q1
    - source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
    - session: 2026-08-09 — mock/transcript-2.md#Q1
    - S: offline recon for a 3T scanner study at the university hospital
    - T: the per-slice loop was the bottleneck in the nightly batch
    - A: replaced the per-slice loop with a batched GPU implementation
    - R: open loop — the measured change was not stated in the room
    - R2 (reflectie): write the baseline down before optimising
    ```

- [ ] **Step 2: Write the two fix files**

    `scripts/tests/fixtures/mock-dryrun/fixes/walkback.md` — what §6(a) of the mode file
    tells the model to append to `interview-brief.md`:

    ```markdown

    ## Walk-back list

    ### WB-1 — "Rewrote the offline reconstruction loop for GPU batching, cutting runtime by a third."
    - transcript: mock/transcript-2.md — Q3
    - quote: Honestly it might have been closer to a third, I am not sure any more.
    - defect: PROBE-COLLAPSE
    - softened: "Rewrote the offline reconstruction loop for GPU batching (measured speed-up; exact figure not retained)."
    - status: proposed

    ### WB-2 — the end-to-end scope of the speed-up
    - transcript: mock/transcript-2.md — Q1
    - quote: it came out roughly 40 percent faster end to end
    - defect: OVER-CLAIM
    - softened: "speed-up measured on the model forward pass, not end to end"
    - status: proposed

    ### WB-3 — the size of the benchmark set
    - transcript: mock/transcript-2.md — Q2
    - quote: on about 200 patient scans
    - defect: UNSOURCED-FACT
    - softened: "benchmarked on a held-out set; the exact count is not recorded"
    - status: proposed
    ```

    `scripts/tests/fixtures/mock-dryrun/fixes/claims-promotion.yaml` — what §6(b) tells the
    model to append to `claims.yaml` once the candidate confirms the fact is real:

    ```yaml
    - term: department cluster
      where: tailoring-plan.md:promoted-from-mock
      source_kind: session-answer
      source_ref: mock/transcript-2.md#Q2
      session_date: "2026-08-09"
      retracted: null
    ```

- [ ] **Step 3: Write the failing dry-run test**

    Create `scripts/tests/test_mock_dryrun.py`:

    ```python
    import pathlib
    import shutil
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import check_mock
    import journal
    import mock_fixtures as F

    FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "mock-dryrun"
    SLUG = "asml-mr-recon-engineer-2026-08-09"


    @pytest.fixture
    def session(tmp_path, monkeypatch):
        shutil.copytree(FIXTURE, tmp_path / "run")
        monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
        return tmp_path / "run"


    def workspace(session):
        return session / "job-profiles" / "demo" / "applications" / SLUG


    def gate(session, capsys):
        code = check_mock.main(
            ["--workspace", str(workspace(session)), "--round", "2", "--today", "2026-08-09"]
        )
        return code, capsys.readouterr().out.strip().splitlines()


    def apply_walkback(session):
        brief = workspace(session) / "interview-brief.md"
        fix = (session / "fixes" / "walkback.md").read_text(encoding="utf-8")
        brief.write_text(brief.read_text(encoding="utf-8") + fix, encoding="utf-8")


    def apply_promotion(session):
        claims = workspace(session) / "claims.yaml"
        fix = (session / "fixes" / "claims-promotion.yaml").read_text(encoding="utf-8")
        claims.write_text(claims.read_text(encoding="utf-8") + fix, encoding="utf-8")


    # ------------------------------------------------------------------ stage A

    def test_stage_a_the_gate_demands_the_walkback(session, capsys):
        code, out = gate(session, capsys)
        assert code == 1
        assert any(line.startswith("WALKBACK_MISSING:") for line in out)


    def test_stage_a_the_provenance_pass_tagged_the_drift_with_its_quote(session):
        text = (workspace(session) / "mock" / "assessment-2.md").read_text(encoding="utf-8")
        assert "tag=UNSOURCED-FACT" in text
        assert "quote=on about 200 patient scans" in text
        assert "quote=I ran it myself on the department cluster" in text


    def test_stage_a_the_quotes_are_really_in_the_transcript(session, capsys):
        """If they were invented, the gate would say so — it does not."""
        _, out = gate(session, capsys)
        assert not [line for line in out if line.startswith("QUOTE_NOT_IN_TRANSCRIPT:")]


    def test_stage_a_the_transcript_pass_did_not_reach_for_the_brief(session, capsys):
        _, out = gate(session, capsys)
        assert not [line for line in out if line.startswith("WRONG_PASS:")]


    # ------------------------------------------------------------------ stage B

    def test_stage_b_the_walkback_satisfies_the_demand_but_the_promotion_is_still_owed(
        session, capsys
    ):
        apply_walkback(session)
        code, out = gate(session, capsys)
        assert code == 1
        assert not [line for line in out if line.startswith("WALKBACK")]
        unresolved = [line for line in out if line.startswith("UNRESOLVED_FACT:")]
        assert len(unresolved) == 1
        assert "department cluster" in unresolved[0]


    # ------------------------------------------------------------------ stage C

    def test_stage_c_the_resolved_round_passes_quietly(session, capsys):
        apply_walkback(session)
        apply_promotion(session)
        code, out = gate(session, capsys)
        assert code == 0
        assert out == []


    def test_every_run_left_a_receipt_in_order(session, capsys):
        gate(session, capsys)
        apply_walkback(session)
        gate(session, capsys)
        apply_promotion(session)
        gate(session, capsys)
        receipts = journal.read_receipts(workspace(session), "check_mock")
        assert [r["verdict"] for r in receipts] == ["fail", "fail", "pass"]
        assert all("mock/assessment-2.md" in r["input_hashes"] for r in receipts)


    def test_the_receipt_hash_tracks_the_file_that_changed(session, capsys):
        gate(session, capsys)
        apply_walkback(session)
        gate(session, capsys)
        first, second = journal.read_receipts(workspace(session), "check_mock")
        assert first["input_hashes"]["interview-brief.md"] != \
            second["input_hashes"]["interview-brief.md"]
        assert first["input_hashes"]["mock/transcript-2.md"] == \
            second["input_hashes"]["mock/transcript-2.md"]


    # ------------------------------------------------------------------ with Plan 2 present

    def test_the_real_vocabulary_scanner_is_also_quiet_on_a_resolved_round(
        session, capsys, monkeypatch
    ):
        pytest.importorskip("lint_no_prediction")
        monkeypatch.undo()
        apply_walkback(session)
        apply_promotion(session)
        code, out = gate(session, capsys)
        assert code == 0, out
    ```

    > **Note:** `monkeypatch.undo()` in the last test removes the stub installed by the
    > `session` fixture, so `check_mock` resolves Plan 2's real scanner. The test skips
    > entirely until Plan 2 has landed — and when it does land, this is the test that proves
    > the two plans compose.

- [ ] **Step 4: Run test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_mock_dryrun.py -q`
    Expected: FAIL with `FileNotFoundError: ... fixtures/mock-dryrun` (before the fixture is
    written) or, once written, `AssertionError` on `test_stage_c_the_resolved_round_passes_quietly`
    if any fixture file drifted from the quotes in the transcript

- [ ] **Step 5: Run the full suite**

    Run: `python3 -m pytest scripts/tests -q`
    Expected: PASS — every test from Tasks 1–8, with at most one `skipped` (the Plan 2 test)

- [ ] **Step 6: Commit**

    ```bash
    git add scripts/tests/fixtures/mock-dryrun scripts/tests/test_mock_dryrun.py
    git commit -m "test(interview): end-to-end dry run — drift tagged, walk-back demanded, round resolved"
    ```

---

## Definition of done

- [ ] `python3 -m pytest scripts/tests -q` is green from the repo root.
- [ ] `python3 scripts/check_mock.py --workspace scripts/tests/fixtures/mock-dryrun/job-profiles/demo/applications/asml-mr-recon-engineer-2026-08-09 --round 2 --today 2026-08-09` exits 1 and prints `WALKBACK_MISSING: …` — the gate really does run from the command line, not only under pytest. (It also appends a receipt to the fixture's `journal.jsonl`; delete that file afterwards so the fixture stays pristine, and confirm with `git status` that nothing under `fixtures/` is modified.)
- [ ] Every file in the File Structure table exists.
- [ ] `SKILL.md` contains `## Mock interview — the anti-coaching line` exactly once, and nothing above it was restructured.
- [ ] Nothing was pushed. `git log --oneline origin/HEAD..HEAD` (or `git log --oneline -8`) shows this plan's commits local only.

## Handover notes for whoever runs the mode first

Three things this plan deliberately did **not** try to close with code, because code cannot
see them:

1. **A scraped item can be the right country, the right date, and still be one person's
   half-remembered account written days later.** There is no second witness. The date stamp
   and the country rule bound the damage; they do not verify the post.
2. **An interviewer persona can be too fair.** The gate cannot tell whether the round asked
   the awkward question. The `COVERAGE` rows are the only audit of that, and they are the
   assessor's own account of what was asked — read them, and if every must-have came back
   `evidenced` in one round, the round was too easy.
3. **The equivalence test — honest is not the same as cringing.** Nothing in this mode fires
   when a candidate systematically undersells a real thing, and under-reporting is invisible
   to every check here. It is exactly the failure mode that hits the stretch candidates and
   career-switchers this skill exists to serve.
