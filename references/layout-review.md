# Review the actual reference and every rendered document

Apply this to the CV **and** the consultation report, using each one's latest
user-selected reference. A folder may contain different visual systems: do not
apply CV typography to the report or use an older report as the reference. Style
matching preserves typography, geometry, hierarchy and spacing, not the original
person's content or number of pages. For a one-page CV, redistribute supported
content and spacing to use the page naturally; do not accept a largely blank
lower third. Never invent text to fill the reference's pages.

Before authoring, write `layout-requirements.yaml` for the CV and
`report-layout-requirements.yaml` for the report. Measure the reference, not the
new output, to set expectations. Record the reference path/SHA-256 (or `null`
with documented defaults), and concrete expected values for all eight `CHECKS`
below. Only an explicit user change may relax these requirements; record it in
`user_overrides`. Do not rewrite requirements to make a failed output pass.

The requirements file also carries measured checks. Example for a fictional CV
(replace text samples with literal text from this candidate and retain the
reference's expected sizes/fonts):

```yaml
reference: null  # Otherwise the same {path, sha256} as the review
expectations:
  fonts: "Chinese SimSun; Latin Times New Roman; no fallback substitution"
  font_sizes: "Name 16 pt; headings and body 11 pt"
  page_geometry: "A4; left/right 36 pt; top 21.85 pt; bottom 24.65 pt"
  headings_and_rules: "Black bold headings, full-width 0.5 pt bottom rules"
  dates_and_alignment: "Centered name/contact; date columns aligned right"
  paragraph_spacing: "Body baseline pitch 15.6 pt plus 2 pt after; preserve indents"
  content_order: "Education, experience, projects, skills; preserve entry order"
  pagination_and_clipping: "One page; no clipping, split entries or stacked blank lines"
page_size_pt: [595.28, 841.89]
text_bounds_pt: [36, 20, 559.28, 817.24]
docx_geometry_twips: {width: 11906, height: 16838, top: 437, bottom: 493, left: 720, right: 720}
minimum_content_bottom_pt: 777  # When full-page use is required, derived from the usable bottom edge
text_samples:
  - {role: name, text: "Example Candidate", size_pt: 16, fonts: [TimesNewRomanPSMT, TimesNewRomanPS-BoldMT]}
  - {role: heading, text: "教育背景", size_pt: 11, fonts: [SimSun], color: 0}
  - {role: body, text: "实际正文中的连续文字", size_pt: 11, fonts: [SimSun]}
```

Use at least `name/heading/body` samples for CVs and `title/heading/body` for
reports, including mixed-script fonts where relevant. `text_bounds_pt` encloses
all painted text, including headers/footers, and is distinct from DOCX margins.
Measure these bounds from the reference's permitted content area. Sizes/bounds
allow 0.6 pt rounding tolerance; DOCX geometry is exact. Use additional samples
for distinct styles (e.g. report table text or Latin body text). Font names are
actual embedded PDF names; subset prefixes are ignored. Optional `color` is the
PDF integer RGB value. These samples do not prove whole-document conformity:
visually compare the remaining content, rules and whitespace on **every page**.
For text repeated in a header and title at different sizes, set `region_pt:
[left, top, right, bottom]` on the sample to measure only the intended text area.
`minimum_content_bottom_pt` is a lower bound on the final text's bottom edge for
a one-page CV. Measure it together with the one-page count and visually reject
artificially large gaps; merely placing one line near the bottom does not pass
the visual check. Record the user's full-page request as an explicit spacing
override when the supplied reference would otherwise leave a large blank area.

This is part of apply review, separate from the three content judges. A judge
reading Markdown cannot verify the Word/PDF layout. Do not call matching headings,
correct page count, or readable Chinese a template match.

1. Open the actual supplied reference. Read its page geometry, effective fonts
   and sizes, heading rules, contact/date placement, paragraph spacing, and
   section/entry/bullet order. Use the latest explicit user changes where they
   override the source (for example full-width rules, different fonts, or removal
   of personal information from a reusable template). Record those changes.
2. Render the final DOCX in Word/LibreOffice or inspect it in an available office
   app. Inspect every page; inspect the final PDF too. A LaTeX PDF does not prove
   that the Word version has the same layout. Export from Word when the two must
   match. Save each inspected page preview under `raw/layout/`.
3. Compare the eight categories below. Keep the source order, not a default
   career heuristic. Check the actual embedded PDF fonts. Do not shrink text to
   conceal overflow. Use at most one blank line between sections and inspect
   dates at the right edge, full-width rules, clipping, and page breaks.
   Inspect bullet emphasis: only an explicit opening `Label:` / `标签：` may be
   bold. Without that opening label and colon, the whole bullet stays plain.
   Do not pick words, numbers or the first clause for emphasis, or add a label
   just to enable bolding. Record this check under `headings_and_rules`.
   The opening label must cover the whole bullet. A mixed education paragraph
   starting with GPA and continuing with courses, research or awards stays plain;
   do not bold GPA just because it is followed by a colon.
4. Fix unapproved differences and render again. After the final inspection,
   write `layout-review.yaml` using the example below, replacing every hash with
   the actual SHA-256. No supplied template means `reference: null`; it does not
   waive the rendered-page review. If visual inspection is unavailable, report
   that limitation and do not write a passed review.
5. Run `python scripts/check_layout.py --workspace <workspace>`. Editing the CV,
   reference, preview or review afterward invalidates its receipt. Run the
   comparison again after any re-render. Keep the audit out of the client report.

**Reject → redo → review again is mandatory.** A mismatch, missing measurement,
unreviewed page or substituted font cannot be waived by readable text or a
content-judge pass. Correct the artifact, export again, regenerate every affected
preview, visually compare again and replace the review with current hashes.

```yaml
reviewer: "Name of the reviewing agent"
reviewed_at: "2026-09-11T12:00:00+08:00"
requirements_sha256: "actual layout-requirements.yaml SHA-256"
reference:
  path: "/actual/path/to/the-user-template.docx"
  sha256: "actual reference SHA-256"
user_overrides:
  - "User's explicit later instruction and what it changes. Use [] if none."
checks:
  fonts: {status: pass, detail: "Reference/user font names and verified output fonts."}
  font_sizes: {status: pass, detail: "Measured name, heading and body sizes."}
  page_geometry: {status: pass, detail: "Compared paper size and all four margins."}
  headings_and_rules: {status: pass, detail: "Compared heading weight and rule width."}
  dates_and_alignment: {status: pass, detail: "Compared contact/date style and alignment."}
  paragraph_spacing: {status: pass, detail: "Compared line spacing, indents and section separation."}
  content_order: {status: pass, detail: "Compared sections, entries and bullet order."}
  pagination_and_clipping: {status: pass, detail: "Inspected every page; no clipping or unintended breaks."}
unresolved_differences: []
word_export:
  path: raw/layout/word-export.pdf
  sha256: "SHA-256 of the Word export, identical to final cv.pdf"
  docx_sha256: "SHA-256 of the DOCX used for that export"
artifacts:
  cv.docx:
    sha256: "actual final DOCX SHA-256"
    pages: 1
    previews:
      - {page: 1, path: raw/layout/word-page-1.png, sha256: "actual preview SHA-256"}
  cv.pdf:
    sha256: "actual final PDF SHA-256"
    pages: 1
    previews:
      - {page: 1, path: raw/layout/pdf-page-1.png, sha256: "actual preview SHA-256"}
```

Include every Word/PDF CV that exists, with one preview per rendered page. When
the delivered PDF is the verified Word export, both entries may point to the
same inspected preview. The gate checks hashes, page coverage and the completed
comparison; the agent remains responsible for making the visual judgment.

For reports, author `report.pdf` in the workspace with the selected visual system.
Before rendering, inventory the reference's tables, column names, list types,
numbering, repeated job fields, contents and source directory. Put the expected
block structure under `expectations.content_order`; compare the actual Markdown
and PDF against it in `checks.content_order` and `checks.headings_and_rules`.
Under `checks.content_order`, record the actual job identities/numbers in the
priority list, key-job section, remaining-job section and directory. Reject
unexplained selection/order mismatches or changed numbers; company grouping may
change directory row order without changing job numbers. Under
`checks.headings_and_rules`, record whether shared company names use visible
row-spanning cells or repeat on every row. Inspect internal dividers and page
breaks; blank company cells with full-width dividers fail this comparison.
Plain Markdown tables must repeat the company name. These are actual content
and visual comparisons, not claims that the hash/geometry gate detects them.
Fonts and colors alone cannot satisfy this comparison. Preserve applicable
blocks even when shortening the report, using only the current case's real rows.
Write `report-layout-review.yaml` using the same structure: bind
`report-layout-requirements.yaml` via `requirements_sha256`, add `source_sha256`
for `report.md`, use `artifacts: {report.pdf: ...}` with all pages, and omit
`word_export`. Then run `python scripts/check_layout.py --workspace <workspace>
--report`. `deliver.py` checks these current inputs before copying an authored
report PDF; it preserves its bytes rather than rebuilding it with default styles.
Missing/stale requirements or a failed check block that delivery. The default
Markdown renderer remains available for initial report generation; create the
workspace PDF and complete this review before the final handoff.
