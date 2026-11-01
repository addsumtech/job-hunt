"""Task 3: Scholar and website captures become snapshots (synthetic captures, no network)."""
import datetime
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import online_presence as op
import paths

SCHOLAR_TEXT = "\n".join([
    "Jane Doe", "Leiden University Medical Center", "Verified email at example.org",
    "Title", "Cited by", "Year",
    "Fast Cardiac MRI Reconstruction With Learned Priors",
    "J Doe, A Smith, B Jones",
    "Medical Physics 53 (2), 2026",
    "4", "2026",
    "A Lightweight Segment Anything Model",
    "J Doe, C Lee",
    "Journal of Machine Learning for Biomedical Imaging, 2025",
    "12", "2025",
    "Prompt-guided Reconstruction for Random Sampling",
    "J Doe, A Smith",
    "International Workshop on Statistical Atlases, 2024",
    "2024",
    "Show more",
])


def capture(tmp_path, text, http_status=200, blocked=None, url="https://scholar.google.com/citations?user=X"):
    data = {"url": url, "title": "page", "text": text, "links": [], "http_status": http_status}
    if blocked is not None:
        data["blocked"] = blocked
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_scholar_rows_parse_title_venue_year_authors(tmp_path):
    result = op.ingest_scholar(capture(tmp_path, SCHOLAR_TEXT))
    assert result["outcome"] == "ok"
    assert [p["title"] for p in result["papers"]] == [
        "Fast Cardiac MRI Reconstruction With Learned Priors",
        "A Lightweight Segment Anything Model",
        "Prompt-guided Reconstruction for Random Sampling"]
    first = result["papers"][0]
    assert first["year"] == 2026 and first["venue"] == "Medical Physics 53 (2)"
    assert first["authors"] == "J Doe, A Smith, B Jones"


def test_scholar_captcha_capture_is_refused(tmp_path):
    text = "Our systems have detected unusual traffic from your computer network."
    result = op.ingest_scholar(capture(tmp_path, text))
    assert result["outcome"] == "refused" and result["papers"] == []


def test_blocked_flag_is_refused(tmp_path):
    result = op.ingest_scholar(capture(tmp_path, SCHOLAR_TEXT, blocked=True))
    assert result["outcome"] == "refused"


@pytest.mark.parametrize("status", [403, 429])
def test_refusal_status_is_refused(tmp_path, status):
    assert op.ingest_website(capture(tmp_path, "x", http_status=status))["outcome"] == "refused"


def test_website_text_is_kept_verbatim(tmp_path):
    text = "Jane Doe\nI build tools.\nNew: a talk at MIDL 2026."
    result = op.ingest_website(capture(tmp_path, text, url="https://jane.example/"))
    assert result == {"outcome": "ok", "code": 200, "url": "https://jane.example/", "text": text}


def test_http_404_capture_is_failed(tmp_path):
    result = op.ingest_website(capture(tmp_path, "Not found", http_status=404))
    assert result["outcome"] == "failed" and result["code"] == 404


def test_scholar_page_with_no_papers_is_ok_and_empty(tmp_path):
    text = "Jane Doe\nTitle\nCited by\nYear\nThere are no articles in this profile."
    result = op.ingest_scholar(capture(tmp_path, text))
    assert result["outcome"] == "ok" and result["papers"] == []


def test_ingest_without_capture_file_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    assert op.main(["ingest", "--name", "Jane Doe", "--source", "scholar",
                    "--capture", str(tmp_path / "missing.json")]) == 2
    assert "missing.json" in capsys.readouterr().err


def test_ingest_cli_snapshots_and_records_the_check(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    ws = paths.profile_dir("Jane Doe") / "searches" / "2026-11-01-x"
    path = capture(tmp_path, SCHOLAR_TEXT)
    assert op.main(["ingest", "--name", "Jane Doe", "--source", "scholar", "--capture", str(path),
                    "--workspace", str(ws), "--today", "2026-11-01"]) == 0
    record = op.load_record(paths.online_presence("Jane Doe"))
    check = record["checks"]["scholar"]
    assert check["date"] == "2026-11-01" and check["outcome"] == "ok"
    snap = json.loads(pathlib.Path(check["snapshot"]).read_text())
    assert len(snap["papers"]) == 3
    assert "online_presence_fetch" in (ws / "journal.jsonl").read_text()
