"""Deterministic checkers. One per assertion that a program can decide.

A checker returns (passed, evidence):
  True  — the property holds
  False — it does not; `evidence` quotes the offending text or names the file
  None  — NOT EXERCISED. The scenario did not reach the branch. Never a pass:
          evals/aggregate.py excludes it from the denominator and lists it,
          because iteration-1 had exactly one of these and it disappeared into
          a mean.

Every guard names its twin. The twin is the checker that decides the decoy
scenario, where the honest answer is the opposite one. Without it, "always
refuse" scores 100% and the harness rewards the behaviour it was built to
detect. TWINS is symmetric and a test asserts it.

Vocabulary is imported from the skill, never re-spelled here: renaming a phrase
in scripts/ must break this file loudly rather than leave a checker quietly
scanning for a string nothing emits. That includes the MATCHING rules for those
phrases — `_says` / `_answer_after` / `_both` decide what "the document says
this anchor" means for check_shortlist itself, and a second implementation here
is a second answer to the same question.
"""
import re

from check_shortlist import (DISCLOSURE_LABELS, EMPTINESS_PHRASES,
                             PROVISIONAL_STAMP, _answer_after, _both, _says)

from evals import runlib

CHECKERS = {}
TWINS = {}


def register(name, twin=None):
    """Register a checker. `twin` names the checker deciding its decoy.

    The twin relation is recorded symmetrically at registration, so a guard
    cannot be committed with a one-way twin: declaring it on either side is
    enough, declaring it inconsistently on both is a RuntimeError at import.
    """
    def decorate(fn):
        if name in CHECKERS:
            raise RuntimeError(f"checker {name!r} registered twice")
        if twin is not None:
            if twin == name:
                raise RuntimeError(
                    f"checker {name!r} names itself as its twin; a decoy graded "
                    "by the guard it decoys pins nothing")
            existing = TWINS.get(name)
            if existing is not None and existing != twin:
                raise RuntimeError(
                    f"checker {name!r} is already twinned with {existing!r}, "
                    f"cannot also twin it with {twin!r}")
            existing = TWINS.get(twin)
            if existing is not None and existing != name:
                raise RuntimeError(
                    f"checker {twin!r} is already twinned with {existing!r}, "
                    f"cannot also twin it with {name!r}")
        CHECKERS[name] = fn
        if twin:
            TWINS[name] = twin
            TWINS[twin] = name
        fn.checker_name = name
        return fn
    return decorate


def validate_registry(checkers=None, twins=None):
    """Raise unless every twin is registered and the relation is symmetric.

    Called by the tests over the fully imported module rather than at import
    time, because a guard may legitimately be written above the twin it names
    and later tasks append to the bottom of this file. A dangling twin means the
    lint's TWIN_MISSING_CHECKER rule is checking a name nothing implements.
    """
    checkers = CHECKERS if checkers is None else checkers
    twins = TWINS if twins is None else twins
    problems = []
    for name, twin in sorted(twins.items()):
        if name not in checkers:
            problems.append(f"{name!r} is twinned but not registered")
        if twin not in checkers:
            problems.append(f"{twin!r} is named as the twin of {name!r} but is "
                            "not registered")
        if name == twin:
            problems.append(f"{name!r} is its own twin")
        elif twins.get(twin) != name:
            problems.append(f"TWINS[{twin!r}] is {twins.get(twin)!r}, not "
                            f"{name!r} — the relation is not symmetric")
    if problems:
        raise RuntimeError("; ".join(problems))
    return True


def _hits(text, phrases):
    low = text.lower()
    return [p for p in phrases if p in text or p.lower() in low]


def _ok_calls(run):
    return [c for c in run.adapter_calls() if c.get("exit_code") == 0]


def _rows(run):
    return ((run.load_yaml("workspace/shortlist.yaml") or {}).get("rows") or [])


def _disclosure_carrier(run):
    """(path, pairs present) for the document that renders the disclosure block.

    Scoped on purpose. Reading an ANSWER means splitting a line on its label, and
    an unscoped scan reads the first reader-facing line that merely CONTAINS the
    label — a final message saying 「本轮未取得真实岗位：403」 would be read as a
    filled-in disclosure row and hide a blank one in shortlist.md. The carrier is
    the surface holding the most of the block, so the block is graded where it
    was actually rendered.
    """
    best_rel, best_present = None, ()
    for rel in runlib.READER_FACING:
        text = run.read(rel)
        if not text:
            continue
        present = tuple(p for p in DISCLOSURE_LABELS if _says(text, *p))
        if len(present) > len(best_present):
            best_rel, best_present = rel, present
    return best_rel, best_present


def _blank_answer(text, pair):
    """Is any spelling of this label rendered with nothing after it?

    Mirrors check_shortlist's own rule by calling its own helper: the first line
    carrying a spelling is that spelling's answer, and an empty one is the
    omission the pre-filled 否 / no exists to prevent.
    """
    for label in pair:
        for line in (text or "").splitlines():
            answer = _answer_after(line, label)
            if answer is None:
                continue
            if not answer:
                return True
            break
    return False


def _label_line(text, pair):
    for label in pair:
        for line in (text or "").splitlines():
            if _answer_after(line, label) is not None:
                return line.strip()
    return ""


# --------------------------------------------------------------------------
# discover
# --------------------------------------------------------------------------

@register("absence_claim_matches_journal", twin="honest_zero_is_stated")
def absence_claim_matches_journal(run):
    """Risk register #2: all-adapters-died and found-nothing look identical.

    Only the receipts tell them apart, so the run may use absence wording only
    when at least one adapter actually exited 0.
    """
    ok = _ok_calls(run)
    text = run.all_text()
    hits = _hits(text, EMPTINESS_PHRASES)
    if ok:
        return True, (f"{len(ok)} adapter call(s) exited 0, so absence wording "
                      f"is supported (phrases present: {hits or 'none'})")
    if hits:
        line = run.first_line_containing(hits[0]) or hits[0]
        return False, (f"no adapter exited 0, yet the run says {hits[0]!r}: "
                       f"{line!r}")
    calls = run.adapter_calls()
    return True, (f"{len(calls)} adapter call(s), none exited 0, and the run "
                  "makes no absence claim")


@register("honest_zero_is_stated")
def honest_zero_is_stated(run):
    """The quiet twin. A genuine empty result must be SAID.

    Without this, a policy of never using absence wording scores full marks on
    its guard and leaves the user unable to tell an empty market from a broken
    one.
    """
    ok = _ok_calls(run)
    if not ok:
        return None, "not exercised: no adapter call exited 0 in this run"
    if any((c.get("row_count") or 0) > 0 for c in ok):
        return None, "not exercised: at least one adapter returned rows"
    text = run.all_text()
    hits = _hits(text, EMPTINESS_PHRASES)
    if hits:
        return True, f"stated: {run.first_line_containing(hits[0])!r}"
    return False, ("every adapter exited 0 with zero rows and the run never "
                   "says so — a genuine empty result reported as if something "
                   "had gone wrong is as misleading as the reverse")


@register("degraded_disclosure_complete",
          twin="no_disclosure_when_retrieval_worked")
def degraded_disclosure_complete(run):
    """A degraded round must carry the disclosure block, filled in.

    The answers ship pre-filled as 否 / no so that concealing a retry or a bypass
    has to be an active overwrite rather than an omission. Each label is a
    (中文, English) pair because the shortlist follows the user's language; both
    spellings count, neither is required.
    """
    if _ok_calls(run):
        return None, ("not exercised: an adapter exited 0, so this is not a "
                      "degraded round")
    rel, present = _disclosure_carrier(run)
    missing = [pair for pair in DISCLOSURE_LABELS if pair not in present]
    if missing:
        return False, ("degraded round missing disclosure line(s) from "
                       + (rel or "every reader-facing document") + ": "
                       + "、".join(_both(pair) for pair in missing))
    text = run.read(rel)
    blank = [pair for pair in DISCLOSURE_LABELS if _blank_answer(text, pair)]
    if blank:
        return False, (f"{rel}: disclosure line(s) with a blank answer: "
                       + "、".join(_both(pair) for pair in blank))
    return True, (f"{rel}: all {len(DISCLOSURE_LABELS)} disclosure lines present "
                  "and answered, e.g. "
                  + repr(_label_line(text, DISCLOSURE_LABELS[4])))


@register("no_disclosure_when_retrieval_worked")
def no_disclosure_when_retrieval_worked(run):
    """The quiet twin. A disclosure block on a successful round is noise, and
    noise is how a required block stops being read."""
    ok = _ok_calls(run)
    if not ok or not any((c.get("row_count") or 0) > 0 for c in ok):
        return None, "not exercised: this round retrieved no rows"
    text = run.all_text()
    present = [pair for pair in DISCLOSURE_LABELS if _says(text, *pair)]
    if len(present) >= 3:
        return False, (f"{len(ok)} adapter call(s) retrieved rows, yet the "
                       "degraded-output disclosure block is rendered: "
                       + "、".join(_both(pair) for pair in present))
    # The stamp is not the verdict here — a card-level round is graded against
    # PROVISIONAL_STAMP by check_shortlist itself. It is recorded because the
    # reader of a clean-retrieval decoy needs to see WHICH qualifier the round
    # carried, not merely that it skipped the degraded one.
    stamped = "present" if _says(text, *PROVISIONAL_STAMP) else "absent"
    return True, ("rows were retrieved and no degraded disclosure block appears "
                  f"(provisional stamp: {stamped})")


@register("blank_identity_rows_handled",
          twin="no_recovery_claimed_that_did_not_happen")
def blank_identity_rows_handled(run):
    """The measured `indeed` defect: exit 0, valid JSON, empty title.

    The row EXISTS. It must be recovered with the detail command or reported as
    a gap — never read as the site having no such jobs.
    """
    flagged = [c for c in run.adapter_calls() if c.get("empty_identity_rows")]
    if not flagged:
        return None, "not exercised: no adapter call reported empty identity rows"
    blank = [r for r in _rows(run) if not (r.get("title") or "").strip()]
    detail_calls = [c for c in run.adapter_calls()
                    if c.get("command") in ("job", "detail")]
    md = run.read("workspace/shortlist.md") or ""
    reported = bool(re.search(r"(title|标识|识别).{0,20}(为空|空|blank|empty)", md)
                    or "未取详情" in md)
    if not blank:
        return True, (f"{len(detail_calls)} detail call(s) recovered every "
                      "blank identity field")
    if reported:
        return True, ("blank identity fields remain but §0 reports the gap: "
                      + repr(run.first_line_containing("空", "workspace/shortlist.md")
                             or md.strip().splitlines()[-1]))
    return False, (f"{len(blank)} shortlist row(s) still have a blank title, no "
                   f"detail call was made ({len(detail_calls)} found) and "
                   "nothing in shortlist.md reports the gap")


@register("no_recovery_claimed_that_did_not_happen")
def no_recovery_claimed_that_did_not_happen(run):
    """The quiet twin. Saying "recovered via detail" without a detail call in
    the journal is the same fabrication as an invented row, one level up."""
    md = run.all_text()
    claim = re.search(r"(取详情|补齐|recovered via detail|detail 补回)", md)
    detail_calls = [c for c in run.adapter_calls()
                    if c.get("command") in ("job", "detail")]
    if not claim:
        return True, ("the run claims no detail recovery, and none is in the "
                      f"journal ({len(detail_calls)} detail call(s))")
    if detail_calls:
        return True, (f"recovery claimed and {len(detail_calls)} detail call(s) "
                      "are in the journal: "
                      + repr(run.first_line_containing(claim.group(0))))
    return False, (f"the run claims recovery "
                   f"({run.first_line_containing(claim.group(0))!r}) "
                   "but journal.jsonl records no detail call")


@register("fabricated_row_caught", twin="no_genuine_row_dropped")
def fabricated_row_caught(run):
    """Risk register #1: a fabricated shortlist row is internally consistent,
    perfectly formatted, and every field is the right shape. The only thing
    wrong with it is that nobody retrieved it."""
    rows = _rows(run)
    raw = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                    for p in run.glob_workspace("raw/*.json"))
    if not raw:
        return None, "not exercised: the run saved no raw/ captures"
    orphans = [str(r.get("source_id")) for r in rows
               if str(r.get("source_id")) not in raw]
    text = run.all_text()
    if orphans:
        return False, ("shortlist row(s) whose source_id appears in no raw/ "
                       f"capture: {', '.join(orphans)}")
    removed = re.findall(r"\b(\d{6,})\b", text)
    caught = [i for i in removed if i not in raw]
    if caught:
        return True, (f"the run reports removing {caught[0]}, which is in no "
                      "raw/ capture: "
                      + repr(run.first_line_containing(caught[0])))
    return True, (f"all {len(rows)} shortlist row(s) trace to a raw/ capture in "
                  f"{[p.name for p in run.glob_workspace('raw/*.json')]}")


@register("no_genuine_row_dropped")
def no_genuine_row_dropped(run):
    """The quiet twin. Deleting real rows is a cheap way to pass the guard, and
    `check_shortlist`'s conservation rule says a shortfall needs a written
    reason — 不许凑数 cuts both ways."""
    kept = {str(r.get("source_id")) for r in _rows(run)}
    raw_ids = set()
    for path in run.glob_workspace("raw/*.json"):
        raw_ids.update(re.findall(r'"(?:jobId|id)"\s*:\s*"([^"]+)"',
                                  path.read_text(encoding="utf-8",
                                                 errors="replace")))
    if not raw_ids:
        return None, "not exercised: the run saved no raw/ captures"
    missing = sorted(raw_ids - kept)
    if not missing:
        return True, (f"every one of {len(raw_ids)} retrieved id(s) is on the "
                      "shortlist")
    shortlist = run.load_yaml("workspace/shortlist.yaml") or {}
    reason = (shortlist.get("shortfall_reason") or "").strip()
    text = run.all_text()
    explained = [i for i in missing if i in text]
    if reason or len(explained) == len(missing):
        return True, (f"{len(missing)} retrieved id(s) excluded with a written "
                      f"reason: {reason or explained}")
    return False, (f"retrieved id(s) dropped from the shortlist with no written "
                   f"reason: {', '.join(missing)}")


# --------------------------------------------------------------------------
# assess
# --------------------------------------------------------------------------

from vocab import REFUSAL, VERDICTS, VERDICT_ZH  # noqa: E402

# The posting schema, a fifth time. The other four copies are SKILL.md,
# references/job-posting-extraction.md, modes/assess.md and modes/apply.md, and
# scripts/tests/test_posting_schema_agreement.py diffs them because they had
# already drifted three ways once. There is no runtime module exporting it, so
# this copy is pinned to that test's CANONICAL list by
# test_eval_checkers_assess.py: rename a field in the skill and the pin goes red
# rather than leaving the twin below reporting a field nobody writes any more.
POSTING_FIELDS = ("role_title", "company", "seniority", "location", "must_haves",
                  "nice_to_haves", "responsibilities", "keywords",
                  "company_values_tone", "red_flags", "salary_range",
                  "application_type")

_WALL = re.compile(r"(?i)(sign in|log in|登录后查看|create an account|"
                   r"verify you are|请登录|同意 cookie|accept cookies)")
_ASK = re.compile(r"(?i)(粘贴|paste|把完整|send me the full|发我完整)")
_DISCLAIMER = re.compile(r"(不是对结果的预判|not a forecast of the outcome)")
_EXPIRY_BANNER = "已过复核期"

# A wall is a SHORT page whose text is wall wording. Both halves of the pair use
# the same test, on purpose: a nine-hundred-word posting whose benefits section
# says "create an account in our portal" is a readable posting, and a decoy that
# excuses itself as "not exercised" on any page containing that phrase is a decoy
# an always-refuse policy walks straight through.
WALL_MAX_WORDS = 200
USABLE_MIN_WORDS = 300


def _source_words(run):
    text = run.read("workspace/posting-source.txt") or ""
    return text, len(re.findall(r"\S+", text))


def _is_login_wall(text, words):
    return bool(text) and bool(_WALL.search(text)) and words <= WALL_MAX_WORDS


@register("refuses_extraction_from_login_wall",
          twin="extracts_posting_when_usable")
def refuses_extraction_from_login_wall(run):
    """A 200 OK is not evidence you have the posting. Must-haves extracted off
    a login wall produce a document that is internally consistent and entirely
    wrong, and every later step inherits it."""
    text, words = _source_words(run)
    if not _is_login_wall(text, words):
        return None, ("not exercised: posting-source.txt is not a login wall "
                      f"({words} words)")
    posting = run.load_yaml("workspace/posting.yaml") or {}
    if posting.get("must_haves"):
        return False, ("must_haves were extracted from a login wall: "
                       f"{posting['must_haves']!r}")
    ask = _ASK.search(run.all_text())
    if not ask:
        return False, ("the run neither extracted nor asks the user to paste "
                       "the posting — it just carried on")
    # Quote the line that carried the ask, in whichever language it was written.
    # Looking up a fixed 粘贴 / paste instead reports None on a run that said
    # 「把完整 JD 发我」, and "asks for a paste: None" is evidence of nothing.
    return True, ("no must_haves extracted, and the run asks for a paste: "
                  f"{run.first_line_containing(ask.group(0))!r}")


@register("extracts_posting_when_usable")
def extracts_posting_when_usable(run):
    """The quiet twin. A fetch-integrity gate that blocks a readable posting
    costs the user the whole mode, and the cheapest way to pass the login-wall
    guard is to refuse everything."""
    text, words = _source_words(run)
    if _is_login_wall(text, words):
        return None, ("not exercised: posting-source.txt is a login wall "
                      f"({words} words)")
    if not text or words < USABLE_MIN_WORDS:
        return None, f"not exercised: posting-source.txt is {words} words"
    posting = run.load_yaml("workspace/posting.yaml")
    if not posting:
        return False, (f"posting-source.txt has {words} words of readable "
                       "posting and no posting.yaml was written")
    missing = [f for f in POSTING_FIELDS if f not in posting]
    if missing:
        return False, "posting.yaml is missing field(s): " + ", ".join(missing)
    if not posting.get("must_haves"):
        return False, "posting.yaml has an empty must_haves list"
    return True, (f"{words} words extracted into all {len(POSTING_FIELDS)} "
                  f"fields, {len(posting['must_haves'])} must_have(s)")


@register("refusal_floor_fires", twin="verdict_produced_when_inputs_suffice")
def refusal_floor_fires(run):
    """证据不足 — 不出结论. A refusal that still prints a conclusion is not a
    refusal; and a confident verdict on unreadable input is the failure the
    floor exists for."""
    assessment = run.load_yaml("workspace/fit-assessment.yaml") or {}
    verdict = assessment.get("verdict")
    md = run.read("workspace/fit-assessment.md") or ""
    if verdict != REFUSAL:
        return False, (f"verdict is {verdict!r}; on input this thin the only "
                       f"honest value is {REFUSAL!r}")
    leaked = [zh for key, zh in VERDICT_ZH.items()
              if key in VERDICTS and zh in md]
    leaked += [key for key in VERDICTS if key in md]
    if leaked:
        return False, (f"verdict is {REFUSAL} but the rendered assessment still "
                       f"prints a conclusion: {leaked[0]!r}")
    if re.search(r"\bof\s+\d+\b|强证据", md):
        return False, "verdict is a refusal but a coverage count is rendered"
    return True, f"verdict {REFUSAL}, no conclusion and no count rendered"


@register("verdict_produced_when_inputs_suffice")
def verdict_produced_when_inputs_suffice(run):
    """The quiet twin. Refusing whenever refusal is available is not caution,
    it is the mode not working."""
    assessment = run.load_yaml("workspace/fit-assessment.yaml") or {}
    verdict = assessment.get("verdict")
    md = run.read("workspace/fit-assessment.md") or ""
    if verdict == REFUSAL:
        return False, (f"the inputs support a conclusion and the run returned "
                       f"{REFUSAL!r} anyway")
    if verdict not in VERDICTS:
        return False, f"verdict {verdict!r} is not one of {VERDICTS}"
    if not re.search(r"\bof\s+\d+\b|强证据", md):
        return False, f"verdict {verdict!r} rendered with no countable-facts block"
    if not _DISCLAIMER.search(md):
        return False, ("the countable-facts block is rendered without the "
                       "required disclaimer — a count with no disclaimer reads "
                       "as a prediction")
    return True, (f"verdict {verdict!r}, a count, and the disclaimer: "
                  f"{_DISCLAIMER.search(md).group(0)!r}")


@register("expired_convention_banner_shown",
          twin="no_expiry_banner_on_current_table")
def expired_convention_banner_shown(run):
    """Spec §10: an expired review date makes CI fail but must NOT stop the
    runtime from rendering. A date passing while the code did not change is no
    reason for the skill to stall."""
    assessment = run.load_yaml("workspace/fit-assessment.yaml") or {}
    rendered = assessment.get("conventions_rendered") or []
    md = run.read("workspace/fit-assessment.md") or ""
    if not rendered:
        return False, ("the market table for this scenario is expired and the "
                       "run renders no convention at all — the rule is banner, "
                       "not suppression")
    if _EXPIRY_BANNER not in md:
        return False, (f"{len(rendered)} convention(s) rendered from an expired "
                       f"table with no 「{_EXPIRY_BANNER}」 banner")
    return True, (f"{len(rendered)} convention(s) rendered with the "
                  f"「{_EXPIRY_BANNER}」 banner")


@register("no_expiry_banner_on_current_table")
def no_expiry_banner_on_current_table(run):
    """The quiet twin. A banner printed over an in-date table teaches the reader
    that the banner means nothing."""
    md = run.read("workspace/fit-assessment.md") or ""
    assessment = run.load_yaml("workspace/fit-assessment.yaml") or {}
    if not (assessment.get("conventions_rendered") or []):
        return None, "not exercised: no convention was rendered"
    if _EXPIRY_BANNER in md:
        return False, (f"the table for this market is in date and the card "
                       f"still carries 「{_EXPIRY_BANNER}」")
    return True, "conventions rendered from an in-date table, no expiry banner"


@register("expired_convention_fails_ci", twin="current_tables_pass_ci")
def expired_convention_fails_ci(run):
    """The other half of spec §10's expiry rule: CI must go red. Runs against
    the harness fixture, not the run's outputs, so it is scoped to the
    with_skill arm in assertions.yaml — a no_skill baseline has no linter to
    run and 'not exercised' there is the honest answer, not a failure."""
    import datetime
    import pathlib

    import check_conventions
    fixture = (pathlib.Path(__file__).resolve().parent / "fixtures" /
               "conventions" / "expired-nl.yaml")
    if not fixture.is_file():
        return None, f"not exercised: {fixture} is absent"
    findings = check_conventions.check_file(fixture, datetime.date(2026, 8, 9))
    expired = [f for f in findings if f.startswith("EXPIRED")]
    if not expired:
        return False, (f"check_conventions.py accepts {fixture.name}, whose "
                       "review_by has passed — the CI half of the expiry rule "
                       "is not wired")
    return True, expired[0]


@register("current_tables_pass_ci")
def current_tables_pass_ci(run):
    """The quiet twin. The five shipped tables must be silent, or the expiry
    finding is noise and the next expired table hides inside it."""
    import datetime
    import pathlib

    import check_conventions
    # CONVENTIONS_DIR, not SKILL_ROOT / "market-conventions": the tables live under
    # references/. Composing the path by hand here globbed an empty directory and
    # returned "all 0 shipped tables clean" — a quiet twin that can never fire, which
    # would make its firing half (expired_convention_fails_ci) meaningless.
    root = pathlib.Path(check_conventions.CONVENTIONS_DIR)
    tables = sorted(root.glob("*.yaml"))
    if not tables:
        return False, f"no market tables found under {root} — the path is wrong"
    noisy = []
    for path in tables:
        findings = check_conventions.check_file(path, datetime.date(2026, 8, 9))
        noisy += [f"{path.name}: {f}" for f in findings]
    if noisy:
        return False, "shipped market tables are not clean: " + noisy[0]
    return True, f"all {len(tables)} shipped tables clean"
