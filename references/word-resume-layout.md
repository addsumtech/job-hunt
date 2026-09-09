# Word resume layout

`render_cv.py --format docx` uses the reviewed black-and-white layout: centered
name/contact block, serif text, full-width rules under section headings, bold
organization/role labels, right-aligned date columns and hanging bullet indents.
Chinese body text is 10 pt; other languages use 11 pt. English body text is
left-aligned so justification cannot stretch word spacing.
Rules are native paragraph borders, not underlined trailing spaces or pictures.

The page size, section order, translated/custom headings, links and personal-data
rules still come from the existing profile contract. Internships remain entries
in `experience`; set an entry's `section: internships` to preserve a separate
internship heading in a supplied template. Other candidates need not use the
example's section order. Photos are absent
from the examples, but an explicitly supplied photo still follows market policy.
Markdown and LaTeX/PDF output are unchanged; export the DOCX with Word/LibreOffice
when a PDF with this exact layout is needed, and check its actual page count.

Fictional, editable examples and their inputs:

- [English profile](../assets/word-resume/en.yaml) · [Word output](../assets/word-resume/en.docx)
- [Chinese profile](../assets/word-resume/zh.yaml) · [Word output](../assets/word-resume/zh.docx)

Regenerate from the repository root:

```sh
python scripts/render_cv.py assets/word-resume/en.yaml --format docx --out cv-en.docx
python scripts/render_cv.py assets/word-resume/zh.yaml --format docx --out cv-zh.docx
```

The examples contain no source resume, photo, private contact details or personal
history. Do not put a user's original reference in the repository when adapting
this layout. Inspect the final export, not only the Word editing view: paragraph
markers and pagination squares are non-printing UI aids, not resume bullets.
