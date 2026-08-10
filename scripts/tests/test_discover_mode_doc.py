"""The mode file is layer 1.5: loaded unconditionally on entering discover.

These assertions are its backstop. Every row field a gate requires, every verdict
string, every disclosure label and every script name must be findable here,
because a mode file that drifts from the gates fails silently — the run just
produces a shortlist the gate then rejects for a reason the mode never mentioned.
"""
import pathlib

import check_opencli_result as coc
import check_shortlist as cs

REPO = pathlib.Path(__file__).resolve().parents[2]
MODE = REPO / "modes" / "discover.md"


def text():
    return MODE.read_text(encoding="utf-8")


def test_every_row_field_the_gate_requires_is_defined_here():
    body = text()
    for field in cs.REQUIRED_ROW_FIELDS:
        assert field in body, f"row field {field!r} is defined nowhere"


def test_every_enum_value_the_gate_accepts_is_listed_here():
    body = text()
    for value in (cs.EXTRACTION_METHODS + cs.QUALITIES + cs.VERIFICATIONS):
        assert value in body, f"enum value {value!r} is listed nowhere"


def test_all_five_verdicts_and_the_provisional_rule_are_present():
    body = text()
    for verdict in cs.VERDICTS:
        assert verdict in body
    assert "provisional: true" in body
    assert "assess 一律重算" in body


def test_only_the_top_three_verdicts_may_get_a_detail_fetch():
    body = text()
    for verdict in cs.TOP_THREE:
        assert verdict in body
    assert "未取详情" in body


def test_the_disclosure_block_ships_prefilled_with_no():
    body = text()
    for label in cs.DISCLOSURE_LABELS:
        assert label in body, f"disclosure label {label!r} missing"
    for label in ("收到限制信号后重试：", "绕过任何平台控制：", "取得真实岗位："):
        line = next(l for l in body.splitlines() if label in l)
        assert line.split(label, 1)[1].strip() == "否", (
            f"{label!r} must ship pre-filled as 否 so concealment is an active "
            "overwrite, not an omission")


def test_the_three_auth_states_are_distinguished():
    body = text()
    for state in ("logged_in", "not_logged_in", "unknown", "no_auth_adapter"):
        assert state in body
    assert "EMPTY STRING" in body
    assert "--full" in body


def test_every_classification_the_wrapper_can_return_has_an_action():
    body = text()
    for classification in coc.CLASSIFICATIONS:
        assert classification in body


def test_bilingual_query_generation_is_required_with_its_reason():
    assert "English-only keywords miss local-language postings" in text()


def test_the_exit_code_rule_is_restated_here():
    body = text()
    assert "先看 exit code" in body
    assert "JSON.parse(stdout || '[]')" in body


def test_the_no_fabrication_rule_is_restated_at_why_matched():
    # spec §8: the fence is repeated in exactly three places, and the
    # shortlist's why_matched field is one of them.
    #
    # Anchored on the DEFINITION, not on the first mention of the word. The
    # first mention is Step 0's "Write how, per row, in `why_matched`", and a
    # window measured from there is satisfied by the unrelated "Never pad the
    # count." two paragraphs later — so the earlier version of this test passed
    # with the entire fence paragraph deleted.
    body = text()
    anchor = "**`why_matched` is one of exactly three places"
    index = body.find(anchor)
    assert index != -1, "the why_matched fence paragraph is gone"
    window = body[index:index + 700]
    assert "绝不" in window
    assert "write a reason that the card does not support" in body


def test_every_script_and_reference_this_mode_uses_is_named():
    body = text()
    for name in ("scripts/enter_mode.py", "scripts/check_opencli_result.py",
                 "scripts/check_no_write.py", "scripts/check_shortlist.py",
                 "scripts/paths.py", "references/discovery-sources.md",
                 "references/source-policy.md",
                 "references/risk-control-signals.yaml"):
        assert name in body, f"{name} is not named in the self-check list"


def test_the_platform_limit_stop_rule_is_absolute():
    body = text()
    assert "不重试" in body
    assert "不改参数重试" in body
    assert "不绕过" in body


def test_the_finding_codes_an_operator_must_react_to_are_explained():
    body = text()
    for code in ("SOURCE_ID_NOT_IN_RAW", "EMPTY_RESULT_UNSUPPORTED",
                 "DETAIL_FETCH_OUT_OF_BAND", "DEGRADED_WITHOUT_DISCLOSURE",
                 "WRITE_COMMAND", "UNKNOWN_ACCESS"):
        assert code in body


def test_the_workspace_path_shape_is_load_bearing_and_stated():
    body = text()
    assert "searches/<YYYY-MM-DD>-<slug>" in body
    assert "raw/<site>-<n>.json" in body
    # R4: the spine paths are resolved through scripts/paths.py, never
    # rebuilt by hand, so the resume-an-unfinished-run lookup keeps working.
    assert "paths.search_dir(" in body
    assert "paths.search_prefs(" in body


def test_the_mode_entry_command_is_the_first_thing_the_file_asks_for():
    # Layer 1.5's second backstop (spec §4.2): the gate requires a field only
    # this file defines, AND journal.jsonl records this file's content hash.
    # Without the second half, "loaded unconditionally" is a hope.
    body = text()
    assert "scripts/enter_mode.py --workspace <ws> --mode discover" in body
    assert "NO_MODE_ENTRY" in body
    assert "MODE_FILE_CHANGED" in body
    entry = body.index("scripts/enter_mode.py")
    for later in ("## Step 0", "opencli auth status"):
        assert body.index(later) > entry, (
            f"{later!r} comes before the mode-entry command; entry is step zero")


def test_the_search_preferences_schema_is_defined_here():
    # spec §4.3 puts search-preferences.yaml in the shared spine and §5.2 has
    # assess branch on it. discover owns writing it, so discover defines it —
    # a schema two modes read and no mode defines is a schema that drifts.
    body = text()
    assert "search-preferences.yaml" in body
    for field in ("target_market", "locations", "seniority", "work_models",
                  "languages", "salary_floor", "avoid", "experience_track"):
        assert field in body, f"search-preferences field {field!r} is defined nowhere"
    assert "cn / nl / de / uk / us / other" in body
    assert "asked, never inferred" in body


def test_the_effort_vocabulary_is_defined_here():
    body = text()
    for value in cs.EFFORT:
        assert value in body, f"effort value {value!r} is listed nowhere"
    assert "order by effort" in body.lower()


def test_insufficient_evidence_is_never_a_shortlist_row():
    # A refusal state is not a listing. check_shortlist.VERDICTS is the five
    # levels, so a row carrying it fires BAD_VERDICT — a mode file that asks
    # for one would be instructing an output its own gate rejects.
    body = text()
    assert "insufficient_evidence" in body          # it IS named…
    assert "dropped from the shortlist" in body     # …as a drop, not a row
    assert "the row is `insufficient_evidence`" not in body


def test_the_card_based_stamp_is_required_in_the_rendered_markdown_too():
    body = text()
    assert cs.PROVISIONAL_STAMP in body
    assert "MD_MISSING_PROVISIONAL_STAMP" in body
