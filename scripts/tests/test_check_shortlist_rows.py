"""Per-row provenance tests for scripts/check_shortlist.py.

Risk register row 1: a fabricated shortlist is internally consistent, perfectly
formatted, and every field has the right shape. The one thing a fabricated row
cannot do is appear in raw/ — so that is what is checked, verbatim, per row.
"""
import pytest

import check_shortlist as cs
import discover_fixtures as fx


def run(workspace, capsys):
    code = cs.main(["--workspace", str(workspace)])
    return code, capsys.readouterr()


def codes(out):
    return sorted({line.split(":", 1)[0] for line in out.strip().splitlines() if line})


def test_the_valid_workspace_is_completely_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_source_id_absent_from_raw_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "999999999"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_ID_NOT_IN_RAW" in codes(captured.out)
    assert "51job-1.json" in captured.out


def test_a_short_source_id_is_rejected_before_the_substring_search(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "17"      # would match almost any capture
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SUSPICIOUS_SOURCE_ID" in codes(captured.out)


def test_a_site_with_no_raw_capture_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    row = dict(data["rows"][0])
    row.update({"id": "linkedin-3812345678", "source_site": "linkedin",
                "source_id": "3812345678",
                "url": "https://www.linkedin.com/jobs/view/3812345678/"})
    data["rows"].append(row)
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_RAW_CAPTURE_FOR_SITE" in codes(captured.out)
    # Reported once, not twice: no SOURCE_ID_NOT_IN_RAW piled on top.
    assert "SOURCE_ID_NOT_IN_RAW" not in codes(captured.out)


def test_an_invented_url_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["url"] = "https://jobs.51job.com/shanghai/173198362.html"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "URL_NOT_FROM_ADAPTER" in codes(captured.out)


def test_the_full_url_with_tracking_params_is_quiet(tmp_path, capsys):
    # Storing either the trimmed url or the adapter's full one must pass;
    # stripping tracking parameters is not evidence of fabrication.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["url"] = (
        "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0")
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_real_source_id_pasted_onto_an_invented_row_fires(tmp_path, capsys):
    # The reproduction this rule was written for: ONE genuine card in raw/, and a
    # row that keeps its jobId and invents title, company, location, salary and
    # raw_text. Verifying source_id and stopping passed it with zero findings.
    import json
    workspace = fx.build_workspace(tmp_path)
    (workspace / "raw" / "51job-1.json").write_text(
        json.dumps([{"jobId": "173215361", "name": "算法工程师",
                     "company": "某公司", "salary": "30-50K", "city": "上海"}],
                   ensure_ascii=False, indent=2), encoding="utf-8")
    brief = fx.load_brief(workspace)
    brief["target_count"] = 1
    fx.save_brief(workspace, brief)
    data = fx.load_shortlist(workspace)
    data["rows"] = [{
        "id": "51job-173215361",
        "title": "Principal MRI Reconstruction Scientist",
        "company": "Philips Research",
        "location": "Eindhoven",
        "salary": "€120,000",
        "url": "",
        "source_site": "51job",
        "source_id": "173215361",
        "extraction_method": "adapter_search",
        "retrieved_at": "2026-08-09T14:02:11Z",
        "quality": "card_only",
        "verification": "collected_unverified",
        "raw_text": ("Principal MRI Reconstruction Scientist | Philips Research | "
                     "Eindhoven, Netherlands | €120,000 per year | PhD in medical "
                     "imaging; compressed sensing; deep-learning reconstruction"),
        "why_matched": "brief.target_titles 命中「算法工程师」；薪资在 brief 区间内。",
        "verdict": "strong_apply",
        "provisional": True,
        "effort": "quick",
    }]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "RAW_TEXT_NOT_IN_RAW" in codes(captured.out)
    # The source_id itself is real, so the old check stays silent — which is the
    # whole point of anchoring a second field.
    assert "SOURCE_ID_NOT_IN_RAW" not in codes(captured.out)


def test_a_title_normalised_in_step_6_stays_quiet(tmp_path, capsys):
    # Step 6 legitimately normalises titles (de-duplication compares on a
    # normalised title), so `title` is NOT the anchored field. A row whose title
    # has been cleaned up while raw_text still carries the card must pass.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["title"] = "高级算法工程师"      # brackets and tail dropped
    data["rows"][1]["title"] = "高级 AI 算法工程师"  # J-code dropped, spaces added
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_raw_text_the_capture_does_not_support_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["raw_text"] = (
        "资深医学影像重建科学家 | 飞利浦研究院 | 埃因霍温 | 年薪 120 万 | "
        "要求压缩感知与深度学习重建经验")
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "RAW_TEXT_NOT_IN_RAW" in codes(captured.out)
    assert "飞利浦研究院" in captured.out          # names what was not found
    assert "why_matched" in captured.out           # and where paraphrase belongs


def test_a_raw_text_with_one_added_annotation_stays_quiet(tmp_path, capsys):
    # The quiet twin of the rule above. A card summary is joined by hand, so a
    # trailing note or a re-wrap must not read as fabrication — only a raw_text
    # that is MOSTLY not in the capture does.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["raw_text"] = (
        data["rows"][0]["raw_text"].replace(" | ", "\n") + "\n（仅卡片信息，未取详情）")
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_an_empty_raw_text_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["raw_text"] = "   "
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_RAW_TEXT" in codes(captured.out)


def test_a_row_id_that_is_not_site_dash_source_id_fires(tmp_path, capsys):
    # modes/discover.md:244 documents `id: <site>-<source_id>`, and until this
    # check nothing tied the two together — so the id could name a posting the
    # provenance chain never touched.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["id"] = "51job-173190000"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_ROW_ID" in codes(captured.out)
    assert "51job-173198362" in captured.out       # names the id it should be
    # The provenance chain itself is untouched, so nothing else fires.
    assert "SOURCE_ID_NOT_IN_RAW" not in codes(captured.out)


def test_empty_title_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["title"] = ""
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "EMPTY_TITLE" in codes(captured.out)


def test_missing_why_matched_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][1]["why_matched"] = "   "
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_WHY_MATCHED" in codes(captured.out)


def test_missing_retrieved_at_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    del data["rows"][0]["retrieved_at"]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_RETRIEVED_AT" in codes(captured.out)
    assert "MISSING_FIELD" in codes(captured.out)


def test_missing_source_site_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_site"] = ""
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_SOURCE_SITE" in codes(captured.out)


def test_a_verdict_outside_the_five_levels_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["verdict"] = "maybe"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_VERDICT" in codes(captured.out)
    assert "strong_apply" in captured.out


def test_a_missing_provisional_stamp_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["provisional"] = False
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MISSING_PROVISIONAL" in codes(captured.out)
    assert "may not be rendered" in captured.out


def test_a_bad_enum_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["extraction_method"] = "screenshot"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_ENUM" in codes(captured.out)


def test_a_bad_effort_value_fires(tmp_path, capsys):
    # effort is what makes D3's "within a band, order by effort-to-close"
    # implementable instead of merely stated, so it is enum-checked like the
    # rest rather than left as free text nobody can sort on.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["effort"] = "a weekend maybe"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_ENUM" in codes(captured.out)
    assert "not_closable" in captured.out


def test_a_duplicated_source_id_fires(tmp_path, capsys):
    # Count conservation from the row side: one retrieved posting may not be
    # listed twice to pad the shortlist toward target_count.
    import copy
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    clone = copy.deepcopy(data["rows"][0])
    clone["id"] = "51job-173198362-b"
    data["rows"].append(clone)
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "DUPLICATE_SOURCE_ID" in codes(captured.out)


def test_the_row_vocabulary_is_the_one_in_scripts_vocab(tmp_path):
    # R1: no closed set is spelled out twice. If check_shortlist ever grows its
    # own copy of the verdicts, this fails rather than drifting quietly.
    import vocab
    assert cs.VERDICTS is vocab.VERDICTS
    assert cs.EFFORT is vocab.EFFORT
    assert cs.TOP_THREE == ("strong_apply", "worth_applying", "stretch")
    assert len(cs.REQUIRED_ROW_FIELDS) == 17
    assert "effort" in cs.REQUIRED_ROW_FIELDS


def test_a_missing_shortlist_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
    import json
    workspace = fx.build_workspace(tmp_path)
    before = len((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines())
    (workspace / "shortlist.yaml").unlink()
    code, captured = run(workspace, capsys)
    assert code == 2
    assert "shortlist.yaml" in captured.err
    lines = (workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == before + 1
    receipt = json.loads(lines[-1])
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "could_not_run"


def test_a_missing_workspace_directory_exits_2_with_no_receipt(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert cs.main(["--workspace", str(missing)]) == 2
    assert "workspace not found" in capsys.readouterr().err
    assert not missing.exists()


def test_a_receipt_is_written_on_pass_and_on_fail(tmp_path, capsys):
    import json
    workspace = fx.build_workspace(tmp_path)
    assert cs.main(["--workspace", str(workspace)]) == 0
    capsys.readouterr()
    receipt = json.loads((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()[-1])
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "pass"
    assert "shortlist.yaml" in receipt["input_hashes"]

    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "999999999"
    fx.save_shortlist(workspace, data)
    assert cs.main(["--workspace", str(workspace)]) == 1
    capsys.readouterr()
    receipt = json.loads((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()[-1])
    assert receipt["verdict"] == "fail"
    assert any(f.startswith("SOURCE_ID_NOT_IN_RAW") for f in receipt["findings"])


# ---------------------------------------------------------------------------
# The country matcher, audited 2026-09-05. This is the one check standing
# between a UK user and "there are no London backend roles", and `indeed`
# resolves --location against a US gazetteer, so it fires exactly where it is
# most needed. Two ways it went quiet:
# ---------------------------------------------------------------------------

_ROWS = [
    {"id": "michigan", "location": "Holland, MI 49423"},
    {"id": "nsw", "location": "Sydney, New South Wales"},
    {"id": "new-england", "location": "Boston, New England Region"},
    {"id": "amsterdam", "location": "Amsterdam, Netherlands"},
    {"id": "noord", "location": "Noord-Holland"},
    {"id": "eu", "location": "Remote in EU"},
    {"id": "ohio", "location": "Columbus, OH 43215"},
]


def _warned(markets):
    out = cs._check_market_fit({"markets": markets}, _ROWS)
    return {f.split("id=")[1].split("'")[1] for f in out}


def test_a_us_town_sharing_a_country_name_no_longer_passes_a_dutch_brief():
    """`Holland, MI 49423` names the Netherlands by substring and Michigan by
    structure, and the intersection test read the first and went quiet. A
    two-letter state after a comma is positive evidence, not one guess."""
    assert "michigan" in _warned(["nl"])


def test_a_longer_place_name_containing_a_country_wins():
    """`Sydney, New South Wales` resolved to `uk` because it contains "wales",
    and `Boston, New England Region` because it contains "england" — both passed
    a UK brief in silence."""
    warned = _warned(["uk"])
    assert "nsw" in warned and "new-england" in warned


def test_the_rows_that_really_are_in_the_brief_market_stay_quiet():
    """The cry-wolf half, and the longer list: this check fires on a WARN, and a
    warning that goes off on correct rows is one the reader stops reading."""
    warned = _warned(["nl"])
    assert "amsterdam" not in warned
    assert "noord" not in warned, "Noord-Holland is the Netherlands"
    assert "eu" not in warned


def test_a_us_brief_is_quiet_on_us_rows_including_the_ambiguous_one():
    warned = _warned(["us"])
    assert "michigan" not in warned and "ohio" not in warned


# ---------------------------------------------------------------------------
# The state code outranks a country token only when it comes LATER.
#
# Found re-reading my own fix, 2026-09-05. Making the state UNCONDITIONALLY
# definitive caught `Holland, MI 49423` and then cried wolf on every honest
# Dutch row written with a province abbreviation — `Amsterdam, NH, Netherlands`
# warned under a Netherlands brief.
#
# Position is the real signal, and it is how job boards write a location:
# City, Region, Country. In `Holland, MI` the country token IS the city name
# and the state follows it; in `Amsterdam, NH, Netherlands` the country is last
# and settles it. It also gets `China, TX` right — a Texas town — which no
# strong-versus-weak token list would.
# ---------------------------------------------------------------------------

_POSITION = [
    # (location, brief market, should warn)
    ("Amsterdam, NH, Netherlands", "nl", False),
    ("Utrecht, UT, Nederland", "nl", False),
    ("Den Haag, ZH, Netherlands", "nl", False),
    ("Rotterdam, South Holland, Netherlands (Hybrid)", "nl", False),
    ("Holland, MI 49423", "nl", True),
    ("Columbus, OH 43215", "nl", True),
    ("China, TX", "cn", True),
    ("Beijing, China", "cn", False),
    ("Columbus, OH 43215", "us", False),
    ("Holland, MI 49423", "us", False),
]


@pytest.mark.parametrize("location,market,warns", _POSITION,
                         ids=[f"{m}-{loc[:22]}" for loc, m, _ in _POSITION])
def test_a_state_code_settles_it_only_when_it_comes_after_the_country(
        location, market, warns):
    found = cs._check_market_fit({"markets": [market]},
                                 [{"id": "r", "location": location}])
    assert bool(found) is warns, found
