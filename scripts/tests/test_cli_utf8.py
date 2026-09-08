"""UTF-8 artifacts and CLI pipes must survive a legacy Windows code page.

The child is deliberately started without UTF-8 mode. These checks exercise the
product entry points and real byte decoding, not a runner-wide environment fix.
"""
import copy
import os
import pathlib
import subprocess
import sys

import pytest

import check_pages
import deliver
import discover_fixtures as fx
import journal
import opencli_meta


SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
TEXT = "中文の求人 · 한국어 · español"


def legacy_cli(script, *args):
    env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp1252:strict")
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          env=env, capture_output=True, encoding="utf-8")


@pytest.mark.parametrize("language,expected", [
    ("zh", "强证据"), ("en", "must-haves"), ("ja", "必須条件"),
    ("ko", "필수 요건"), ("es", "sólida"),
])
def test_count_cli_uses_utf8_even_when_python_starts_with_legacy_stdio(tmp_path, language, expected):
    (tmp_path / "fit-assessment.yaml").write_text("requirements: []\n", encoding="utf-8")
    result = legacy_cli("count_coverage.py", "--workspace", tmp_path, "--lang", language)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
    assert "Traceback" not in result.stderr
    assert journal.read_receipts(tmp_path, "count_coverage")[-1]["verdict"] == "recorded"


def test_unreadable_input_still_reports_its_unicode_path_and_receipt(tmp_path):
    ws = tmp_path / "候補者-한서진"
    ws.mkdir()
    result = legacy_cli("count_coverage.py", "--workspace", ws)
    assert result.returncode == 2
    assert ws.name in result.stderr
    assert "Traceback" not in result.stderr
    receipt = journal.read_receipts(ws, "count_coverage")[-1]
    assert receipt["verdict"] == "could_not_run"
    assert journal.receipt_intact(receipt)


def test_shortlist_prints_all_findings_instead_of_crashing_after_the_first(tmp_path):
    ws = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(ws)
    row = copy.deepcopy(data["rows"][0])
    row.update(id="51job-987654321", source_id="987654321",
               url="https://jobs.51job.com/shanghai/987654321.html")
    data["rows"].append(row)
    fx.save_shortlist(ws, data)
    result = legacy_cli("check_shortlist.py", "--workspace", ws)
    assert result.returncode == 1, result.stderr
    assert "SOURCE_ID_NOT_IN_RAW:" in result.stdout
    assert "URL_NOT_FROM_ADAPTER:" in result.stdout
    assert "Traceback" not in result.stderr
    assert journal.read_receipts(ws, "check_shortlist")[-1]["verdict"] == "fail"


def utf8_tool(monkeypatch, body):
    """Use a real UTF-8-producing subprocess, with cp1252 as the fallback reader."""
    run = subprocess.run
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "cp1252")

    def emit(_argv, **kwargs):
        return run([sys.executable, "-c",
                    "import sys; sys.stdout.buffer.write(" + repr(body) + ")"], **kwargs)

    monkeypatch.setattr(subprocess, "run", emit)
    monkeypatch.setattr(check_pages.shutil, "which", lambda _name: "test-tool")


@pytest.mark.parametrize("consumer", ["pdf_delivery", "pdf_gate", "markdown", "opencli"])
def test_external_utf8_output_is_not_decoded_as_the_windows_locale(tmp_path, monkeypatch, consumer):
    utf8_tool(monkeypatch, TEXT.encode("utf-8"))
    if consumer == "pdf_delivery":
        output = deliver.pdf_text(tmp_path / "document.pdf")
    elif consumer == "pdf_gate":
        output = check_pages._pdftotext(tmp_path / "document.pdf")
    elif consumer == "markdown":
        md = tmp_path / "document.md"
        md.write_text("# Source\n", encoding="utf-8")
        output = deliver.visible_markdown(md)
    else:
        output = opencli_meta._help_yaml("51job", None, True)
    assert output == TEXT


def test_invalid_utf8_tool_output_is_unavailable_not_a_successful_read(tmp_path, monkeypatch):
    utf8_tool(monkeypatch, b"\xffnot-utf8")
    assert deliver.pdf_text(tmp_path / "document.pdf") == ""
    with pytest.raises(opencli_meta.MetadataUnavailable):
        opencli_meta._help_yaml("51job", None, True)
