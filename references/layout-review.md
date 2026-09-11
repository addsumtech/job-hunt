# Review the actual template and rendered CV

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

```yaml
reviewer: "Name of the reviewing agent"
reviewed_at: "2026-09-11T12:00:00+08:00"
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
