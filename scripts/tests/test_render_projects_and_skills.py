"""Found by a real apply run on 2026-09-20.

Two renderer defects that reached a delivered CV. Both are silent: the profile
parses, every gate passes, and the loss is only visible by looking at the page.
"""
import pathlib
import subprocess
import sys

import yaml
from docx import Document

ROOT = pathlib.Path(__file__).resolve().parents[2]
RENDER = ROOT / "scripts" / "render_cv.py"

PROFILE = {
    "meta": {"name": "Jane Doe", "target_market": "nl", "language": "en"},
    "contact": {"email": "jane@example.com"},
    "projects": [{
        "name": "job-hunt",
        "role": "Author, open source",
        "bullets": ["39 acceptance-gate scripts and 160 test files, run by GitHub Actions.",
                    "Delivery is refused when a rendered PDF stops matching its source."],
    }],
    "skills": {"llm_and_agents": ["LoRA", "agent evaluation"], "programming": ["Python"]},
}


def render(tmp_path, fmt, profile=PROFILE):
    src = tmp_path / "p.yaml"
    src.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    out = tmp_path / f"cv.{fmt}"
    done = subprocess.run([sys.executable, str(RENDER), str(src), "--format", fmt, "--out", str(out)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return out


def test_project_bullets_reach_the_markdown(tmp_path):
    """They were dropped silently: only name/role/description/links rendered."""
    text = render(tmp_path, "md").read_text(encoding="utf-8")
    assert "39 acceptance-gate scripts and 160 test files" in text
    assert "Delivery is refused when a rendered PDF stops matching its source." in text


def test_project_bullets_reach_the_docx(tmp_path):
    document = Document(render(tmp_path, "docx"))
    body = "\n".join(p.text for p in document.paragraphs)
    assert "39 acceptance-gate scripts and 160 test files" in body


def test_a_skills_group_key_is_not_printed_raw(tmp_path):
    """`llm_and_agents` reached a delivered CV as the label "Llm_and_agents:"."""
    text = render(tmp_path, "md").read_text(encoding="utf-8")
    assert "Llm_and_agents" not in text and "llm_and_agents" not in text
    assert "Llm and agents" in text


def test_an_authored_group_label_keeps_its_own_case(tmp_path):
    profile = dict(PROFILE, skills={"LLM & agents": ["LoRA"], "ML/AI": ["PyTorch"]})
    text = render(tmp_path, "md", profile).read_text(encoding="utf-8")
    assert "LLM & agents" in text and "ML/AI" in text


def test_project_bullets_reach_the_latex_pdf(tmp_path):
    """The md and docx tests both passed while this renderer was crashing:
    `parts += [...]` made the name local and the LaTeX path raised
    UnboundLocalError. Only rendering a PDF showed it."""
    pdf = render(tmp_path, "pdf")
    if not pdf.exists():                      # no LaTeX engine on this machine
        tex = pdf.with_suffix(".tex")
        assert tex.exists(), "neither a PDF nor its .tex source was produced"
        source = tex.read_text(encoding="utf-8")
    else:
        import pymupdf
        with pymupdf.open(pdf) as doc:
            source = "\n".join(page.get_text() for page in doc)
    assert "39 acceptance-gate scripts and 160 test files" in source
    assert "Delivery is refused when a rendered PDF stops matching its source." in source
