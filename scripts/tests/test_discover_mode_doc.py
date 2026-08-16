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
    for pair in cs.DISCLOSURE_LABELS:
        for label in pair:
            assert label in body, f"disclosure label {label!r} missing"
    # Pre-filled in BOTH spellings. Pairing the labels and leaving this
    # assertion on the three Chinese ones would ship the English half of the
    # block without the one backstop that makes it worth having: an answer that
    # is already 否/no can only become 是/yes by an active overwrite, never by an
    # omission, and only if something checks that it was not left blank.
    for label, answer in (("收到限制信号后重试：", "否"),
                          ("绕过任何平台控制：", "否"),
                          ("取得真实岗位：", "否"),
                          ("Retried after a stop signal:", "no"),
                          ("Bypassed any platform control:", "no"),
                          ("Obtained real postings:", "no")):
        line = next(l for l in body.splitlines() if label in l)
        assert line.split(label, 1)[1].strip() == answer, (
            f"{label!r} must ship pre-filled as {answer!r} so concealment is an "
            "active overwrite, not an omission")


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
    for code in ("SOURCE_ID_NOT_IN_RAW", "RAW_TEXT_NOT_IN_RAW", "NO_RAW_TEXT",
                 "BAD_ROW_ID", "SOURCE_REPORT_RAW_PATH",
                 "WARN_ROW_OUTSIDE_BRIEF_MARKET", "EMPTY_RESULT_UNSUPPORTED",
                 "DETAIL_FETCH_OUT_OF_BAND", "DEGRADED_WITHOUT_DISCLOSURE",
                 "WRITE_COMMAND", "UNKNOWN_ACCESS"):
        assert code in body


def test_the_row_id_format_and_the_raw_text_anchor_are_both_stated():
    # The gate requires three anchors and the mode file defines all three, or a
    # run produces rows its own gate rejects for a reason nobody wrote down.
    body = text()
    assert "<site>-<source_id>" in body
    assert "raw/<site>-*.json" in body
    # And the reason `title` is NOT one of them, because step 6 normalises it.
    assert "not the anchored field" in body


def test_the_indeed_us_site_restriction_is_stated_before_the_first_call():
    # Measured 2026-08-16: `--location "London"` returns Columbus, Ohio with
    # exit 0. An empty shortlist has no rows for the gate to warn about, so this
    # paragraph is the only backstop on the false-empty branch — and it has to
    # arrive before Step 4 runs the search.
    body = text()
    assert "US site" in body
    assert "Columbus, Ohio" in body
    assert body.index("US site") < body.index("## Step 4"), (
        "the restriction has to be read before the search, not after it")


def test_the_raw_files_path_convention_is_pinned_to_one_spelling():
    body = text()
    assert "`raw/` prefix" in body
    assert "SOURCE_REPORT_RAW_PATH" in body


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
    for spelling in cs.PROVISIONAL_STAMP:
        assert spelling in body, f"provisional stamp {spelling!r} is defined nowhere"
    assert "MD_MISSING_PROVISIONAL_STAMP" in body


def test_the_english_scaffolding_of_the_document_is_defined_here_too():
    # Pairing the two GATE literals and nothing else yields an English document
    # with Chinese furniture — worse than either language alone, because it reads
    # to the user as a bug and passes every check. The mode file is the only
    # place these section names and labels are defined, so it is the only place
    # the English spellings can come from.
    body = text()
    for anchor in ("§0 Sources and read quality", "§0.1 Trigger",
                   "§0.2 Disclosure", "no detail fetched",
                   "direction-level shortlist"):
        assert anchor in body, f"English scaffolding {anchor!r} is defined nowhere"
    # …and the Chinese originals are still here, because a mirror replaces
    # nothing.
    for anchor in ("§0 来源与读取质量", "§0.1 触发原因", "§0.2 披露", "未取详情",
                   "方向级 shortlist"):
        assert anchor in body, f"{anchor!r} was dropped rather than mirrored"


def test_the_language_rule_the_pairing_rests_on_is_written_down():
    # spec §10: 「CV 跟市场走；评估/shortlist/面试复盘跟用户走」. Without the rule
    # stated, the next reader sees seven paired literals and no reason for them.
    body = text()
    assert "the user's language" in body or "跟用户走" in body
