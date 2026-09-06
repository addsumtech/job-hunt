# Mode: assess — 该不该投

**Entry condition:** a posting exists — a URL, pasted text, or a row the user named from
a shortlist. Nothing else in this file runs until step 1 has produced usable text.

**This mode owns** `posting.yaml`, `posting-source.txt`, `cv-source.txt`,
`evidence-blocks.json`, `fit-assessment.yaml`, `fit-assessment.md`, `coverage.json`.
It reads `profile.yaml` and never writes it. Resolve the workspace with
`paths.workspace(name, company, role, "2026-08-09")` — never by joining strings. That
one function owns the shape `~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`,
which is byte-identical to the old skill's so "resume an unfinished application" keeps
working; a run that builds its own path breaks resumption silently.

---

## 0. Enter the mode — before anything else

```
python3 scripts/enter_mode.py --workspace <ws> --mode assess
```

This writes a `mode_entry` record to `journal.jsonl` carrying this file's content hash,
and `check_assessment.py` refuses to pass without it (`NO_MODE_ENTRY`) or with a hash
that no longer matches the file on disk (`MODE_FILE_CHANGED`). Read this file in full
after running it. The record is not paperwork: it is the only thing that distinguishes
"the model loaded this file" from "the model produced something shaped like what this
file asks for", and without it a layer-1.5 file is an optional reference again.

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
not match the stored market. That file is written by discover mode; if it does not
exist, just ask. Never write it from here.

Markets with tables: `cn`, `nl`, `de`, `uk`, `us`. Anything else → set
`market: other` in `fit-assessment.yaml`, say 「本市场无惯例数据」, and render no
convention card at all. The sixth token is `other`, never `none` — one spelling, so two
gates cannot disagree about the same word. **Never substitute a neighbouring market's
conventions.**

## 3. Extract `posting.yaml` — the complete field list

Twelve names, in this order — the same names in the same order as `SKILL.md`'s
extraction field table, `references/job-posting-extraction.md`, and `modes/apply.md`
Step 2. Two copies is one thing; two copies that disagree is a downstream gate failing
on a file the upstream mode was told to write. This used to claim the copies were
*byte-identical*, which was never true and was worse than the drift it described: it
told the next maintainer the copies were in sync, so they would not diff them.
`scripts/tests/test_posting_schema_agreement.py` now diffs all four.

```yaml
role_title: "..."          # exactly as written in the posting
company: "..."             # the exact public employer name
seniority: mid             # intern | junior | mid | senior | lead
location: "..."            # the posting's own location text, verbatim, one string
must_haves: []             # required / essential / minimum / "you must"
nice_to_haves: []          # preferred / bonus / a plus / ideally / advantageous
responsibilities: []       # what the person will actually do, in the posting's words
keywords: []               # exact ATS terms, casing preserved: "PyTorch", "CI/CD"
company_values_tone: "..."
red_flags: []
salary_range: null         # the stated band, or null
application_type: cv       # cv | structured
```

Three fields carry weight far past their size:
- `company` — the **exact public employer name**. `apply` mode names the workspace
  directory from it and `check_letter.py` verifies the letter's recipient against it,
  emitting `NO_COMPANY_IN_POSTING` — a hard finding — when this field is absent. Every
  apply run downstream of an assess run that skipped it fails on that line.
- `salary_range` — when present, ask the user **once** whether the band fits. A band
  mismatch is a common silent screen-out and is cheaper to surface now than after a
  full application. If no range is stated, do not raise salary at all.
- `application_type` — `structured` when the posting splits Essential / Desirable
  criteria, names behaviours or a competency framework, or asks the applicant to
  evidence each criterion. It is the **only** signal that routes to a
  supporting-statement deliverable in `apply`. Getting it wrong produces a perfectly
  good CV for a process that does not read CVs.

An earlier compression of this list **silently dropped `salary_range` and
`application_type`**, and that defect shipped. There is no `language` field here: the
language the CV is calibrated for lives in `meta.language` on the profile, and a second
copy of it in the posting file is a second thing for the two to disagree about.

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

**The mechanical form, because "surface it first" is not checkable and this rule is too
important to leave uncheckable.** Whenever any requirement row is `screening: knockout`
with `match: gap` or `match: no_evidence`, `fit-assessment.md` opens with a
`## 硬性阻断项` section, **above** the counts block, and that section names every such
row **by its id**:

```markdown
## 硬性阻断项

- **R2** — 该岗位要求你已经持有欧盟工作许可。这是法律层面的门槛，不是表述问题。
- **R5** — 岗位要求本地注册执业资格。
```

Writing in English? The heading is `## Hard blockers`. Those two spellings are the only
ones `check_assessment.py` recognises — the section is a heading it has to find, so it
is the one place here where the exact string matters.

**Write the answer down, in the two §6 fields built for it.** What the posting demands
goes in `stated_conditions` (a `type`, a `stance`, and an evidence ref to the JD block
it came from); what the user told you goes in `declared_work_status` — their own words
about their own status, never inferred, and `unknown` when the answer was not clear.
`consistency.py` compares the two and prints `NOTICE_WORK_AUTH_CONFLICT` or
`NOTICE_WORK_AUTH_VERIFY`, which always say *these two appear to conflict, check it
yourself* and never *you are not eligible*. Asking and then not recording the answer
leaves those notices unable to fire at all (`WARN_NO_WORK_STATUS`), and a misspelled
token switches them off silently (`BAD_WORK_STATUS`, `BAD_STATED_CONDITION`). This is a
second line behind the knockout row below, not a replacement for it.

Write the barrier in your own words, in the reader's language — paraphrase is expected
and correct. The **id** is the mechanical handle, and it is what `check_assessment.py`
looks for: `NO_DISQUALIFIER_SECTION` when the section is absent,
`DISQUALIFIER_NOT_NAMED` when it is there but does not list a blocking row's id, and
`DISQUALIFIER_AFTER_VERDICT` when it renders below the verdict line. Keying the check on
the posting's own wording instead would fire on every honest translation, and a check
that cries wolf on correct output is one people stop reading.

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

## 6. `fit-assessment.yaml` — the complete schema

This schema is defined here and nowhere else; `check_assessment.py` requires it. It has
two halves and for a while only the second one was written down. The requirement rows
were here; the **top-level fields** were not, and three scripts read them. A field this
file never names is a field a faithful run never writes — and `count_coverage.py` then
had to print two of them anyway.

**The top level. `level_direction` and `effort` are PRINTED on the coverage card in §7.**

```yaml
market: cn                      # vocab.MARKET_KEYS (cn | nl | de | uk | us), or
                                # vocab.NO_MARKET ("other") when no table applies.
                                # Never "none" — the sixth token is "other" everywhere.
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
actions:                        # the single authoritative to-do list
  - action: "Publish the torchrun port"
    acceptance: "Repo README shows a two-GPU run log"
    when: before_apply          # now | before_apply | later
conventions_rendered: [cn-boss-profile-is-the-screen]
```

`effort` appears twice in this file and prices two different things on one scale: at the
top level, closing the remaining gaps **as a whole**; on a row, closing **that row**.
Nothing compares the two automatically — set the top-level one by reading your own rows,
because a `not_closable` above a table of `evening`s is a contradiction only a reader
will catch. What `consistency.py` does check is the top-level `effort` against the
**verdict**: `strong_apply` beside `multi_day` or `not_closable` prints
`NOTICE_VERDICT_EFFORT`. Note what that means for leaving the field out — it reads the
raw field, so an absent `effort` fired nothing while the card printed 「补不上」 anyway.
The detector built for exactly that contradiction could not see it, because the
contradiction existed only on the card.

**These two are not optional, and the reason is that the card prints them.**
`count_coverage.py` used to fill an absent `level_direction` with `unclear` and an absent
`effort` with `not_closable` — and then again inside its Chinese label lookups, so the
default `--lang zh` card invented a value even after the obvious defaults were removed.
The result shipped 「投递建议：强烈建议投」 directly above 「可补缺口所需投入：补不上」 on
an assessment whose only gapped row said `effort: evening` and carried a `how_to_close`,
with every gate at exit 0. A card is allowed to say **nobody judged this** — it renders
「未评估」 / `not assessed` — but it may never invent the most pessimistic value and print
it in the same column as an assessed one. `check_assessment.py` fails with
`MISSING_LEVEL_DIRECTION` and `MISSING_EFFORT` when either is absent or out of enum, on
every verdict except the §8 refusal, where by design there is no card to print.

`declared_work_status` is the user's **own statement**, from the §4 question — never
inferred from a name, a university, or a location. `unknown` is a real answer and the
right one when you did not get a clear reply; it suppresses both work-authorization
notices, which is the safe direction, so `check_assessment.py` only warns
(`WARN_NO_WORK_STATUS`) when the field is missing. What it does **not** tolerate is a
value outside the set: `consistency.py` compares a `stance` against this field and
returns nothing for any token it does not recognise, so a hyphen in `needs-sponsorship`
switches the notice off and leaves a card that looks clean. That is `BAD_WORK_STATUS`,
and `BAD_STATED_CONDITION` for the same fault in a `type` or a `stance`.

**The requirement rows.** One row per must-have and per named responsibility.

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

The middle three lines come from three different places, and mixing them up is how a
card ends up stating something nobody worked out. The two count lines are computed off
the §6 rows. 「职级匹配」 and 「可补缺口所需投入」 are read **straight off the top-level
`level_direction` and `effort`** — nothing derives them from the rows. Leave either unset
and the line reads 「未评估」 (`not assessed` on the English card) and
`check_assessment.py` fails: that token means *nobody judged this*, and it is never a
value you may write into the YAML.

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
or invent one.

**If an entry's `review_by` has passed, still render it, with a 「已过复核期」 banner.**
A date going by while the code did not change should not stop the skill working. The CI
lint (`check_conventions.py --all`) fails on the expired date so a person fixes it; the
runtime gate downgrades it to `WARN_EXPIRED_REVIEW_BY` and instead requires the banner
string 「已过复核期」 to appear in `fit-assessment.md` (`MISSING_STALE_BANNER`). On an
English card the banner is **"past its review date"** — like every other anchor in this
file it is a pair, and the card follows the user's language. Rendering a stale card
without telling the reader it is stale is the one thing that is worse than either.

The one sentence you write in this section is where **this CV** stands against the
convention, and it cites CV blocks like any other claim. List the ids you rendered in
`conventions_rendered:`.

Conventions feed **neither the verdict nor any consistency check**. They are the one
class of claim with no source text behind them; keeping them out of the arithmetic is
what stops an unciteable assertion moving a citeable conclusion.

## 10. When the verdict is 大概率被筛掉 or 硬性阻断: the other half

A verdict without this half is a door closed with nothing behind it. Produce all three,
under a `## 那该怎么办` heading — `## What to do instead` if you are writing in English.

**(a) Exactly one strategy**, from this closed set — not two, not a menu:

| Strategy | Use it when |
|---|---|
| `apply_anyway` 投了再说 | The gap is soft and the cost of applying is an evening |
| `reposition` 重新定位 | The same evidence reads much better against a different role family |
| `skill_sprint` 技能冲刺 | One named, closable requirement is doing all the blocking |
| `side_door` 侧门切入 | A contract, internal transfer, adjacent team or smaller employer reaches the same work |
| `change_track` 换方向 | The blocking requirement is structural and not worth closing for this goal |

Write the chosen token literally — `check_assessment.py` counts how many of the five
appear **inside that section** and fails on zero (`NO_STRATEGY_SECTION`) and on more
than one (`STRATEGY_NOT_UNIQUE`). A menu is not a recommendation; picking is the work.
Naming a rejected strategy in the same section counts as a second one, so contrast it
in prose above the heading, or name it without its token.

**(b) A 30/60/90 table** with exactly these columns:

| 目标 | 行动 | 验收标准 |
|---|---|---|
| ... | ... | ... |

In English: `| Goal | Action | Acceptance criterion |`.

**(c) A roadmap carrying an 输出物 (`Deliverable`) column.**

`验收标准` and `输出物` — or `Acceptance criterion` and `Deliverable` — are where the
entire value of this section sits. They are what turn advice into something checkable,
and `NO_ACCEPTANCE_COLUMN` fails the gate when neither spelling of either column header
is present. Every row of both tables must also appear in
`actions:` in `fit-assessment.yaml`; that list is the single authoritative to-do list,
and `consistency.py` compares it against the closable gaps.

## 11. Gates — run all of them, in this order

```
python3 scripts/evidence_blocks.py     --workspace <ws>   # step 5, listed again for order
python3 scripts/count_coverage.py      --workspace <ws>
python3 scripts/consistency.py         --workspace <ws>
python3 scripts/check_evidence_refs.py --workspace <ws>
python3 scripts/lint_no_prediction.py  --workspace <ws>
python3 scripts/check_assessment.py    --workspace <ws>
```

`check_assessment.py` runs last on purpose: it reads the other five gates' receipts out
of `journal.jsonl` and refuses to pass if any of them is missing (`MISSING_RECEIPT`) or
recorded a failure (`UPSTREAM_FAILED`). Re-deriving their answers instead would let a
gate that was never run look identical to a gate that passed.

Attach every notice `consistency.py` printed beside the thing it qualifies. Notices
**report and never repair**: code can see two fields disagree, it cannot see which one
is right, and choosing silently would swap a visible contradiction for an invisible
guess.

**Never report success without a receipt.** A skipped gate produces no output, and that
looks exactly like a clean one. `check_assessment.py` writes the receipt that lets you
say this passed.

## Hand the artifacts over — `deliver.py`, not a sentence in the final message

A workspace under `~/.claude/job-profiles/` is where the skill works, and it is
not where a person looks. Nobody browses a dotfile directory, and a path pasted
into a chat message is gone the moment the session scrolls. So the last step of
every mode is a command, not a claim:

```bash
python3 scripts/deliver.py --workspace <ws>
```

It copies this round's readable artifacts **straight into `~/Downloads`**, named
`<slug>-<file>`, renders every Markdown to **PDF as well**, and prints the paths.
Quote them in the completion message. The slug prefix is not a folder in
disguise: two rounds both produce `shortlist.md`, and a bare name would have the
second silently overwrite the first.

**The PDF is verified, not trusted.** `pandoc --pdf-engine=tectonic` on a Chinese
document exits 0, prints a warning nobody reads, and writes a PDF whose every CJK
glyph is a box — measured, 528 characters in and 0 read back. So a CJK document
gets a CJK font chosen by probing what this machine actually has, and every PDF
is read back with `pdftotext` and compared against its source before it counts as
delivered. One that lost characters is deleted and reported; the Markdown still
ships.

**It is a copy, and the split is deliberate.** `raw/`, `journal.jsonl` and the
adapter `.err` files stay in the workspace: they are the provenance chain, they
are unreadable to a person, and an audit has to read them where they live rather
than in an export that may have gone stale.

**Do not move the workspace itself.** `scripts/paths.py` owns that layout,
`modes/apply.md`'s resume-an-unfinished-run lookup finds work BY the path shape,
and `check_claims.py` fingerprints the master profile at that path. `~/Downloads`
is also a directory the user's own housekeeping empties.

`deliver.py` exits 0 or 2, never 1 — there is no such thing as a delivery
finding. Exit 2 with `DELIVER_DEST_UNWRITABLE` is the macOS case worth knowing:
`~/Downloads` sits behind TCC, it can start refusing writes part-way through a
session, and `os.access` says yes while the write fails. The script probes by
writing a real file. When it exits 2, say so and offer `--to` with somewhere
else — do not silently leave the artifacts undelivered.

## 12. Self-check before you hand this over

- [ ] `scripts/enter_mode.py --mode assess` ran before anything else, and this file was
      read in full after it.
- [ ] `posting-source.txt` is verbatim and unedited; `posting.yaml` carries all twelve
      fields, including `company`, `salary_range` and `application_type`.
- [ ] Disqualifiers were asked about, and a `## 硬性阻断项` section names each blocking
      row **by id**, **before** the verdict.
- [ ] Every requirement row prints its evidence reference; no block id appears in prose.
- [ ] `fit-assessment.yaml` carries the top-level fields too, not just the rows:
      `level_direction` and `effort` are both set and both in enum — the card prints
      them, and 「未评估」 on a shipped card means nobody judged a line the reader will
      read as judged.
- [ ] The §4 work-authorization answer is recorded: `declared_work_status` (`unknown`
      is a legal answer) and a `stated_conditions` entry for what the posting demands.
- [ ] The coverage block is the one `count_coverage.py` produced, byte for byte.
- [ ] The disclaimer is present, unchanged, directly under the block.
- [ ] No percentage, no `n/m` score, no prediction word — except a quoted employer
      rubric with its source named on the next line.
- [ ] Convention cards are verbatim from `references/market-conventions/<market>.yaml`,
      `applies_when` was honoured, and `conventions_rendered` lists their ids.
- [ ] Any rendered entry whose `review_by` has passed carries the 「已过复核期」 /
      "past its review date" banner, in the card's own language.
- [ ] Every consistency notice that fired is attached where it fired.
- [ ] If the verdict is 大概率被筛掉 or 硬性阻断: **exactly one** strategy token from the
      closed set, a 30/60/90 table with a `验收标准` column, and a roadmap with an
      `输出物` column — all mirrored into `actions:`.
- [ ] A discover-stage 「基于卡片信息的初判」 verdict was **not** copied in. assess
      always recomputes.
- [ ] `check_assessment.py` exited 0 and its receipt is in `journal.jsonl`.
