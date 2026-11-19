"""Post-1.5.0 review: names and footer share one language rule, and a redelivery
neither deletes nor overwrites a file it cannot prove is its own.

Every case here was reproduced against 1.5.0 on 2026-11-20 before the fix.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import deliver
from test_deliver import MANIFEST, client_files, posting_workspace, run

EN = "# Advice\n\nThis role is worth applying to. Confirm the scope first.\n"

# ---- one language rule for the footer and the names ------------------------

ZH_WITH_LINKS = """# 岗位评估报告

## 结论

这个岗位值得投递，核心要求与你的经历基本匹配，建议本周内完成申请。

- 职位：[Senior Machine Learning Engineer, Ranking and Recommendations](https://careers.example.com/jobs/senior-machine-learning-engineer-ranking-recommendations-amsterdam-12345678)
- 原文要求：Python, PySpark, Kubernetes, TensorFlow, PyTorch, Airflow, Kafka, AWS SageMaker
- 团队介绍：<https://careers.example.com/teams/machine-learning-and-data-science>

先确认签证支持，再准备一个真实项目的例子。
"""
ZH_WITH_COMMENT = ("# 评估\n\n<!-- reviewer note: the candidate asked for a short answer; keep "
                   "the wording plain and do not repeat the posting text verbatim -->\n\n"
                   "这个岗位值得申请，先确认工作范围。\n")
KO_WITH_STACK = ("# 공고 평가\n\n이 공고는 지원할 가치가 있습니다.\n\n- 요구 기술: Python, Kubernetes, "
                 "TensorFlow, PyTorch, Airflow, Kafka, AWS SageMaker, Spark, Terraform, PostgreSQL\n"
                 "- Senior Machine Learning Engineer, Ranking and Recommendations Platform\n\n"
                 "먼저 업무 범위를 확인하세요.\n")
JA_HAN_ONLY_TITLE = ("# 応募書類\n\n## 結論\n\nこの求人には応募する価値があります。まず業務範囲を確認してください。"
                     "職務経歴書は実績を数字で示すように直しました。\n")
JA_KANJI_HEAVY_BODY = ("# 求人評価レポート\n\n## 結論\n\n応募推奨。\n\n## 要件対応\n\n"
                       "- 機械学習基盤開発経験：該当（推薦基盤構築、三年）\n"
                       "- 大規模分散処理経験：該当（広告配信基盤運用）\n- 日本語能力：業務上問題無\n"
                       "- 勤務地：東京都港区、在宅勤務可\n- 年収：八百万円以上\n")
ZH_HAN_ONLY_TITLE_ENGLISH_BODY = "# 岗位评估\n\nPython, Kubernetes, TensorFlow, PyTorch, Airflow.\n"

LANGUAGE_CASES = {
    "zh_links_and_stack": (ZH_WITH_LINKS, "zh"),
    "zh_english_comment": (ZH_WITH_COMMENT, "zh"),
    "ko_english_stack": (KO_WITH_STACK, "ko"),
    "ja_han_only_title": (JA_HAN_ONLY_TITLE, "ja"),
    "ja_kanji_heavy_body": (JA_KANJI_HEAVY_BODY, "ja"),
    "zh_han_only_title_english_body": (ZH_HAN_ONLY_TITLE_ENGLISH_BODY, "zh"),
}


@pytest.mark.parametrize("case", sorted(LANGUAGE_CASES))
def test_names_and_footer_come_from_the_same_language(tmp_path, case):
    """Rendered for real: the folder, the file name and the footer agree."""
    pymupdf = pytest.importorskip("pymupdf")
    text, lang = LANGUAGE_CASES[case]
    ws = posting_workspace(tmp_path, "acme-engineer-2026-10-24", "Acme", "Engineer", "X",
                           mode="assess")
    (ws / "report.md").write_text(text, encoding="utf-8")
    assert deliver.delivery_language(ws) == lang
    dest = tmp_path / "out"
    assert run(ws, dest) == 0
    folder = deliver.CLIENT_FOLDERS_BY_LANG[lang]["report"]
    pdfs = [rel for rel in client_files(dest) if rel.endswith(".pdf")]
    assert len(pdfs) == 1 and pdfs[0].startswith(folder + "/"), pdfs
    with pymupdf.open(dest / pdfs[0]) as document:
        lines = {line.strip() for line in document[0].get_text().splitlines()}
    footers = {style["footer"] for style in deliver._REPORT_STYLES.values()}
    assert lines & footers == {deliver._REPORT_STYLES[lang]["footer"]}


# ---- Spanish has to be the language of the sentences -----------------------

def test_an_english_report_quoting_a_spanish_posting_stays_english():
    text = ("# Posting assessment\n\nThis Madrid role is worth applying to, and your "
            "background covers most of what it asks for. The posting is in Spanish; the "
            "line that matters is quoted below so you can check my reading.\n\n"
            "> Requisitos: 5 años de experiencia en Python.\n\n"
            "You meet the first requirement through the Acme project.\n")
    assert deliver.text_language(text) == "en"


def test_a_portuguese_report_falls_back_to_english_names():
    text = ("# Avaliação da vaga\n\nEsta vaga merece a sua candidatura. Os requisitos "
            "principais correspondem ao seu percurso, e as entrevistas costumam ter duas "
            "fases. Confirma primeiro o âmbito da função e prepara um exemplo concreto do "
            "seu projeto mais recente.\n")
    assert deliver.text_language(text) == "en"


def test_spanish_sentences_and_bare_spanish_labels_are_still_spanish():
    assert deliver.text_language(
        "Este puesto merece tu candidatura. Confirma los requisitos y prepara un "
        "ejemplo de tu experiencia.") == "es"
    # No sentences to weigh: the vocabulary alone decides, as before.
    assert deliver.text_language("Requisitos\n\nExperiencia\n") == "es"


# ---- a redelivery proves ownership before it deletes or overwrites ----------

def test_an_unrecorded_chinese_named_file_is_kept_when_its_bytes_differ(tmp_path, capsys):
    """The workspace already owns the folder, so foreign_files never ran; the
    user's own 简历/简历.pdf was deleted as 'this workspace's earlier copy'."""
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "Acme BV", "ML Engineer",
                           "X")
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    (dest / "简历").mkdir()
    (dest / "简历/简历.pdf").write_bytes(b"%PDF the user's own Chinese CV")
    (dest / "简历/简历.tex").write_text("the user's own source", encoding="utf-8")
    capsys.readouterr()
    assert run(ws, dest, "--no-pdf") == 0
    assert "NOTICE_LEGACY_NAME_REPLACED" not in capsys.readouterr().err
    assert (dest / "简历/简历.pdf").read_bytes() == b"%PDF the user's own Chinese CV"
    assert (dest / "简历/简历.tex").is_file()
    assert "Application/CV.pdf" in client_files(dest)


def test_an_unrecorded_chinese_named_copy_of_this_round_is_still_replaced(tmp_path, capsys):
    """The proof that does hold: the same bytes this round delivers."""
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "Acme BV", "ML Engineer",
                           "X")
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    (dest / "简历").mkdir()
    (dest / "简历/简历.pdf").write_bytes((ws / "cv.pdf").read_bytes())
    capsys.readouterr()
    assert run(ws, dest, "--no-pdf") == 0
    assert "NOTICE_LEGACY_NAME_REPLACED: 简历/简历.pdf" in capsys.readouterr().err
    assert not (dest / "简历").exists()


def _recorded_chinese_delivery(ws, dest):
    """What 1.4.1 left for an English report: Chinese names, recorded in the manifest."""
    (ws / "report.md").write_text(
        "# 投递建议\n\n这个岗位值得申请，先确认工作范围，再准备一个真实项目的例子。\n", encoding="utf-8")
    assert run(ws, dest, "--no-pdf") == 0
    assert "简历/简历.pdf" in client_files(dest)
    (ws / "report.md").write_text(EN, encoding="utf-8")


def test_a_renamed_redelivery_never_overwrites_a_file_it_did_not_record(tmp_path, capsys):
    """After the upgrade the CV lands on Application/CV.pdf, where the client kept
    their own; the manifest sent the round straight back to the folder."""
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "Acme BV", "ML Engineer",
                           "X")
    dest = tmp_path / "JobSearch"
    _recorded_chinese_delivery(ws, dest)
    (dest / "Application").mkdir()
    (dest / "Application/CV.pdf").write_bytes(b"%PDF the client's own master CV")
    capsys.readouterr()
    assert run(ws, dest, "--no-pdf") == 0
    err = capsys.readouterr().err
    assert (dest / "Application/CV.pdf").read_bytes() == b"%PDF the client's own master CV"
    sub = "Application package"
    assert "NOTICE_SEPARATE_FOLDER" in err and "Application/CV.pdf" in err and sub in err
    files = client_files(dest)
    assert f"{sub}/Application/CV.pdf" in files
    # Its own recorded Chinese-named round is still cleaned up, not left beside it.
    assert not any(rel.startswith(("报告/", "简历/")) for rel in files), files
    # And the next round goes back to that subfolder without another notice.
    assert run(ws, dest, "--no-pdf") == 0
    assert "NOTICE_SEPARATE_FOLDER" not in capsys.readouterr().err
    assert client_files(dest) == files


def test_a_renamed_redelivery_into_a_clean_folder_stays_where_it_was(tmp_path, capsys):
    """No unowned file in the way: the ordinary upgrade keeps its folder."""
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "Acme BV", "ML Engineer",
                           "X")
    dest = tmp_path / "out"
    _recorded_chinese_delivery(ws, dest)
    capsys.readouterr()
    assert run(ws, dest) == 0
    assert "NOTICE_SEPARATE_FOLDER" not in capsys.readouterr().err
    assert client_files(dest) == {
        "Report/Acme BV－ML Engineer－2026-10-24－Application advice.md",
        "Report/Acme BV－ML Engineer－2026-10-24－Application advice.pdf",
        "Application/CV.md", "Application/CV.pdf"}
    # A plain redelivery over its own rendered PDF is not a clash either.
    assert run(ws, dest) == 0
    assert "NOTICE_SEPARATE_FOLDER" not in capsys.readouterr().err


def _case_insensitive(directory):
    (directory / "probe").write_text("", encoding="utf-8")
    try:
        return (directory / "PROBE").exists()
    finally:
        (directory / "probe").unlink()


def test_a_case_only_rename_does_not_delete_the_report_just_delivered(tmp_path, capsys):
    """acme bv -> Acme BV: on macOS and Windows the old spelling IS the new file."""
    if not _case_insensitive(tmp_path):
        pytest.skip("needs a case-insensitive volume")
    ws = posting_workspace(tmp_path, "acme-ml-engineer-2026-10-24", "acme bv", "ML Engineer",
                           "X")
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    (ws / "posting.yaml").write_text('company: "Acme BV"\nrole_title: "ML Engineer"\n',
                                     encoding="utf-8")
    capsys.readouterr()
    assert run(ws, dest, "--no-pdf") == 0
    err = capsys.readouterr().err
    assert "NOTICE_STALE_FILE_KEPT" not in err and "NOTICE_SEPARATE_FOLDER" not in err
    reports = [rel for rel in client_files(dest) if rel.startswith("Report/")]
    assert len(reports) == 1 and reports[0].lower().endswith("application advice.md")
    assert (dest / MANIFEST).is_file()


# ---- 1.5.1 follow-ups ------------------------------------------------------

def test_a_short_spanish_report_without_the_vocabulary_is_spanish():
    text = ("# Informe\n\nEl equipo es pequeño y la empresa está en Madrid. Hay margen "
            "para crecer, pero el puesto pide más años de los que tienes.\n")
    assert deliver.text_language(text) == "es"


@pytest.mark.parametrize("text", [
    "The team is small and the company is in Madrid. Los Angeles and El Paso are "
    "the other offices, and Las Vegas is the third. You would report to the CTO.",
    "L'équipe est petite et la société est à Paris. Il y a de la marge pour grandir, "
    "mais le poste demande plus d'années que vous n'en avez.",
    "Il team è piccolo e la società è a Milano. C'è margine per crescere, ma il "
    "ruolo chiede più anni di quelli che hai. Lo stipendio è nella media.",
    "A equipa é pequena e a empresa está em Lisboa. Há margem para crescer, mas a "
    "vaga pede mais anos do que tens. O salário está na média.",
    "Het team is klein en het bedrijf zit in Utrecht. Er is ruimte om te groeien, "
    "maar de functie vraagt meer jaren dan je hebt.",
])
def test_other_latin_languages_still_fall_back_to_english(text):
    assert deliver.text_language(text) == "en"
