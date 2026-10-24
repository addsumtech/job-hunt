import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import journal
import lint_cv

CLEAN = """# Test User

## Experience

### Research Engineer — Acme (2022–present)
- Built a GPU reconstruction pipeline that cut scan time from 12 to 7 minutes.
- Drove the migration of 40 clinical protocols onto the new solver.
- Drove a two-person team through the vendor integration with Philips.
- Advised the finance team on a leveraged buyout of the imaging division.

## Skills
- Python, C++, PyTorch
"""


def _cv(tmp_path, text=CLEAN):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "cv.md").write_text(text, encoding="utf-8")
    return ws


def test_a_clean_cv_passes_silently(tmp_path, capsys):
    ws = _cv(tmp_path)
    assert lint_cv.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_leveraged_buyout_is_not_a_cliche(tmp_path):
    """A finance CV legitimately says 'leveraged buyout'. Firing on it would
    teach the reader to skip every CLICHE line."""
    assert lint_cv.findings_for("- Advised on a leveraged buyout of the division.") == []


@pytest.mark.parametrize('text', [
    'Analysed leverage and cash conversion across portfolio companies.',
    'Modelled financial leverage, debt capacity and covenant headroom.',
    'Compared operating leverage and net leverage ratios.',
    'Advised on leveraged finance and leveraged loans.',
    'Built a leveraged-buyout model with downside sensitivities.',
])
@pytest.mark.parametrize('prefix', ['', '- '])
def test_financial_leverage_is_not_a_generic_action_verb(text, prefix):
    assert lint_cv.findings_for(prefix + text) == []


@pytest.mark.parametrize('text', [
    'Leveraged data to drive results.',
    'Leveraging technology to transform operations.',
    'Leverage data to improve processes.',
    'I leverage expertise to support clients.',
    'Used financial leverage models and leveraged insights to drive results.',
])
def test_finance_vocabulary_does_not_disable_the_verb_cliche(text):
    assert any(f.startswith('CLICHE:') for f in lint_cv.findings_for('- ' + text))


def test_two_bullets_opening_with_the_same_verb_is_not_flagged(tmp_path):
    """Two is variation; three is a template. The threshold has to sit where
    ordinary writing does not trip it.

    The fixture opens two bullets with 'Drove' rather than 'Led' on purpose:
    `findings_for` only tracks openers of 4+ characters, so a three-letter verb
    is never counted and a test built on it would pass without the threshold
    ever being reached — proving the button exists, not that pressing it does
    anything. Measured on CLEAN: openers == {'built': [6], 'drove': [7, 8],
    'advised': [9], 'python': [12]}."""
    assert [f for f in lint_cv.findings_for(CLEAN) if f.startswith("REPEATED_VERB")] == []


def test_cliche_is_reported_with_its_line_number(tmp_path, capsys):
    ws = _cv(tmp_path, CLEAN + "\n- A results-driven engineer with a proven track record.\n")
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "CLICHE: cv.md:" in out
    assert "results-driven" in out and "proven track record" in out


def test_weak_openers_are_reported(tmp_path, capsys):
    ws = _cv(tmp_path, "# X\n- Responsible for the reconstruction pipeline and its tests.\n")
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "WEAK_OPENER: cv.md:2" in out and "Responsible for" in out


def test_an_over_long_bullet_is_reported_with_its_length(tmp_path, capsys):
    long_bullet = "- " + ("Rebuilt the acquisition pipeline end to end " * 8).strip() + "."
    ws = _cv(tmp_path, "# X\n" + long_bullet + "\n")
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "LONG_BULLET: cv.md:2" in out and "characters" in out


def test_three_bullets_with_the_same_opening_verb_are_reported(tmp_path, capsys):
    text = ("# X\n"
            "- Spearheaded the solver rewrite across two teams.\n"
            "- Spearheaded the vendor migration for 40 protocols.\n"
            "- Spearheaded the clinical rollout at three sites.\n")
    ws = _cv(tmp_path, text)
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "REPEATED_VERB" in out and "spearheaded" in out
    assert "2, 3, 4" in out


def test_missing_cv_is_exit_2(tmp_path, capsys):
    ws = tmp_path / "empty"; ws.mkdir()
    assert lint_cv.main(["--workspace", str(ws)]) == 2
    assert "cv.md" in capsys.readouterr().err


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws = _cv(tmp_path)
    lint_cv.main(["--workspace", str(ws)])
    (ws / "cv.md").unlink()
    assert lint_cv.main(["--workspace", str(ws)]) == 2
    assert [r["verdict"] for r in journal.read_receipts(ws, "lint_cv")] == \
        ["pass", "could_not_run"]


# ---------------------------------------------------------------------------
# lint_cv enforced a style rule on one alphabet. Four bullets opening `负责…`
# ("responsible for") and three opening `Führte…` produced NOTHING, while
# `Verantwortlich` ×3 did fire — because it happens to be pure ASCII.
# `_WORD_RE = [A-Za-z]...` also truncated at the first non-ASCII letter, so
# REPEATED_VERB compared the string "F" for every German bullet.
# ---------------------------------------------------------------------------

def test_the_word_matcher_reads_a_whole_non_ascii_word():
    assert lint_cv._WORD_RE.match("Führte").group(0) == "Führte"
    assert lint_cv._WORD_RE.match("Ștefan").group(0) == "Ștefan"


def test_a_weak_opener_is_flagged_in_chinese():
    cv = "\n".join(["- 负责设计推荐系统", "- 负责优化训练流程", "- 负责撰写文档"])
    assert any(f.startswith("WEAK_OPENER") for f in lint_cv.findings_for(cv))


def test_a_repeated_verb_is_counted_in_german():
    cv = "\n".join(["- Führte die Migration durch", "- Führte Workshops durch",
                    "- Führte Interviews mit dem Team"])
    assert any(f.startswith("REPEATED_VERB") for f in lint_cv.findings_for(cv))


def test_a_repeated_verb_is_counted_in_chinese():
    cv = "\n".join(["- 构建了训练流水线", "- 构建了评估框架", "- 构建了部署脚本"])
    assert any(f.startswith("REPEATED_VERB") for f in lint_cv.findings_for(cv))


def test_varied_non_ascii_bullets_stay_quiet():
    """The cry-wolf half: a CJK opener is two to four characters, so the matcher
    must not take the whole clause (never repeats) or one character (always
    repeats)."""
    cv = "\n".join(["- 构建了训练流水线", "- 优化了推理延迟", "- 撰写了技术文档"])
    assert not any(f.startswith("REPEATED_VERB") for f in lint_cv.findings_for(cv))


# ---------------------------------------------------------------------------
# A name is not phrasing. AI_VOCABULARY fired on a skill ("Pivotal Cloud
# Foundry") and a paper title ("Robust Motion-Corrected MRI Reconstruction"),
# exited 1 and blocked check_apply, and the only way to clear it was to falsify
# a product name or a citation. Measured 2026-10-24 on render_cv's own layout.
# ---------------------------------------------------------------------------

NAMES_CV = """# Jane Doe
jane@example.com

## Experience

**Research Engineer**, Acme BV
_2023-01 – Present_

- Cut MRI reconstruction time from 40 s to 6 s by porting the solver to CUDA.

## Skills
- **Tools:** Pivotal Cloud Foundry, Docker, MongoDB Realm

## Certifications
- Pivotal Certified Spring Professional (2021)

## Publications
- J. Doe, A. Smith. Robust Motion-Corrected MRI Reconstruction. MRM 2024.
"""


def test_skills_certifications_and_publication_titles_are_not_ai_vocabulary(tmp_path, capsys):
    assert lint_cv.findings_for(NAMES_CV) == []
    ws = _cv(tmp_path, NAMES_CV)
    assert lint_cv.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_the_summary_and_the_bullets_are_still_scanned():
    cv = NAMES_CV.replace(
        "## Experience",
        "Robust engineer who spearheaded imaging work.\n\n## Experience").replace(
        "- Cut MRI", "- Spearheaded a pivotal rewrite that cut MRI")
    found = lint_cv.findings_for(cv)
    assert any("'robust'" in f and "cv.md:4:" in f for f in found), found
    assert any("'spearheaded'" in f and "cv.md:11:" in f for f in found), found
    assert any("'pivotal'" in f and "cv.md:11:" in f for f in found), found
    assert len(found) == 4, found      # the summary's two, the bullet's two


def test_a_section_after_the_publications_is_scanned_again():
    cv = NAMES_CV + "\n## Volunteer\n- Ran a robust outreach programme.\n"
    assert [f for f in lint_cv.findings_for(cv) if "'robust'" in f] != []


def test_a_subheading_inside_the_publications_stays_a_publication():
    cv = ("# X\n\n## Publications\n\n### Journal articles\n"
          "- Doe J. Leveraging robust priors for MRI. MRM 2024.\n")
    assert lint_cv.findings_for(cv) == []


def test_a_cliche_in_the_skills_list_is_still_a_cliche():
    """Only the AI-vocabulary list is lifted there: "team player" is the
    candidate describing themselves, not the name of a product."""
    cv = "# X\n\n## Skills\n- **Soft skills:** team player, excellent communicator\n"
    assert any(f.startswith("CLICHE:") for f in lint_cv.findings_for(cv))


def test_three_first_author_papers_are_not_a_repeated_verb():
    cv = ("# X\n\n## Publications\n"
          "- Nowak Z, Smith A. Leveraging sparsity in MRI. MRM 2024.\n"
          "- Nowak Z, Lee B. Robust coil compression. ISMRM 2023.\n"
          "- Nowak Z. Seamless motion correction. MICCAI 2022.\n")
    assert lint_cv.findings_for(cv) == []


@pytest.mark.parametrize("heading", ["## 专业技能", "## Kenntnisse", "## スキル",
                                     "## Technical Skills", "## Skills & Tools", "## 技能"])
def test_a_localized_or_hand_written_skills_heading_is_recognised(heading):
    assert lint_cv.findings_for(f"# X\n\n{heading}\n- Pivotal Cloud Foundry\n") == []


def test_meta_headings_names_the_skills_section_of_an_untabled_language(tmp_path, capsys):
    cv = "# X\n\n## Umiejętności\n- Pivotal Cloud Foundry\n"
    assert lint_cv.findings_for(cv)          # nothing says this heading is the skills list
    profile = {"meta": {"language": "pl", "headings": {"skills": "Umiejętności"}}}
    assert lint_cv.findings_for(cv, profile=profile) == []
    ws = _cv(tmp_path, cv)
    (ws / "tailored-profile.yaml").write_text(
        "meta:\n  language: pl\n  headings:\n    skills: Umiejętności\n", encoding="utf-8")
    assert lint_cv.main(["--workspace", str(ws)]) == 0
    capsys.readouterr()


def test_an_employer_named_in_the_entry_header_is_not_ai_vocabulary():
    """`**title**, org` is render_cv's entry header: the line that merely names
    the company, which is the case the _NOT_PROSE comment already promised."""
    cv = ("# X\n\n## Experience\n\n**Software Engineer**, Pivotal Software  \n"
          "_2015-06 – 2019-12_\n\n- Shipped the buildpack cache.\n")
    assert lint_cv.findings_for(cv) == []


def test_a_project_description_is_prose_and_still_scanned():
    cv = "# X\n\n## Projects\n\n**SegKit** — lead — a robust segmentation toolkit\n"
    assert any("'robust'" in f for f in lint_cv.findings_for(cv))


# ---------------------------------------------------------------------------
# Japanese and Korean are verb-final. Three bullets that open with the same
# object noun (データ…) were reported as one verb repeated three times on a CV
# whose verbs (移行 / 削減 / 主導) all differ.
# ---------------------------------------------------------------------------

def test_japanese_bullets_opening_with_the_same_noun_are_not_a_repeated_verb():
    cv = ("# 山田 太郎\n\n## 職務経歴\n\n"
          "- データ基盤をBigQueryへ移行し、月次集計を6時間から40分に短縮\n"
          "- データ品質チェックを自動化し、手戻りを月20件から3件に削減\n"
          "- データ分析チーム5名の採用と育成を主導\n")
    assert lint_cv.findings_for(cv) == []


@pytest.mark.parametrize("bullets", [
    ["데이터 파이프라인을 구축하여 집계 시간을 6시간에서 40분으로 단축",
     "데이터 품질 검사를 자동화하여 재작업을 월 20건에서 3건으로 감소",
     "데이터 분석팀 5명을 채용하고 육성"],
    ["Kubernetes 클러스터를 구축하여 배포 시간을 단축",
     "Kubernetes 비용을 월 30% 절감",
     "Kubernetes 모니터링 체계를 도입"],
])
def test_korean_bullets_opening_with_the_same_noun_are_not_a_repeated_verb(bullets):
    cv = "# X\n\n## 경력\n\n" + "".join(f"- {b}\n" for b in bullets)
    assert not any(f.startswith("REPEATED_VERB") for f in lint_cv.findings_for(cv))


def test_a_katakana_name_does_not_exempt_an_english_bullet():
    """Katakana alone is a name inside another language's bullet; the English
    verb still opens it, so the repetition still counts."""
    cv = ("# X\n- Spearheaded the ソニー migration.\n- Spearheaded the vendor work.\n"
          "- Spearheaded the clinical rollout.\n")
    assert any(f.startswith("REPEATED_VERB") for f in lint_cv.findings_for(cv))
