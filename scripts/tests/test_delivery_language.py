"""Delivered folder and file names follow the report's language.

The README is in five languages, but every delivery used to land in 报告/ and
简历/ whatever the client reads. The PDF footer already followed the report's
language; the names now follow the same rule (deliver.text_language).
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import deliver
import report_names
from test_deliver import MANIFEST, client_files, posting_workspace, run

REPORTS = {
    "zh": ("# 投递建议\n\n这个岗位值得申请，先确认工作范围，再准备一个真实项目的例子。\n",
           "报告", "简历", "投递建议报告"),
    "en": ("# Advice\n\nThis role is worth applying to. Confirm the scope first.\n",
           "Report", "Application", "Application advice"),
    "es": ("# Consejos\n\nEste puesto merece tu candidatura. Confirma los requisitos y "
           "prepara un ejemplo de tu experiencia.\n", "Informe", "Candidatura",
           "Consejos de candidatura"),
    "ja": ("# 応募アドバイス\n\nこの求人には応募する価値があります。まず業務範囲を確認してください。\n",
           "レポート", "応募書類", "応募アドバイス"),
    "ko": ("# 지원 조언\n\n이 공고는 지원할 가치가 있습니다. 먼저 업무 범위를 확인하세요.\n",
           "보고서", "지원 서류", "지원 조언 보고서"),
}


@pytest.mark.parametrize("lang", sorted(REPORTS))
def test_names_follow_the_report_language(tmp_path, lang):
    text, report_folder, cv_folder, report_type = REPORTS[lang]
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "Acme BV", "ML Engineer",
                           "X")
    (ws / "report.md").write_text(text, encoding="utf-8")
    assert deliver.text_language(text) == lang
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    cv = deliver.CLIENT_NAMES_BY_LANG[lang]["cv"]
    assert client_files(dest) == {
        f"{report_folder}/Acme BV－ML Engineer－2026-10-24－{report_type}.md",
        f"{cv_folder}/{cv}.md", f"{cv_folder}/{cv}.pdf"}


def test_every_language_has_every_name():
    stems = set(deliver.CLIENT_NAMES_BY_LANG["zh"])
    modes = set(report_names.MODE_NAMES["zh"])
    for lang in deliver.CLIENT_NAMES_BY_LANG:
        assert set(deliver.CLIENT_NAMES_BY_LANG[lang]) == stems, lang
        assert set(report_names.MODE_NAMES[lang]) == modes, lang
        assert lang in report_names.LEGACY_NAMES and lang in deliver.CLIENT_FOLDERS_BY_LANG
        assert set(deliver.MODE_FOLDERS_BY_LANG[lang]) == {*modes, ""}, lang


def test_no_mode_folder_collides_with_a_reserved_folder():
    """A second mode's subfolder named like a document folder would be read back as
    one (面试准备 once collided this way)."""
    for lang, labels in deliver.MODE_FOLDERS_BY_LANG.items():
        for label in labels.values():
            assert label not in deliver._RESERVED_FOLDERS, (lang, label)


def test_a_recorded_chinese_delivery_is_replaced_by_the_english_round(tmp_path):
    """After the upgrade, an English client's earlier 报告/ and 简历/ files, which the
    manifest records, are removed when the same workspace redelivers."""
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "Acme BV", "ML Engineer",
                           "X")
    dest = tmp_path / "out"
    (ws / "report.md").write_text(REPORTS["zh"][0], encoding="utf-8")
    assert run(ws, dest, "--no-pdf") == 0
    assert any(rel.startswith("报告/") for rel in client_files(dest))
    (ws / "report.md").write_text(REPORTS["en"][0], encoding="utf-8")
    assert run(ws, dest, "--no-pdf") == 0
    files = client_files(dest)
    assert not any(rel.startswith(("报告/", "简历/")) for rel in files), files
    assert "Application/CV.pdf" in files and (dest / MANIFEST).is_file()


def test_with_no_text_to_tell_the_names_stay_chinese(tmp_path):
    assert deliver.delivery_language(tmp_path) == "zh"
    assert deliver.client_path(pathlib.Path("cv.pdf")).as_posix() == "简历/简历.pdf"
