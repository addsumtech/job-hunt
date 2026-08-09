# Assess Mode and Grounding Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the standalone "should I apply to this posting" mode of the `job-hunt` skill, together with the grounding machinery (evidence blocks, deterministic contradiction checks, the single counting path, the anti-prediction lint) and the five hand-written market-convention tables that the whole skill rests on.

**Architecture:** Three layers. `scripts/*.py` hold everything a program can decide — chunking source text into addressable blocks, resolving or dropping evidence references, counting coverage, finding contradictions, linting the market tables. `references/market-conventions/*.yaml` hold the one class of assertion that has no source text to cite, written by a person, dated, provenance-kinded, and rendered verbatim. `modes/assess.md` is the layer-1.5 file loaded unconditionally on entering assess mode; it defines the `fit-assessment.yaml` row schema that `check_assessment.py` requires and nothing else defines — that is its backstop.

**Tech Stack:** Python 3 (stdlib + PyYAML only for this plan; `python-docx` is used elsewhere in the skill), pytest, YAML data files, Markdown output.

## Global Constraints

These are copied verbatim from the shared contract. Do not rename, re-sign, or re-shape anything here.

- Repo root: `/Users/donghanglyu/code_project/job-hunt`. The repo root **is** the skill. Git is already initialised.
- Python 3, stdlib + PyYAML + python-docx only. pytest for tests. Run tests with: `python3 -m pytest scripts/tests -q` from the repo root.
- Every gate script obeys this CLI contract, no exceptions:
  ```
  python3 scripts/<name>.py --workspace <path> [script-specific args]
  exit 0  = gate passed
  exit 1  = gate failed (findings printed to stdout, one per line, each prefixed with a stable
            UPPERCASE code, e.g. "UNSOURCED: ...", "STALE: ...", "NO_SOURCE_ID: ...")
  exit 2  = could not run (missing input file); message to stderr
  ```
- Every gate appends exactly one receipt line to `<workspace>/journal.jsonl` before exiting.
- `scripts/journal.py` is written in **Plan 1** and imported by every gate here. Its API:
  ```python
  def append(workspace: pathlib.Path, record: dict) -> None
  def receipt(workspace: pathlib.Path, gate: str, input_hashes: dict[str, str],
              verdict: str, findings: list[str] | None = None) -> dict
  def sha256_file(path: pathlib.Path) -> str
  def read_receipts(workspace: pathlib.Path, gate: str | None = None) -> list[dict]
  ```
- `scripts/paths.py` is written in **Plan 1**. `PROFILES_ROOT = pathlib.Path.home() / ".claude" / "job-profiles"`; `profile_dir(name)`, `master_profile(name)`, `search_prefs(name)`, `answer_bank(name)`, `search_dir(name, slug)`, `workspace(name, company, role, date)`.
- **The ONE verdict vocabulary** — these exact strings, everywhere:
  `"strong_apply" | "worth_applying" | "stretch" | "likely_screen_out" | "blocked"`.
  Orthogonal refusal state (NOT a sixth level): `"insufficient_evidence"`.
  Human-facing zh labels: 强烈建议投 / 值得投 / 可以冲刺 / 大概率被筛掉 / 硬性阻断 / 证据不足—不出结论.
  discover-stage verdicts carry `provisional: true` and MUST NOT be copied into an assessment.
- **Requirement-row enums** — these exact strings:
  `level: "required" | "preferred" | "unclear"`;
  `screening: "knockout" | "weighted" | "nice_to_have"`;
  `match: "strong" | "partial" | "gap" | "no_evidence"`;
  `recency: "current" | "recent" | "dated" | "undated"`;
  `effort: "quick" | "evening" | "multi_day" | "not_closable"`.
- **Evidence block ids:** `"CV-%03d"` and `"JD-%03d"`. Chunking parameters: max 900 chars per block, max 80 blocks per source, split on blank lines or a newline preceding a bullet/number/CJK numeral, over-long paragraphs sentence-split on `[。.!?]`, drop chunks under 8 chars.
- **Dates:** today is `2026-08-09`. Use it for filenames and any dated example. Never call an unstamped date helper in an example; show the literal date.
- **Git rules** (violating these is a plan defect): stage NAMED PATHS only — never `git add -A`, never `git add .`. **NEVER push.** Commit locally only. Do not pass `-c user.name` / `-c user.email`.
- **Journal receipt verdict strings used by this plan:** `"pass"`, `"fail"`, `"reported"` (a script that surfaces findings without judging them), `"produced"` (a script that writes a derived artifact).
- **Testing discipline (non-negotiable):** every check's tests must pin the QUIET case as hard as the firing case. A check that cries wolf on ordinary output is worse than no check, because the reader learns to skip the line and it stops working on the run that mattered. A test that only imports a module proves the button exists, not that pressing it does anything.

### The `fit-assessment.yaml` schema (authoritative copy — Task 12 writes this into `modes/assess.md`)

Every script in this plan reads this shape. It is reproduced here so no task has to guess.

```yaml
market: cn                      # one of cn | nl | de | uk | us | none
verdict: worth_applying         # one of the five, or insufficient_evidence
provisional: false              # always false in an assessment; discover rows carry true
effort: evening                 # overall: quick | evening | multi_day | not_closable
level_direction: lateral        # step_up | lateral | step_down | unclear
declared_work_status: needs_sponsorship
                                # authorized | needs_sponsorship | student_or_graduate
                                # | temporary_route | unknown
stated_conditions:              # work-authorization style conditions read off the posting
  - type: sponsorship           # sponsorship | work_authorization | citizenship | clearance
                                # | licence | onsite_location | other
    stance: requires_existing   # requires_existing | offers_support | unclear
    evidence: [{ref: JD-004}]
requirements:
  - id: R1
    kind: must_have             # must_have | responsibility
    text: "Experience with distributed training frameworks"
    level: required
    screening: knockout
    match: partial
    recency: recent
    effort: evening             # per-row: what closing THIS row would take
    how_to_close: "Port the existing single-GPU trainer to torchrun and publish it."
    evidence: [{ref: CV-012}, {ref: JD-007}]
actions:                        # the single authoritative to-do list
  - action: "Publish the torchrun port"
    acceptance: "Repo README shows a two-GPU run log"
    when: before_apply          # now | before_apply | later
conventions_rendered: [cn-boss-profile-is-the-screen]
```

Rules that bind every consumer of this file:
- A row with `match: no_evidence` MUST have an empty `evidence` list. Any other row MUST have at least one ref that resolves against `evidence-blocks.json`.
- `strong` counts as strong only when `recency` is `current`, `recent` or `undated`. `match: strong` with `recency: dated` counts as **partial** — evidence that is only dated is not strong evidence. `undated` does not downgrade: a CV that omits dates is a formatting fact, not a staleness fact, and downgrading it would punish a shape rather than a claim.
- `partial` and `gap` are NEVER merged into a covered number.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/evidence_blocks.py` | Cut `posting-source.txt` → `JD-nnn` and the CV → `CV-nnn`; write `evidence-blocks.json`. The only chunker. |
| `scripts/check_evidence_refs.py` | Resolve every ref against the block ids; drop and list the unresolvable ones; strip block ids out of reader-facing prose. |
| `scripts/lint_no_prediction.py` | Ban percentages, `n/m` score patterns and prediction vocabulary (EN + ZH) from rendered files, with one allowlist for a cited published employer rubric. |
| `scripts/consistency.py` | Four pure deterministic contradiction detectors + the notice texts. Reports, never repairs. |
| `scripts/count_coverage.py` | The ONLY count-producing path. Computes and renders the countable-facts block. |
| `scripts/check_conventions.py` | The market-table lint: digit/percent ban, source provenance, protected traits, duplicate ids, expired `review_by`, en/zh symmetry, `unverified` discipline. Also the table loader. |
| `scripts/check_assessment.py` | The assess-mode gate. Composes the five checks above and adds the assessment-only rules. |
| `scripts/tests/conftest.py` | Puts `scripts/` on `sys.path` so tests can `import evidence_blocks`. |
| `scripts/tests/test_*.py` | One test module per script. Each pins the quiet case as hard as the firing case. |
| `references/market-conventions/README.md` | The rules for adding an entry. This file **is** `check_conventions.py`'s spec. |
| `references/market-conventions/{cn,nl,de,uk,us}.yaml` | The five hand-written tables. Rendered verbatim, never restated by the model. |
| `modes/assess.md` | Layer 1.5. Defines the `fit-assessment.yaml` row schema, the fetch-integrity thresholds, the complete `posting.yaml` field list, the refusal floor, and the "what to do instead" half. |
| `docs/superpowers/research/2026-08-09-market-conventions/` | The durable copy of the research the tables are built from: `markets.json` plus the four adversarial reviews. |
| `requirements.txt` | Created by Plan 1. This plan only reads it. |

---

### Task 1: Evidence blocks — the chunker

**Files:**
- Create: `scripts/evidence_blocks.py`
- Create: `scripts/tests/conftest.py`
- Test: `scripts/tests/test_evidence_blocks.py`

**Interfaces:**
- Consumes: `journal.receipt(workspace, gate, input_hashes, verdict, findings=None) -> dict`, `journal.sha256_file(path) -> str` (both from Plan 1's `scripts/journal.py`).
- Produces:
  - `MAX_BLOCK_CHARS = 900`, `MAX_BLOCKS_PER_SOURCE = 80`, `MIN_CHUNK_CHARS = 8`
  - `normalize_block_text(value: str) -> str`
  - `split_long_paragraph(paragraph: str) -> list[str]`
  - `split_into_chunks(text: str) -> list[str]`
  - `build_blocks(text: str, prefix: str, source: str) -> list[dict]` — each dict is `{"id": "JD-001", "source": "jd", "text": "..."}`
  - `flatten_yaml_to_text(obj, prefix: str = "") -> str`
  - `read_source(path: pathlib.Path) -> str`
  - `main(argv: list[str] | None = None) -> int`
  - The on-disk artifact `evidence-blocks.json`:
    ```json
    {"generated_at": "2026-08-09T00:00:00Z",
     "sources": {"jd": {"path": "...", "sha256": "..."}, "cv": {"path": "...", "sha256": "..."}},
     "blocks": [{"id": "JD-001", "source": "jd", "text": "..."}]}
    ```

- [ ] **Step 1: Write the failing test**

  Create `scripts/tests/conftest.py`:
  ```python
  import pathlib
  import sys

  # Tests import the gate scripts by module name. scripts/ is not a package on purpose:
  # each script must also be runnable as `python3 scripts/<name>.py` from the repo root.
  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
  ```

  Create `scripts/tests/test_evidence_blocks.py`:
  ```python
  import json

  import evidence_blocks as eb


  def test_ids_are_three_digit_zero_padded_and_prefixed():
      blocks = eb.build_blocks("first paragraph here\n\nsecond paragraph here", "JD", "jd")
      assert [b["id"] for b in blocks] == ["JD-001"]
      assert blocks[0]["source"] == "jd"
      # both paragraphs are short, so they repack into one block under the 900 ceiling
      assert "first paragraph here" in blocks[0]["text"]
      assert "second paragraph here" in blocks[0]["text"]


  def test_cjk_numbered_list_splits_at_each_cjk_numeral():
      text = "岗位职责如下：\n一、" + "负"*400 + "\n二、" + "责"*400 + "\n三、" + "任"*400
      chunks = eb.split_into_chunks(text)
      assert len(chunks) == 2, chunks
      assert chunks[0].startswith("岗位职责如下：")
      assert "一、" in chunks[0] and "二、" in chunks[0]
      assert chunks[1].startswith("三、")
      assert all(len(c) <= eb.MAX_BLOCK_CHARS for c in chunks)


  def test_short_chunks_are_dropped_by_character_count_not_byte_count():
      # Five Chinese characters is fifteen bytes in UTF-8 and ten latin display columns.
      # It must be dropped on the CHARACTER count, exactly as a five-letter latin line
      # would be -- otherwise the same source is chunked differently in two languages.
      assert eb.split_into_chunks("我要找工作") == []
      assert eb.split_into_chunks("short") == []


  def test_a_short_paragraph_beside_a_long_one_survives_by_repacking():
      # The floor applies to the finished chunk, not to the paragraph. A short heading
      # merged into the paragraph under it is content, not noise.
      chunks = eb.split_into_chunks("职责\n\n负责磁共振重建流水线的开发与维护工作。")
      assert len(chunks) == 1
      assert chunks[0].startswith("职责")
      assert "负责磁共振重建流水线" in chunks[0]


  def test_nine_character_cjk_line_survives():
      chunks = eb.split_into_chunks("我在做磁共振重建研究")
      assert chunks == ["我在做磁共振重建研究"]


  def test_over_long_paragraph_is_sentence_split_on_cjk_and_latin_stops():
      paragraph = ("这是第一句。" * 60) + ("This is a sentence. " * 60)
      chunks = eb.split_long_paragraph(paragraph)
      assert len(chunks) > 1
      assert all(len(c) <= eb.MAX_BLOCK_CHARS for c in chunks)
      assert chunks[0].startswith("这是第一句。")


  def test_single_sentence_over_the_ceiling_is_hard_sliced():
      paragraph = "x" * 2000
      chunks = eb.split_long_paragraph(paragraph)
      assert [len(c) for c in chunks] == [900, 900, 200]


  def test_bullet_list_splits_at_every_bullet():
      text = "\n".join(f"- bullet {i} " + "y" * 500 for i in range(4))
      chunks = eb.split_into_chunks(text)
      assert len(chunks) == 4
      assert all(len(c) <= eb.MAX_BLOCK_CHARS for c in chunks)
      assert [c[:10] for c in chunks] == ["- bullet 0", "- bullet 1",
                                          "- bullet 2", "- bullet 3"]


  def test_block_cap_is_eighty_per_source():
      text = "\n\n".join("z" * 500 for _ in range(200))
      blocks = eb.build_blocks(text, "CV", "cv")
      assert len(blocks) == eb.MAX_BLOCKS_PER_SOURCE
      assert blocks[-1]["id"] == "CV-080"


  def test_flatten_yaml_to_text_is_deterministic_and_readable():
      profile = {"name": "Donghang", "skills": {"infra": ["Docker", "Slurm"]}}
      out = eb.flatten_yaml_to_text(profile)
      assert "name: Donghang" in out
      assert "skills.infra[0]: Docker" in out
      assert "skills.infra[1]: Slurm" in out
      assert eb.flatten_yaml_to_text(profile) == out


  def test_main_writes_the_artifact_and_a_receipt(tmp_path):
      (tmp_path / "posting-source.txt").write_text(
          "Requirements\n\n- Five years of C++\n\n- MR physics background", encoding="utf-8")
      (tmp_path / "cv-source.txt").write_text(
          "Experience\n\nBuilt a C++ reconstruction pipeline at Leiden.", encoding="utf-8")
      rc = eb.main(["--workspace", str(tmp_path)])
      assert rc == 0
      data = json.loads((tmp_path / "evidence-blocks.json").read_text(encoding="utf-8"))
      ids = [b["id"] for b in data["blocks"]]
      assert ids[0] == "JD-001"
      assert any(i.startswith("CV-") for i in ids)
      assert set(data["sources"]) == {"jd", "cv"}
      assert len(data["sources"]["jd"]["sha256"]) == 64
      receipts = [json.loads(line) for line in
                  (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
      assert [r["gate"] for r in receipts] == ["evidence_blocks"]


  def test_main_exits_two_when_the_posting_source_is_missing(tmp_path, capsys):
      (tmp_path / "cv-source.txt").write_text("something long enough", encoding="utf-8")
      assert eb.main(["--workspace", str(tmp_path)]) == 2
      assert "posting-source.txt" in capsys.readouterr().err
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_evidence_blocks.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'evidence_blocks'`

- [ ] **Step 3: Write minimal implementation**

  Create `scripts/evidence_blocks.py`:
  ```python
  #!/usr/bin/env python3
  """Cut the posting and the CV into addressable evidence blocks.

  Port of marketfit-job-lens src/ai/evidenceBlocks.js. The parameters are fixed by the
  skill's shared contract and are load-bearing: 900 characters per block, 80 blocks per
  source, split on blank lines or a newline before a bullet / number / CJK numeral,
  sentence-split over-long paragraphs on [。.!?], drop chunks under 8 characters.

  Why blocks exist: every analytical sentence in an assessment must point at text that
  really exists. That is a plausibility bound, not a proof -- it guarantees a claim
  points at something real, never that the claim follows from it. Carry that sentence
  into the skill's own output; a reader who mistakes it for proof is worse off than one
  who was told nothing.

  Every length here is counted in CHARACTERS. Not bytes, and not latin display columns.
  A nine-character Chinese line is a real line; measuring it in bytes would keep junk and
  measuring it in latin width would silently delete a third of a Chinese posting.
  """
  from __future__ import annotations

  import argparse
  import datetime as _dt
  import json
  import pathlib
  import re
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import journal  # noqa: E402

  MAX_BLOCK_CHARS = 900
  MAX_BLOCKS_PER_SOURCE = 80
  MIN_CHUNK_CHARS = 8

  _PARAGRAPH_SPLIT = re.compile(r"\n{2,}|\n(?=\s*[-*0-9一二三四五六七八九十])")
  _SENTENCE_SPLIT = re.compile(r"(?<=[。.!?])\s+")


  def normalize_block_text(value: str) -> str:
      text = str(value or "")
      text = text.replace("\u00a0", " ")   # NBSP: pasted postings are full of them
      text = re.sub(r"[ \t]+", " ", text)
      text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
      text = re.sub(r"\n{3,}", "\n\n", text)
      return text.strip()


  def split_long_paragraph(paragraph: str) -> list[str]:
      if len(paragraph) <= MAX_BLOCK_CHARS:
          return [paragraph]
      sentences = [s for s in _SENTENCE_SPLIT.split(paragraph) if s]
      if len(sentences) <= 1:
          return [paragraph[i:i + MAX_BLOCK_CHARS]
                  for i in range(0, len(paragraph), MAX_BLOCK_CHARS)]
      chunks: list[str] = []
      current = ""
      for sentence in sentences:
          if not current:
              current = sentence
          elif len(current) + 1 + len(sentence) <= MAX_BLOCK_CHARS:
              current = f"{current} {sentence}"
          else:
              chunks.append(current)
              current = sentence
      if current:
          chunks.append(current)
      return chunks


  def split_into_chunks(text: str) -> list[str]:
      normalized = normalize_block_text(text)
      paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(normalized)]
      paragraphs = [p for p in paragraphs if p]
      if not paragraphs and normalized:
          paragraphs = [normalized]
      chunks: list[str] = []
      current = ""
      for paragraph in paragraphs:
          for piece in split_long_paragraph(paragraph):
              if not current:
                  current = piece
              elif len(current) + 1 + len(piece) <= MAX_BLOCK_CHARS:
                  current = f"{current}\n{piece}"
              else:
                  chunks.append(current)
                  current = piece
      if current:
          chunks.append(current)
      return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


  def build_blocks(text: str, prefix: str, source: str) -> list[dict]:
      chunks = split_into_chunks(text)[:MAX_BLOCKS_PER_SOURCE]
      return [{"id": f"{prefix}-{index + 1:03d}", "source": source, "text": chunk}
              for index, chunk in enumerate(chunks)]


  def flatten_yaml_to_text(obj, prefix: str = "") -> str:
      """Render a parsed YAML document as one leaf per paragraph.

      The master profile is YAML, and assess must be able to cite it. Chunking the raw
      file would put YAML punctuation inside blocks; flattening to "path: value" lines
      keeps every block quotable by a human reviewer checking a citation.
      """
      parts: list[str] = []
      if isinstance(obj, dict):
          for key in obj:
              child = f"{prefix}.{key}" if prefix else str(key)
              parts.append(flatten_yaml_to_text(obj[key], child))
      elif isinstance(obj, list):
          for index, item in enumerate(obj):
              parts.append(flatten_yaml_to_text(item, f"{prefix}[{index}]"))
      else:
          parts.append(f"{prefix}: {obj}" if prefix else str(obj))
      return "\n\n".join(p for p in parts if p)


  def read_source(path: pathlib.Path) -> str:
      raw = path.read_text(encoding="utf-8")
      if path.suffix.lower() in {".yaml", ".yml"}:
          import yaml
          return flatten_yaml_to_text(yaml.safe_load(raw) or {})
      return raw


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="Build evidence blocks for an assessment.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      parser.add_argument("--jd", type=pathlib.Path, default=None)
      parser.add_argument("--cv", type=pathlib.Path, default=None)
      parser.add_argument("--out", type=pathlib.Path, default=None)
      args = parser.parse_args(argv)

      workspace = args.workspace
      jd_path = args.jd or workspace / "posting-source.txt"
      cv_path = args.cv or workspace / "cv-source.txt"
      out_path = args.out or workspace / "evidence-blocks.json"

      for label, path in (("posting-source.txt", jd_path), ("cv source", cv_path)):
          if not path.exists():
              print(f"cannot run: {label} not found at {path}", file=sys.stderr)
              return 2

      blocks = build_blocks(read_source(jd_path), "JD", "jd")
      blocks += build_blocks(read_source(cv_path), "CV", "cv")
      payload = {
          "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "sources": {
              "jd": {"path": str(jd_path), "sha256": journal.sha256_file(jd_path)},
              "cv": {"path": str(cv_path), "sha256": journal.sha256_file(cv_path)},
          },
          "blocks": blocks,
      }
      out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
      journal.receipt(
          workspace, "evidence_blocks",
          {"jd": payload["sources"]["jd"]["sha256"], "cv": payload["sources"]["cv"]["sha256"]},
          "produced", [f"BLOCKS: {len(blocks)}"])
      print(f"BLOCKS: {len(blocks)} written to {out_path}")
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_evidence_blocks.py -q`
  Expected: PASS (11 passed)

- [ ] **Step 5: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add scripts/evidence_blocks.py scripts/tests/conftest.py scripts/tests/test_evidence_blocks.py
  git commit -m "assess: evidence-block chunker with CJK-safe character counting"
  ```

---

### Task 2: Evidence-reference resolution — drop, don't fail

**Files:**
- Create: `scripts/check_evidence_refs.py`
- Test: `scripts/tests/test_check_evidence_refs.py`

**Interfaces:**
- Consumes: `journal.receipt(...)`, `journal.sha256_file(path)`; the `evidence-blocks.json` shape produced by Task 1.
- Produces:
  - `REF_RE = re.compile(r"\b(?:CV|JD)-\d{3}\b")`
  - `load_block_ids(path: pathlib.Path) -> set[str]`
  - `drop_unresolvable_refs(assessment: dict, ids: set[str]) -> tuple[dict, list[str]]` — returns the cleaned assessment and one `DROPPED_REF: ...` finding per removed ref.
  - `strip_block_ids(markdown: str) -> tuple[str, list[str]]` — returns the cleaned markdown and one `STRIPPED_ID: ...` finding per removed token.
  - `main(argv=None) -> int`

**Why this shape.** Rejecting an assessment because its evidence list is empty punishes the honest shape, while an *invented* ref lands in exactly that same empty array and sails through. So both land on the same place: the ref is dropped and listed, and the assessment survives. That is a plausibility bound, not a proof.

The two modes exist because the drop is the mechanism working, not the assessment failing. Default mode rewrites and exits 0. `--check-only` makes no writes and exits 1 if any drop would be needed — that is what `check_assessment.py` calls, so the shipped file is provably clean by the time anyone reads it.

**Where ids may legitimately appear.** The spec requires every counted requirement to be printed *with* its evidence reference so the denominator is auditable. So a markdown **table row** (a line whose stripped form starts with `|`) is exempt from stripping — that is the audit surface. Everywhere else — headlines, rationale, the strategy section, the 30/60/90 table's prose cells, the market-convention standing sentence — a block id is noise to a reader who never sees the block list, and gets removed. Name the thing itself: "the posting's sponsorship line", "your 2023 C++ port".

- [ ] **Step 1: Write the failing test**

  Create `scripts/tests/test_check_evidence_refs.py`:
  ```python
  import json

  import yaml

  import check_evidence_refs as cer

  BLOCKS = {"blocks": [{"id": "CV-001", "source": "cv", "text": "C++ reconstruction pipeline"},
                       {"id": "JD-001", "source": "jd", "text": "Five years of C++"}]}

  CLEAN_YAML = {
      "market": "nl",
      "verdict": "worth_applying",
      "requirements": [
          {"id": "R1", "kind": "must_have", "text": "C++", "level": "required",
           "screening": "weighted", "match": "strong", "recency": "current",
           "effort": "quick", "evidence": [{"ref": "CV-001"}, {"ref": "JD-001"}]},
          {"id": "R2", "kind": "must_have", "text": "Kubernetes", "level": "required",
           "screening": "weighted", "match": "no_evidence", "recency": "undated",
           "effort": "multi_day", "evidence": []},
      ],
  }

  CLEAN_MD = (
      "# Fit assessment\n\n"
      "Your C++ reconstruction work lines up with the posting's C++ requirement.\n\n"
      "| Requirement | match | evidence |\n"
      "|---|---|---|\n"
      "| C++ | strong | CV-001, JD-001 |\n"
      "| Kubernetes | no_evidence | — |\n"
  )


  def _workspace(tmp_path, assessment=None, markdown=None, blocks=None):
      (tmp_path / "evidence-blocks.json").write_text(
          json.dumps(blocks or BLOCKS, ensure_ascii=False), encoding="utf-8")
      (tmp_path / "fit-assessment.yaml").write_text(
          yaml.safe_dump(assessment or CLEAN_YAML, allow_unicode=True), encoding="utf-8")
      (tmp_path / "fit-assessment.md").write_text(
          markdown if markdown is not None else CLEAN_MD, encoding="utf-8")
      return tmp_path


  # ---------- the quiet case, pinned as hard as the firing case ----------

  def test_ordinary_assessment_passes_and_is_left_byte_identical(tmp_path, capsys):
      ws = _workspace(tmp_path)
      before_yaml = (ws / "fit-assessment.yaml").read_bytes()
      before_md = (ws / "fit-assessment.md").read_bytes()
      assert cer.main(["--workspace", str(ws)]) == 0
      assert (ws / "fit-assessment.yaml").read_bytes() == before_yaml
      assert (ws / "fit-assessment.md").read_bytes() == before_md
      out = capsys.readouterr().out
      assert "DROPPED_REF" not in out and "STRIPPED_ID" not in out


  def test_ids_inside_a_markdown_table_row_are_never_stripped():
      cleaned, findings = cer.strip_block_ids("| C++ | strong | CV-001, JD-001 |\n")
      assert cleaned == "| C++ | strong | CV-001, JD-001 |\n"
      assert findings == []


  def test_an_empty_evidence_list_is_not_a_finding():
      _, findings = cer.drop_unresolvable_refs(
          {"requirements": [{"id": "R2", "match": "no_evidence", "evidence": []}]},
          {"CV-001"})
      assert findings == []


  def test_check_only_passes_on_the_clean_workspace(tmp_path):
      ws = _workspace(tmp_path)
      assert cer.main(["--workspace", str(ws), "--check-only"]) == 0


  # ---------- the firing cases ----------

  def test_an_invented_ref_is_dropped_and_listed(tmp_path, capsys):
      assessment = json.loads(json.dumps(CLEAN_YAML))
      assessment["requirements"][0]["evidence"].append({"ref": "CV-042"})
      ws = _workspace(tmp_path, assessment=assessment)
      assert cer.main(["--workspace", str(ws)]) == 0          # dropping is not a failure
      out = capsys.readouterr().out
      assert "DROPPED_REF: CV-042" in out
      rewritten = yaml.safe_load((ws / "fit-assessment.yaml").read_text(encoding="utf-8"))
      refs = [e["ref"] for e in rewritten["requirements"][0]["evidence"]]
      assert refs == ["CV-001", "JD-001"]


  def test_check_only_fails_when_a_ref_would_be_dropped(tmp_path):
      assessment = json.loads(json.dumps(CLEAN_YAML))
      assessment["requirements"][0]["evidence"].append({"ref": "JD-999"})
      ws = _workspace(tmp_path, assessment=assessment)
      before = (ws / "fit-assessment.yaml").read_bytes()
      assert cer.main(["--workspace", str(ws), "--check-only"]) == 1
      assert (ws / "fit-assessment.yaml").read_bytes() == before   # check-only never writes


  def test_a_block_id_in_prose_is_stripped_with_its_brackets():
      cleaned, findings = cer.strip_block_ids(
          "Your C++ port (CV-001) matches the posting (JD-001).\n")
      assert cleaned == "Your C++ port matches the posting.\n"
      assert len(findings) == 2
      assert findings[0].startswith("STRIPPED_ID: ")


  def test_cjk_brackets_around_an_id_are_stripped_too():
      cleaned, _ = cer.strip_block_ids("你的 C++ 经历（CV-001）与岗位要求吻合。\n")
      assert cleaned == "你的 C++ 经历与岗位要求吻合。\n"


  def test_zero_blocks_is_a_hard_failure(tmp_path, capsys):
      ws = _workspace(tmp_path, blocks={"blocks": []})
      assert cer.main(["--workspace", str(ws)]) == 1
      assert "NO_BLOCKS:" in capsys.readouterr().out


  def test_missing_input_exits_two(tmp_path, capsys):
      assert cer.main(["--workspace", str(tmp_path)]) == 2
      assert "evidence-blocks.json" in capsys.readouterr().err


  def test_a_receipt_is_written_exactly_once(tmp_path):
      ws = _workspace(tmp_path)
      cer.main(["--workspace", str(ws)])
      lines = (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
      assert len(lines) == 1
      assert json.loads(lines[0])["gate"] == "check_evidence_refs"
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_evidence_refs.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'check_evidence_refs'`

- [ ] **Step 3: Write minimal implementation**

  Create `scripts/check_evidence_refs.py`:
  ```python
  #!/usr/bin/env python3
  """Resolve every evidence reference, drop the ones that do not resolve, and keep
  block ids out of the prose a reader actually sees.

  Dropping rather than failing is the whole design. An empty evidence list is not an
  error: rejecting it discards an honest analysis, while an INVENTED ref lands in that
  same empty array and sails through. Punishing the honest shape and passing the
  dishonest one is exactly backwards, so both land on [].

  Stripping ids from prose is belt-and-braces. The mode file asks the model not to write
  them there and it mostly complies, which is exactly the problem: a rule that holds most
  of the time still ships the defect, and only this layer can stop it. Grounding is
  unaffected -- refs travel in the evidence lists, and in the requirement table, which is
  the one place a reader is meant to see them because it is what makes the denominator
  auditable.
  """
  from __future__ import annotations

  import argparse
  import json
  import pathlib
  import re
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import journal  # noqa: E402
  import yaml  # noqa: E402

  REF_RE = re.compile(r"\b(?:CV|JD)-\d{3}\b")
  _BRACKETED = re.compile(
      r"[\(（\[【]\s*(?:CV|JD)-\d{3}(?:\s*[,、;；]\s*(?:CV|JD)-\d{3})*\s*[\)）\]】]")


  def load_block_ids(path: pathlib.Path) -> set[str]:
      data = json.loads(path.read_text(encoding="utf-8"))
      return {block["id"] for block in data.get("blocks", [])}


  def drop_unresolvable_refs(assessment: dict, ids: set[str]) -> tuple[dict, list[str]]:
      findings: list[str] = []
      for row in assessment.get("requirements") or []:
          kept = []
          for item in row.get("evidence") or []:
              ref = str(item.get("ref", "")).strip()
              if ref in ids:
                  kept.append(item)
              else:
                  findings.append(
                      f"DROPPED_REF: {ref or '<empty>'} in requirement "
                      f"{row.get('id', '?')} does not name an existing block")
          if "evidence" in row or kept:
              row["evidence"] = kept
      for condition in assessment.get("stated_conditions") or []:
          kept = []
          for item in condition.get("evidence") or []:
              ref = str(item.get("ref", "")).strip()
              if ref in ids:
                  kept.append(item)
              else:
                  findings.append(
                      f"DROPPED_REF: {ref or '<empty>'} in stated_conditions "
                      f"({condition.get('type', '?')}) does not name an existing block")
          condition["evidence"] = kept
      return assessment, findings


  def strip_block_ids(markdown: str) -> tuple[str, list[str]]:
      findings: list[str] = []
      out_lines: list[str] = []
      for number, line in enumerate(markdown.splitlines(keepends=True), start=1):
          if line.lstrip().startswith("|"):
              out_lines.append(line)          # the auditable requirement table
              continue
          found = REF_RE.findall(line)
          if not found:
              out_lines.append(line)
              continue
          for ref in found:
              findings.append(
                  f"STRIPPED_ID: {ref} appeared in reader-facing prose at line {number}; "
                  f"name the thing itself instead")
          cleaned = _BRACKETED.sub("", line)
          cleaned = REF_RE.sub("", cleaned)
          cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
          cleaned = re.sub(r" +([,.;:!?，。；：！？）】])", r"\1", cleaned)
          cleaned = re.sub(r"([（【(\[]) +", r"\1", cleaned)
          cleaned = re.sub(r"[ \t]+(\n)", r"\1", cleaned)
          out_lines.append(cleaned)
      return "".join(out_lines), findings


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="Resolve or drop evidence references.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      parser.add_argument("--check-only", action="store_true",
                          help="make no writes; exit 1 if any drop or strip would happen")
      args = parser.parse_args(argv)

      workspace = args.workspace
      blocks_path = workspace / "evidence-blocks.json"
      yaml_path = workspace / "fit-assessment.yaml"
      md_path = workspace / "fit-assessment.md"
      for path in (blocks_path, yaml_path):
          if not path.exists():
              print(f"cannot run: {path.name} not found at {path}", file=sys.stderr)
              return 2

      ids = load_block_ids(blocks_path)
      findings: list[str] = []
      if not ids:
          findings.append("NO_BLOCKS: evidence-blocks.json holds no blocks; "
                          "re-run evidence_blocks.py before assessing")

      assessment = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
      assessment, ref_findings = drop_unresolvable_refs(assessment, ids)
      findings += ref_findings

      markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
      cleaned_md, md_findings = strip_block_ids(markdown)
      findings += md_findings

      if not args.check_only:
          if ref_findings:
              yaml_path.write_text(
                  yaml.safe_dump(assessment, allow_unicode=True, sort_keys=False),
                  encoding="utf-8")
          if md_findings:
              md_path.write_text(cleaned_md, encoding="utf-8")

      hard_failure = any(f.startswith("NO_BLOCKS:") for f in findings)
      failed = hard_failure or (args.check_only and bool(findings))
      for finding in findings:
          print(finding)
      journal.receipt(
          workspace, "check_evidence_refs",
          {"evidence-blocks.json": journal.sha256_file(blocks_path),
           "fit-assessment.yaml": journal.sha256_file(yaml_path)},
          "fail" if failed else ("pass" if args.check_only else "reported"),
          findings)
      return 1 if failed else 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_evidence_refs.py -q`
  Expected: PASS (11 passed)

- [ ] **Step 5: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add scripts/check_evidence_refs.py scripts/tests/test_check_evidence_refs.py
  git commit -m "assess: resolve-or-drop evidence refs, strip block ids from prose"
  ```

---

### Task 3: The anti-prediction lint

**Files:**
- Create: `scripts/lint_no_prediction.py`
- Test: `scripts/tests/test_lint_no_prediction.py`

**Interfaces:**
- Consumes: `journal.receipt(...)`, `journal.sha256_file(path)`.
- Produces:
  - `VERDICT_LABELS: tuple[str, ...]` — every zh and en verdict token, masked before scanning.
  - `mask_exempt_spans(line: str) -> str` — same-length masking of URLs and verdict labels.
  - `blockquote_allowlist(lines: list[str]) -> set[int]` — 0-based line numbers exempted by a cited published employer rubric.
  - `scan_text(text: str, label: str) -> list[str]` — findings, each prefixed `PERCENT:`, `SCORE_PATTERN:` or `PREDICTION_WORD:`.
  - `target_files(workspace: pathlib.Path) -> list[pathlib.Path]`
  - `main(argv=None) -> int`

**The two traps this lint has to survive.**

1. **The verdict vocabulary contains a banned word.** The human-facing zh label for `likely_screen_out` is 大概率被筛掉, which literally contains 概率. A naive scan fires on every assessment that reaches that verdict — the most common one this skill will ever print. So every verdict label is masked out *before* scanning. A bare 大概率 elsewhere still fires; only the exact label is exempt.
2. **URLs carry digits and percent-encoding.** `https://www.gov.uk/2026/08/09/foo` matches the `n/m` score pattern, and `%20` matches the percent ban. A URL is an identifier, not a claim — the same reasoning that exempts a citation's title in the market tables. URLs are masked before scanning.

**The one allowlist.** Where an employer publishes its own rubric (UK Civil Service Success Profiles named in the advert, an NHS values framework, a university person specification), the skill may walk the candidate through *that* scale — in the employer's own wording, with the source named, as a list of what the panel was asked to look for. Quoting an employer's scale is reporting; treating it as a conclusion is inventing. Mechanically: a contiguous run of blockquote lines is exempt when the run's own last line, or one of the two lines after it, is an attribution line carrying an `https://` URL.

- [ ] **Step 1: Write the failing test**

  Create `scripts/tests/test_lint_no_prediction.py` (note: this listing is fenced with
  **four** backticks because the fixture itself contains a three-backtick block — the real
  `fit-assessment.md` prints the counted facts inside a fence, and the lint must be tested
  against the shape it will actually meet):
  ````python
  import json

  import lint_no_prediction as lint

  ORDINARY = """# Fit assessment — MR Reconstruction Scientist

  ```
  must-have 强证据：   8 of 11   （partial 2，gap 1，无证据 0）
  核心职责已证实：     4 of 6
  职级匹配：           平级
  可补缺口所需投入：   一晚
  投递建议：           大概率被筛掉
  ```

  ⚠️ 以上是对证据的清点，不是对结果的预判。每一项都连同它的证据引用一起印出，分母可以逐条审计；
  本 skill 不给出面试或录用的可能性估计，也不给 0–100 分。要不要投，由你决定。

  | Requirement | level | screening | match |
  |---|---|---|---|
  | C++ | required | knockout | strong |
  | Kubernetes | required | weighted | gap |

  Source of the posting: https://www.gov.uk/2026/08/09/example-vacancy
  """

  CITED_RUBRIC = """The advert names the employer's own framework, so here is that scale
  in its own words:

  > Level 3 — Demonstrates the behaviour consistently; 100% of the named criteria are
  > evidenced with examples.
  > — Civil Service, Success Profiles: Behaviours, https://www.gov.uk/government/publications/success-profiles

  That is the list the panel was asked to look for. It is not a statement about you.
  """


  def _write(tmp_path, name, text):
      path = tmp_path / name
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(text, encoding="utf-8")
      return path


  # ---------- the quiet case, pinned as hard as the firing case ----------

  def test_an_ordinary_assessment_passes(tmp_path, capsys):
      _write(tmp_path, "fit-assessment.md", ORDINARY)
      assert lint.main(["--workspace", str(tmp_path)]) == 0
      assert capsys.readouterr().out.strip() == ""


  def test_the_counted_facts_line_is_not_a_score_pattern():
      assert lint.scan_text("must-have 强证据：   8 of 11", "x") == []


  def test_the_likely_screen_out_label_does_not_fire_its_own_lint():
      assert lint.scan_text("投递建议：大概率被筛掉", "x") == []
      assert lint.scan_text("APPLY VERDICT: likely_screen_out", "x") == []


  def test_the_required_disclaimer_passes():
      zh = ("⚠️ 以上是对证据的清点，不是对结果的预判。本 skill 不给出面试或录用的可能性估计，"
            "也不给 0–100 分。")
      en = ("This is a count of evidence, not a forecast of the outcome. This skill states "
            "no interview or hiring outcome estimate and no 0–100 score.")
      assert lint.scan_text(zh, "x") == []
      assert lint.scan_text(en, "x") == []


  def test_a_url_with_a_date_path_is_not_a_score_pattern():
      assert lint.scan_text("See https://www.gov.uk/2026/08/09/example", "x") == []


  def test_a_url_with_percent_encoding_is_not_a_percent():
      assert lint.scan_text("See https://example.org/a%20b", "x") == []


  def test_the_word_strong_as_a_match_label_does_not_fire():
      assert lint.scan_text("| C++ | required | knockout | strong |", "x") == []
      assert lint.scan_text("Your C++ evidence is strong and recent.", "x") == []


  def test_a_cited_published_employer_rubric_is_allowed(tmp_path):
      _write(tmp_path, "fit-assessment.md", CITED_RUBRIC)
      assert lint.main(["--workspace", str(tmp_path)]) == 0


  # ---------- the firing cases ----------

  def test_a_percentage_fires():
      findings = lint.scan_text("Keyword coverage is 73% of the must-haves.", "x")
      assert len(findings) == 1 and findings[0].startswith("PERCENT:")


  def test_a_slash_score_fires():
      findings = lint.scan_text("You score 8/11 on the requirements.", "x")
      assert len(findings) == 1 and findings[0].startswith("SCORE_PATTERN:")


  def test_english_prediction_vocabulary_fires():
      for text in ["You are a strong candidate for this role.",
                   "Your chances here are good.",
                   "The probability of an interview is high.",
                   "The odds are in your favour.",
                   "You are likely to be interviewed.",
                   "This CV would pass the screen."]:
          findings = lint.scan_text(text, "x")
          assert findings and findings[0].startswith("PREDICTION_WORD:"), text


  def test_chinese_prediction_vocabulary_fires():
      for text in ["面试概率不低。", "这个岗位的通过率很高。", "命中率一般。", "录取率未知。"]:
          findings = lint.scan_text(text, "x")
          assert findings and findings[0].startswith("PREDICTION_WORD:"), text


  def test_a_blockquote_without_an_attribution_url_is_not_allowed():
      text = ("> Level 3 — 100% of the named criteria are evidenced.\n"
              "> — Civil Service, Success Profiles\n\nSo that is the bar.\n")
      findings = lint.scan_text(text, "x")
      assert findings and findings[0].startswith("PERCENT:")


  def test_the_gate_scans_every_named_surface(tmp_path):
      _write(tmp_path, "shortlist.md", "Interview probability: high.\n")
      _write(tmp_path, "mock/assessment-1.md", "You are a weak candidate.\n")
      _write(tmp_path, "mock/cheatsheet.md", "Coverage 9/10.\n")
      assert lint.main(["--workspace", str(tmp_path)]) == 1
      findings = [json.loads(line) for line in
                  (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()
                  ][0]["findings"]
      surfaces = {f.split(" ", 1)[1].split(":")[0] for f in findings}
      assert surfaces == {"shortlist.md", "mock/assessment-1.md", "mock/cheatsheet.md"}


  def test_no_target_files_exits_two(tmp_path, capsys):
      assert lint.main(["--workspace", str(tmp_path)]) == 2
      assert "no rendered file" in capsys.readouterr().err
  ````

- [ ] **Step 2: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_lint_no_prediction.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'lint_no_prediction'`

- [ ] **Step 3: Write minimal implementation**

  Create `scripts/lint_no_prediction.py`:
  ```python
  #!/usr/bin/env python3
  """Ban invented numbers and prediction vocabulary from anything a reader sees.

  There is no data behind "45-65% chance of an interview"; it is a made-up number that
  reads with the authority of arithmetic. Collapsing strong / partial / gap into one
  score needs a weight for a partial match, and any weight would be invented too. So the
  conclusion is a word, the counts are printed with the evidence behind each row, and
  this lint keeps the made-up numbers out.

  Two things are masked before any scan, and both matter:

  * The verdict labels. 大概率被筛掉 -- the human-facing label for likely_screen_out --
    literally contains 概率. Without masking, this lint fires on the most common verdict
    the skill prints, and a gate that cries wolf on ordinary output is one people switch
    off. A bare 大概率 elsewhere still fires.
  * URLs. https://www.gov.uk/2026/08/09/x matches the n/m score pattern and %20 matches
    the percent ban. A URL is an identifier, not a claim -- the same reason a citation's
    title is exempt from the digit ban in the market tables.

  The one allowlist: where an employer publishes its own rubric, the skill may walk the
  candidate through THAT scale, in the employer's wording, with the source named. Quoting
  an employer's scale is reporting. Treating it as a conclusion is inventing.
  """
  from __future__ import annotations

  import argparse
  import pathlib
  import re
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import journal  # noqa: E402

  VERDICT_LABELS = (
      "强烈建议投", "值得投", "可以冲刺", "大概率被筛掉", "硬性阻断", "证据不足—不出结论",
      "strong_apply", "worth_applying", "stretch", "likely_screen_out", "blocked",
      "insufficient_evidence",
  )

  _URL = re.compile(r"https?://\S+")
  _PERCENT = re.compile(r"%")
  _SCORE = re.compile(r"\b\d+\s*/\s*\d+\b")
  _WORDS = re.compile(
      r"\bchances?\b|\bprobabilit(?:y|ies)\b|\bodds\b"
      r"|\blikely to be (?:hired|interviewed|shortlisted|rejected)\b"
      r"|\b(?:strong|weak) candidate\b|\bwould pass\b|\bno-hire\b"
      r"|概率|通过率|命中率|录取率",
      re.IGNORECASE)
  _ATTRIBUTION = re.compile(r"^\s*>?\s*(?:—|--|-|Source:|来源[:：])\s+.*https?://\S+")

  CHECKS = (("PERCENT", _PERCENT), ("SCORE_PATTERN", _SCORE), ("PREDICTION_WORD", _WORDS))


  def mask_exempt_spans(line: str) -> str:
      """Blank out URLs and verdict labels, preserving length so columns stay honest."""
      masked = _URL.sub(lambda m: " " * len(m.group(0)), line)
      for label in VERDICT_LABELS:
          if label in masked:
              masked = masked.replace(label, " " * len(label))
      return masked


  def blockquote_allowlist(lines: list[str]) -> set[int]:
      exempt: set[int] = set()
      index = 0
      while index < len(lines):
          if not lines[index].lstrip().startswith(">"):
              index += 1
              continue
          start = index
          while index < len(lines) and lines[index].lstrip().startswith(">"):
              index += 1
          end = index - 1
          window = [lines[end]] + lines[end + 1:end + 3]
          if any(_ATTRIBUTION.match(candidate) for candidate in window):
              exempt.update(range(start, end + 1))
      return exempt


  def scan_text(text: str, label: str) -> list[str]:
      lines = text.splitlines()
      exempt = blockquote_allowlist(lines)
      findings: list[str] = []
      for number, line in enumerate(lines):
          if number in exempt:
              continue
          masked = mask_exempt_spans(line)
          for code, pattern in CHECKS:
              for match in pattern.finditer(masked):
                  original = line[match.start():match.end()]
                  findings.append(f"{code}: {label}:{number + 1}: {original!r} "
                                  f"in {line.strip()!r}")
      return findings


  def target_files(workspace: pathlib.Path) -> list[pathlib.Path]:
      found = []
      for relative in ("fit-assessment.md", "shortlist.md", "cheatsheet.md",
                       "mock/cheatsheet.md"):
          path = workspace / relative
          if path.exists():
              found.append(path)
      found += sorted((workspace / "mock").glob("assessment-*.md"))
      return found


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="Ban predictions and invented numbers.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      parser.add_argument("--files", nargs="*", type=pathlib.Path, default=None)
      args = parser.parse_args(argv)

      workspace = args.workspace
      files = list(args.files) if args.files else target_files(workspace)
      if not files:
          print(f"cannot run: no rendered file to scan under {workspace}", file=sys.stderr)
          return 2

      findings: list[str] = []
      hashes: dict[str, str] = {}
      for path in files:
          try:
              relative = str(path.relative_to(workspace))
          except ValueError:
              relative = path.name
          hashes[relative] = journal.sha256_file(path)
          findings += scan_text(path.read_text(encoding="utf-8"), relative)

      for finding in findings:
          print(finding)
      journal.receipt(workspace, "lint_no_prediction", hashes,
                      "fail" if findings else "pass", findings)
      return 1 if findings else 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_lint_no_prediction.py -q`
  Expected: PASS (14 passed)

- [ ] **Step 5: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add scripts/lint_no_prediction.py scripts/tests/test_lint_no_prediction.py
  git commit -m "assess: anti-prediction lint with verdict-label and URL masking"
  ```

---

### Task 4: Deterministic contradiction detectors

**Files:**
- Create: `scripts/consistency.py`
- Test: `scripts/tests/test_consistency.py`

**Interfaces:**
- Consumes: `journal.receipt(...)`, `journal.sha256_file(path)`; the `fit-assessment.yaml` schema in Global Constraints.
- Produces:
  - `CONFLICT_EFFORTS = ("multi_day", "not_closable")`
  - `verdict_effort_conflict(assessment: dict) -> bool`
  - `loose_knockouts(rows: list[dict]) -> int` — the count when it exceeds two, else `0`
  - `uncovered_gap_actions(rows: list[dict], actions: list[dict]) -> dict | None` — `{"gaps": int, "actions": int}` or `None`
  - `work_authorization_alignment(condition: dict, declared_status: str) -> str | None` — `"conflict" | "supported" | "verify" | None`
  - `overall_authorization_alignment(conditions: list[dict], declared_status: str) -> str | None`
  - `notices(assessment: dict) -> list[dict]` — each `{"code", "anchor_zh", "anchor_en", "text_zh", "text_en"}`
  - `NOTICE_CODES = ("NOTICE_VERDICT_EFFORT", "NOTICE_LOOSE_KNOCKOUTS", "NOTICE_GAP_ACTIONS", "NOTICE_WORK_AUTH_CONFLICT", "NOTICE_WORK_AUTH_VERIFY")`
  - `main(argv=None) -> int`

**Why it reports and never repairs.** Code can see that two fields disagree; it cannot see which one is right, and picking silently would replace a visible contradiction with an invisible guess. Every check here fires on a countable fact, never on meaning, so a false positive costs the reader one line of caution and never suppresses a finding.

**Re-anchoring notes (these differ from marketfit on purpose — do not "fix" them back):**
- `verdict_effort_conflict` fires on `multi_day` and `not_closable` only, **not** on `evening`. In marketfit the effort estimate priced the whole tailoring job, so an evening contradicted a strong fit. Here `effort` prices closing the *gaps*, and a strong_apply whose remaining gaps take an evening is an ordinary, honest assessment. Including `evening` would fire on a large share of good assessments.
- `work_authorization_alignment` returns `"verify"`, never `"conflict"`, for `requires_existing` × `student_or_graduate` and `requires_existing` × `temporary_route`. Calling that a conflict would wrongly kill viable applications, so it asks. The output is always "these two appear to conflict, check it yourself", never "you are not eligible".
- `NOTICE_VERDICT_EFFORT` is suppressed when `NOTICE_WORK_AUTH_CONFLICT` fired: that notice is already telling the reader the verdict above it does not hold, and two hedges on one line teach the reader to skip both.

- [ ] **Step 1: Write the failing test**

  Create `scripts/tests/test_consistency.py`:
  ```python
  import json

  import yaml

  import consistency as cons


  def row(**kwargs):
      base = {"id": "R1", "kind": "must_have", "text": "x", "level": "required",
              "screening": "weighted", "match": "strong", "recency": "current",
              "effort": "quick", "how_to_close": "", "evidence": [{"ref": "CV-001"}]}
      base.update(kwargs)
      return base


  # ---------- check 1: verdict vs effort ----------

  def test_strong_apply_priced_at_days_is_a_conflict():
      assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                           "effort": "multi_day"}) is True
      assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                           "effort": "not_closable"}) is True


  def test_strong_apply_priced_at_an_evening_is_NOT_a_conflict():
      # Deliberate divergence from marketfit: effort here prices closing the gaps, and a
      # strong apply with an evening of work left is an ordinary honest assessment.
      assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                           "effort": "evening"}) is False


  def test_other_verdicts_and_missing_effort_are_never_conflicts():
      for verdict in ("worth_applying", "stretch", "likely_screen_out", "blocked",
                      "insufficient_evidence"):
          assert cons.verdict_effort_conflict({"verdict": verdict,
                                               "effort": "not_closable"}) is False
      assert cons.verdict_effort_conflict({"verdict": "strong_apply"}) is False
      assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                           "effort": "wobbly"}) is False
      assert cons.verdict_effort_conflict({}) is False


  # ---------- check 2: loose knockouts ----------

  def test_two_knockouts_are_credible_and_report_zero():
      rows = [row(screening="knockout"), row(screening="knockout"),
              row(screening="weighted"), row(screening="nice_to_have")]
      assert cons.loose_knockouts(rows) == 0


  def test_three_knockouts_report_the_count():
      assert cons.loose_knockouts([row(screening="knockout")] * 3) == 3


  def test_no_rows_report_zero():
      assert cons.loose_knockouts([]) == 0
      assert cons.loose_knockouts(None) == 0


  # ---------- check 3: closable gaps vs actions ----------

  def test_a_plan_at_least_as_long_as_its_closable_gaps_reports_nothing():
      rows = [row(match="gap", effort="evening", how_to_close="do the thing"),
              row(match="partial", effort="quick", how_to_close="do the other thing")]
      actions = [{"action": "a", "acceptance": "x", "when": "before_apply"},
                 {"action": "b", "acceptance": "y", "when": "before_apply"}]
      assert cons.uncovered_gap_actions(rows, actions) is None


  def test_a_not_closable_gap_does_not_count_against_the_plan():
      rows = [row(match="gap", effort="not_closable", how_to_close="cannot")]
      assert cons.uncovered_gap_actions(rows, []) is None


  def test_a_gap_with_no_how_to_close_does_not_count_against_the_plan():
      rows = [row(match="gap", effort="evening", how_to_close="")]
      assert cons.uncovered_gap_actions(rows, []) is None


  def test_more_closable_gaps_than_actions_reports_both_numbers():
      rows = [row(match="gap", effort="evening", how_to_close="one"),
              row(match="gap", effort="quick", how_to_close="two")]
      assert cons.uncovered_gap_actions(rows, [{"action": "a"}]) == {"gaps": 2, "actions": 1}


  # ---------- check 4: work authorization ----------

  def test_requires_existing_against_needs_sponsorship_is_a_conflict():
      assert cons.work_authorization_alignment(
          {"type": "sponsorship", "stance": "requires_existing"},
          "needs_sponsorship") == "conflict"


  def test_offers_support_against_needs_sponsorship_is_supported():
      assert cons.work_authorization_alignment(
          {"type": "sponsorship", "stance": "offers_support"},
          "needs_sponsorship") == "supported"


  def test_a_student_or_temporary_route_asks_rather_than_kills():
      for status in ("student_or_graduate", "temporary_route"):
          assert cons.work_authorization_alignment(
              {"type": "work_authorization", "stance": "requires_existing"},
              status) == "verify"


  def test_unknown_status_and_unrelated_condition_types_never_fire():
      assert cons.work_authorization_alignment(
          {"type": "sponsorship", "stance": "requires_existing"}, "unknown") is None
      assert cons.work_authorization_alignment(
          {"type": "onsite_location", "stance": "requires_existing"},
          "needs_sponsorship") is None
      assert cons.work_authorization_alignment(
          {"type": "sponsorship", "stance": "unclear"}, "needs_sponsorship") is None
      assert cons.work_authorization_alignment(
          {"type": "sponsorship", "stance": "requires_existing"}, "authorized") is None


  def test_one_conflict_outranks_everything():
      conditions = [{"type": "sponsorship", "stance": "offers_support"},
                    {"type": "citizenship", "stance": "requires_existing"}]
      assert cons.overall_authorization_alignment(
          conditions, "needs_sponsorship") == "conflict"


  # ---------- notices ----------

  def test_an_ordinary_assessment_produces_no_notices():
      assessment = {"verdict": "worth_applying", "effort": "evening",
                    "declared_work_status": "authorized",
                    "stated_conditions": [{"type": "sponsorship", "stance": "offers_support"}],
                    "requirements": [row(screening="knockout"), row()],
                    "actions": [{"action": "a"}]}
      assert cons.notices(assessment) == []


  def test_the_verdict_effort_notice_is_suppressed_by_a_work_auth_conflict():
      assessment = {"verdict": "strong_apply", "effort": "not_closable",
                    "declared_work_status": "needs_sponsorship",
                    "stated_conditions": [{"type": "sponsorship",
                                           "stance": "requires_existing"}],
                    "requirements": [], "actions": []}
      codes = [n["code"] for n in cons.notices(assessment)]
      assert codes == ["NOTICE_WORK_AUTH_CONFLICT"]


  def test_every_notice_carries_both_languages_and_an_anchor():
      assessment = {"verdict": "strong_apply", "effort": "multi_day",
                    "declared_work_status": "unknown",
                    "requirements": [row(screening="knockout")] * 3, "actions": []}
      produced = cons.notices(assessment)
      assert [n["code"] for n in produced] == ["NOTICE_VERDICT_EFFORT",
                                               "NOTICE_LOOSE_KNOCKOUTS"]
      for notice in produced:
          assert notice["anchor_zh"] and notice["anchor_zh"] in notice["text_zh"]
          assert notice["anchor_en"] and notice["anchor_en"] in notice["text_en"]
          assert notice["code"] in cons.NOTICE_CODES


  # ---------- the CLI ----------

  def test_the_cli_reports_without_failing(tmp_path, capsys):
      assessment = {"verdict": "strong_apply", "effort": "multi_day",
                    "declared_work_status": "unknown", "requirements": [], "actions": []}
      (tmp_path / "fit-assessment.yaml").write_text(
          yaml.safe_dump(assessment, allow_unicode=True), encoding="utf-8")
      # A fired notice is a finding ABOUT the assessment, not a failure OF this script.
      assert cons.main(["--workspace", str(tmp_path)]) == 0
      assert "NOTICE_VERDICT_EFFORT" in capsys.readouterr().out
      record = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
      assert record["gate"] == "consistency" and record["verdict"] == "reported"


  def test_the_cli_exits_two_without_an_assessment(tmp_path, capsys):
      assert cons.main(["--workspace", str(tmp_path)]) == 2
      assert "fit-assessment.yaml" in capsys.readouterr().err
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_consistency.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'consistency'`

- [ ] **Step 3: Write minimal implementation**

  Create `scripts/consistency.py`:
  ```python
  #!/usr/bin/env python3
  """Contradictions inside a single assessment, found in code rather than asked for in
  prose. Pure, deterministic, and deliberately not the model's job to police.

  The mode file already states each of these rules, and the model already follows them
  most of the time. That is exactly the problem this file exists for: a rule obeyed most
  of the time still ships the defect, and this one ships it invisibly. Nothing about a
  strong_apply priced at three days looks broken on screen -- it looks like an assessment.
  The reader has no way to know the two halves were produced by a model contradicting
  itself, so they average them, and the average is not a judgement anyone made.

  Every check reports rather than repairs. Code can see that two fields disagree; it
  cannot see which one is right, and picking silently would replace a visible
  contradiction with an invisible guess.

  These are deliberately the checks that survive being wrong. Each fires on a countable
  fact, never on meaning, so a false positive costs the reader one line of caution and
  never suppresses a finding.
  """
  from __future__ import annotations

  import argparse
  import pathlib
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import journal  # noqa: E402
  import yaml  # noqa: E402

  CONFLICT_EFFORTS = ("multi_day", "not_closable")
  AUTH_CONDITION_TYPES = ("sponsorship", "work_authorization", "citizenship")

  NOTICE_CODES = ("NOTICE_VERDICT_EFFORT", "NOTICE_LOOSE_KNOCKOUTS", "NOTICE_GAP_ACTIONS",
                  "NOTICE_WORK_AUTH_CONFLICT", "NOTICE_WORK_AUTH_VERIFY")


  def verdict_effort_conflict(assessment: dict | None) -> bool:
      """A verdict saying the CV already covers what this posting screens on, beside an
      effort estimate saying the remaining gaps take days or cannot be closed at all.

      `evening` is NOT included, and that is a deliberate divergence from the extension
      this is ported from. There, effort priced the whole tailoring job. Here it prices
      closing the gaps, and a strong apply with an evening of work left is an ordinary,
      honest assessment. A check that fired on those would be ignored within a week.
      """
      if not assessment or assessment.get("verdict") != "strong_apply":
          return False
      return assessment.get("effort") in CONFLICT_EFFORTS


  def loose_knockouts(rows: list[dict] | None) -> int:
      """How many requirements were marked hard filters, when that count is high enough
      to mean the rule was applied loosely.

      A knockout is a condition a recruiter can check without judgement and which ends
      the application on its own. Postings label half their list "required", and the whole
      point of the screening axis is to be the smaller, harder list underneath that label.
      When it stops being smaller it has collapsed back into the thing it was separating
      from, and the ordering built on it is no longer a screening order.

      Not reclassified: code can count them but cannot tell which one is genuine.
      """
      count = sum(1 for item in (rows or []) if (item or {}).get("screening") == "knockout")
      return count if count > 2 else 0


  def uncovered_gap_actions(rows: list[dict] | None,
                            actions: list[dict] | None) -> dict | None:
      """Gaps that claim a pre-application fix while the plan is too short to hold them.

      `actions` is the single authoritative to-do list; every instruction implied by a
      row's how_to_close is supposed to appear there exactly once. Matching them by
      meaning would need the model back and would produce false positives on wording
      alone, so only the degenerate case is checked: more closable gaps than there are
      actions in total. That is narrower than the rule it guards, and it is the part of
      the rule that can be checked without guessing.
      """
      closable = sum(1 for item in (rows or [])
                     if (item or {}).get("match") in ("gap", "partial")
                     and (item or {}).get("effort") in ("quick", "evening", "multi_day")
                     and str((item or {}).get("how_to_close") or "").strip())
      total = len(actions or [])
      return {"gaps": closable, "actions": total} if closable > total else None


  def work_authorization_alignment(condition: dict | None,
                                   declared_status: str | None) -> str | None:
      """Arithmetic on two self-reported facts, in code because the answer must be the
      same every run. A model asked to make this comparison gets it right most of the
      time, and the case it gets wrong is the one where the job is impossible for the
      reader.

      The output is always "these two appear to conflict, check it yourself", never
      "you are not eligible".
      """
      condition = condition or {}
      if condition.get("type") not in AUTH_CONDITION_TYPES:
          return None
      if declared_status in (None, "", "unknown"):
          return None                     # the default must never trigger a downgrade
      stance = condition.get("stance")
      if stance == "offers_support" and declared_status == "needs_sponsorship":
          return "supported"
      if stance == "requires_existing":
          if declared_status == "needs_sponsorship":
              return "conflict"
          if declared_status in ("student_or_graduate", "temporary_route"):
              # Calling this a conflict would wrongly kill viable applications, so it asks.
              return "verify"
      return None


  def overall_authorization_alignment(conditions: list[dict] | None,
                                      declared_status: str | None) -> str | None:
      results = [work_authorization_alignment(c, declared_status) for c in (conditions or [])]
      for level in ("conflict", "verify", "supported"):
          if level in results:
              return level
      return None


  def _notice(code: str, text_zh: str, text_en: str, anchor_zh: str, anchor_en: str) -> dict:
      return {"code": code, "text_zh": text_zh, "text_en": text_en,
              "anchor_zh": anchor_zh, "anchor_en": anchor_en}


  def notices(assessment: dict | None) -> list[dict]:
      assessment = assessment or {}
      rows = assessment.get("requirements") or []
      produced: list[dict] = []

      alignment = overall_authorization_alignment(
          assessment.get("stated_conditions"), assessment.get("declared_work_status"))
      if alignment == "conflict":
          produced.append(_notice(
              "NOTICE_WORK_AUTH_CONFLICT",
              "岗位写明要求已持有工作许可，而你声明需要担保：这两条看起来冲突，请你自己向雇主核实。"
              "本 skill 不判定任何人的法律资格。",
              "The posting requires existing work authorization and you have declared that "
              "you need sponsorship. These two appear to conflict — check it with the "
              "employer yourself. This skill does not decide anyone's legal eligibility.",
              "这两条看起来冲突", "These two appear to conflict"))
      elif alignment == "verify":
          produced.append(_notice(
              "NOTICE_WORK_AUTH_VERIFY",
              "岗位写明要求已持有工作许可，而你走的是学生/毕业生或临时通道：这不一定是冲突，"
              "但要向雇主核实这条通道算不算数。",
              "The posting requires existing work authorization and your route is a "
              "student/graduate or temporary one. That is not necessarily a conflict — ask "
              "the employer whether that route counts.",
              "不一定是冲突", "not necessarily a conflict"))

      if verdict_effort_conflict(assessment) and alignment != "conflict":
          # Suppressed under a work-auth conflict: that notice is already telling the
          # reader the verdict above it does not hold.
          produced.append(_notice(
              "NOTICE_VERDICT_EFFORT",
              "结论与投入互相矛盾：一份已经覆盖了这个岗位筛选项的简历，不该还要数日的投入、"
              "或者根本补不上。请以下面的需求表为准，而不是上面那个词。",
              "The verdict and the effort estimate disagree: a CV that already covers what "
              "this posting screens on should not still need days of work, or work that "
              "cannot be done at all. Weigh the requirement rows below over the word above.",
              "结论与投入互相矛盾", "The verdict and the effort estimate disagree"))

      count = loose_knockouts(rows)
      if count:
          produced.append(_notice(
              "NOTICE_LOOSE_KNOCKOUTS",
              f"有 {count} 条需求被标成了硬性筛选项。多数岗位最多只有一条，"
              f"所以下面的排序请当作近似，而不是真正会把你筛掉的东西。",
              f"{count} requirements are marked hard filters. Most postings have at most "
              f"one, so read the order below as approximate rather than as what actually "
              f"screens you out.",
              "被标成了硬性筛选项", "are marked hard filters"))

      uncovered = uncovered_gap_actions(rows, assessment.get("actions"))
      if uncovered:
          produced.append(_notice(
              "NOTICE_GAP_ACTIONS",
              f"有 {uncovered['gaps']} 个缺口写着可以在投递前补上，"
              f"但行动清单只有 {uncovered['actions']} 条——上面的建议有一部分没有进入这份清单。",
              f"{uncovered['gaps']} gaps say they can be closed before applying, but the "
              f"plan lists {uncovered['actions']} actions — some of the advice above did "
              f"not make it into this list.",
              "没有进入这份清单", "did not make it into this list"))
      return produced


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="Report contradictions in an assessment.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      args = parser.parse_args(argv)

      path = args.workspace / "fit-assessment.yaml"
      if not path.exists():
          print(f"cannot run: fit-assessment.yaml not found at {path}", file=sys.stderr)
          return 2

      assessment = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
      findings = [f"{n['code']}: {n['text_en']}" for n in notices(assessment)]
      for finding in findings:
          print(finding)
      journal.receipt(args.workspace, "consistency",
                      {"fit-assessment.yaml": journal.sha256_file(path)},
                      "reported", findings)
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_consistency.py -q`
  Expected: PASS (20 passed)

- [ ] **Step 5: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add scripts/consistency.py scripts/tests/test_consistency.py
  git commit -m "assess: deterministic contradiction detectors, report-never-repair"
  ```

---

### Task 5: `count_coverage.py` — the only count-producing path

**Files:**
- Create: `scripts/count_coverage.py`
- Test: `scripts/tests/test_count_coverage.py`

**Interfaces:**
- Consumes: `journal.receipt(...)`, `journal.sha256_file(path)`; the `fit-assessment.yaml` schema.
- Produces:
  - `LEVEL_DIRECTION_ZH`, `EFFORT_ZH`, `VERDICT_ZH` — the enum→label maps (also used by `modes/assess.md`).
  - `coverage(rows: list[dict]) -> dict` — `{"must_total", "must_strong", "must_partial", "must_gap", "must_no_evidence", "resp_total", "resp_demonstrated", "invalid"}`; `invalid` is a list of finding strings.
  - `render_block(assessment: dict, counts: dict, lang: str = "zh") -> str` — the exact fenced-block body, no fence markers.
  - `main(argv=None) -> int` — prints the block, writes `<workspace>/coverage.json`.

**Why one path.** The old skill had two coverage formulas over the same must-have list; they always disagreed, and prose was left to manage the disagreement. There is exactly one function here, one rendered block, and `check_assessment.py` requires the rendered block to be byte-identical to what this function produces. A second number cannot survive that.

**Counting rules (each is a test):**
- `must_strong` counts `match == "strong"` only. `partial` and `gap` are never merged into a covered number.
- `match: "strong"` with `recency: "dated"` counts as **partial**, not strong. Evidence that is only dated satisfies the keyword and reads as rusty to a human.
- `recency: "undated"` does **not** downgrade. A CV that omits dates is a formatting fact, not a staleness fact.
- The invariant `must_strong + must_partial + must_gap + must_no_evidence == must_total` is asserted. A break means a row carries a value outside the enum, which is a `INVALID_MATCH` / `INVALID_RECENCY` finding and exit 1 — never a silent substitution. Substituting a value instead of dropping the row would put a claim we invented into the model's mouth: `no_evidence` is a finding about the CV, not a default.

- [ ] **Step 1: Write the failing test**

  Create `scripts/tests/test_count_coverage.py`:
  ```python
  import json

  import yaml

  import count_coverage as cc


  def row(**kwargs):
      base = {"id": "R", "kind": "must_have", "text": "x", "level": "required",
              "screening": "weighted", "match": "strong", "recency": "current",
              "effort": "quick", "evidence": [{"ref": "CV-001"}]}
      base.update(kwargs)
      return base


  ASSESSMENT = {
      "verdict": "worth_applying", "effort": "evening", "level_direction": "lateral",
      "requirements": [
          row(match="strong", recency="current"),
          row(match="strong", recency="undated"),
          row(match="strong", recency="dated"),
          row(match="partial"),
          row(match="gap"),
          row(match="no_evidence", evidence=[]),
          row(kind="responsibility", match="strong", recency="recent"),
          row(kind="responsibility", match="strong", recency="dated"),
          row(kind="responsibility", match="partial"),
      ],
  }


  def test_only_strong_counts_as_strong():
      counts = cc.coverage(ASSESSMENT["requirements"])
      assert counts["must_total"] == 6
      assert counts["must_strong"] == 2          # current + undated
      assert counts["must_partial"] == 2         # partial + strong-but-dated
      assert counts["must_gap"] == 1
      assert counts["must_no_evidence"] == 1
      assert counts["invalid"] == []


  def test_undated_evidence_is_not_downgraded():
      counts = cc.coverage([row(match="strong", recency="undated")])
      assert counts["must_strong"] == 1 and counts["must_partial"] == 0


  def test_dated_evidence_is_downgraded_to_partial():
      counts = cc.coverage([row(match="strong", recency="dated")])
      assert counts["must_strong"] == 0 and counts["must_partial"] == 1


  def test_responsibilities_use_the_same_vocabulary():
      counts = cc.coverage(ASSESSMENT["requirements"])
      assert counts["resp_total"] == 3
      assert counts["resp_demonstrated"] == 1    # recent yes, dated no, partial no


  def test_the_parts_always_sum_to_the_whole():
      counts = cc.coverage(ASSESSMENT["requirements"])
      assert (counts["must_strong"] + counts["must_partial"] + counts["must_gap"]
              + counts["must_no_evidence"]) == counts["must_total"]


  def test_an_out_of_enum_match_is_reported_never_substituted():
      counts = cc.coverage([row(match="partly")])
      assert counts["must_total"] == 1
      assert counts["must_strong"] == counts["must_partial"] == 0
      assert any(f.startswith("INVALID_MATCH:") for f in counts["invalid"])


  def test_an_out_of_enum_recency_is_reported():
      counts = cc.coverage([row(match="strong", recency="ancient")])
      assert any(f.startswith("INVALID_RECENCY:") for f in counts["invalid"])


  def test_the_rendered_block_is_stable_and_exact():
      counts = cc.coverage(ASSESSMENT["requirements"])
      block = cc.render_block(ASSESSMENT, counts, "zh")
      assert block == (
          "must-have 强证据：   2 of 6   （partial 2，gap 1，无证据 1）\n"
          "核心职责已证实：     1 of 3\n"
          "职级匹配：           平级\n"
          "可补缺口所需投入：   一晚\n"
          "投递建议：           值得投")
      assert cc.render_block(ASSESSMENT, counts, "zh") == block


  def test_the_english_block_uses_the_same_numbers():
      counts = cc.coverage(ASSESSMENT["requirements"])
      block = cc.render_block(ASSESSMENT, counts, "en")
      assert block == (
          "must-haves strongly evidenced:   2 of 6   (partial 2, gap 1, no evidence 1)\n"
          "core responsibilities demonstrated: 1 of 3\n"
          "level match:                     lateral\n"
          "effort to close the gaps:        evening\n"
          "apply verdict:                   worth_applying")


  def test_the_block_contains_no_percentage_and_no_slash_score():
      counts = cc.coverage(ASSESSMENT["requirements"])
      for lang in ("zh", "en"):
          block = cc.render_block(ASSESSMENT, counts, lang)
          assert "%" not in block
          assert "/" not in block


  def test_main_writes_coverage_json_and_prints_the_block(tmp_path, capsys):
      (tmp_path / "fit-assessment.yaml").write_text(
          yaml.safe_dump(ASSESSMENT, allow_unicode=True), encoding="utf-8")
      assert cc.main(["--workspace", str(tmp_path)]) == 0
      data = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
      assert data["must_strong"] == 2 and data["resp_total"] == 3
      assert "must-have 强证据：   2 of 6" in capsys.readouterr().out


  def test_main_fails_on_an_out_of_enum_value(tmp_path, capsys):
      broken = {"verdict": "stretch", "effort": "quick", "level_direction": "unclear",
                "requirements": [row(match="partly")]}
      (tmp_path / "fit-assessment.yaml").write_text(
          yaml.safe_dump(broken, allow_unicode=True), encoding="utf-8")
      assert cc.main(["--workspace", str(tmp_path)]) == 1
      assert "INVALID_MATCH:" in capsys.readouterr().out


  def test_main_exits_two_without_an_assessment(tmp_path, capsys):
      assert cc.main(["--workspace", str(tmp_path)]) == 2
      assert "fit-assessment.yaml" in capsys.readouterr().err
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_count_coverage.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'count_coverage'`

- [ ] **Step 3: Write minimal implementation**

  Create `scripts/count_coverage.py`:
  ```python
  #!/usr/bin/env python3
  """The one place a number in an assessment comes from.

  The skill this replaces computed must-have coverage twice, with two formulas, over the
  same list. The two never agreed, and prose was left managing the disagreement. There is
  one function here, one rendered block, and check_assessment.py requires the block in
  fit-assessment.md to be byte-identical to what this produces. A second number cannot
  survive that.

  No percentage, and no slash score. Collapsing strong / partial / gap into one number
  needs a weight for a partial match, and any weight would be invented. The block shows
  exactly what was counted and claims nothing that was not; every counted row is printed
  in the requirement table beside its evidence reference, so the denominator is auditable
  row by row and a reader can object to any single line.
  """
  from __future__ import annotations

  import argparse
  import json
  import pathlib
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import journal  # noqa: E402
  import yaml  # noqa: E402

  MATCHES = ("strong", "partial", "gap", "no_evidence")
  RECENCIES = ("current", "recent", "dated", "undated")

  LEVEL_DIRECTION_ZH = {"step_up": "上跳", "lateral": "平级", "step_down": "下沉",
                        "unclear": "不明"}
  EFFORT_ZH = {"quick": "当天", "evening": "一晚", "multi_day": "数日",
               "not_closable": "补不上"}
  VERDICT_ZH = {"strong_apply": "强烈建议投", "worth_applying": "值得投",
                "stretch": "可以冲刺", "likely_screen_out": "大概率被筛掉",
                "blocked": "硬性阻断", "insufficient_evidence": "证据不足—不出结论"}


  def coverage(rows: list[dict] | None) -> dict:
      counts = {"must_total": 0, "must_strong": 0, "must_partial": 0, "must_gap": 0,
                "must_no_evidence": 0, "resp_total": 0, "resp_demonstrated": 0,
                "invalid": []}
      for index, item in enumerate(rows or []):
          item = item or {}
          identifier = item.get("id", f"#{index + 1}")
          match = item.get("match")
          recency = item.get("recency")
          if match not in MATCHES:
              counts["invalid"].append(
                  f"INVALID_MATCH: row {identifier} has match {match!r}, "
                  f"not one of {MATCHES}")
              match = None
          if recency not in RECENCIES:
              counts["invalid"].append(
                  f"INVALID_RECENCY: row {identifier} has recency {recency!r}, "
                  f"not one of {RECENCIES}")
              recency = None
          # Evidence that is only dated satisfies the keyword and reads as rusty to a
          # human, so it lands on partial. `undated` does NOT downgrade: a CV that omits
          # dates is a formatting fact, not a staleness fact.
          effective = "partial" if (match == "strong" and recency == "dated") else match
          kind = item.get("kind")
          if kind == "responsibility":
              counts["resp_total"] += 1
              if effective == "strong":
                  counts["resp_demonstrated"] += 1
          elif kind == "must_have":
              counts["must_total"] += 1
              if effective == "strong":
                  counts["must_strong"] += 1
              elif effective == "partial":
                  counts["must_partial"] += 1
              elif effective == "gap":
                  counts["must_gap"] += 1
              elif effective == "no_evidence":
                  counts["must_no_evidence"] += 1
          else:
              counts["invalid"].append(
                  f"INVALID_KIND: row {identifier} has kind {kind!r}, "
                  f"not 'must_have' or 'responsibility'")
      return counts


  def render_block(assessment: dict, counts: dict, lang: str = "zh") -> str:
      verdict = assessment.get("verdict", "insufficient_evidence")
      direction = assessment.get("level_direction", "unclear")
      effort = assessment.get("effort", "not_closable")
      if lang == "zh":
          return (
              f"must-have 强证据：   {counts['must_strong']} of {counts['must_total']}   "
              f"（partial {counts['must_partial']}，gap {counts['must_gap']}，"
              f"无证据 {counts['must_no_evidence']}）\n"
              f"核心职责已证实：     {counts['resp_demonstrated']} of {counts['resp_total']}\n"
              f"职级匹配：           {LEVEL_DIRECTION_ZH.get(direction, '不明')}\n"
              f"可补缺口所需投入：   {EFFORT_ZH.get(effort, '补不上')}\n"
              f"投递建议：           {VERDICT_ZH.get(verdict, '证据不足—不出结论')}")
      return (
          f"must-haves strongly evidenced:   {counts['must_strong']} of "
          f"{counts['must_total']}   (partial {counts['must_partial']}, "
          f"gap {counts['must_gap']}, no evidence {counts['must_no_evidence']})\n"
          f"core responsibilities demonstrated: {counts['resp_demonstrated']} of "
          f"{counts['resp_total']}\n"
          f"level match:                     {direction}\n"
          f"effort to close the gaps:        {effort}\n"
          f"apply verdict:                   {verdict}")


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="Count must-have and responsibility "
                                                   "coverage. The only counting path.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      parser.add_argument("--lang", choices=("zh", "en"), default="zh")
      args = parser.parse_args(argv)

      path = args.workspace / "fit-assessment.yaml"
      if not path.exists():
          print(f"cannot run: fit-assessment.yaml not found at {path}", file=sys.stderr)
          return 2

      assessment = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
      counts = coverage(assessment.get("requirements"))
      findings = list(counts["invalid"])
      block = render_block(assessment, counts, args.lang)

      payload = dict(counts)
      payload["block_zh"] = render_block(assessment, counts, "zh")
      payload["block_en"] = render_block(assessment, counts, "en")
      (args.workspace / "coverage.json").write_text(
          json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

      for finding in findings:
          print(finding)
      print(block)
      journal.receipt(args.workspace, "count_coverage",
                      {"fit-assessment.yaml": journal.sha256_file(path)},
                      "fail" if findings else "pass", findings)
      return 1 if findings else 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_count_coverage.py -q`
  Expected: PASS (13 passed)

- [ ] **Step 5: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add scripts/count_coverage.py scripts/tests/test_count_coverage.py
  git commit -m "assess: single count-producing path with an auditable denominator"
  ```

---

### Task 6: The market-table lint and its written spec

**Files:**
- Create: `references/market-conventions/README.md`
- Create: `scripts/check_conventions.py`
- Create: `docs/superpowers/research/2026-08-09-market-conventions/markets.json`
- Create: `docs/superpowers/research/2026-08-09-market-conventions/review-{cn,nl_weu,de,us_uk}.md`
- Test: `scripts/tests/test_check_conventions.py`

**Interfaces:**
- Consumes: `journal.receipt(...)`, `journal.sha256_file(path)`.
- Produces:
  - `MARKET_KEYS = ("cn", "nl", "de", "uk", "us")`
  - `PROSE_FIELDS`, `PROPER_NOUNS`, `PROTECTED_TRAITS`
  - `load_market_file(path: pathlib.Path) -> dict`
  - `conventions_by_id(data: dict) -> dict[str, dict]`
  - `check_file(path: pathlib.Path, today: datetime.date) -> list[str]` — findings; `WARN_`-prefixed ones do not fail
  - `main(argv=None) -> int`

**Why this table needs a lint at all.** This is the one thing in the whole skill not derived from the CV or the posting, and it is deliberately the only one. Every other conclusion is traceable to an evidence block; a market convention has nothing to cite, which is why it is written here by a person, dated, and rendered to the reader verbatim rather than restated by the model. The model may say where this CV stands against a convention — that claim cites CV blocks like any other — but it may not author, strengthen or extend the convention itself. Nothing automated can check that an entry is *true*. `why` and `added` exist so a person can review it.

**The digit ban and its deliberate hole.** A statistic here cannot be sourced and must not be invented, so a digit or a percent sign in a prose field fails the build. But `url`, `title`, `retrieved` and `quote` are exempt: a cited document's title is not a claim, it is an identifier, and statutes and case law are numbered — that is how they are named. Banning digits there stops no invented statistic; it only forces the citation to be wrong, or to be dropped in favour of a weaker source that happens to have no number in its name. A closed `PROPER_NOUNS` list exempts `H-1B`, `Form I-9` and `Form I-983` for the same reason — the reviewer flagged explicitly that removing them would leave sentences a reader cannot act on. It is a closed list on purpose: a general "proper nouns are fine" rule is a lint-dodge licence.

**Calibration.** The length-ratio and modal-asymmetry warnings were measured against all forty source entries before the thresholds were chosen: `len(text_zh)/len(text_en)` runs 0.258–0.424 across the set, and the modal-marker delta runs −1 to +3. The thresholds below (`< 0.20` or `> 0.60`; `|delta| >= 3`) sit outside the body of the distribution on purpose. A gate that cries wolf on the repo's own fixtures is a gate someone eventually switches off.

- [ ] **Step 1: Land the research the tables are built from**

  The five YAML tables in Tasks 7–11 are built from a research file and four adversarial reviews that currently live only in a session scratchpad. Copy them into the repo first so the later tasks have a durable, reviewable source. Run exactly:
  ```
  SRC=/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad
  DST=/Users/donghanglyu/code_project/job-hunt/docs/superpowers/research/2026-08-09-market-conventions
  mkdir -p "$DST"
  cp "$SRC/markets.json" "$DST/markets.json"
  python3 - <<'PY'
  import json, pathlib
  dst = pathlib.Path("/Users/donghanglyu/code_project/job-hunt/docs/superpowers/"
                     "research/2026-08-09-market-conventions")
  for entry in json.loads((dst / "markets.json").read_text(encoding="utf-8")):
      (dst / f"review-{entry['market']}.md").write_text(entry["review"], encoding="utf-8")
      print("wrote", f"review-{entry['market']}.md")
  PY
  ```
  Expected: `review-cn.md`, `review-nl_weu.md`, `review-de.md`, `review-us_uk.md` written beside `markets.json`.

  If `$SRC/markets.json` no longer exists, STOP and report it — Tasks 7–11 cannot be done from memory, and inventing a market convention is the one failure in this skill that a reader has no source text to catch.

- [ ] **Step 2: Write `references/market-conventions/README.md`**

  This file is `check_conventions.py`'s spec. Write it exactly (the listing below is
  fenced with **five** backticks because the README itself contains a three-backtick
  YAML block — that block is part of the README's content):
  `````markdown
  # Market conventions

  What a market screens on that the posting does not say.

  This table is the one thing in an assessment that is not derived from the CV or the
  posting, and it is deliberately the only one. Every other conclusion cites an evidence
  block; a market convention has nothing to cite, which is why it is written here by a
  person, dated, and rendered to the reader **verbatim** rather than restated by the
  model. The model may say where this CV stands against a convention — that sentence
  cites CV blocks like any other — but it may not author, strengthen or extend the
  convention itself.

  Nothing automated can check that an entry is true. `why` and `added` exist so a person
  can review it. `scripts/check_conventions.py` checks only the things a program can
  decide. **Named residual risk: an entry can be substantively wrong rather than
  numerically stale, and nothing here detects that. Only human review does.**

  ## Market keys

  `cn`, `nl`, `de`, `uk`, `us`. A posting whose market is none of these gets
  「本市场无惯例数据」 and no convention card at all. Never substitute a neighbouring
  market's conventions: a wrong market card reads exactly like a right one, and the
  reader has no source text to check it against.

  ## Entry shape

  ```yaml
  market: cn
  conventions:
    - id: cn-boss-profile-is-the-screen      # unique in the file, [a-z0-9-]+
      text_en: |-
        The sentence the reader sees, in English.
      text_zh: |-
        读者看到的那句话，中文。
      applies_when: "The condition under which this card renders at all."
      added: "2026-08-09"
      review_by: "2027-02-09"
      source:
        kind: published                       # published | maintainer
        publisher: "Who published it"
        title: "The document's title"
        url: "https://..."
        retrieved: "2026-08-09"
        quote: "verbatim string from the source that supports this entry"
        also:                                 # optional further citations, same shape
          - publisher: "..."
            title: "..."
            url: "https://..."
            retrieved: "2026-08-09"
            quote: "..."
      why: "Why a candidate cannot see this from the posting."
      protected_trait_note: "..."             # required ONLY if a protected trait appears
  unverified:
    - note: "What could not be sourced."
      disclaims: [cn-boss-profile-is-the-screen]
  ```

  ## Rules for adding an entry

  - **No numbers.** A statistic here cannot be sourced and must not be invented.
    `check_conventions.py` fails on a digit or a percent sign in `text_en`, `text_zh`,
    `applies_when`, `why`, `source.publisher` or `source.note`. Write "look the current
    amount up on <the official page>", never the amount.
  - **`url`, `title`, `retrieved` and `quote` are exempt from the digit ban.** A cited
    document's title is an identifier, not a claim, and statutes are numbered — that is
    how they are named. Banning digits there would only force the citation to be wrong.
  - **Proper nouns that are the entry's only handle are exempt**, from a closed list in
    the script (`H-1B`, `Form I-9`, `Form I-983`). Do not "fix" a lint hit by deleting
    one — a reader cannot find the rule without its name. Extend the list in code, with a
    comment, or do not use the name.
  - **Never hide a threshold behind a blank.** "The figure is set in the rule" is a
    lint-dodge, not compliance: the reader cannot act on it. Point at the exact source to
    read the number in.
  - **Every entry says where it came from.** `source.kind` is `maintainer` when the person
    maintaining this table has worked in that market and is stating what they saw, or
    `published` when it rests on something citable, in which case it carries `publisher`,
    `title`, `url` and the date the url was checked. The two deserve different weight.
    A citation proves a claim was *published* — not that it is true, still current, or
    applicable to this reader. `retrieved` dates the check; it does not keep it fresh.
  - **No protected traits.** Age, nationality, country of education, gender, ethnicity,
    religion, disability and institutional prestige stay out. Where the fact genuinely
    *is* a citizenship or national-origin rule — a right-to-work check, a
    citizenship-discrimination complaint route — the entry must carry a
    `protected_trait_note` saying so. That field makes the exception a decision someone
    made rather than a slip nobody noticed.
  - **No CV layout.** Length, photographs and date formatting are tailoring instructions,
    not market screening facts. This table is about what the market weighs.
  - **Nothing already covered elsewhere.** A third telling of the same fact is the
    repetition the requirement rows already prevent.
  - **Both languages, always.** A claim shipped in only one language is a claim no
    reviewer compares. Reviews have repeatedly caught the Chinese saying more than the
    English (source says "encourages", zh says 「被要求」; a statute limiting the scope of
    a right, zh saying it does not exist at all). The lint warns on a length-ratio
    outlier and on modal-verb asymmetry, and **that is a hint, not a guarantee: semantic
    drift is not scriptable, and reviewing it is a person's job.**
  - **`review_by` is mandatory** and is derived from staleness: an entry whose underlying
    fact is re-issued yearly gets three months; one that moves with practice gets six;
    a statute or a stable mechanism gets twelve. An expired `review_by` **fails this
    lint** (so CI catches it), while at runtime the card still renders with a
    「已过复核期」 banner — a date passing without the code changing should not stop the
    skill working.
  - **`unverified` must name what it disclaims.** Every assertion an `unverified` note
    disclaims must be **removed from the rendered text**, not footnoted. The reader never
    sees `unverified`, so a footnote there protects nobody. The lint warns when a note
    and the text it disclaims share vocabulary, because that is what that defect looks
    like.
  `````

- [ ] **Step 3: Write the failing test**

  Create `scripts/tests/test_check_conventions.py`:
  ```python
  import datetime
  import json

  import yaml

  import check_conventions as cck

  TODAY = datetime.date(2026, 8, 9)

  GOOD = {
      "market": "cn",
      "conventions": [{
          "id": "cn-boss-profile-is-the-screen",
          "text_en": ("On BOSS直聘 the recruiter does not see your CV file first. What they "
                      "see is the structured profile you filled in at registration — the "
                      "operator's own SEC filing calls it a mini resume — and your full CV "
                      "and contact details reach them only on mutual consent inside the "
                      "chat. Treat those profile fields as the actual screening document "
                      "and write them for a reader who will decide from them alone."),
          "text_zh": ("在 BOSS 直聘上，招聘方一开始看不到你的简历附件，只能看到你注册时填写的在线"
                      "简历；完整简历和联系方式要等双方在聊天中互相同意后才会送达。所以真正被筛的"
                      "是在线资料的那几栏，要按「对方只看这些就下判断」来写。"),
          "applies_when": "Applying through BOSS直聘, on any track (社招, 校招 or 实习).",
          "added": "2026-08-09",
          "review_by": "2027-02-09",
          "source": {"kind": "published",
                     "publisher": "Kanzhun Limited (operator of BOSS直聘)",
                     "title": "Annual Report on Form 20-F for the fiscal year ended "
                              "December 31, 2025",
                     "url": "https://www.sec.gov/Archives/edgar/data/1842827/x.htm",
                     "retrieved": "2026-08-09",
                     "quote": "enterprise users on our platforms can only see a job "
                              "seeker's mini resume that contains limited information"},
          "why": ("The posting shows a job description and a chat button. Nothing on it "
                  "tells you that the artefact being screened is your platform profile "
                  "rather than the CV you spent your effort on."),
      }],
  }


  def write(tmp_path, data, name="cn.yaml"):
      path = tmp_path / name
      path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                      encoding="utf-8")
      return path


  def mutate(**changes):
      data = json.loads(json.dumps(GOOD))
      data["conventions"][0].update(changes)
      return data


  # ---------- the quiet case, pinned as hard as the firing case ----------

  def test_a_real_shipped_entry_produces_no_findings_at_all(tmp_path):
      assert cck.check_file(write(tmp_path, GOOD), TODAY) == []


  def test_digits_in_url_title_retrieved_and_quote_are_exempt(tmp_path):
      # The title carries "Form 20-F ... December 31, 2025", the url an EDGAR CIK, the
      # quote a sentence from a filing. None of those is a claim this table is making.
      assert cck.check_file(write(tmp_path, GOOD), TODAY) == []


  def test_the_allowlisted_proper_nouns_pass(tmp_path):
      data = mutate(text_en="Some US employers sit outside the H-1B numerical cap, and "
                            "Form I-9 lets the worker choose which documents to present; "
                            "Form I-983 is the employer-side training plan.",
                    text_zh="有些美国雇主不受 H-1B 名额限制；Form I-9 由劳动者自行选择出示"
                            "哪些证件；Form I-983 是雇主一侧的培训计划。")
      assert [f for f in cck.check_file(write(tmp_path, data), TODAY)
              if f.startswith("DIGIT_IN_PROSE")] == []


  def test_a_protected_trait_with_a_written_note_passes(tmp_path):
      data = mutate(
          text_en="An employer may restrict hiring to US citizens only where a law "
                  "requires it.",
          text_zh="只有在法律要求时，雇主才可以把招聘限定为美国公民。",
          protected_trait_note="The fact IS a citizenship-discrimination rule; naming the "
                               "trait is what makes the complaint route usable.")
      assert [f for f in cck.check_file(write(tmp_path, data), TODAY)
              if f.startswith("PROTECTED_TRAIT")] == []


  def test_the_real_entrys_length_ratio_and_modal_balance_are_quiet(tmp_path):
      findings = cck.check_file(write(tmp_path, GOOD), TODAY)
      assert not [f for f in findings if f.startswith("WARN_LENGTH_RATIO")]
      assert not [f for f in findings if f.startswith("WARN_MODAL_ASYMMETRY")]


  def test_a_review_by_in_the_future_passes(tmp_path):
      assert cck.check_file(write(tmp_path, mutate(review_by="2026-08-10")), TODAY) == []


  # ---------- the firing cases, taken from live violations the reviewer found ----------

  def test_51job_in_an_english_body_fails(tmp_path):
      data = mutate(text_en="Alongside 51job there is a state-organised recruitment "
                            "channel worth checking.")
      findings = cck.check_file(write(tmp_path, data), TODAY)
      assert any(f.startswith("DIGIT_IN_PROSE:") and "51job" in f for f in findings)


  def test_the_30_percent_ruling_fails_in_both_languages(tmp_path):
      data = mutate(text_en="The 30% ruling is administered by the Belastingdienst.",
                    text_zh="所谓 30% 规则由荷兰税务局管理。")
      findings = cck.check_file(write(tmp_path, data), TODAY)
      assert any(f.startswith("PERCENT_IN_PROSE:") and "text_en" in f for f in findings)
      assert any(f.startswith("PERCENT_IN_PROSE:") and "text_zh" in f for f in findings)


  def test_a_directive_number_in_the_body_fails(tmp_path):
      data = mutate(text_en="Directive (EU) 2023/970 gives you a right to the pay range.")
      assert any(f.startswith("DIGIT_IN_PROSE:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_protected_trait_without_a_note_fails(tmp_path):
      data = mutate(text_en="Employers here weigh nationality when shortlisting.",
                    text_zh="这里的雇主在初筛时会看国籍。")
      findings = cck.check_file(write(tmp_path, data), TODAY)
      assert any(f.startswith("PROTECTED_TRAIT:") and "nationality" in f for f in findings)
      assert any(f.startswith("PROTECTED_TRAIT:") and "国籍" in f for f in findings)


  def test_an_expired_review_by_fails(tmp_path):
      data = mutate(review_by="2026-08-08")
      assert any(f.startswith("EXPIRED_REVIEW_BY:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_duplicate_id_fails(tmp_path):
      data = json.loads(json.dumps(GOOD))
      data["conventions"].append(json.loads(json.dumps(GOOD["conventions"][0])))
      assert any(f.startswith("DUPLICATE_ID:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_missing_text_zh_fails(tmp_path):
      data = json.loads(json.dumps(GOOD))
      del data["conventions"][0]["text_zh"]
      assert any(f.startswith("MISSING_FIELD:") and "text_zh" in f
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_published_source_without_https_or_a_date_fails(tmp_path):
      data = mutate(source={"kind": "published", "publisher": "X", "title": "Y",
                            "url": "http://example.org", "retrieved": "August 2026"})
      findings = cck.check_file(write(tmp_path, data), TODAY)
      assert any(f.startswith("BAD_SOURCE_URL:") for f in findings)
      assert any(f.startswith("BAD_SOURCE_RETRIEVED:") for f in findings)


  def test_an_unknown_source_kind_fails(tmp_path):
      data = mutate(source={"kind": "remembered", "note": "I think so"})
      assert any(f.startswith("BAD_SOURCE_KIND:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_maintainer_source_needs_a_note(tmp_path):
      data = mutate(source={"kind": "maintainer"})
      assert any(f.startswith("MISSING_SOURCE_NOTE:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_wildly_unbalanced_translation_warns(tmp_path):
      data = mutate(text_zh="见上。")
      assert any(f.startswith("WARN_LENGTH_RATIO:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_modal_asymmetry_warns_when_only_one_language_obliges(tmp_path):
      data = mutate(text_zh="招聘方必须先看在线简历；你必须填满那几栏；完整简历不得在双方同意前"
                            "送达；因此你应当把在线资料当成真正被筛的文件来写。")
      assert any(f.startswith("WARN_MODAL_ASYMMETRY:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_an_unverified_note_must_name_what_it_disclaims(tmp_path):
      data = json.loads(json.dumps(GOOD))
      data["unverified"] = [{"note": "Nothing was sourced about 猎聘."}]
      assert any(f.startswith("MISSING_UNVERIFIED_DISCLAIMS:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_an_unverified_note_naming_an_unknown_entry_fails(tmp_path):
      data = json.loads(json.dumps(GOOD))
      data["unverified"] = [{"note": "n/a", "disclaims": ["cn-does-not-exist"]}]
      assert any(f.startswith("UNVERIFIED_TARGET_UNKNOWN:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  def test_a_note_disclaiming_a_claim_the_text_still_makes_warns(tmp_path):
      data = json.loads(json.dumps(GOOD))
      data["unverified"] = [{
          "note": ("Not sourced: that the structured profile filled in at registration "
                   "is the actual screening document a recruiter decides from."),
          "disclaims": ["cn-boss-profile-is-the-screen"]}]
      assert any(f.startswith("WARN_UNVERIFIED_OVERLAP:")
                 for f in cck.check_file(write(tmp_path, data), TODAY))


  # ---------- the CLI ----------

  def test_warnings_alone_do_not_fail_the_gate(tmp_path, capsys):
      path = write(tmp_path, mutate(text_zh="见上。"))
      assert cck.main(["--workspace", str(tmp_path), "--market-file", str(path),
                       "--today", "2026-08-09"]) == 0
      assert "WARN_LENGTH_RATIO" in capsys.readouterr().out


  def test_a_hard_finding_fails_the_gate_and_journals_a_receipt(tmp_path):
      path = write(tmp_path, mutate(review_by="2026-08-08"))
      assert cck.main(["--workspace", str(tmp_path), "--market-file", str(path),
                       "--today", "2026-08-09"]) == 1
      record = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
      assert record["gate"] == "check_conventions" and record["verdict"] == "fail"


  def test_a_missing_market_file_exits_two(tmp_path, capsys):
      assert cck.main(["--workspace", str(tmp_path),
                       "--market-file", str(tmp_path / "nope.yaml")]) == 2
      assert "nope.yaml" in capsys.readouterr().err
  ```

- [ ] **Step 4: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_conventions.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'check_conventions'`

- [ ] **Step 5: Write minimal implementation**

  Create `scripts/check_conventions.py`:
  ```python
  #!/usr/bin/env python3
  """Whether a market-conventions table may ship.

  These tables carry the one class of assertion in this skill with no source text behind
  it, so they are written by a person, dated, provenance-kinded, and rendered verbatim.
  Nothing here can check that an entry is TRUE. It checks the things a program can decide,
  and every threshold below was calibrated against the forty source entries before it was
  chosen -- a gate that cries wolf on the repo's own fixtures is a gate someone
  eventually switches off.

  references/market-conventions/README.md is this script's spec. If the two disagree, the
  README is what a person reads before adding an entry, so fix the script.
  """
  from __future__ import annotations

  import argparse
  import datetime
  import pathlib
  import re
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import journal  # noqa: E402
  import yaml  # noqa: E402

  MARKET_KEYS = ("cn", "nl", "de", "uk", "us")
  PROSE_FIELDS = ("text_en", "text_zh", "applies_when", "why")
  SOURCE_PROSE_FIELDS = ("publisher", "note")
  REQUIRED_FIELDS = ("id", "text_en", "text_zh", "applies_when", "added", "review_by",
                     "source", "why")

  # Closed on purpose. These three names are the only handle a reader has on the rules
  # they belong to; deleting the digits to satisfy the lint would leave sentences nobody
  # can act on. A general "proper nouns are fine" rule would be a lint-dodge licence.
  PROPER_NOUNS = ("Form I-983", "Form I-9", "H-1B", "I-983", "I-9")

  PROTECTED_TRAITS = (
      r"\bage\b", r"\bnationality\b", r"\bnational origin\b", r"\bcitizens?(?:hip)?\b",
      r"\bgender\b", r"\bsex\b", r"\bethnicity\b", r"\brace\b", r"\breligion\b",
      r"\bdisabilit(?:y|ies)\b", r"\bmarital status\b", r"\bpregnan\w*",
      "年龄", "国籍", "性别", "民族", "种族", "宗教", "残疾", "婚姻状况", "怀孕",
  )

  # Measured across all forty source entries: len(zh)/len(en) runs 0.258-0.424, and the
  # modal-marker delta runs -1..+3. These bounds sit outside the body of both.
  RATIO_LOW, RATIO_HIGH = 0.20, 0.60
  MODAL_DELTA = 3

  _MODAL_EN = re.compile(
      r"\bmust\b|\bshall\b|\bmay not\b|\bcannot\b|\b(?:is|are) required to\b"
      r"|\b(?:is|are) obliged to\b|\b(?:is|are) barred\b|\b(?:is|are) prohibited\b"
      r"|\b(?:is|are) not (?:allowed|permitted)\b", re.IGNORECASE)
  _MODAL_ZH = re.compile(r"必须|不得|应当|禁止|有义务|方可")
  _ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
  _HTTPS = re.compile(r"^https://\S+$")
  _ID = re.compile(r"^[a-z0-9-]+$")
  _LATIN_TOKEN = re.compile(r"[A-Za-z]{6,}")
  _CJK_TOKEN = re.compile(r"[一-鿿]{3,}")


  def load_market_file(path: pathlib.Path) -> dict:
      return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


  def conventions_by_id(data: dict) -> dict[str, dict]:
      return {c.get("id"): c for c in (data.get("conventions") or []) if c.get("id")}


  def _strip_exempt(text: str) -> str:
      for noun in PROPER_NOUNS:
          text = text.replace(noun, "")
      return text


  def _tokens(text: str) -> set[str]:
      return ({m.group(0).lower() for m in _LATIN_TOKEN.finditer(text)}
              | {m.group(0) for m in _CJK_TOKEN.finditer(text)})


  def _check_source(entry_id: str, source, findings: list[str]) -> None:
      if not isinstance(source, dict):
          findings.append(f"MISSING_FIELD: {entry_id}.source is absent or not a mapping")
          return
      kind = source.get("kind")
      if kind not in ("maintainer", "published"):
          findings.append(f"BAD_SOURCE_KIND: {entry_id}.source.kind is {kind!r}, "
                          f"not 'maintainer' or 'published'")
          return
      if kind == "maintainer" and not str(source.get("note") or "").strip():
          findings.append(f"MISSING_SOURCE_NOTE: {entry_id} is a maintainer entry with no "
                          f"note saying what the maintainer saw")
      citations = [source] if kind == "published" else []
      citations += list(source.get("also") or [])
      for index, citation in enumerate(citations):
          where = f"{entry_id}.source" if index == 0 else f"{entry_id}.source.also[{index-1}]"
          for field in ("publisher", "title"):
              if not str(citation.get(field) or "").strip():
                  findings.append(f"MISSING_FIELD: {where}.{field} is empty")
          if not _HTTPS.match(str(citation.get("url") or "")):
              findings.append(f"BAD_SOURCE_URL: {where}.url is "
                              f"{citation.get('url')!r}, not an https URL")
          if not _ISO_DATE.match(str(citation.get("retrieved") or "")):
              findings.append(f"BAD_SOURCE_RETRIEVED: {where}.retrieved is "
                              f"{citation.get('retrieved')!r}, not YYYY-MM-DD")


  def check_file(path: pathlib.Path, today: datetime.date) -> list[str]:
      data = load_market_file(path)
      findings: list[str] = []

      if data.get("market") not in MARKET_KEYS:
          findings.append(f"BAD_MARKET: {path.name} declares market "
                          f"{data.get('market')!r}, not one of {MARKET_KEYS}")

      seen: set[str] = set()
      for entry in data.get("conventions") or []:
          entry = entry or {}
          entry_id = str(entry.get("id") or "<no id>")
          if not _ID.match(entry_id):
              findings.append(f"BAD_ID: {entry_id!r} is not [a-z0-9-]+")
          if entry_id in seen:
              findings.append(f"DUPLICATE_ID: {entry_id} appears more than once")
          seen.add(entry_id)

          for field in REQUIRED_FIELDS:
              if field != "source" and not str(entry.get(field) or "").strip():
                  findings.append(f"MISSING_FIELD: {entry_id}.{field} is empty")

          prose = {field: str(entry.get(field) or "") for field in PROSE_FIELDS}
          source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
          for field in SOURCE_PROSE_FIELDS:
              if source.get(field):
                  prose[f"source.{field}"] = str(source[field])
          for field, text in prose.items():
              scanned = _strip_exempt(text)
              if "%" in scanned:
                  findings.append(f"PERCENT_IN_PROSE: {entry_id}.{field} states a "
                                  f"percentage: {text.strip()[:80]!r}")
              digits = sorted(set(re.findall(r"[0-9]", scanned)))
              if digits:
                  snippet = next((w for w in re.findall(r"\S*[0-9]\S*", scanned)), "")
                  findings.append(f"DIGIT_IN_PROSE: {entry_id}.{field} states a number "
                                  f"({snippet!r}) in: {text.strip()[:80]!r}")
              for pattern in PROTECTED_TRAITS:
                  hit = re.search(pattern, text, re.IGNORECASE)
                  if hit and not str(entry.get("protected_trait_note") or "").strip():
                      findings.append(
                          f"PROTECTED_TRAIT: {entry_id}.{field} names "
                          f"{hit.group(0)!r} with no protected_trait_note explaining why "
                          f"the fact cannot be stated without it")

          _check_source(entry_id, entry.get("source"), findings)

          for field in ("added", "review_by"):
              value = str(entry.get(field) or "")
              if not _ISO_DATE.match(value):
                  findings.append(f"BAD_DATE: {entry_id}.{field} is {value!r}, "
                                  f"not YYYY-MM-DD")
              elif field == "review_by" and datetime.date.fromisoformat(value) < today:
                  findings.append(f"EXPIRED_REVIEW_BY: {entry_id} was due for review on "
                                  f"{value}; re-check the source or re-date it")

          english, chinese = prose.get("text_en", ""), prose.get("text_zh", "")
          if english and chinese:
              ratio = len(chinese) / len(english)
              if ratio < RATIO_LOW or ratio > RATIO_HIGH:
                  findings.append(
                      f"WARN_LENGTH_RATIO: {entry_id} zh/en length ratio is {ratio:.2f}, "
                      f"outside {RATIO_LOW}-{RATIO_HIGH}; one language may be saying "
                      f"more than the other")
              delta = len(_MODAL_ZH.findall(chinese)) - len(_MODAL_EN.findall(english))
              if abs(delta) >= MODAL_DELTA:
                  findings.append(
                      f"WARN_MODAL_ASYMMETRY: {entry_id} has {delta:+d} more obligation "
                      f"markers in zh than en; check that neither version strengthens a "
                      f"'usually' into a 'must'")

      known = conventions_by_id(data)
      for index, item in enumerate(data.get("unverified") or []):
          item = item or {}
          targets = item.get("disclaims") or []
          if not targets:
              findings.append(f"MISSING_UNVERIFIED_DISCLAIMS: unverified[{index}] does not "
                              f"name the entry or field it disclaims")
              continue
          note_tokens = _tokens(str(item.get("note") or ""))
          for target in targets:
              entry_id = str(target).split(".")[0]
              entry = known.get(entry_id)
              if entry is None:
                  findings.append(f"UNVERIFIED_TARGET_UNKNOWN: unverified[{index}] names "
                                  f"{target!r}, which is not an entry in {path.name}")
                  continue
              shared = note_tokens & _tokens(
                  f"{entry.get('text_en', '')} {entry.get('text_zh', '')}")
              if len(shared) >= 3:
                  findings.append(
                      f"WARN_UNVERIFIED_OVERLAP: unverified[{index}] disclaims "
                      f"{target} yet shares {sorted(shared)} with its rendered text; an "
                      f"assertion the note disclaims must be REMOVED from the text, not "
                      f"footnoted — the reader never sees this note")
      return findings


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="Lint the market-convention tables.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      parser.add_argument("--market-file", action="append", type=pathlib.Path, default=[])
      parser.add_argument("--all", action="store_true",
                          help="check every shipped table under references/market-conventions")
      parser.add_argument("--today", default=None, help="YYYY-MM-DD, for deterministic tests")
      args = parser.parse_args(argv)

      today = (datetime.date.fromisoformat(args.today) if args.today
               else datetime.date.today())
      files = list(args.market_file)
      if args.all:
          root = pathlib.Path(__file__).resolve().parents[1] / "references" / "market-conventions"
          files += [root / f"{key}.yaml" for key in MARKET_KEYS]
      if not files:
          print("cannot run: pass --market-file or --all", file=sys.stderr)
          return 2
      for path in files:
          if not path.exists():
              print(f"cannot run: {path} not found", file=sys.stderr)
              return 2

      findings: list[str] = []
      hashes: dict[str, str] = {}
      for path in files:
          hashes[path.name] = journal.sha256_file(path)
          findings += check_file(path, today)

      for finding in findings:
          print(finding)
      hard = [f for f in findings if not f.startswith("WARN_")]
      journal.receipt(args.workspace, "check_conventions", hashes,
                      "fail" if hard else "pass", findings)
      return 1 if hard else 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 6: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_conventions.py -q`
  Expected: PASS (24 passed)

- [ ] **Step 7: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add references/market-conventions/README.md scripts/check_conventions.py \
          scripts/tests/test_check_conventions.py \
          docs/superpowers/research/2026-08-09-market-conventions
  git commit -m "conventions: table lint plus the README that is its spec, and the source research"
  ```

---

### Task 7: `references/market-conventions/cn.yaml`

**Files:**
- Create: `references/market-conventions/cn.yaml`
- Test: (none new — the deliverable is `check_conventions.py --market-file references/market-conventions/cn.yaml` exiting 0 with no hard finding)

**Interfaces:**
- Consumes: `check_conventions.check_file(path, today) -> list[str]`, `check_conventions.load_market_file(path) -> dict`; the entry shape in `references/market-conventions/README.md`; the research at `docs/superpowers/research/2026-08-09-market-conventions/`.
- Produces: `references/market-conventions/cn.yaml` with ten entries, ids exactly as in the table below. `modes/assess.md` and `check_assessment.py` reference these ids.

**The build rule for every table task (7 through 11).** Follow it literally; do not improvise convention text.

1. Read the entry in `docs/superpowers/research/2026-08-09-market-conventions/markets.json` (`entry.conventions[i]`) and the matching numbered section of the review file.
2. **KEEP** → copy `text_en`, `text_zh`, `applies_when`, `why` byte-for-byte from `markets.json`.
3. **KEEP-WITH-EDIT** → the review contains the replacement wording. Where the review gives a whole `text_en`/`text_zh`, use it byte-for-byte. Where it gives "replacement for the final sentence" / "insert the third sentence", splice **only at the sentence the review quotes** and leave every surrounding sentence untouched. Do not rewrite for style.
4. **DROP** → the entry does not appear in any table. Record the id and the one-line reason in the `# DROPPED` comment block at the top of the file.
5. Restructure the flat `source_kind` + `source_detail` prose into the structured `source:` mapping the README specifies: `kind`, `publisher`, `title`, `url`, `retrieved`, `quote` (one verbatim string from `source_detail`), plus `also:` for every further citation `source_detail` carries. The review states, per entry, which URL the quote actually belongs to — use that attribution, not the original one.
6. Set `added: "2026-08-09"` on every entry, and `review_by` from the table below. The mapping is the README's rule applied to the reviewer's staleness rating: high → `2026-11-09`, medium → `2027-02-09`, low → `2027-08-09`.
7. **Apply only edits the reviewer wrote out.** Everything the reviewer listed under "Important and missing" goes verbatim into a `# NEXT REVIEW` comment block at the top of the file, and into nothing else. Writing a new convention from a research note is authoring a market claim, and this table is the one place where only a person who checked the source may do that.

**Disposition — `cn`, from `review-cn.md`. All ten entries ship.**

| # | id | Verdict | Shipped text comes from | `review_by` |
|---|---|---|---|---|
| 1 | `cn-boss-profile-is-the-screen` | KEEP-WITH-EDIT | review §1 replacement block (drops the unsourced 「迷你简历」 terminology claim) | 2027-02-09 |
| 2 | `cn-salary-expectation-declared-up-front` | KEEP-WITH-EDIT | review §2 replacement block (drops the unsourced "feeds the matching" claim) | 2027-02-09 |
| 3 | `cn-campus-track-is-cohort-gated-and-early` | KEEP-WITH-EDIT | review §3 replacement block (the entry's own sources refute the exclusivity claim) | 2026-11-09 |
| 4 | `cn-fresh-graduate-status-is-administrative` | KEEP-WITH-EDIT | review §4 replacement block (restores the central baseline 「各省自行规定」 erased) | 2026-11-09 |
| 5 | `cn-three-party-agreement-is-not-the-employment-contract` | KEEP | `markets.json` verbatim. Correct `source.publisher` to 教育部学生服务与素质发展中心 and note the article is 综合整理, an official-platform explainer rather than a primary instrument | 2027-08-09 |
| 6 | `cn-state-organised-recruitment-channel` | KEEP-WITH-EDIT | review §6 replacement block. **This is one of the live constraint violations the lint exists for: the old `text_en` contained "51job".** | 2026-11-09 |
| 7 | `cn-posting-salary-is-not-a-defined-quantity` | KEEP-WITH-EDIT | review §7 replacement block (drops the statistics-definition category slip; 可主张 no longer rendered as 必须履行) | 2027-08-09 |
| 8 | `cn-what-an-employer-may-ask-and-what-truthfulness-costs` | KEEP-WITH-EDIT | `markets.json` text with **only the final sentence** replaced by review §8's two blocks (adds the Beijing-only scope the reader could not otherwise see) | 2027-08-09 |
| 9 | `cn-hukou-application-is-filed-by-the-employer` | KEEP-WITH-EDIT | review §9 replacement block. Also re-point `source` at 沪教委学〔2026〕13号 via the SJTU page the review verified, and add the SJTU 申请主体 and one-filing-per-cycle quotes to `source.also`. The unsourced "registration cut-off" detail must not reappear. | 2026-11-09 |
| 10 | `cn-internship-is-usually-not-an-employment-relationship` | KEEP | `markets.json` verbatim. Add the review's precision note to `source.note`: the statutory sentence covers 勤工助学, and the broad proposition rests on commentary plus two contrasting outcomes. | 2027-08-09 |

**`unverified` for `cn.yaml`.** Carry items 1–7 of `markets.json`'s `cn.entry.unverified` across, each as `{note, disclaims}`. `disclaims` must name the entry the note limits — item 3 (背调 prevalence) disclaims `cn-what-an-employer-may-ask-and-what-truthfulness-costs`; item 5 (期望薪资 norms) disclaims `cn-salary-expectation-declared-up-front`; item 6 (薪资构成 detail) disclaims `cn-posting-salary-is-not-a-defined-quantity`. Items with no matching entry are dropped rather than pointed at an unrelated one. **If the lint returns `WARN_UNVERIFIED_OVERLAP`, the fix is to delete the disclaimed assertion from `text_en`/`text_zh` — not to soften the note.** The reader never sees `unverified`.

- [ ] **Step 1: Write the file**

  Create `references/market-conventions/cn.yaml`. The first entry, written out in full, is the pattern for the other nine:
  ```yaml
  # Market conventions — China (cn)
  #
  # Built 2026-08-09 from docs/superpowers/research/2026-08-09-market-conventions/
  # markets.json + review-cn.md. Every `published` URL in that research was fetched and
  # every "Verbatim:" string grepped against the fetched text on 2026-08-09.
  #
  # DROPPED
  #   (none — all ten cn entries ship)
  #
  # NEXT REVIEW — sourced facts the reviewer found MISSING. Do not write these into
  # conventions from this comment; a person must check the source first.
  #   1. 劳动合同法 第九条: an employer may not withhold your 居民身份证 or other documents,
  #      demand a guarantee, or collect property from you under any name. China-wide,
  #      invisible on any posting, and the legal hook for the 招转培 pattern entry 6 flags.
  #   2. 第八条 running the other way: the employer must 如实告知 工作内容、工作条件、
  #      工作地点、职业危害、安全生产状况、劳动报酬. Entry 8 ships only the candidate-side duty.
  #   3. The 国聘行动 notice bans 毕业院校 / 国（境）外学习经历 / 学习方式 / 本单位实习期限 as
  #      screening conditions — for participants in that campaign, not market-wide.
  #   4. Shanghai: a failed employer 落户 filing cannot be re-submitted by another employer
  #      in the same cycle.
  #   5. 劳动合同法 第十条: a written contract must be concluded within one month of starting.

  market: cn

  conventions:
    - id: cn-boss-profile-is-the-screen
      text_en: |-
        On BOSS直聘 the recruiter does not see your CV file first. What they see is the
        structured profile you filled in at registration — the operator's own SEC filing
        calls it a mini resume — and your full CV and contact details reach them only on
        mutual consent inside the chat. Treat those profile fields as the actual
        screening document and write them for a reader who will decide from them alone.
      text_zh: |-
        在 BOSS 直聘上，招聘方一开始看不到你的简历附件，只能看到你注册时填写的在线简历；完整简历和
        联系方式要等双方在聊天中互相同意后才会送达。所以真正被筛的是在线资料的那几栏，要按「对方只看
        这些就下判断」来写。
      applies_when: "Applying through BOSS直聘, on any track (社招, 校招 or 实习)."
      added: "2026-08-09"
      review_by: "2027-02-09"
      source:
        kind: published
        publisher: "Kanzhun Limited (operator of BOSS直聘), filed with the U.S. Securities and Exchange Commission"
        title: "Annual Report on Form 20-F for the fiscal year ended December 31, 2025"
        url: "https://www.sec.gov/Archives/edgar/data/1842827/000110465926050959/bz-20251231x20f.htm"
        retrieved: "2026-08-09"
        quote: "enterprise users on our platforms can only see a job seeker's mini resume that contains limited information. Enterprise users are not allowed to access job seekers' full resume or their contact information without job seekers' express consents"
        also:
          - publisher: "Kanzhun Limited"
            title: "Annual Report on Form 20-F for the fiscal year ended December 31, 2025"
            url: "https://www.sec.gov/Archives/edgar/data/1842827/000110465926050959/bz-20251231x20f.htm"
            retrieved: "2026-08-09"
            quote: "job seekers are required to provide basic personal and professional information, to create a mini resume which can be viewed by interested enterprise users"
      why: |-
        The posting shows a job description and a chat button. Nothing on it tells you
        that the artefact being screened is your platform profile rather than the CV you
        spent your effort on, so candidates optimise the wrong document.
  ```

  Then add the remaining nine entries in the order of the disposition table.

- [ ] **Step 2: Run the lint to verify the table ships**

  Run:
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  python3 scripts/check_conventions.py --workspace /tmp/jh-lint \
      --market-file references/market-conventions/cn.yaml --today 2026-08-09
  ```
  Expected: exit `0`. Any `DIGIT_IN_PROSE`, `PERCENT_IN_PROSE`, `PROTECTED_TRAIT`, `MISSING_FIELD`, `BAD_SOURCE_*` or `EXPIRED_REVIEW_BY` line is a defect in the YAML, not in the lint — fix the YAML. `WARN_` lines do not fail; read each one and either fix the drift or record in the `# NEXT REVIEW` block why it is acceptable.

- [ ] **Step 3: Verify the entry count and ids**

  Run:
  ```
  cd /Users/donghanglyu/code_project/job-hunt && python3 -c "
  import pathlib, sys; sys.path.insert(0, 'scripts')
  import check_conventions as c
  d = c.load_market_file(pathlib.Path('references/market-conventions/cn.yaml'))
  ids = [e['id'] for e in d['conventions']]
  print(len(ids)); print('\n'.join(ids))"
  ```
  Expected: `10`, then the ten ids of the disposition table in that order.

- [ ] **Step 4: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add references/market-conventions/cn.yaml
  git commit -m "conventions: cn table, ten entries with the adversarial review applied"
  ```

---

### Task 8: `references/market-conventions/nl.yaml`

**Files:**
- Create: `references/market-conventions/nl.yaml`

**Interfaces:**
- Consumes: `check_conventions.check_file(path, today) -> list[str]`, `check_conventions.load_market_file(path) -> dict`; `references/market-conventions/README.md`; `docs/superpowers/research/2026-08-09-market-conventions/{markets.json,review-nl_weu.md}`.
- Produces: `references/market-conventions/nl.yaml` with nine entries, ids as in the table below (note the `nl-weu-` prefix is gone).

**Re-scoping.** The research key is `nl_weu`; the spec splits it and keeps `nl` only, because the Belgian half is two sourced facts with no application artifacts, no interview shape and no language expectations — the reviewer's own closing finding says "either scope the market key to NL, or source Belgium". So: **the Belgium-only entry is dropped, and every Belgian clause is cut out of the entries that survive.** Ids lose the `weu`.

**The build rule (repeated in full — do not improvise convention text).**

1. Read `entry.conventions[i]` in `markets.json` under `market: nl_weu`, and the matching numbered section of `review-nl_weu.md`.
2. **KEEP** → copy `text_en`, `text_zh`, `applies_when`, `why` byte-for-byte.
3. **KEEP-WITH-EDIT** → use the review's replacement wording byte-for-byte where it gives a whole field; splice only at the sentence it quotes where it gives a partial. Do not rewrite for style.
4. **DROP** → the entry appears in no table; id and one-line reason go in the `# DROPPED` comment block.
5. Restructure `source_kind` + `source_detail` into the structured `source:` mapping with `also:` for further citations, using the attribution the review corrects to.
6. `added: "2026-08-09"`; `review_by` from the table.
7. Apply only edits the reviewer wrote out; "Important and missing" goes verbatim into `# NEXT REVIEW` and nowhere else.

**Disposition — `nl`, from `review-nl_weu.md`.**

| # | New id | Verdict | Shipped text comes from | `review_by` |
|---|---|---|---|---|
| 1 | `nl-recognised-sponsor-gate` | KEEP-WITH-EDIT | review §1 replacement `text_en`/`text_zh`. Attribute the register quote to the **Work** register page only, and add the orientation-year permit citation to `source.also` — that permit is applied for by the candidate and breaks the "the employer is the deciding factor" frame. | 2027-02-09 |
| 2 | `nl-salary-criterion-reset-annually` | KEEP-WITH-EDIT | review §2: `text_en` as given; for `text_zh` splice in the market-rate sentence the review quotes and change nothing else. | 2026-11-09 |
| 3 | `nl-expat-scheme-is-an-employer-filing` | KEEP-WITH-EDIT | review §3 replacement blocks. **Live constraint violation: the old text carried "30% ruling" / 「30% 规则」 twice in each language.** Add the announced-reduction citation to `source.also`. | 2026-11-09 |
| — | `nl-weu-be-single-permit-is-regional` | **DROP** | Belgium-only. The spec's market keys are cn/nl/de/uk/us; an entry that can only ever fire on a Belgian posting can never render, and leaving it invites a Dutch applicant reading Belgian regional-competence advice. | — |
| 4 | `nl-sector-agreement-sets-the-band` | KEEP-WITH-EDIT | review §5 replacement blocks, **minus the Belgian sentence** — delete "In Belgium, sectoral minimum pay scales are set per joint committee (paritair comité / commission paritaire) and published in a government database." and its zh counterpart 「在比利时，行业最低工资表按「联合委员会」…公布。」 Use the review's replacement `applies_when` with "or Belgium" removed and "or joint committee" removed. Drop the Belgian citation from `source`. | 2027-02-09 |
| 5 | `nl-motivation-letter-is-scored` | KEEP-WITH-EDIT | review §6 replacement blocks and replacement `applies_when` (which already scopes Belgium out). Fix the misquoted phone sentence in `source.quote` to the page's exact wording, including the "first prepared clear questions" clause. | 2027-02-09 |
| 6 | `nl-language-requirement-must-be-justified` | KEEP-WITH-EDIT (heavy) | review §7 replacement blocks. Add the College-status citation to `source.also` — its opinions are authoritative but **not legally binding**, and the replacement text says so, which is the whole reason this entry survives rather than being dropped. | 2027-02-09 |
| 7 | `nl-references-only-with-prior-permission` | KEEP-WITH-EDIT | review §8 replacement blocks. Add NVP clause 2.3 verbatim to `source.also`, or delete the background-check sentence — do not ship the sentence with clause 2.6 attached to it. | 2027-08-09 |
| 8 | `nl-pay-range-not-pay-history` | KEEP-WITH-EDIT | `markets.json` text with review §9's middle replacement spliced in, **plus two constraint fixes**: replace the literal "2023/970" with "the EU pay-transparency directive" (en) and 「欧盟薪酬透明指令」 (zh), and add a `protected_trait_note` for the quoted "gender-neutral" / 「性别中立」 standard — it describes the *employer's* criteria inside a quoted legal test, not a candidate attribute. Use the review's replacement `applies_when` (EEA dropped). | 2026-11-09 |
| 9 | `nl-regulated-profession-needs-formal-recognition` | KEEP-WITH-EDIT | review §10 replacement blocks. | 2027-08-09 |

**`unverified` for `nl.yaml`.** Carry across the items from `markets.json` `nl_weu.entry.unverified` that still have a target after the re-scoping, each `{note, disclaims}`. The reviewer's cross-cutting finding is the acceptance criterion: in conventions 5, 6, 7 and 8 the `unverified` section correctly stated a claim was not sourced and the rendered text made that claim anyway. **Every claim `unverified` disclaims must be absent from the replacement text before this file is committed.** `WARN_UNVERIFIED_OVERLAP` is the mechanical hint; read the note and the text side by side yourself.

- [ ] **Step 1: Write the file**, following the shape of `cn.yaml`'s first entry: `market: nl`, a `# DROPPED` block naming `nl-weu-be-single-permit-is-regional`, a `# NEXT REVIEW` block carrying the review's "Important and missing" items 1–7 verbatim, then the nine entries in table order.

- [ ] **Step 2: Run the lint**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  python3 scripts/check_conventions.py --workspace /tmp/jh-lint \
      --market-file references/market-conventions/nl.yaml --today 2026-08-09
  ```
  Expected: exit `0`. In particular there must be **no** `PERCENT_IN_PROSE` on `nl-expat-scheme-is-an-employer-filing` and **no** `DIGIT_IN_PROSE` on `nl-pay-range-not-pay-history` — those two were the live violations this table is being rebuilt to close.

- [ ] **Step 3: Verify the entry count and that Belgium is gone**
  ```
  cd /Users/donghanglyu/code_project/job-hunt && python3 -c "
  import pathlib, sys; sys.path.insert(0, 'scripts')
  import check_conventions as c
  d = c.load_market_file(pathlib.Path('references/market-conventions/nl.yaml'))
  ids = [e['id'] for e in d['conventions']]
  blob = pathlib.Path('references/market-conventions/nl.yaml').read_text(encoding='utf-8')
  body = '\n'.join(l for l in blob.splitlines() if not l.lstrip().startswith('#'))
  print(len(ids)); print('\n'.join(ids))
  print('belgium mentions in body:', body.lower().count('belgi'), body.count('比利时'))"
  ```
  Expected: `9`, the nine ids, and `belgium mentions in body: 0 0`.

- [ ] **Step 4: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add references/market-conventions/nl.yaml
  git commit -m "conventions: nl table, re-scoped off nl_weu with the Belgian half dropped"
  ```

---

### Task 9: `references/market-conventions/de.yaml`

**Files:**
- Create: `references/market-conventions/de.yaml`

**Interfaces:**
- Consumes: `check_conventions.check_file(path, today) -> list[str]`, `check_conventions.load_market_file(path) -> dict`; `references/market-conventions/README.md`; `docs/superpowers/research/2026-08-09-market-conventions/{markets.json,review-de.md}`.
- Produces: `references/market-conventions/de.yaml` with eight entries.

**The build rule (repeated in full — do not improvise convention text).**

1. Read `entry.conventions[i]` in `markets.json` under `market: de`, and the matching numbered section of `review-de.md`.
2. **KEEP** → copy `text_en`, `text_zh`, `applies_when`, `why` byte-for-byte.
3. **KEEP-WITH-EDIT** → use the review's replacement wording byte-for-byte where it gives a whole field; splice only at the sentence it quotes where it gives a partial. Do not rewrite for style.
4. **DROP** → the entry appears in no table; id and one-line reason go in the `# DROPPED` comment block.
5. Restructure `source_kind` + `source_detail` into the structured `source:` mapping with `also:` for further citations, using the attribution the review corrects to.
6. `added: "2026-08-09"`; `review_by` from the table.
7. Apply only edits the reviewer wrote out; "Important and missing" goes verbatim into `# NEXT REVIEW` and nowhere else.

**Disposition — `de`, from `review-de.md`.**

| # | id | Verdict | Shipped text comes from | `review_by` |
|---|---|---|---|---|
| 1 | `de-arbeitszeugnis-is-a-graded-document` | KEEP-WITH-EDIT | review §1 replacement blocks. Both fixes are load-bearing: the certificate is **not** issued automatically (it is an entitlement you assert), and the grade above the middle needs 「stets」 **and** 「vollen」 together — a reinforcing word alone does not lift it, which is exactly the error this entry exists to prevent. | 2027-08-09 |
| 2 | `de-degree-classification-is-a-separate-procedure` | KEEP-WITH-EDIT | `markets.json` text with review §2's "third sentence onward" replacement spliced in. Drop the unsourced word "voluntary" from `source`; keep the anabin incompleteness caveat, which is the most actionable line on the source and was missing. Use the review's number-word substitutes: "are not the same thing, and are run by different bodies" / 「不是一回事，分属不同机构」. | 2027-08-09 |
| 3 | `de-employer-drives-the-permit-not-you` | KEEP-WITH-EDIT | `markets.json` text with **exactly two** reviewer-written edits: replace 「有义务保证求职者配合」 with 「有义务督促求职者履行配合义务」 (the statute says *work toward*, not *guarantee*), and add "for the skilled-worker and study-related residence purposes the provision lists" so the accelerated procedure does not read as universally available. | 2026-11-09 |
| 4 | `de-works-council-must-consent-to-the-hire` | KEEP-WITH-EDIT | review §4's replacement `applies_when` and its replacement tail for `text_en`/`text_zh`. The tail is the correction that matters: the council's objection window is short and consent counts as given if it lapses, so this stage cannot explain a long silence — the original invited a candidate to attribute months of nothing to the works council. | 2027-08-09 |
| 5 | `de-your-notice-period-sets-the-start-date` | KEEP-WITH-EDIT (substantive legal error) | review §5 replacement blocks, and add the § 23 KSchG citation the review supplies to `source.also`. The original collapsed the **employer-side** service-length ladder into a rule about the candidate's own resignation; a long-tenured candidate following it names a start date months later than the law requires and loses offers over a period they do not owe. | 2027-08-09 |
| 6 | `de-public-sector-pay-is-classified-not-negotiated` | KEEP-WITH-EDIT (source labelling only) | `markets.json` text verbatim. In `source`, name § 16 Abs. 2 **TV-L** for the BAG case and state that the BVA catalogue covers the **federal** agreement — the two cover different collective agreements and the citation did not say so. | 2027-02-09 |
| 7 | `de-application-is-a-file-not-a-cv` | KEEP-WITH-EDIT (ship-blocker) | review §7 replacement final sentences. **Fix the Cyrillic contamination: 「证明材料可另行索取」, not 「证明материалы可另行索取」** — that string renders verbatim to the reader. Add the counterweight sentence the agency states on the same page (limit the attachments to what the job needs). Cut the submission-mechanics sentence; it is layout, and this table is about what the market weighs. | 2027-02-09 |
| 8 | `de-austrian-and-swiss-certificates-do-not-transfer` (renamed from `de-dach-reference-letters-do-not-transfer`) | KEEP-WITH-EDIT | `markets.json` text with review §8's replacement Austrian clause, plus the SECO sentence that a Swiss certificate may carry negatives where material. Update the SECO url to its 301 target. `applies_when` re-scoped: the candidate holds Austrian or Swiss work history **and is applying in Germany**. | 2027-08-09 |
| — | `de-dach-ch-permit-is-employer-filed-and-capped` | **DROP** | Switzerland-only. The spec fixes the key set at cn/nl/de/uk/us, so this can never render under any of them — and if a renderer ever ignored `applies_when`, a German applicant would read Swiss quota advice as their own. | — |
| — | `de-dach-at-advertised-pay-is-a-floor` | **DROP** | Austria-only, same reason. Entry 8 survives because its subject is a document a **German** employer will read. | — |

**`unverified` for `de.yaml`.** Carry the `de.entry.unverified` items across as `{note, disclaims}`, **with two corrections the reviewer made**: the item claiming no official source could be found on the Bewerbungsfoto is wrong (the source is a page the entry already cites), so drop that item and record the correction in `# NEXT REVIEW`; and the item on the Anschreiben's status at international employers stays, disclaiming `de-application-is-a-file-not-a-cv`.

- [ ] **Step 1: Write the file** — `market: de`, a `# DROPPED` block naming both DACH entries with the reasons above, a `# NEXT REVIEW` block carrying `review-de.md`'s "Important and missing" items 1–5 verbatim, then the eight entries in table order.

- [ ] **Step 2: Run the lint**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  python3 scripts/check_conventions.py --workspace /tmp/jh-lint \
      --market-file references/market-conventions/de.yaml --today 2026-08-09
  ```
  Expected: exit `0`.

- [ ] **Step 3: Verify the count, the ids, and that no Cyrillic survived**
  ```
  cd /Users/donghanglyu/code_project/job-hunt && python3 -c "
  import pathlib, re, sys; sys.path.insert(0, 'scripts')
  import check_conventions as c
  p = pathlib.Path('references/market-conventions/de.yaml')
  d = c.load_market_file(p)
  ids = [e['id'] for e in d['conventions']]
  print(len(ids)); print('\n'.join(ids))
  print('cyrillic:', re.findall(r'[Ѐ-ӿ]+', p.read_text(encoding='utf-8')))"
  ```
  Expected: `8`, the eight ids, and `cyrillic: []`.

- [ ] **Step 4: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add references/market-conventions/de.yaml
  git commit -m "conventions: de table, DACH-only entries dropped and the notice-period error fixed"
  ```

---

### Task 10: `references/market-conventions/uk.yaml`

**Files:**
- Create: `references/market-conventions/uk.yaml`

**Interfaces:**
- Consumes: `check_conventions.check_file(path, today) -> list[str]`, `check_conventions.load_market_file(path) -> dict`; `references/market-conventions/README.md`; `docs/superpowers/research/2026-08-09-market-conventions/{markets.json,review-us_uk.md}`.
- Produces: `references/market-conventions/uk.yaml` with five entries. `uk-civil-service-scores-named-behaviours-not-cover-letters` is the entry `lint_no_prediction.py`'s blockquote allowlist exists for — an employer that publishes its own rubric.

**Re-scoping.** The research key is `us_uk`; the spec splits it, because the two markets are very different and the bundle made a US-sourced claim read as universal. Entries 7–10 are UK and come here; 1, 2, 3, 5, 6 are US and go to Task 11. Entry 4 covered both and is **split into two entries**, one per table, each carrying only its own half of the review's replacement text. Ids lose the `us_uk-` prefix and the `uk-` prefix stays.

**The build rule (repeated in full — do not improvise convention text).**

1. Read `entry.conventions[i]` in `markets.json` under `market: us_uk`, and the matching numbered section of `review-us_uk.md`.
2. **KEEP** → copy `text_en`, `text_zh`, `applies_when`, `why` byte-for-byte.
3. **KEEP-WITH-EDIT** → use the review's replacement wording byte-for-byte where it gives a whole field; splice only at the sentence it quotes where it gives a partial. Do not rewrite for style.
4. **SPLIT** → take only the sentences of the review's replacement text that belong to this market, and nothing else.
5. Restructure `source_kind` + `source_detail` into the structured `source:` mapping with `also:` for further citations, using the attribution the review corrects to.
6. `added: "2026-08-09"`; `review_by` from the table.
7. Apply only edits the reviewer wrote out; "Important and missing" goes verbatim into `# NEXT REVIEW` and nowhere else.

**Disposition — `uk`, from `review-us_uk.md`.**

| # | New id | Verdict | Shipped text comes from | `review_by` |
|---|---|---|---|---|
| 1 | `uk-check-the-public-sponsor-register-before-applying` | KEEP | `markets.json` verbatim (review §7: no digits, no drift, no overreach; refusing to state the salary figure and pointing at gov.uk is the correct pattern for a fact that changes yearly). Needs `protected_trait_note` only if the shipped text names a nationality term — check the lint output rather than assuming. | 2027-02-09 |
| 2 | `uk-right-to-work-check-is-universal-and-you-pick-the-evidence` | KEEP-WITH-EDIT (small) | `markets.json` text with review §8's scoping change: "but **if you are not a British or Irish citizen** the choice of evidence is yours" / 「但若你不是英国或爱尔兰公民，选择用哪种证明是你的权利」. British and Irish citizens have a different route entirely. Add `protected_trait_note`: the fact **is** a citizenship-based evidence rule, and scoping it is what makes it correct rather than what makes it discriminatory. | 2027-02-09 |
| 3 | `uk-civil-service-scores-named-behaviours-not-cover-letters` | KEEP-WITH-EDIT (small) | `markets.json` text with review §9's three fixes: add the two verified job-description sentences to `source` so the row is self-defending; soften "A general letter … scores nothing" to the review's exact replacement ("does not evidence any named behaviour, and each one is assessed on its own evidence" / 「无法为任何一项被点名的行为提供证据…」); add "where behaviours are assessed," because the page conditions it on the recruiting manager choosing to assess them. | 2027-02-09 |
| 4 | `uk-nhs-shortlisting-is-assessed-against-the-person-specification` | KEEP-WITH-EDIT (substantive) | `markets.json` text with review §10's replacement second half, **and the id and opening changed from "scored" to "assessed"** — "scored" is not sourced; the pages say "judging how well your application matches". The conflation fix is the point: the *supporting information* section is where NHS Jobs tells you to sell yourself, and the *essential-and-desirable-criteria* section is the one carrying the do-not-identify-yourself instruction. A reader following the original would anonymise and de-narrativise the wrong box. | 2026-11-09 |
| 5 | `uk-notice-period-sets-your-start-date` | KEEP-WITH-EDIT, SPLIT from `us_uk-at-will-versus-notice-period-changes-your-start-date` | **Only the UK sentences** of review §4's replacement `text_en`/`text_zh` — from "The UK works the other way:" to "…is therefore negotiated around a notice period as a matter of course." Plus the closing cross-market sentence, rewritten to the single market it now serves: keep "check your own contract, which may set the notice you owe". The review verified the UK half fully; it is the US half that rested on one state's agency. Restore the truncated gov.uk quote in `source.quote` — the sentence continues "…or give notice verbally when it should be given in writing." | 2027-02-09 |

**`unverified` for `uk.yaml`.** Carry across the UK-relevant items of `us_uk.entry.unverified` as `{note, disclaims}`, including item 6 (UK employment law in flux) disclaiming `uk-notice-period-sets-your-start-date`.

- [ ] **Step 1: Write the file** — `market: uk`, a `# NEXT REVIEW` block carrying `review-us_uk.md`'s "Important and missing" item 1 (the **Civil Service Nationality Rules** eligibility gate that sits in front of everything entry 3 describes — verified, published, and omitted; the reviewer flags that it names a protected trait, so a person must decide) and item 3 (the two suppressed thresholds), then the five entries in table order.

- [ ] **Step 2: Run the lint**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  python3 scripts/check_conventions.py --workspace /tmp/jh-lint \
      --market-file references/market-conventions/uk.yaml --today 2026-08-09
  ```
  Expected: exit `0`. `PROTECTED_TRAIT` on `uk-right-to-work-check-is-universal-and-you-pick-the-evidence` must be closed by a written `protected_trait_note`, never by deleting the scoping — deleting it would make the entry wrong.

- [ ] **Step 3: Verify the count and ids**
  ```
  cd /Users/donghanglyu/code_project/job-hunt && python3 -c "
  import pathlib, sys; sys.path.insert(0, 'scripts')
  import check_conventions as c
  d = c.load_market_file(pathlib.Path('references/market-conventions/uk.yaml'))
  ids = [e['id'] for e in d['conventions']]
  print(len(ids)); print('\n'.join(ids))"
  ```
  Expected: `5`, and no id containing `scored` or `us_uk`.

- [ ] **Step 4: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add references/market-conventions/uk.yaml
  git commit -m "conventions: uk table split out of us_uk, NHS section conflation fixed"
  ```

---

### Task 11: `references/market-conventions/us.yaml` and the all-tables regression test

**Files:**
- Create: `references/market-conventions/us.yaml`
- Test: `scripts/tests/test_market_tables.py`

**Interfaces:**
- Consumes: `check_conventions.check_file(path, today) -> list[str]`, `check_conventions.load_market_file(path) -> dict`, `check_conventions.MARKET_KEYS`; `docs/superpowers/research/2026-08-09-market-conventions/{markets.json,review-us_uk.md}`.
- Produces: `references/market-conventions/us.yaml` with six entries, and a test that holds **all five** shipped tables to the lint on every run.

**The build rule (repeated in full — do not improvise convention text).**

1. Read `entry.conventions[i]` in `markets.json` under `market: us_uk`, and the matching numbered section of `review-us_uk.md`.
2. **KEEP** → copy `text_en`, `text_zh`, `applies_when`, `why` byte-for-byte.
3. **KEEP-WITH-EDIT** → use the review's replacement wording byte-for-byte where it gives a whole field; splice only at the sentence it quotes where it gives a partial. Do not rewrite for style.
4. **SPLIT** → take only the sentences of the review's replacement text that belong to this market, and nothing else.
5. Restructure `source_kind` + `source_detail` into the structured `source:` mapping with `also:` for further citations, using the attribution the review corrects to.
6. `added: "2026-08-09"`; `review_by` from the table.
7. Apply only edits the reviewer wrote out; "Important and missing" goes verbatim into `# NEXT REVIEW` and nowhere else.

**Disposition — `us`, from `review-us_uk.md`.**

| # | New id | Verdict | Shipped text comes from | `review_by` |
|---|---|---|---|---|
| 1 | `us-authorisation-and-sponsorship-are-separate-screens` | KEEP-WITH-EDIT | review §1 replacement `text_en`/`text_zh` and replacement `why`. The original claimed what US application *forms* do; the source only says an employer *may ask*. Add `protected_trait_note`: the fact **is** a citizenship-status discrimination rule, and the complaint route is unusable without naming the basis. | 2027-08-09 |
| 2 | `us-employer-class-decides-h1b-cap-exposure` | KEEP-WITH-EDIT | review §2 replacement `text_en`/`text_zh` and replacement `why`. Three fixes: restore the "at a qualifying institution" limb of the duties test, correct `why` (cap exemption turns on the organisation **and** the duties — the original `why` contradicted the regulation the entry cites), and drop the absolute "postings never mention this". `H-1B` is on the lint's `PROPER_NOUNS` allowlist — **do not delete it to satisfy a lint**, it is the only string that makes this entry findable. | 2026-11-09 |
| 3 | `us-stem-opt-is-an-employer-side-requirement` | KEEP-WITH-EDIT (one word each) | `markets.json` text with "never" → "rarely" and 「从不披露」 → 「很少披露」. Everything else survived scrutiny intact. **Do not add an E-Verify employer lookup**: the reviewer's fetch returned HTTP 403 and they make no claim that a public one exists. | 2027-02-09 |
| 4 | `us-at-will-is-the-default` | KEEP-WITH-EDIT, SPLIT from `us_uk-at-will-versus-notice-period-changes-your-start-date` | **Only the US sentences** of review §4's replacement `text_en`/`text_zh` — from "US employment is at-will in the ordinary case" to "…the customary short resignation notice is a norm, not an entitlement." That replacement already carries the scoping the original lacked: at-will is state law rather than a federal statute, so it is a default and not a universal rule. The unsourced employer-behaviour claims ("US employers commonly expect a near-term start date", "the at-will wording is standard boilerplate") do **not** ship. | 2027-02-09 |
| 5 | `us-pay-range-in-a-posting-is-jurisdictional-not-cultural` | KEEP-WITH-EDIT | `markets.json` text with review §5's four fixes: cite the redirect **destination** URL for Colorado so the row does not rot; change 「在所有对外发布的职位、晋升和调岗机会中」 to 「在其对外发布的相关职位、晋升和调岗机会中」 (the source says "designated", not "all"); add "a job description and" before "a compensation range" in en and 「职位描述与」 in zh; leave "mostly" as "mostly" and do not let it drift to "only". | 2026-11-09 |
| 6 | `us-you-choose-your-form-i9-documents` | KEEP-WITH-EDIT | review §6 replacement for the last two sentences of `text_en`/`text_zh`. **Two things must be fixed or this must not ship.** (a) `source.quote` currently ends `"Employers can't specify which documents they" [require]` — `[require]` is a word nobody wrote, closing a quote cut mid-clause. The real sentence is `"Employers can't specify which documents they will accept from a worker and should not prevent an individual from working because of a document's future expiration date."` Use it in full. (b) The prohibition is conditional in the source — "on the basis of citizenship, immigration status, or national origin" — and dropping that basis leaves a reader with no complaint. The replacement text restores it. Add `protected_trait_note` for the same reason as entry 1. | 2027-08-09 |

**`unverified` for `us.yaml`.** Carry the US-relevant items of `us_uk.entry.unverified` across as `{note, disclaims}`, **with the reviewer's correction**: item 5 says no official source was verified for a US salary-history ban, and the entry's own Colorado source contains one verbatim. Drop that item and record the correction in `# NEXT REVIEW`.

- [ ] **Step 1: Write the file** — `market: us`, a `# NEXT REVIEW` block carrying `review-us_uk.md`'s "Important and missing" items 2 (Colorado's pay-history ban, verbatim from a page already fetched) and 3 (the two suppressed thresholds — `at least half of their work time` and `four or more employees`, both verified and both currently unusable as written), plus the "Could not source" note about the E-Verify lookup, then the six entries in table order.

- [ ] **Step 2: Write the all-tables regression test**

  Create `scripts/tests/test_market_tables.py`:
  ```python
  import datetime
  import pathlib

  import check_conventions as cck

  ROOT = pathlib.Path(__file__).resolve().parents[2] / "references" / "market-conventions"
  # Pinned so the suite does not start failing on a review_by date rolling past. When it
  # does roll past, that is the CI lint's job to say so, not this test's.
  BUILD_DAY = datetime.date(2026, 8, 9)

  EXPECTED_COUNTS = {"cn": 10, "nl": 9, "de": 8, "uk": 5, "us": 6}


  def test_every_market_key_has_a_table():
      for key in cck.MARKET_KEYS:
          assert (ROOT / f"{key}.yaml").exists(), key


  def test_every_shipped_table_passes_the_lint_with_no_hard_finding():
      for key in cck.MARKET_KEYS:
          findings = cck.check_file(ROOT / f"{key}.yaml", BUILD_DAY)
          hard = [f for f in findings if not f.startswith("WARN_")]
          assert hard == [], f"{key}.yaml: {hard}"


  def test_the_entry_counts_match_the_dispositions_the_reviewer_signed_off():
      for key, expected in EXPECTED_COUNTS.items():
          data = cck.load_market_file(ROOT / f"{key}.yaml")
          assert len(data["conventions"]) == expected, key


  def test_no_id_collides_across_tables():
      seen: dict[str, str] = {}
      for key in cck.MARKET_KEYS:
          for entry_id in cck.conventions_by_id(cck.load_market_file(ROOT / f"{key}.yaml")):
              assert entry_id not in seen, f"{entry_id} in {key} and {seen[entry_id]}"
              seen[entry_id] = key


  def test_the_dropped_entries_appear_in_no_table():
      dropped = ("nl-weu-be-single-permit-is-regional",
                 "de-dach-ch-permit-is-employer-filed-and-capped",
                 "de-dach-at-advertised-pay-is-a-floor")
      for key in cck.MARKET_KEYS:
          ids = set(cck.conventions_by_id(cck.load_market_file(ROOT / f"{key}.yaml")))
          assert ids.isdisjoint(dropped), key


  def test_the_three_live_violations_the_reviewer_found_are_gone():
      # "51job" in an English body, "30% ruling" in both languages, "2023/970" in a body.
      cn = (ROOT / "cn.yaml").read_text(encoding="utf-8")
      nl = (ROOT / "nl.yaml").read_text(encoding="utf-8")
      for blob, needle in ((cn, "51job"), (nl, "30%"), (nl, "2023/970")):
          body = "\n".join(l for l in blob.splitlines() if not l.lstrip().startswith("#"))
          assert needle not in body, needle


  def test_the_allowlisted_proper_nouns_survived_the_digit_ban():
      us = (ROOT / "us.yaml").read_text(encoding="utf-8")
      for needle in ("H-1B", "Form I-9"):
          assert needle in us, needle
  ```

- [ ] **Step 3: Run the lint and the test**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  python3 scripts/check_conventions.py --workspace /tmp/jh-lint --all --today 2026-08-09
  python3 -m pytest scripts/tests/test_market_tables.py -q
  ```
  Expected: the lint exits `0`; the test reports PASS (7 passed).

- [ ] **Step 4: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add references/market-conventions/us.yaml scripts/tests/test_market_tables.py
  git commit -m "conventions: us table plus an all-tables regression over the shipped five"
  ```

---

### Task 12: `modes/assess.md` — the layer-1.5 mode file

**Files:**
- Create: `modes/assess.md`

**Interfaces:**
- Consumes: `paths.workspace(name, company, role, date)`; `scripts/evidence_blocks.py`, `scripts/count_coverage.py`, `scripts/consistency.py`, `scripts/check_evidence_refs.py`, `scripts/lint_no_prediction.py`, `scripts/check_conventions.py`, `scripts/check_assessment.py`; `references/market-conventions/{cn,nl,de,uk,us}.yaml`.
- Produces (these are the definitions Task 13 enforces and nothing else supplies):
  - the `posting.yaml` field list,
  - the `fit-assessment.yaml` row schema,
  - `DISCLAIMER_ANCHOR_ZH = "不是对结果的预判"` and `DISCLAIMER_ANCHOR_EN = "not a forecast of the outcome"`,
  - the closed strategy set `apply_anyway | reposition | skill_sprint | side_door | change_track`,
  - the 30/60/90 column names 目标 | 行动 | 验收标准 and the roadmap's 输出物 column.

**Why this file is layer 1.5 and not a reference.** Entering assess mode loads it unconditionally — the model never has to judge whether it is relevant, there are only four such files, and the choice is deterministic. It has two backstops at once: `check_assessment.py` requires artifact fields that only this file defines, and `journal.jsonl` records its content hash. That is what makes it different from the optional-reference regression this skill's owner has already been bitten by.

- [ ] **Step 1: Write the file**

  Create `modes/assess.md` with exactly this content:
  `````markdown
  # Mode: assess — 该不该投

  **Entry condition:** a posting exists — a URL, pasted text, or a row the user named from
  a shortlist. Nothing else in this file runs until step 1 has produced usable text.

  **This mode owns** `posting.yaml`, `posting-source.txt`, `cv-source.txt`,
  `evidence-blocks.json`, `fit-assessment.yaml`, `fit-assessment.md`, `coverage.json`.
  It reads `profile.yaml` and never writes it. Workspace path, byte-identical in shape to
  the old skill so "resume an unfinished application" keeps working:
  `~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`

  ---

  ## 1. Fetch-integrity gate — a 200 OK is not evidence you have the posting

  LinkedIn, Workday, Greenhouse, Lever, Taleo, iCIMS and most portals return a success
  status for a login wall, a cookie banner, a bot check or a search page. Extracting
  must-haves off a login wall produces a document that is internally consistent and
  entirely wrong, and every later step inherits it.

  | Reading | Verdict |
  |---|---|
  | About 300 words or more of readable job-description prose **and** a requirements or qualifications section | **usable** — proceed |
  | Under about 200 words, **or** no qualifications language, **or** a login / consent / bot-check prompt | **blocked** — ask the user to paste the full posting text |
  | Between those, or ambiguous | treat as blocked and ask; the cost of asking is one message |

  Save whatever you got, verbatim and unedited, as `posting-source.txt`. That file is the
  end of the source chain for every downstream claim — editing it makes provenance
  theatre. If the posting genuinely cannot be obtained, stop and say so. Never proceed on
  guessed requirements.

  ## 2. Market — ask, do not infer

  Ask the user which market this role is in. Do not match place names: a wrong market card
  reads exactly like a right one and the reader has no source text to check it against.
  If `search-preferences.yaml` already holds a target market, confirm it **once per
  session** rather than once per posting — but re-ask whenever the posting's location does
  not match the stored market.

  Markets with tables: `cn`, `nl`, `de`, `uk`, `us`. Anything else →
  「本市场无惯例数据」 and no convention card at all. **Never substitute a neighbouring
  market's conventions.**

  ## 3. Extract `posting.yaml` — the complete field list

  ```yaml
  role_title: "..."          # exactly as written in the posting
  seniority: mid             # intern | junior | mid | senior | lead
  location:
    city: "..."
    country: "..."
    arrangement: onsite      # remote | hybrid | onsite
  must_haves: []             # required / essential / minimum / "you must"
  nice_to_haves: []          # preferred / bonus / a plus / ideally / advantageous
  responsibilities: []       # what the person will actually do, in the posting's words
  keywords: []               # exact ATS terms, casing preserved: "PyTorch", "CI/CD"
  company_values_tone: "..."
  red_flags: []
  salary_range: null         # the stated band, or null
  application_type: cv       # cv | structured
  language: en               # the posting's own language
  ```

  Two fields carry weight far past their size, and an earlier compression of this list
  **silently dropped both**:
  - `salary_range` — when present, ask the user **once** whether the band fits. A band
    mismatch is a common silent screen-out and is cheaper to surface now than after a
    full application. If no range is stated, do not raise salary at all.
  - `application_type` — `structured` when the posting splits Essential / Desirable
    criteria, names behaviours or a competency framework, or asks the applicant to
    evidence each criterion. It is the **only** signal that routes to a
    supporting-statement deliverable in `apply`. Getting it wrong produces a perfectly
    good CV for a process that does not read CVs.

  Non-English cue words map the same way: `Erforderlich` / `Voraussetzungen` /
  `Sie bringen mit` → must_have; `Wünschenswert` / `von Vorteil` → nice_to_have;
  `Exigé` / `Requis` → must_have; `Souhaité` → nice_to_have; `必须` / `必备` → must_have;
  `歓迎` / `尚可` / `加分` → nice_to_have.

  ## 4. Disqualifiers first, and ask

  A disqualifier is a wall, not a wish: work authorization, a legally required licence or
  clearance, a hard on-site requirement, language fluency, a regulated experience floor.
  Surface these **before anything else** and ask the user directly whether they meet them.
  No reframing closes a legal barrier, and a "mitigation" that treats one as a wording
  problem reads to a recruiter as already handled.

  ## 5. Cut evidence blocks

  ```
  python3 scripts/evidence_blocks.py --workspace <ws> \
      --jd <ws>/posting-source.txt --cv <ws>/cv-source.txt
  ```
  `cv-source.txt` is the CV text this assessment cites — paste, or a copy of the master
  profile. Do not hand-write `evidence-blocks.json`; it is derived.

  **What blocks buy, stated honestly and carried into your output:** a reference that
  resolves guarantees the claim points at something real. It does **not** guarantee the
  claim follows from it. It is a plausibility bound, not a proof.

  ## 6. The requirement table

  One row per must-have and per named responsibility. This schema is defined here and
  nowhere else; `check_assessment.py` requires it.

  ```yaml
  requirements:
    - id: R1
      kind: must_have          # must_have | responsibility
      text: "the requirement in the posting's own words"
      level: required          # required | preferred | unclear   — what the posting CALLS it
      screening: knockout      # knockout | weighted | nice_to_have — what it DOES at screening
      match: partial           # strong | partial | gap | no_evidence
      recency: recent          # current | recent | dated | undated
      effort: evening          # quick | evening | multi_day | not_closable — to close THIS row
      how_to_close: "..."      # "" when nothing closes it
      evidence: [{ref: CV-012}]
  ```

  `level` and `screening` are separate axes on purpose, and it is the least obvious win
  here: most "required" lists are wish-lists, and counting the label is exactly what turns
  a missing clearance from a **stop** into a score deduction.

  Row rules, enforced by `check_assessment.py`:
  - `match: no_evidence` → `evidence: []`. Every other row needs at least one ref that
    resolves. An absent citation never means the thing is absent — it means nobody cited it.
  - Print every row in `fit-assessment.md` **with its evidence reference**. That is what
    makes the denominator auditable and lets a reader object to one line rather than to
    the whole number. Block ids belong in that table and nowhere else in the prose.

  ## 7. Countable facts, no score

  Run `python3 scripts/count_coverage.py --workspace <ws>` and paste its block verbatim
  into `fit-assessment.md` inside a fence. It is the **only** counting path; a second
  number written by hand will fail the gate.

  ```
  must-have 强证据：   8 of 11   （partial 2，gap 1，无证据 0）
  核心职责已证实：     4 of 6
  职级匹配：           平级
  可补缺口所需投入：   一晚
  投递建议：           大概率被筛掉
  ```

  `强证据` counts `strong` only. `partial` and `gap` are never merged into a covered
  number. Evidence that is only `dated` counts as `partial`.

  **Required disclaimer, immediately under the block. Ship one of these two, unchanged:**

  > ⚠️ 以上是对证据的清点，不是对结果的预判。每一项都连同它的证据引用一起印出，分母可以逐条审计；
  > 本 skill 不给出面试或录用的可能性估计，也不给 0–100 分。要不要投，由你决定。

  > ⚠️ This is a count of evidence, not a forecast of the outcome. Every item is printed
  > with its evidence reference so the denominator can be audited row by row. This skill
  > states no interview or hiring outcome estimate and no 0–100 score. Whether to apply
  > is your call.

  The disclaimer is what stops a count being read as a prediction. `check_assessment.py`
  looks for 「不是对结果的预判」 or "not a forecast of the outcome".

  ## 8. The refusal floor — 证据不足，不出结论

  Set `verdict: insufficient_evidence` and print **no** coverage block and **no** verdict
  from the five-level list when any of these holds:
  - the posting could not be read,
  - the CV could not be read,
  - an image source has regions you cannot make out,
  - the CV is a skills list with no supporting entries behind it.

  Say what you could not read and what you need. **When the input cannot support a
  conclusion, a confident positive conclusion is forbidden.** This is a floor, not a sixth
  verdict level: it is orthogonal to the ordered five, because "I could not read the
  input" is not a point on that scale.

  ## 9. Market convention cards — verbatim, id-allowlisted

  Load `references/market-conventions/<market>.yaml`. Render only entries whose
  `applies_when` is satisfied, and render `text_en` / `text_zh` **character for
  character**. You may not author, strengthen or extend an entry, attach a number to one,
  or invent one. If an entry's `review_by` has passed, still render it, with a
  「已过复核期」 banner.

  The one sentence you write in this section is where **this CV** stands against the
  convention, and it cites CV blocks like any other claim. List the ids you rendered in
  `conventions_rendered:`.

  Conventions feed **neither the verdict nor any consistency check**. They are the one
  class of claim with no source text behind them; keeping them out of the arithmetic is
  what stops an unciteable assertion moving a citeable conclusion.

  ## 10. When the verdict is 大概率被筛掉 or 硬性阻断: the other half

  A verdict without this half is a door closed with nothing behind it. Produce all three.

  **(a) Exactly one strategy**, from this closed set — not two, not a menu:

  | Strategy | Use it when |
  |---|---|
  | `apply_anyway` 投了再说 | The gap is soft and the cost of applying is an evening |
  | `reposition` 重新定位 | The same evidence reads much better against a different role family |
  | `skill_sprint` 技能冲刺 | One named, closable requirement is doing all the blocking |
  | `side_door` 侧门切入 | A contract, internal transfer, adjacent team or smaller employer reaches the same work |
  | `change_track` 换方向 | The blocking requirement is structural and not worth closing for this goal |

  **(b) A 30/60/90 table** with exactly these columns:

  | 目标 | 行动 | 验收标准 |
  |---|---|---|
  | ... | ... | ... |

  **(c) A roadmap carrying an 输出物 column.**

  `验收标准` and `输出物` are where the entire value of this section sits — they are what
  turn advice into something checkable. Every row of both tables must also appear in
  `actions:` in `fit-assessment.yaml`; that list is the single authoritative to-do list,
  and `consistency.py` compares it against the closable gaps.

  ## 11. Gates — run all of them, in this order

  ```
  python3 scripts/count_coverage.py      --workspace <ws>
  python3 scripts/consistency.py         --workspace <ws>
  python3 scripts/check_evidence_refs.py --workspace <ws>
  python3 scripts/lint_no_prediction.py  --workspace <ws>
  python3 scripts/check_assessment.py    --workspace <ws>
  ```

  Attach every notice `consistency.py` printed beside the thing it qualifies. Notices
  **report and never repair**: code can see two fields disagree, it cannot see which one
  is right, and choosing silently would swap a visible contradiction for an invisible
  guess.

  **Never report success without a receipt.** A skipped gate produces no output, and that
  looks exactly like a clean one. `check_assessment.py` writes the receipt that lets you
  say this passed.

  ## 12. Self-check before you hand this over

  - [ ] `posting-source.txt` is verbatim and unedited; `posting.yaml` carries
        `salary_range` and `application_type`.
  - [ ] Disqualifiers were asked about, and they render **before** the verdict.
  - [ ] Every requirement row prints its evidence reference; no block id appears in prose.
  - [ ] The coverage block is the one `count_coverage.py` produced, byte for byte.
  - [ ] The disclaimer is present, unchanged, directly under the block.
  - [ ] No percentage, no `n/m` score, no prediction word — except a quoted employer
        rubric with its source named on the next line.
  - [ ] Convention cards are verbatim from `references/market-conventions/<market>.yaml`,
        `applies_when` was honoured, and `conventions_rendered` lists their ids.
  - [ ] Every consistency notice that fired is attached where it fired.
  - [ ] If the verdict is 大概率被筛掉 or 硬性阻断: one strategy, a 30/60/90 table with
        `验收标准`, and a roadmap with `输出物` — all mirrored into `actions:`.
  - [ ] A discover-stage 「基于卡片信息的初判」 verdict was **not** copied in. assess
        always recomputes.
  - [ ] `check_assessment.py` exited 0 and its receipt is in `journal.jsonl`.
  `````

- [ ] **Step 2: Verify the file defines what the gate will look for**

  Run:
  ```
  cd /Users/donghanglyu/code_project/job-hunt && python3 -c "
  import pathlib
  t = pathlib.Path('modes/assess.md').read_text(encoding='utf-8')
  for needle in ['不是对结果的预判', 'not a forecast of the outcome', 'salary_range',
                 'application_type', 'insufficient_evidence', 'how_to_close',
                 'conventions_rendered', '验收标准', '输出物', 'apply_anyway',
                 'side_door', 'change_track']:
      assert needle in t, needle
  print('all anchors present')"
  ```
  Expected: `all anchors present`

- [ ] **Step 3: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add modes/assess.md
  git commit -m "assess: layer-1.5 mode file defining the row schema and the refusal floor"
  ```

---

### Task 13: `check_assessment.py` — the assess-mode gate

**Files:**
- Create: `scripts/check_assessment.py`
- Test: `scripts/tests/test_check_assessment.py`

**Interfaces:**
- Consumes:
  - `journal.receipt(...)`, `journal.sha256_file(path)`, `journal.read_receipts(workspace, gate)`
  - `check_evidence_refs.load_block_ids(path) -> set[str]`, `check_evidence_refs.drop_unresolvable_refs(assessment, ids) -> tuple[dict, list[str]]`, `check_evidence_refs.strip_block_ids(markdown) -> tuple[str, list[str]]`
  - `lint_no_prediction.scan_text(text, label) -> list[str]`, `lint_no_prediction.target_files(workspace) -> list[pathlib.Path]`
  - `consistency.notices(assessment) -> list[dict]`
  - `count_coverage.coverage(rows) -> dict`, `count_coverage.render_block(assessment, counts, lang) -> str`
  - `check_conventions.check_file(path, today) -> list[str]`, `check_conventions.conventions_by_id(data) -> dict`, `check_conventions.load_market_file(path) -> dict`, `check_conventions.MARKET_KEYS`
  - the anchors defined in `modes/assess.md`
- Produces: `DISCLAIMER_ANCHORS`, `check(workspace, market_dir, today) -> list[str]`, `main(argv=None) -> int`

**What this gate adds on top of the five it composes.** Each of these closes a way the assessment can be internally consistent and still wrong:
- **`ROW_UNSOURCED`** — a row that claims a match with no resolvable reference. `no_evidence` with an empty list is the honest shape and passes.
- **`NO_DISCLAIMER`** — the counts without the disclaimer is a count that reads as a prediction.
- **`DISQUALIFIER_AFTER_VERDICT`** — a hard barrier printed after the conclusion has already been read is a barrier nobody registered.
- **`NOTICE_NOT_ATTACHED`** — a contradiction the code found and the document did not mention is a contradiction the reader averages away.
- **`COUNT_MISMATCH`** — a number in the document that `count_coverage.py` did not produce is a second, unreconciled number.
- **`CONVENTION_PARAPHRASED`** — the model restating a convention is exactly how a 「usually」 becomes a 「must」 with nothing to check it against.
- **`REFUSAL_WITH_VERDICT`** — a refusal that still prints a conclusion is not a refusal.

- [ ] **Step 1: Write the failing test**

  Create `scripts/tests/test_check_assessment.py`:
  ```python
  import copy
  import datetime
  import json

  import yaml

  import check_assessment as ca
  import count_coverage as cc

  TODAY = datetime.date(2026, 8, 9)

  BLOCKS = {"blocks": [
      {"id": "CV-001", "source": "cv", "text": "Built a C++ reconstruction pipeline"},
      {"id": "CV-002", "source": "cv", "text": "Ran Slurm jobs on a shared cluster"},
      {"id": "JD-001", "source": "jd", "text": "Five years of C++"},
      {"id": "JD-002", "source": "jd", "text": "You must already hold an EU work permit"},
  ]}

  MARKET = {"market": "nl", "conventions": [{
      "id": "nl-recognised-sponsor-gate",
      "text_en": "Check the company in the public register of recognised sponsors before "
                 "you invest in a tailored application.",
      "text_zh": "投递前先在公开的认可担保方名录里查一下这家公司，再决定要不要为它定制材料。",
      "applies_when": "A Netherlands role that needs a work-related residence permit.",
      "added": "2026-08-09", "review_by": "2027-08-09",
      "source": {"kind": "published", "publisher": "IND",
                 "title": "Highly skilled migrant",
                 "url": "https://ind.nl/en/residence-permits/work/highly-skilled-migrant",
                 "retrieved": "2026-08-09",
                 "quote": "Only an employer recognised by the IND can apply for your permit."},
      "why": "A posting often says nothing either way about sponsor status.",
  }]}

  ASSESSMENT = {
      "market": "nl", "verdict": "worth_applying", "provisional": False,
      "effort": "evening", "level_direction": "lateral",
      "declared_work_status": "authorized",
      "stated_conditions": [{"type": "work_authorization", "stance": "requires_existing",
                             "evidence": [{"ref": "JD-002"}]}],
      "requirements": [
          {"id": "R1", "kind": "must_have", "text": "Five years of C++", "level": "required",
           "screening": "knockout", "match": "strong", "recency": "current",
           "effort": "quick", "how_to_close": "",
           "evidence": [{"ref": "CV-001"}, {"ref": "JD-001"}]},
          {"id": "R2", "kind": "must_have", "text": "Kubernetes in production",
           "level": "required", "screening": "weighted", "match": "no_evidence",
           "recency": "undated", "effort": "multi_day",
           "how_to_close": "", "evidence": []},
          {"id": "R3", "kind": "responsibility", "text": "Run jobs on a shared cluster",
           "level": "unclear", "screening": "nice_to_have", "match": "strong",
           "recency": "recent", "effort": "quick", "how_to_close": "",
           "evidence": [{"ref": "CV-002"}]},
      ],
      "actions": [{"action": "Read the sponsor register",
                   "acceptance": "Employer found or not found, written down",
                   "when": "before_apply"}],
      "conventions_rendered": ["nl-recognised-sponsor-gate"],
  }

  DISCLAIMER = ("⚠️ 以上是对证据的清点，不是对结果的预判。每一项都连同它的证据引用一起印出，"
                "分母可以逐条审计；本 skill 不给出面试或录用的可能性估计，也不给 0–100 分。"
                "要不要投，由你决定。")


  def build(tmp_path, assessment=None, markdown=None, market=None):
      assessment = copy.deepcopy(assessment or ASSESSMENT)
      tmp_path.mkdir(parents=True, exist_ok=True)
      (tmp_path / "evidence-blocks.json").write_text(
          json.dumps(BLOCKS, ensure_ascii=False), encoding="utf-8")
      (tmp_path / "fit-assessment.yaml").write_text(
          yaml.safe_dump(assessment, allow_unicode=True, sort_keys=False), encoding="utf-8")
      market_dir = tmp_path / "market"
      market_dir.mkdir(exist_ok=True)
      (market_dir / "nl.yaml").write_text(
          yaml.safe_dump(market or MARKET, allow_unicode=True, sort_keys=False),
          encoding="utf-8")
      if markdown is None:
          counts = cc.coverage(assessment["requirements"])
          block = cc.render_block(assessment, counts, "zh")
          markdown = (
              "# Fit assessment\n\n"
              "## 硬性阻断项\n\n"
              "该岗位要求你已经持有欧盟工作许可（Kubernetes in production 另见下表）。\n\n"
              "## 计数\n\n"
              "```\n" + block + "\n```\n\n"
              + DISCLAIMER + "\n\n"
              "| 需求 | level | screening | match | 证据 |\n"
              "|---|---|---|---|---|\n"
              "| Five years of C++ | required | knockout | strong | CV-001, JD-001 |\n"
              "| Kubernetes in production | required | weighted | no_evidence | — |\n"
              "| Run jobs on a shared cluster | unclear | nice_to_have | strong | CV-002 |\n\n"
              "## 市场惯例\n\n"
              "投递前先在公开的认可担保方名录里查一下这家公司，再决定要不要为它定制材料。\n\n"
              "你的简历没有说明当前的居留身份，因此在这条惯例上无法定位。\n")
      (tmp_path / "fit-assessment.md").write_text(markdown, encoding="utf-8")
      return tmp_path, market_dir


  # ---------- the quiet case, pinned as hard as the firing case ----------

  def test_a_well_formed_assessment_passes_with_no_findings(tmp_path):
      ws, market_dir = build(tmp_path)
      assert ca.check(ws, market_dir, TODAY) == []


  def test_the_cli_passes_and_writes_exactly_one_receipt(tmp_path, capsys):
      ws, market_dir = build(tmp_path)
      assert ca.main(["--workspace", str(ws), "--market-dir", str(market_dir),
                      "--today", "2026-08-09"]) == 0
      assert capsys.readouterr().out.strip() == ""
      lines = (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
      assert [json.loads(l)["gate"] for l in lines] == ["check_assessment"]
      assert json.loads(lines[0])["verdict"] == "pass"


  def test_a_no_evidence_row_with_an_empty_list_is_not_unsourced(tmp_path):
      ws, market_dir = build(tmp_path)
      assert not [f for f in ca.check(ws, market_dir, TODAY)
                  if f.startswith("ROW_UNSOURCED")]


  def test_the_english_disclaimer_is_accepted_too(tmp_path):
      ws, market_dir = build(tmp_path)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
          DISCLAIMER, "⚠️ This is a count of evidence, not a forecast of the outcome. "
                      "Whether to apply is your call.")
      (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
      assert not [f for f in ca.check(ws, market_dir, TODAY)
                  if f.startswith("NO_DISCLAIMER")]


  # ---------- the firing cases ----------

  def test_a_row_claiming_a_match_with_no_resolvable_ref_fails(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["requirements"][0]["evidence"] = [{"ref": "CV-999"}]
      ws, market_dir = build(tmp_path, assessment=broken)
      findings = ca.check(ws, market_dir, TODAY)
      assert any(f.startswith("ROW_UNSOURCED:") and "R1" in f for f in findings)


  def test_a_missing_disclaimer_fails(tmp_path):
      ws, market_dir = build(tmp_path)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(DISCLAIMER, "")
      (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
      assert any(f.startswith("NO_DISCLAIMER:") for f in ca.check(ws, market_dir, TODAY))


  def test_a_disqualifier_named_only_after_the_verdict_fails(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["requirements"][1]["screening"] = "knockout"   # a knockout with no evidence
      ws, market_dir = build(tmp_path, assessment=broken)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
      md = md.replace("Kubernetes in production", "another requirement")
      (ws / "fit-assessment.md").write_text(
          md + "\n## 硬性阻断项\n\n该岗位要求 Kubernetes in production。\n", encoding="utf-8")
      assert any(f.startswith("DISQUALIFIER_AFTER_VERDICT:")
                 for f in ca.check(ws, market_dir, TODAY))


  def test_the_same_disqualifier_named_before_the_verdict_passes(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["requirements"][1]["screening"] = "knockout"
      ws, market_dir = build(tmp_path, assessment=broken)
      # The fixture already names it in the 硬性阻断项 section above the counts block.
      assert not [f for f in ca.check(ws, market_dir, TODAY)
                  if f.startswith("DISQUALIFIER_AFTER_VERDICT")]


  def test_a_fired_notice_that_is_not_attached_fails(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["verdict"] = "strong_apply"
      broken["effort"] = "multi_day"
      ws, market_dir = build(tmp_path, assessment=broken)
      findings = ca.check(ws, market_dir, TODAY)
      assert any(f.startswith("NOTICE_NOT_ATTACHED:") and "NOTICE_VERDICT_EFFORT" in f
                 for f in findings)


  def test_attaching_the_notice_text_clears_it(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["verdict"] = "strong_apply"
      broken["effort"] = "multi_day"
      ws, market_dir = build(tmp_path, assessment=broken)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
      (ws / "fit-assessment.md").write_text(
          md + "\n> 结论与投入互相矛盾：请以下面的需求表为准。\n", encoding="utf-8")
      assert not [f for f in ca.check(ws, market_dir, TODAY)
                  if f.startswith("NOTICE_NOT_ATTACHED")]


  def test_a_hand_edited_count_fails(tmp_path):
      ws, market_dir = build(tmp_path)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
          "1 of 2", "2 of 2")
      (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
      assert any(f.startswith("COUNT_MISMATCH:") for f in ca.check(ws, market_dir, TODAY))


  def test_a_paraphrased_convention_fails(tmp_path):
      ws, market_dir = build(tmp_path)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
          "投递前先在公开的认可担保方名录里查一下这家公司，再决定要不要为它定制材料。",
          "你必须先在名录里查到这家公司，否则不要投。")
      (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
      assert any(f.startswith("CONVENTION_PARAPHRASED:") for f in
                 ca.check(ws, market_dir, TODAY))


  def test_an_unknown_convention_id_fails(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["conventions_rendered"] = ["nl-invented-by-the-model"]
      ws, market_dir = build(tmp_path, assessment=broken)
      assert any(f.startswith("CONVENTION_UNKNOWN_ID:")
                 for f in ca.check(ws, market_dir, TODAY))


  def test_a_prediction_word_in_the_rendered_file_fails(tmp_path):
      ws, market_dir = build(tmp_path)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
      (ws / "fit-assessment.md").write_text(md + "\n你是一个很强的候选人，录取率不低。\n",
                                            encoding="utf-8")
      assert any(f.startswith("PREDICTION_WORD:") for f in ca.check(ws, market_dir, TODAY))


  def test_a_block_id_left_in_prose_fails(tmp_path):
      ws, market_dir = build(tmp_path)
      md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
      (ws / "fit-assessment.md").write_text(md + "\n你的 C++ 经历（CV-001）很对口。\n",
                                            encoding="utf-8")
      assert any(f.startswith("STRIPPED_ID:") for f in ca.check(ws, market_dir, TODAY))


  def test_a_refusal_that_still_prints_a_verdict_fails(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["verdict"] = "insufficient_evidence"
      ws, market_dir = build(tmp_path, assessment=broken)
      assert any(f.startswith("REFUSAL_WITH_VERDICT:")
                 for f in ca.check(ws, market_dir, TODAY))


  def test_a_provisional_discover_verdict_may_not_be_carried_in(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["provisional"] = True
      ws, market_dir = build(tmp_path, assessment=broken)
      assert any(f.startswith("PROVISIONAL_VERDICT:")
                 for f in ca.check(ws, market_dir, TODAY))


  def test_a_market_with_no_table_is_fine_only_if_nothing_was_rendered(tmp_path):
      broken = copy.deepcopy(ASSESSMENT)
      broken["market"] = "none"
      broken["conventions_rendered"] = []
      ws, market_dir = build(tmp_path, assessment=broken)
      assert not [f for f in ca.check(ws, market_dir, TODAY)
                  if f.startswith("CONVENTION")]
      broken["conventions_rendered"] = ["nl-recognised-sponsor-gate"]
      ws2, market_dir2 = build(tmp_path / "b", assessment=broken)
      assert any(f.startswith("CONVENTION_UNKNOWN_ID:")
                 for f in ca.check(ws2, market_dir2, TODAY))


  def test_a_broken_market_table_fails_the_assessment(tmp_path):
      market = copy.deepcopy(MARKET)
      market["conventions"][0]["review_by"] = "2026-08-08"
      ws, market_dir = build(tmp_path, market=market)
      assert any(f.startswith("EXPIRED_REVIEW_BY:")
                 for f in ca.check(ws, market_dir, TODAY))


  def test_missing_inputs_exit_two(tmp_path, capsys):
      assert ca.main(["--workspace", str(tmp_path)]) == 2
      assert "fit-assessment.yaml" in capsys.readouterr().err
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_assessment.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'check_assessment'`

- [ ] **Step 3: Write minimal implementation**

  Create `scripts/check_assessment.py`:
  ```python
  #!/usr/bin/env python3
  """Whether an assessment may be shown to the person who asked for it.

  Composes the five checks that stand on their own -- evidence refs, the prediction lint,
  the contradiction detectors, the counting path, the market-table lint -- and adds the
  rules that only make sense once all five outputs sit in the same document.

  Each added rule closes a way an assessment can be internally consistent and still
  wrong: counts without the disclaimer read as a prediction; a hard barrier printed after
  the conclusion is a barrier nobody registered; a contradiction found in code and absent
  from the page is one the reader averages away; a convention restated by the model is how
  a "usually" becomes a "must" with nothing to check it against.

  A mode may not claim success without a receipt. A skipped gate produces no output, and
  that looks exactly like a clean one.
  """
  from __future__ import annotations

  import argparse
  import copy
  import datetime
  import pathlib
  import sys

  sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

  import check_conventions as conventions  # noqa: E402
  import check_evidence_refs as refs  # noqa: E402
  import consistency  # noqa: E402
  import count_coverage as coverage  # noqa: E402
  import journal  # noqa: E402
  import lint_no_prediction as prediction  # noqa: E402
  import yaml  # noqa: E402

  DISCLAIMER_ANCHORS = ("不是对结果的预判", "not a forecast of the outcome")
  VERDICT_MARKERS = ("投递建议：", "apply verdict:")
  FIVE_LEVELS = ("strong_apply", "worth_applying", "stretch", "likely_screen_out", "blocked")


  def _verdict_line_index(lines: list[str]) -> int | None:
      for index, line in enumerate(lines):
          if any(marker in line for marker in VERDICT_MARKERS):
              return index
      return None


  def check(workspace: pathlib.Path, market_dir: pathlib.Path,
            today: datetime.date) -> list[str]:
      findings: list[str] = []
      assessment = yaml.safe_load(
          (workspace / "fit-assessment.yaml").read_text(encoding="utf-8")) or {}
      markdown = (workspace / "fit-assessment.md").read_text(encoding="utf-8")
      lines = markdown.splitlines()
      block_ids = refs.load_block_ids(workspace / "evidence-blocks.json")

      # 1. Evidence references, in check-only form: nothing may still need dropping.
      _, dropped = refs.drop_unresolvable_refs(copy.deepcopy(assessment), block_ids)
      findings += dropped
      _, stripped = refs.strip_block_ids(markdown)
      findings += stripped

      # 2. Row-level sourcing. `no_evidence` with an empty list is the honest shape.
      for row in assessment.get("requirements") or []:
          row = row or {}
          resolvable = [e for e in (row.get("evidence") or [])
                        if str((e or {}).get("ref", "")).strip() in block_ids]
          if row.get("match") == "no_evidence":
              if row.get("evidence"):
                  findings.append(f"ROW_UNSOURCED: row {row.get('id')} is no_evidence but "
                                  f"carries references; one of the two is wrong")
          elif not resolvable:
              findings.append(f"ROW_UNSOURCED: row {row.get('id')} claims "
                              f"match={row.get('match')!r} with no reference that resolves "
                              f"to a block")

      # 3. The prediction lint, over every rendered surface in the workspace.
      for path in prediction.target_files(workspace):
          findings += prediction.scan_text(path.read_text(encoding="utf-8"),
                                           str(path.relative_to(workspace)))

      # 4. Consistency notices must be attached where they fired.
      for notice in consistency.notices(assessment):
          if notice["anchor_zh"] not in markdown and notice["anchor_en"] not in markdown:
              findings.append(f"NOTICE_NOT_ATTACHED: {notice['code']} fired and its text "
                              f"is nowhere in fit-assessment.md; attach it beside the "
                              f"thing it qualifies")

      # 5. The counting path is the only counting path.
      counts = coverage.coverage(assessment.get("requirements"))
      findings += counts["invalid"]
      refusing = assessment.get("verdict") == "insufficient_evidence"
      if not refusing:
          rendered = [coverage.render_block(assessment, counts, lang) for lang in ("zh", "en")]
          if not any(block in markdown for block in rendered):
              findings.append("COUNT_MISMATCH: fit-assessment.md does not contain the "
                              "block count_coverage.py produces; a second number written "
                              "by hand cannot be reconciled with this one")
          if not any(anchor in markdown for anchor in DISCLAIMER_ANCHORS):
              findings.append("NO_DISCLAIMER: the required disclaimer is absent; a count "
                              "without it reads as a prediction")

      # 6. The refusal floor is a refusal, not a sixth level.
      if refusing:
          for marker in VERDICT_MARKERS:
              if marker in markdown:
                  findings.append(f"REFUSAL_WITH_VERDICT: verdict is "
                                  f"insufficient_evidence but {marker!r} still renders a "
                                  f"conclusion")
      elif assessment.get("verdict") not in FIVE_LEVELS:
          findings.append(f"BAD_VERDICT: {assessment.get('verdict')!r} is not one of "
                          f"{FIVE_LEVELS} or 'insufficient_evidence'")
      if assessment.get("provisional"):
          findings.append("PROVISIONAL_VERDICT: a discover-stage 基于卡片信息的初判 was "
                          "carried into an assessment; assess always recomputes")

      # 7. Disqualifiers render before the verdict.
      verdict_index = _verdict_line_index(lines)
      if verdict_index is not None:
          for row in assessment.get("requirements") or []:
              row = row or {}
              if row.get("screening") != "knockout":
                  continue
              if row.get("match") not in ("gap", "no_evidence"):
                  continue
              text = str(row.get("text") or "").strip()
              first = next((i for i, line in enumerate(lines) if text and text in line), None)
              if first is None or first > verdict_index:
                  findings.append(
                      f"DISQUALIFIER_AFTER_VERDICT: row {row.get('id')} is a knockout the "
                      f"candidate does not meet, and it does not appear before the verdict "
                      f"line; a wall printed after the conclusion is a wall nobody read")

      # 8. Market conventions: allowlisted by id, rendered verbatim.
      market = assessment.get("market")
      table = market_dir / f"{market}.yaml"
      known: dict[str, dict] = {}
      if market in conventions.MARKET_KEYS:
          if not table.exists():
              findings.append(f"CONVENTION_TABLE_MISSING: {table} does not exist")
          else:
              findings += conventions.check_file(table, today)
              known = conventions.conventions_by_id(conventions.load_market_file(table))
      for entry_id in assessment.get("conventions_rendered") or []:
          entry = known.get(entry_id)
          if entry is None:
              findings.append(f"CONVENTION_UNKNOWN_ID: {entry_id} is not an entry in "
                              f"{table.name}; the model may not author a convention")
              continue
          if not any(str(entry.get(field, "")).strip() and
                     str(entry[field]).strip() in markdown
                     for field in ("text_en", "text_zh")):
              findings.append(f"CONVENTION_PARAPHRASED: {entry_id} was listed as rendered "
                              f"but neither text_en nor text_zh appears verbatim in "
                              f"fit-assessment.md")
      return findings


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(description="The assess-mode gate.")
      parser.add_argument("--workspace", required=True, type=pathlib.Path)
      parser.add_argument("--market-dir", type=pathlib.Path, default=None)
      parser.add_argument("--today", default=None)
      args = parser.parse_args(argv)

      workspace = args.workspace
      market_dir = args.market_dir or (
          pathlib.Path(__file__).resolve().parents[1] / "references" / "market-conventions")
      today = (datetime.date.fromisoformat(args.today) if args.today
               else datetime.date.today())

      required = [workspace / "fit-assessment.yaml", workspace / "fit-assessment.md",
                  workspace / "evidence-blocks.json"]
      for path in required:
          if not path.exists():
              print(f"cannot run: {path.name} not found at {path}", file=sys.stderr)
              return 2

      findings = check(workspace, market_dir, today)
      hard = [f for f in findings if not f.startswith("WARN_")]
      for finding in findings:
          print(finding)
      journal.receipt(workspace, "check_assessment",
                      {path.name: journal.sha256_file(path) for path in required},
                      "fail" if hard else "pass", findings)
      return 1 if hard else 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_assessment.py -q`
  Expected: PASS (20 passed)

- [ ] **Step 5: Run the whole suite**

  Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
  Expected: PASS, every module green, no test skipped.

- [ ] **Step 6: Commit**
  ```
  cd /Users/donghanglyu/code_project/job-hunt
  git add scripts/check_assessment.py scripts/tests/test_check_assessment.py
  git commit -m "assess: composing gate over refs, lint, consistency, counts and conventions"
  ```

---

## Done means

- `python3 -m pytest scripts/tests -q` is green from the repo root.
- `python3 scripts/check_conventions.py --workspace /tmp/jh-lint --all --today 2026-08-09` exits 0.
- `references/market-conventions/` holds `README.md` and five tables totalling 38 entries (cn 10, nl 9, de 8, uk 5, us 6), with the three dropped ids present in none of them.
- `modes/assess.md` defines the `fit-assessment.yaml` row schema, the fetch-integrity thresholds, the full `posting.yaml` field list including `salary_range` and `application_type`, the `insufficient_evidence` floor, and the "what to do instead" half.
- Every commit stages named paths only. Nothing was pushed.











