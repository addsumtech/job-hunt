import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_word_limits


def test_korean_declared_character_limit_rejects_one_character_over():
    at_limit = "### 경험 (20자 이내)\n" + "가" * 20
    over = "### 경험 (20자 이내)\n" + "가" * 21
    posting = {"application_type": "structured"}
    assert not any("WORD_LIMIT" in f for f in check_word_limits.findings_for(at_limit, posting))
    assert check_word_limits.sections(over)[0][2] == 21
    assert check_word_limits.findings_for(over, posting)


def test_mixed_words_are_not_lost_beside_cjk():
    assert check_word_limits._words("Python경험 SQL 技术") == 6
    assert check_word_limits._words("Python SQL experience") == 3
