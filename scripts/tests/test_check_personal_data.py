import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_personal_data
import journal


def _ws(tmp_path, profile):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return ws


def test_clean_cluster1_profile_passes_quietly(tmp_path, capsys):
    ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "United States (Boston, MA)"},
                        "contact": {"email": "z@x.com"}})
    assert check_personal_data.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_eu_profile_with_photo_and_dob_passes_quietly(tmp_path, capsys):
    """A photo on a Dutch CV is a convention. Firing here would train the reader
    to ignore this gate."""
    ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "Amsterdam, Netherlands",
                                 "photo": "/tmp/p.png"},
                        "contact": {"personal": {"date_of_birth": "1992-04-01"}}})
    assert check_personal_data.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_cluster1_profile_still_carrying_a_dob_fails_and_names_the_field(tmp_path, capsys):
    ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "United States of America"},
                        "contact": {"personal": {"date_of_birth": "1992-04-01"}}})
    assert check_personal_data.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "CLUSTER1_PERSONAL_DATA" in out
    assert "contact.personal.date_of_birth" in out


def test_unrecognized_market_with_personal_data_fails(tmp_path, capsys):
    ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "Dubai, UAE",
                                 "photo": "/tmp/p.png"},
                        "contact": {"personal": {"nationality": "CN"}}})
    assert check_personal_data.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MARKET_UNRECOGNIZED" in out
    assert "meta.photo" in out and "contact.personal.nationality" in out


def test_missing_target_market_with_personal_data_fails(tmp_path, capsys):
    ws = _ws(tmp_path, {"meta": {"name": "Z"},
                        "contact": {"personal": {"date_of_birth": "1992"}}})
    assert check_personal_data.main(["--workspace", str(ws)]) == 1
    assert "NO_TARGET_MARKET" in capsys.readouterr().out


def test_missing_profile_is_exit_2_not_a_pass(tmp_path, capsys):
    ws = tmp_path / "empty"; ws.mkdir()
    assert check_personal_data.main(["--workspace", str(ws)]) == 2
    assert "tailored-profile.yaml" in capsys.readouterr().err


def test_every_exit_path_leaves_exactly_one_receipt(tmp_path):
    for profile, expected in (
        ({"meta": {"target_market": "us"}}, "pass"),
        ({"meta": {"target_market": "us"}, "contact": {"personal": {"date_of_birth": "1"}}}, "fail"),
    ):
        ws = _ws(tmp_path / expected, profile)
        check_personal_data.main(["--workspace", str(ws)])
        receipts = journal.read_receipts(ws, "check_personal_data")
        assert len(receipts) == 1
        assert receipts[0]["verdict"] == expected
    ws = tmp_path / "gone"; ws.mkdir()
    check_personal_data.main(["--workspace", str(ws)])
    receipts = journal.read_receipts(ws, "check_personal_data")
    assert len(receipts) == 1 and receipts[0]["verdict"] == "could_not_run"
