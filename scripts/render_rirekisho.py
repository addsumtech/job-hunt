#!/usr/bin/env python3
"""Render a Japanese 履歴書 (rirekisho) form from a canonical profile.

The rirekisho is the standardized Japanese CV form many traditional employers
expect — a different document from the Western CV that ``render_cv.py`` produces
(which maps to the companion 職務経歴書 / shokumu-keirekisho). It is form-based:

  • a personal-information block with a photo box,
  • a combined 学歴・職歴 (education + work history) chronological table,
  • a 免許・資格 (licenses / qualifications) table,
  • free-text 志望の動機 (motivation) and 本人希望記入欄 (requests) boxes.

Japan-specific fields live under ``jp:`` in the profile — all optional, and all
**personal data the candidate supplies** (never invented). The skill collects
them honestly:

  jp.name_furigana, jp.date_of_birth, jp.age, jp.gender, jp.address,
  jp.address_furigana, jp.photo_path, jp.date (the "as of" form date),
  jp.motivation, jp.personal_request

The 学歴・職歴 table is derived from the standard ``education`` and ``experience``
entries (merged, sorted, with 入学/卒業 and 入社/退社 rows). Nothing is fabricated.

Output: Markdown (preview) and ``.docx`` (the authentic, editable form — export
to PDF from Word/LibreOffice; the CJK form is not routed through LaTeX).

Usage:
  python render_rirekisho.py PROFILE.yaml --format md|docx --out OUTPATH
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import render_cv  # reuse load_profile + _is_current


# ── date helpers ──────────────────────────────────────────────────────────────

def _ym(s):
    """Extract (year, month) strings from a date like '2023-09' / '2021' /
    '2023年9月'. Returns ('', '') if no year is present."""
    m = re.match(r"\s*(\d{4})(?:[-/.年\s]+(\d{1,2}))?", str(s or ""))
    if not m:
        return "", ""
    month = str(int(m.group(2))) if m.group(2) else ""   # drop leading zero (9, not 09)
    return m.group(1), month


def _sortable(s):
    y, mo = _ym(s)
    return (int(y) if y else 9999, int(mo) if mo else 0)


# ── content builders ──────────────────────────────────────────────────────────

def gakureki_shokureki_rows(profile):
    """Build the combined 学歴・職歴 rows: a 学歴 header, enrolled/graduated rows
    per degree, a 職歴 header, joined/left rows per role, and a closing 以上."""
    rows = [{"y": "", "m": "", "text": "学歴", "align": "center"}]
    for ed in sorted(profile.get("education") or [], key=lambda e: _sortable(e.get("start"))):
        name = " ".join(x for x in [ed.get("institution", ""), ed.get("degree", "")] if x)
        y, mo = _ym(ed.get("start"))
        rows.append({"y": y, "m": mo, "text": f"{name}　入学"})
        ey, emo = _ym(ed.get("end"))
        verb = "在学中" if render_cv._is_current(ed) else "卒業"
        rows.append({"y": ey, "m": emo, "text": f"{name}　{verb}"})

    rows.append({"y": "", "m": "", "text": "職歴", "align": "center"})
    exp = profile.get("experience") or []
    if not exp:
        rows.append({"y": "", "m": "", "text": "なし", "align": "center"})
    for ex in sorted(exp, key=lambda e: _sortable(e.get("start"))):
        org = ex.get("org", "")
        y, mo = _ym(ex.get("start"))
        rows.append({"y": y, "m": mo, "text": f"{org}　入社"})
        if render_cv._is_current(ex):
            rows.append({"y": "", "m": "", "text": "現在に至る"})
        else:
            ey, emo = _ym(ex.get("end"))
            rows.append({"y": ey, "m": emo, "text": f"{org}　退社"})

    rows.append({"y": "", "m": "", "text": "以上", "align": "right"})
    return rows


def licenses_rows(profile):
    """免許・資格 rows from the free-form certifications list."""
    rows = []
    for cert in (profile.get("certifications") or []):
        y, mo = _ym(cert)
        rows.append({"y": y, "m": mo, "text": cert})
    if not rows:
        rows.append({"y": "", "m": "", "text": "特になし"})
    return rows


# ── Markdown renderer (preview) ───────────────────────────────────────────────

def render_markdown(profile):
    jp = profile.get("jp") or {}
    meta = profile.get("meta") or {}
    c = profile.get("contact") or {}
    out = ["# 履歴書"]
    if jp.get("date"):
        out.append(f"{jp['date']}　現在")

    out += ["", "## 基本情報", ""]
    out.append(f"- ふりがな: {jp.get('name_furigana', '')}")
    out.append(f"- 氏名: {meta.get('name', '')}")
    dob, age = jp.get("date_of_birth", ""), jp.get("age", "")
    out.append(f"- 生年月日: {dob}" + (f"（満{age}歳）" if age else ""))
    if jp.get("gender"):
        out.append(f"- 性別: {jp['gender']}")
    if jp.get("address_furigana"):
        out.append(f"- ふりがな（現住所）: {jp['address_furigana']}")
    out.append(f"- 現住所: {jp.get('address', c.get('location', ''))}")
    out.append(f"- TEL: {c.get('phone', '')}")
    out.append(f"- E-mail: {c.get('email', '')}")

    out += ["", "## 学歴・職歴", "", "| 年 | 月 | 学歴・職歴 |", "|---|---|---|"]
    for r in gakureki_shokureki_rows(profile):
        out.append(f"| {r['y']} | {r['m']} | {r['text']} |")

    out += ["", "## 免許・資格", "", "| 年 | 月 | 免許・資格 |", "|---|---|---|"]
    for r in licenses_rows(profile):
        out.append(f"| {r['y']} | {r['m']} | {r['text']} |")

    if jp.get("motivation"):
        out += ["", "## 志望の動機", "", jp["motivation"].strip()]
    if jp.get("personal_request"):
        out += ["", "## 本人希望記入欄", "", jp["personal_request"].strip()]
    return "\n".join(out) + "\n"


# ── docx renderer (the authentic, editable form) ──────────────────────────────

def _ym_table(doc, title, rows):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    doc.add_heading(title, level=1)
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "年", "月", title
    for r in rows:
        cells = t.add_row().cells
        if r.get("align") == "center":
            merged = cells[0].merge(cells[1]).merge(cells[2])
            merged.text = r["text"]
            merged.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            cells[0].text = str(r.get("y", ""))
            cells[1].text = str(r.get("m", ""))
            cells[2].text = r.get("text", "")
            if r.get("align") == "right":
                cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT


def _box(doc, title, text):
    doc.add_heading(title, level=1)
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    t.cell(0, 0).text = text.strip()


def render_docx(profile, out_path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Mm

    jp = profile.get("jp") or {}
    meta = profile.get("meta") or {}
    c = profile.get("contact") or {}
    doc = Document()
    doc.add_heading("履歴書", level=0)
    if jp.get("date"):
        p = doc.add_paragraph(f"{jp['date']}　現在")
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Personal-info block: 4×2 grid, photo cell merged down the right column.
    info = doc.add_table(rows=4, cols=2)
    info.style = "Table Grid"
    info.cell(0, 0).text = f"ふりがな　{jp.get('name_furigana', '')}"
    info.cell(1, 0).text = f"氏名　{meta.get('name', '')}"
    dob, age = jp.get("date_of_birth", ""), jp.get("age", "")
    line = f"生年月日　{dob}" + (f"（満{age}歳）" if age else "")
    if jp.get("gender"):
        line += f"　　性別　{jp['gender']}"
    info.cell(2, 0).text = line
    addr = jp.get("address", c.get("location", ""))
    contact_text = ""
    if jp.get("address_furigana"):
        contact_text += f"ふりがな　{jp['address_furigana']}\n"
    contact_text += f"現住所　{addr}\nTEL　{c.get('phone', '')}　　E-mail　{c.get('email', '')}"
    info.cell(3, 0).text = contact_text

    photo = info.cell(0, 1).merge(info.cell(3, 1))
    photo_path = jp.get("photo_path")
    if photo_path and pathlib.Path(photo_path).exists():
        photo.paragraphs[0].add_run().add_picture(photo_path, width=Mm(30))
    else:
        photo.text = "写真貼付欄\n縦 36〜40mm\n横 24〜30mm"
    photo.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    _ym_table(doc, "学歴・職歴", gakureki_shokureki_rows(profile))
    _ym_table(doc, "免許・資格", licenses_rows(profile))
    if jp.get("motivation"):
        _box(doc, "志望の動機", jp["motivation"])
    if jp.get("personal_request"):
        _box(doc, "本人希望記入欄", jp["personal_request"])

    doc.save(str(out_path))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--format", choices=["md", "docx"], default="docx",
                    help="docx is the authentic form; export it to PDF from Word/LibreOffice")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    profile = render_cv.load_profile(args.profile)
    out = pathlib.Path(args.out)
    if args.format == "md":
        out.write_text(render_markdown(profile), encoding="utf-8")
    else:
        render_docx(profile, out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
