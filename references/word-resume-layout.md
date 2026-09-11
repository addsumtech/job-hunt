# Word resume layout

`render_cv.py --format docx` uses the reviewed black-and-white layout: centered
name/contact block, serif text, full-width rules under section headings, bold
organization/role labels, right-aligned date columns and hanging bullet indents.
Body text defaults to 11 pt: Times New Roman for English and SimSun (宋体)
for Chinese, including Chinese titles. English body text is
left-aligned so justification cannot stretch word spacing.
Rules are native paragraph borders, not underlined trailing spaces or pictures.
Within a bullet, bold only an explicit opening label ending in a colon
(`Label:` or `标签：`). Leave the remaining text plain. If there is no opening
label and colon, leave the entire bullet plain; do not infer emphasis from its
first clause, keywords or numbers. Do not add labels merely to enable bolding.
The label must describe the entire bullet, not just its first fact. For example,
leave `GPA: ...; courses ...; research ...` wholly plain: the rest of the bullet
is not an explanation of GPA. A colon alone does not justify bold emphasis.

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

A supplied template takes precedence over these default fonts and sizes. Inspect
its document defaults, styles and direct run formatting, including the name font
and mixed body sizes. Preserve the actual font families (Songti SC is not SimSun)
and remove inherited theme overrides when setting them. Verify the fonts embedded
in the exported PDF; readable Chinese alone does not prove template fidelity.
If the source font exists in the installed office suite, make that exact font
available to the exporter. Do not shrink body text merely to force one page.

Aim for a balanced, well-filled page using the supplied content. Where space
permits, separate section headings with at most one blank line (prefer paragraph
spacing over empty paragraphs); never stack blank lines or invent content to
fill the page. Verify pagination after adjusting spacing. These conventions
apply to report PDFs too: English Times New Roman, Chinese SimSun; verify actual
exported fonts and use the installed office-suite font when available. A newer
explicit user typography request overrides the reference template.
Record a requested Chinese font in `meta.cjk_font` of the workspace profile.
Delivery honors that selection before its bundled report fonts; a missing selected
font is reported instead of silently substituted. Without an explicit selection,
the bundled report renderer remains available without a TeX installation.
