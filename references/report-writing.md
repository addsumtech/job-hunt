# Write a report the client can use

Read this before drafting or revising client-facing career reports in any mode.
It applies to `report.md`, explanations in shortlists and assessments, interview
advice, and the final hand-off. It supplements the language contract; it does not
rewrite source quotations, schema keys, IDs, required labels or computed counts.

Before delivery, remove internal test narration from the whole report, including
the title, body and footer. A fictional-profile test still produces a sample
client report: do not insert “固定虚构履历”“并非真人面试”“本轮只练了” or describe
which software test stages ran. Store that provenance in the private test record.
Turn any useful result into concrete preparation advice without inventing actual
user interview performance. The delivery marker check is a backstop; reading the
whole report for its intended audience remains mandatory.

## Readability before brevity

Remove words that do no work, not words that make the explanation understandable.
Keep the full subject, necessary connectors such as “因为 / 但 / because”, and
the consequence for the reader. If an edit makes the reader reconstruct what a
noun refers to or reread the sentence, it is too compressed. For example, “先核实
年限再补材料” is less useful than “先问招聘方是否认可你现有工作的相关经验，再决定
是否为这个岗位准备项目材料”. A detailed report should explain the reasoning fully.

Use two editing passes. First subtract warm-ups, vague praise, stock contrasts
and repetition. Then add whatever the reader needs to understand the judgment:
the relevant requirement, the actual experience, an unresolved question or a
specific next action. This second pass adds reasoning, not an invented personal
voice, an anecdote, a number or another slogan.

## Start with the reader's decision

Tell the reader what to do and why: which roles to examine first, what prevents
a decision, or what to prepare. A heading should identify its subject without
requiring the previous page: “北京优先考虑的三个岗位”, not “优先方向 1/2”;
“Check sponsorship before applying”, not “Strategic considerations”.

Separate three things in the explanation: what the posting or CV actually says,
what you infer from it, and what you suggest doing. “Your CV does not describe a
product launch” is not “You have never launched a product”. An undisclosed salary
is not evidence that a pay floor is met, even after the prose is polished.

Preserve explicit employer information without adding speculative uncertainty.
If a title says “深圳/北京” while a location badge only says “深圳”, display both
cities from the title. The shorter badge alone does not establish that Beijing
is uncertain. If useful, describe the field difference briefly in a note rather
than attaching “待确认” to the location. Reserve uncertainty labels for a real
unresolved conflict or missing information that affects the client's decision.

Explain the basis of an ordering instead of only saying “再看某类岗位”. Tie the
priority to the actual requirements, documented experience and preparation effort.
Do not infer that a client is mainly To C, or unsuitable for To B/platform work,
from personal apps or content projects alone. Distinguish using an API from owning
a platform product's requirements, release, compatibility and enterprise use cases;
describe which responsibilities are documented and which are still missing.

For a long report, use a short decision summary and a contents page with useful
section names and working page links. Put comparable jobs in a table or use
consistent field labels. Explain each count's unit and exclusions once near the
count; do not make the reader reconcile postings, grouped roles and closed jobs.

Before calling a consultation complete, read every retained posting in full.
The initial shortlist and the final report have different completeness standards:
unattempted summary cards are research leads, not completed report entries.
Keep an unavailable description only with a captured access failure, its visible
reason and an unresolved status. An explicitly requested preliminary delivery
may retain cards. Follow discover mode and `deliver.py` for the checked inputs;
reading a description does not imply a completed CV-to-requirement mapping.

Deduplicate repeated captures of the same source ID. In the reading directory,
exact company-and-full-title matches may share one row: list all cities and keep
every distinct posting link, labeled with its city and posting ID. Keep the source
records separate underneath so this display grouping does not merge vacancies or
evidence. Put each posting link on its own line, even when two short labels would
fit side by side. Different posting IDs with the same title and substantially
repeated descriptions are distinct official entries, not proof of independent
vacancies or hiring headcount. Keep their links without inflating the grouped-role
count. If only one city's full description was read, identify that city; its
requirements or verification status do not automatically apply to the others.
Different seniority, product, team or specialization means a different title and
must remain a separate row. For example, Beijing and Shanghai postings named
“AI产品经理（垂类场景）-Aime” can share a row with both links; “高级AI产品经理-飞书多维表格”
and “高级AI产品经理（基础产品方向）-抖音” cannot. State both the grouped-role count and
the underlying posting count. Exclude confirmed closed postings from the entire
client report, including historical appendices, links and count explanations.
Keep those records and their exclusion reasons in the private research log; only
include them in the report if the client specifically requests historical roles.
Client usefulness decides what earns space: explain limitations that affect the
next decision, without turning internal query bookkeeping into report content.

## Make a detailed report easy to navigate

Use the job directory and its original posting links as the report's source
list. Do not add a separate source/methodology/scope chapter when that directory
already supplies the links. Keep ownership verification chains, annual-report
page references, collection windows and commentary about restrictions the
posting never stated in the private research notes. If a finding affects the
decision, give its practical conclusion once with the relevant job, such as an
application deadline or a specific contract question; do not narrate how the
evidence was checked. This does not remove the need to do and retain that work.

Group the job directory by hiring company, keeping that company's roles
consecutive. Use separate company, position, location and original-link columns.
In the PDF, show a shared company name in a visibly merged cell spanning its
roles: internal row dividers must not cross that company cell. If the renderer
cannot merge cells, repeat the full company name on each row. Repeat it in plain
Markdown tables, which have no row spans; do not leave a blank company cell under
a full-width row divider. When a group crosses a page, repeat the company name
on the new page. Preserve each role's full title and distinct links, including
the existing city/ID grouping rules. Company grouping does not merge different
roles or imply identical vacancies.

Place the table of contents after the report title and brief metadata, before
the first numbered section. Do not place it after the first section's narrative
or table. Verify that order in both the editable text and rendered PDF, and
check the actual page destinations after pagination.

Let numbered sections continue on the current page when room remains. Do not
force the second section, or every section, onto a new page merely to preserve
a previous page count. Keep headings with following content, then inspect every
page for avoidable blank areas and a lone trailing table row. Adjust ordinary
spacing or table padding while retaining the approved font sizes; never add
empty space or shrink text to meet an arbitrary number of pages.

When following a report example, copy its information structure as well as its
typography. For the consultation-report pattern, preserve: a priority table;
numbered key jobs with consistent “匹配依据 / 经验缺口 / 投递准备” fields; a table
of remaining jobs and tradeoffs; numbered preparation steps; an interview
preparation list/table; and a numbered job directory with company, full title,
location, reading status and usable source links. Use a linked contents list
for a multi-section report. Scale the rows to the actual evidence; never copy
the example's job count or fabricate entries to fill it.

Give adjacent sections different jobs in the reader's workflow. For example,
application preparation answers what to confirm before applying, which CV/version
to use or revise, and what to check before sending. Interview preparation answers
which questions to practise, how to explain real decisions and outcomes, and what
to ask the interviewer. Put the full case preparation in the interview section;
refer to it briefly elsewhere only when that reference advances a distinct action.
A sequence of similarly titled preparation lists is not a coherent workflow.
Name the role a tailored CV or interview plan targets, especially when the report
compares several roles; distinguish an existing deliverable from a suggested
future version. These are section purposes, not mandatory headings or counts.

Use one stable displayed number per job throughout the priority table, detailed
sections and directory. A company-grouped directory may change row order, but
must not renumber those jobs. If a section promises the key or priority jobs,
its selection and order must follow the stated priority list; put the remaining
jobs in the remaining-jobs section. A deliberately different selection needs a
clear section label and a reason visible to the reader. An internal limit on
how many jobs were mapped is not a reader-facing reason to call lower-priority
jobs the priorities. Check the job identities and numbers, not just the counts.

Review structure explicitly after rewriting. Compare the reference and output's
table columns, field labels, numbering, grouping and links in both Markdown and
PDF. A single summary table does not replace all of the example's lists. Record
this comparison in the layout review under `content_order` and
`headings_and_rules`; missing lists or tables require another formatting pass.

Keep the approved typography; follow `references/word-resume-layout.md` for the
English Times New Roman and Chinese SimSun report convention and its language,
template and user-request exceptions. Verify the embedded fonts in the output.
The default consultation palette is white paper with navy emphasis (`#17365d`),
very pale blue table alternation (`#f5f7fd`) and light blue rules (`#c5d2e3`).
A newer user palette or supplied template takes precedence. A request to borrow
colors does not authorize copying a reference's fonts, spacing or entire layout.

Use a compact conclusion, a clickable contents page for a long report, clear
section headings, and a complete directory after the recommendations. Put the
job requirement, the client's relevant experience, what remains uncertain and
the next action close together. Use stable comparison labels, not unexplained
“1/2” group names. Preserve the detailed reasoning and useful interview preparation.
Use space for this information; avoid decorative blank areas, repeated warnings,
compressed fragments and smaller type merely to fit more on a page. Check page
balance, table wrapping, link labels, contents targets and all report versions.
Paginate directories by the rendered height of whole entries, including their
links, rather than imposing a fixed number of rows that leaves large blank areas.

Default to a conventional written report, not a presentation deck. Use continuous
sections and ordinary paragraphs; a new section does not automatically need a new
page. As a starting point, use 12 pt body text, 14 pt section headings, a 16–18 pt
document title, 1.35–1.5 line spacing and modest paragraph spacing. Tables may use
11–12 pt when readable. A later explicit size or supplied report template wins.
In Markdown, use one H1 for the document title, H2 for sections and H3 for roles
or subtopics, so the renderer can preserve that visual hierarchy.
Write contents entries as Markdown links to heading anchors; the bundled renderer
resolves them after pagination. Do not hard-code page numbers into the source.
Keep figures at reading size rather than turning counts into oversized statistic
cards. Use comparison tables where they help, with no card frame around every
recommendation. A compact linked contents block can share the opening page.

Remove subtitles and lead-ins that explain the document instead of the jobs.
For example, delete “这些岗位也已读完整要求。表中说明了哪些可以继续了解，哪些暂时不值得
优先准备。” and “每个方向都给出准备材料与需要回答的问题。” Start with the actual
judgment, requirement or preparation material. Do not systematically add a gray
explanatory sentence beneath every heading. Keep dates, genuine evidence-status
labels and useful source qualifications; they carry information.

If the reader says the type looks large, measure the current body and heading
sizes before changing them. Reduce oversized headings, card padding and forced
page breaks first. A proposed larger point size will not make a report denser;
explain that briefly and use a sensible standard size when the user's number was
only an example. Preserve substantive analysis during reflow rather than cutting
it to fit. Inspect the new pages at normal reading scale.

For a revision, maintain a private acceptance list covering every explicit user
correction, not just the latest one. Check that list against every final PDF and
the shared skill instructions: prose, layout, fonts, palette, source titles,
grouped cities and links, excluded closed roles, and justified uncertainty. Rerun
relevant repository checks and actual report generation; passing text-based tests
alone cannot establish that the output meets the user's layout requirements.

## Replace abstraction with something the reader can identify

Name the person, task, document, action or result behind an abstract phrase.
“补证据” should say whether you mean a project description, prototype, test
record, release note or a clarification from the candidate. “跨团队交付” should
say who worked together, what the candidate did and what was delivered, when the
sources establish those details. If the details are unknown, ask for them or state
the gap; do not invent a realistic-sounding example as the candidate's history.

These are editing examples, **not replacement macros**. Their facts must be
supported in the actual case.

| Before | More useful wording |
|---|---|
| 现有经历与该方向相邻，具备一定迁移价值。 | 你做过批量评测，这个岗位也要求设计评测指标，值得先读它的完整要求。 |
| 补充端到端产品闭环的证据。 | 整理一个真实项目，说明需求从哪里来、你决定了什么、功能怎样上线、上线后看了哪些数据。 |
| 强化跨职能协同与结果导向意识。 | 简历还没说清你与研发怎样合作。选一个实际参与的项目，写清你的责任和验收方式。 |
| 从能力到业务，构建差异化竞争力。 | 面试时解释：这个功能解决了谁的问题，你怎样判断它值得做。 |
| 薪酬区间存在不确定性，建议进一步核验。 | 招聘页没写薪资。先问固定税前月薪是否达到你的要求，再决定是否花时间准备。 |
| Leverage transferable competencies to demonstrate end-to-end ownership. | Describe one real project: what you decided, who you worked with, what shipped, and how you checked the result. |

Use technical terms when they matter to the role; explain an unfamiliar one on
first use, in the reader's language. Keep employer names and exact job titles
unchanged in the source directory. In your explanation, introduce “PRD（产品需求
文档）” before using PRD alone. Do not replace a precise term such as API, RAG or
clinical registration with a vague synonym just to sound less technical.

## Remove formulaic prose without removing substance

- Delete introductions that merely announce the next sentence, repeated
  conclusions, and advice that could be pasted unchanged into any client's report.
- Remove meta-commentary such as “本文将 / 这里要说清楚 / let me be clear” and
  self-praise for the report's rigor. Describe the source limitation itself:
  “招聘页没有写薪资”, not “本报告坚持审慎核验薪酬信息”. Put only limitations that
  affect the client's decision in the report; keep tool diagnostics private.
- Rewrite literal translations, strings of abstract nouns, slogan-like endings,
  and repeated “不是……而是……”, “从……到……”, “既……又……更……” constructions when
  they obscure the point. A real comparison can stay; a rhetorical flourish
  should not carry the reasoning.
- Prefer connected sentences with a clear subject and action. Do not turn each
  clause into a bullet, force every paragraph into three parts, or replace one
  template with the same new sentence pattern throughout the report. Consistent
  labels in a comparison table help reading and are not a prose defect.
- Give actions a real subject. Replace “市场会奖励复合能力” with the particular
  requirement an identified employer published. Do not upgrade ordinary English
  such as “use” and “make” into “leverage” and “facilitate” for a professional tone.
- Name the actual object: the CV, the experience the client described, a job
  advert or a specific work record. Do not blur them into “现有材料” or narrate
  an internal evidence assessment when the reader needs an action. For example,
  “简历还没写出连接器延期的处理结果；面试前补清最后的到货安排” identifies both
  the missing detail and the next step. Keep a real distinction between missing
  experience and a detail merely absent from the CV; do not turn clearer prose
  into a new factual claim.
- Lead preparation advice with what to do or explain. Put a relevant honesty
  boundary beside that action once; avoid making every section another list of
  things the client must not say. This does not remove real gaps or authorize
  invented achievements, numbers or first-person interview scripts.
- Address the client directly. An anonymized public example may say “示例中的
  求职者”, but should not sound like an internal assessment of a person who is
  absent from the conversation. Do not invent anecdotes or casual slang to
  manufacture a human voice.
- Keep substantive reasons, employer requirements, real gaps, source links and
  useful preparation detail. A request for a detailed report is not an invitation
  to pad it with repeated cautions; a request for plain language is not a request
  for a shorter report.

Apply the method in the requested language, using natural local phrasing rather
than translating the Chinese examples word for word. These are editorial
judgments, not a universal blacklist or an “AI probability” score. A vocabulary
lint can suggest places to reread; it cannot certify readability, and it must not
rewrite job quotations or fail a table merely for repeating a useful label.

## Review the rendered report before delivery

First fix passages the user has identified. Then read the whole report as its
intended reader, checking:

1. Can I find the recommendation and its reason without reading every page?
2. Does each important judgment name the relevant job requirement and what the
   supplied background does or does not establish?
3. Can I carry out each proposed next step? Replace “加强/完善/补齐” on their own
   with the actual thing to ask, prepare or verify.
4. Is each unfamiliar term explained, each heading meaningful, and each paragraph
   adding information rather than restating another paragraph?
5. Did the revision preserve facts, uncertainty, sources, consent boundaries and
   distinctions between completed work and suggestions?
6. Do the priority list, key-job section, remaining-job section and directory
   refer to the same jobs with stable numbers? Check every identity and order;
   correct an unexplained mismatch even when all section counts are correct.
7. Is each role visibly attached to its company? Inspect the rendered group
   boundaries, including page breaks: merge company cells clearly or repeat
   the name, and keep every Markdown row's company identifiable.
8. Do adjacent sections answer different reader questions, with a clear next
   action? Trace any repeated case across sections: each occurrence must add a
   distinct purpose rather than repeat the same preparation or warning.
9. Are the target role, CV version, existing work and suggested next steps clear?
   Replace vague “material/evidence” references with the actual object, then check
   that the rewrite preserved what is known, missing or still to be confirmed.

For a long report, compare pages as well as individual sentences. Look for the
same paragraph opening, rhetorical reversal, overused bolding or repeated
conclusion across sections. Keep the stable labels needed to compare jobs;
change repetitive narrative only where it makes the report easier to read.
After changing a claim or label, search every requested version for its old
wording, including the summary, contents and closing advice. A new body with an
old summary is not a completed revision.

Read any rewritten paragraph aloud or as ordinary speech to catch awkward
translations and overloaded sentences. Record representative before/after fixes
and any unresolved issue in the private work notes; do not add a review scorecard
to the client's report or claim an independent review that did not happen.

Rerun the existing prediction/evidence checks relevant to changed claims, then
render and inspect the final pages, contents links and external links. Preserve
approved fonts, colors and layout preferences. For a reader who prefers detail,
use the available space for useful comparisons and explanations, not decorative
blank areas, repeated text or smaller type. Review all requested language and
public/private versions for shared leftover phrasing before delivering them.

## Method sources and adaptation

The editorial method is adapted from the supplied `martin-writer`, its
`long-doc-rewrite` reference, `martin-writer-en`, and the bilingual
`ai-flavor-remover` skills. `zimeiti-copywriter` contributes the use of one
reviewed master when producing multiple versions. Their source notes credit
humanizer-zh, stop-slop, ai-flavor-remover, HC3, humanizer, human-writing,
Wikipedia's Signs of AI writing and writing-agent. This reference contains the
career-report method; none of those skills or checkers is a runtime dependency.

Keep the readability-first, subtract-then-add, source-integrity and whole-document
review ideas. Do not import the originals' social-platform hooks, first-person
persona quotas, engagement requests, fixed word/frequency budgets, automatic
style scores or universal punctuation bans. Career reports retain the client's
formatting choices, necessary questions, exact quotations and source links.
## Report format acceptance

Before rendering, follow `layout-review.md` and record the latest report
reference's visual system in `report-layout-requirements.yaml`. Preserve its
fonts/sizes, margins, heading color/weight, rules, tables, paragraph spacing,
headers and footers; do not reuse the CV's styling or an unrelated default PDF
theme. Its page count is not a target for padding or font shrinking. Render to
workspace `report.pdf`, inspect every page beside the reference, and run
`check_layout.py --workspace <workspace> --report`. Any unapproved difference
requires correction, re-render and re-review before delivery. A readable PDF or
good writing alone does not meet the format requirement. `deliver.py` preserves
the reviewed PDF; do not replace it at handoff.
