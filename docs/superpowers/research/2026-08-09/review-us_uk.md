# Adversarial review — market `us_uk`

**Verification method:** every `source_kind: published` URL was fetched on 2026-08-09 (WebFetch, or curl where the host 403s WebFetch). Raw text saved under `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/` (`ier.txt`, `t8.txt`, `ca.txt`, `cdle.txt`, `nhs.txt`, `nhsev.txt`, `csb.txt`, `prtw.html`). Constraint scan run mechanically via `scan.py`.

**All 13 cited URLs resolved HTTP 200 and every "Verbatim:" string was found in the fetched text — with two exceptions, both flagged below (a fabricated bracketed completion in #6, and one claim in #4 that is not on the page cited).**

## Cross-cutting constraint scan (mechanical, `scan.py`)

| Check | Result |
|---|---|
| Percent sign | **None** in any `text_en`/`text_zh`. |
| Digits | Only in proper nouns: `H-1B` (#2), `Form I-983` (#3), `Form I-9` (#6). No digit is a quantity. |
| Written-out numbers | Only idiomatic `one`, `both`, `first`, `single` / `一`, `两`. No quantity claims. |
| Statistics | **None.** No entry attaches a figure to anything. |

If the lint is literal on `[0-9]`, #2/#3/#6 will fire on visa- and form-names. That is a lint problem, not an entry problem — do not let someone "fix" it by removing `H-1B` or `Form I-9`, which are the only strings that make those entries findable.

**Two places the no-digit rule has already cost real content** (lint-dodge, not compliance): #2's "the figure is set in the rule" hides `at least half of their work time` (8 CFR 214.2(h)(8)(iii)(F)(4), verified), and #5's "a size threshold set in the statute" hides `four or more employees` (NYSDOL, verified). A reader cannot act on either sentence as written. Fix by pointing at the source explicitly, not by leaving a blank.

---

## 1. `us-authorisation-and-sponsorship-are-separate-screens` — KEEP-WITH-EDIT

Source verified verbatim in `ier.txt`: *"Generally, an employer may ask job applicants if they have the legal right to work in the United States and if they will need sponsorship for an employment visa."* and *"An employer may restrict hiring to U.S. citizens only when a law, regulation, executive order, or government contract requires the employer to do so."*

**Overreach — the lead sentence outruns the source.** DOJ says an employer *may ask*. The entry says *"US application forms ask ... as separate questions"* — a claim about what forms actually do, and that the two are separate fields. Nothing in the source supports either. Second unsourced empirical claim: *"Whether the employer sponsors at all is normally a policy fixed before the role was ever advertised."* Third, in `why`: *"The posting almost never states the employer's sponsorship policy"* — an unmeasured frequency.

Replacement `text_en`:
> A US employer may ask whether you have the legal right to work in the United States, and separately whether you will need sponsorship for an employment visa — the Department of Justice confirms both questions are permitted. They are different questions, and where a form asks both, answer each on its own terms rather than collapsing them. The posting usually does not say whether the employer sponsors, so establish that before you invest further. One limit worth knowing: an employer may restrict hiring to US citizens only where a law, regulation, executive order or government contract requires it, and the Immigrant and Employee Rights Section takes complaints about citizenship-status discrimination where that is not the case.

Replacement `text_zh`:
> 美国雇主可以问「你是否有在美国合法工作的权利」，也可以另外再问「你是否需要签证担保」——美国司法部确认这两问都被允许。它们是不同的问题；申请表若两问都列，请分别如实回答，不要合并处理。招聘启事通常不会写明这家雇主是否提供担保，所以在继续投入之前先弄清楚。另有一条界限值得知道：只有在法律、法规、行政命令或政府合同要求时，雇主才可以把招聘限定为美国公民；不属于这些情形的「仅限美国公民」，司法部 Immigrant and Employee Rights Section 受理有关公民身份歧视的投诉。

Replacement `why`: *"The posting usually does not state the employer's sponsorship policy, and a rejection does not tell you which filter caught you."*

zh/en drift: none material. Protected trait: names citizenship status (protected under the INA) — unavoidable here, since the fact *is* a citizenship-discrimination rule; caller's call. Staleness: **low**.

## 2. `us-employer-class-decides-h1b-cap-exposure` — KEEP-WITH-EDIT

Source verified verbatim from the eCFR XML I fetched (`t8.txt`, offset ~320970), at **8 CFR 214.2(h)(8)(iii)(F)** — numbering in the entry is correct for the current text. Confirmed: the (F)(2) affiliation tests, and *"Work performed 'at' the qualifying institution may include work performed in the United States through telework, remote work, or other off-site work."* The registration claim is also supported: (h)(8)(iii)(A)(1) says registration is required *"before a petitioner can file an H-1B cap-subject petition"*.

**Three defects.**

(a) **Misstates the (F)(4) test.** Actual text: *"...will spend at least half of their work time performing job duties **at a qualifying institution**, organization, or entity **and** those job duties directly further an activity that supports or advances one of the fundamental purposes, missions, objectives, or functions..."* The entry drops the "at a qualifying institution" limb and keeps only the mission limb, which makes the test look broader than it is.

(b) **`why` contradicts the regulation the entry itself cites.** `why` says *"Cap-exempt status is a property of the employing organisation, not of the vacancy."* The same paragraph says *"USCIS will focus on the job duties to be performed, rather than where the duties are physically performed"* — and (F)(4) is a duties-and-time test. `text_en` gets this right; `why` gets it wrong.

(c) *"Postings never mention this"* — absolute, unsourced.

Replacement `text_en`:
> Some US employers sit in a statutory class exempt from the H-1B numerical cap: institutions of higher education, nonprofit entities related to or affiliated with them, nonprofit research organisations, and governmental research organisations. Postings rarely mention it, yet it changes what the employer can do and when, because the electronic registration requirement bites only on cap-subject petitions. The regulation also reaches past direct employment: someone employed elsewhere can still be cap-exempt if they spend at least the share of work time the rule specifies performing job duties at a qualifying institution and those duties directly further its higher-education, nonprofit-research or government-research mission — and work performed 'at' the institution may include telework, remote and other off-site work. Look the threshold up in the cited regulation before relying on it. What predicts the possibilities is the kind of organisation and the duties, not whether the advert says sponsorship is available.

Replacement `text_zh`:
> 有一类美国雇主在法规上不受 H-1B 名额上限限制：高等教育机构、与其存在关联或附属关系的非营利实体、非营利研究机构，以及政府研究机构。招聘启事很少提这一点，但它直接决定雇主能做什么、什么时候能做，因为电子登记（抽签）只对受名额限制的申请生效。法规还越过了「直接雇用」这一层：即使受雇于其他单位，只要本人把不低于法规所定份额的工作时间用于在合格机构从事职务，且这些职务直接服务于该机构的高等教育、非营利研究或政府研究使命，也可算作免名额；并且法规明确「在」该机构完成的工作可以包括远程与异地工作。具体门槛请按所引法规原文查证后再据以行动。所以真正能预测可行性的，是雇主属于哪类组织、职务内容为何，而不是启事上有没有写「提供签证担保」。

Replacement `why`: *"Cap exemption turns on the character of the employing organisation and on the duties performed, neither of which the advert describes. Candidates screen adverts for 'sponsorship available' and skip whole categories of employer for whom the annual cap is not the binding constraint."*

zh/en drift: none. Staleness: **medium-high** — this paragraph was renumbered in the recent H-1B modernization rulemaking (older secondary sources still cite `(h)(8)(ii)(F)`), and my citation is pinned to the eCFR `2026-08-01` snapshot. Re-verify the subparagraph letters annually.

## 3. `us-stem-opt-is-an-employer-side-requirement` — KEEP-WITH-EDIT

Source verified verbatim at 8 CFR 214.2(f)(10)(ii)(C)(5) and (C)(6) in `t8.txt`, including the E-Verify "good standing" sentence, the EIN sentence, and the Form I-983 reporting-agreement sentence. Claim and source match exactly.

**One overreach:** *"Adverts never disclose E-Verify enrolment"* — absolute and unsourced, and I would not bet on it being true. Change `never` → `rarely`. Same in zh (`从不披露` → `很少披露`).

Only that word needs changing in both languages. Everything else in this entry survived scrutiny intact — it is the cleanest of the three US regulatory entries.

*Note for the missing-items list:* I tried to verify a public E-Verify participating-employer lookup so the entry could tell the reader how to check. `https://www.e-verify.gov/about-e-verify/e-verify-data/employer-search` returned **HTTP 403 to both WebFetch and curl** on 2026-08-09. **I am therefore not asserting that such a search exists** — do not add it without a successful fetch.

zh/en drift: none. Staleness: **medium** (STEM OPT rules have been subject to litigation and rulemaking).

## 4. `at-will-versus-notice-period-changes-your-start-date` — KEEP-WITH-EDIT (weakest entry; DROP is defensible)

California DIR PDF verified verbatim, including the footer `Termination of Employment (Rev. 1/2011)`: *"Within the State of California, employment may be terminated at the will of either party... Unless the parties have previously agreed to the contrary, there is no notice required to be given by either party."*

**(a) A claim that is not on the page cited.** `text_en` says *"your contract can require longer"*. The cited gov.uk page (`/handing-in-your-notice/giving-notice`, fetched in full) contains only: *"You must give at least a week's notice if you've been in your job for more than a month."*, *"Your contract will tell you whether you need to give notice in writing - otherwise you can do it verbally."*, and the breach sentence. I also fetched the sibling page `/handing-in-your-notice/your-employment-contract`, which says only *"If you want to leave your job, check your employment contract to find out your employer's policy on handing in notice."* **Neither page states that a contract can require longer notice.** Either source it separately or cut the clause.

**(b) Silently truncated "verbatim".** `source_detail` quotes *"You may be in breach of your contract if you do not give enough notice."* The actual sentence continues: *"...or give notice verbally when it should be given in writing."* Restore the full sentence or mark the ellipsis.

**(c) National claim, single-state source.** `text_en` opens *"US employment is at-will by default"* with no scoping, sourced to one state's labour agency. The `unverified` section is honest about this, but the rendered row is not — and the reader sees no source text.

**(d) Unsourced employer-behaviour claims:** *"US employers commonly expect a near-term start date and read a long notice period as a scheduling problem"* and *"the at-will wording in a US offer letter is standard boilerplate rather than a warning sign."* Nothing supports either.

**(e) `why` overstates:** *"promises a start date they cannot legally deliver."* Under the cited page, giving short notice risks **breach of contract**, not legal impossibility — and the statutory floor is short. Fix.

Replacement `text_en`:
> US employment is at-will in the ordinary case — California's labour standards agency states the doctrine plainly: either party may end the relationship at any time and, unless they agreed otherwise, neither owes the other notice. At-will is state law rather than a federal statute, so it is the default rather than a universal rule, and the customary short resignation notice is a norm, not an entitlement. The UK works the other way: gov.uk tells employees they must give at least a week's notice once they have been in the job beyond a short qualifying period, and warns that you may be in breach of your contract if you do not give enough notice or give it verbally when it should be in writing — so check your own contract, which may set the notice you owe. A UK start date is therefore negotiated around a notice period as a matter of course. If you are applying into both markets, state your availability against the right default in each.

Replacement `text_zh`:
> 美国的雇佣在通常情况下是「随意雇佣」（at-will）——加州劳工标准执行部门的官方表述是：任何一方都可以随时结束雇佣关系，除非双方另有约定，互不负提前通知义务。at-will 属于各州法而非联邦成文法，因此它是默认规则、不是放之全国皆准的铁律；惯例上的短期离职通知是习惯，不是法定权利。英国方向相反：gov.uk 告诉雇员，在职超过一段较短的资格期后，至少须提前一周通知，并提醒通知不足、或本应书面却口头通知，都可能构成违约——所以要查自己的合同，看它约定了多少通知期。因此英国的到岗日期天然是围绕通知期谈的。若同时投这两个市场，请按各自的默认规则分别声明你的可到岗时间。

If the table's rule is "no entry may state a national practice from a single-state source", then **DROP the US half and keep a UK-notice-only entry** — the UK half is fully sourced.

zh/en drift: none material (both carried the same defects). Staleness: **medium** on the UK side; the entry's own `unverified` item 6 correctly flags that UK employment law is in flux.

## 5. `us-pay-range-in-a-posting-is-jurisdictional-not-cultural` — KEEP-WITH-EDIT

Both sources verified verbatim. Colorado (`cdle.txt`): *"Part 2, referred to by the Division as 'Pay Transparency,' requires transparency in pay and job opportunities. Specifically, it requires employers to disclose compensation in all job postings and notices, both internal and public. This disclosure must include information about benefits and how and when to apply."* New York: *"New York State businesses with four or more employees"*, the commission sentence and the anti-retaliation sentence all present. The *"both states run complaint channels"* claim also verified — CDLE *"The Division investigates complaints against employers..."*; NYSDOL *"Any current, prospective, or potential employee or applicant who claims to have experienced a violation of this law can file a complaint with New York State Department of Labor."*

**(a) URL redirects.** `https://cdle.colorado.gov/equalpaytransparency` 301s to `https://cdle.colorado.gov/dlss/labor-laws-by-topic/equal-pay-for-equal-work-act`. Not a homepage redirect and the content is correct — but cite the destination URL so the row does not rot.

**(b) zh is stronger than en.** en: *"a compensation range for advertised job, promotion and transfer opportunities"*. zh: *"在**所有对外发布的**职位、晋升和调岗机会中列出薪酬区间"*. The source says *"designated job opportunities, promotions, and transfers"* — `所有` (all) is an escalation the source does not license. Change `在所有对外发布的职位、晋升和调岗机会中` → `在其对外发布的相关职位、晋升和调岗机会中`.

**(c) Both languages drop a required element** of the NY rule: employers must *"provide job descriptions and list compensation ranges"*. Add "a job description and" before "a compensation range" in en, and `职位描述与` in zh.

**(d)** *"mostly a question of which state's law reaches the role"* — unsourced causal claim, but hedged with "mostly". Acceptable; do not let it drift to "only".

Staleness: **high** — this is the entry most likely to be wrong within a year. State legislatures add and amend posting-disclosure laws every session. Keep the entry's existing discipline of naming only the two states actually fetched, and add a re-verify date.

## 6. `us-you-choose-your-form-i9-documents` — KEEP-WITH-EDIT (contains the entry's clearest source-integrity defect)

Most quotes verified verbatim in `ier.txt`, including the List A / List B / List C sentence, *"During both initial verification and reverification, a worker may choose which documentation to present from the List of Acceptable Documents"*, and the full "Employers of any size" sentence.

**(a) FABRICATED QUOTE COMPLETION — must fix.** The entry renders the source as:

> `"Employers can't specify which documents they" [require]`

The actual sentence in the fetched page is:

> *"Employers can't specify which documents they **will accept from a worker** and should not prevent an individual from working because of a document's future expiration date."*

The bracketed `[require]` is not a clarifying insertion — it is a word nobody wrote, closing a quote that was cut mid-clause. It appears **twice**: in this convention's `source_detail` and again in the `application_artifacts` prose. Replace both with the full sentence. This is the single thing in the entry I would block a ship on, because the table is rendered to a reader with no source text beside it and the quotation marks are the only warranty they get.

**(b) Overreach — the dropped qualifier is load-bearing.** `text_en` and `text_zh` both state the prohibition unconditionally. The source conditions it: *"employers are not allowed to, **on the basis of citizenship, immigration status, or national origin**, request more or different documents..."* That basis is exactly what makes it an IER matter, and a reader who omits it from a complaint has no complaint. Both languages drop it identically, so there is no zh/en drift — just a shared defect.

Replacement for the last two sentences of `text_en`:
> Employers of any size are barred from unfair documentary practices — on the basis of citizenship, immigration status or national origin, requesting more or different documents than are required, rejecting documents that reasonably appear genuine, or specifying certain documents over others. None of this appears in a posting, and where a recruiter or onboarding team narrows you to one named document on such a basis, that is what the Immigrant and Employee Rights Section takes complaints about.

Replacement for the corresponding zh:
> 任何规模的雇主都不得实施「不当证件要求」——即基于公民身份、移民身份或原属国，索取超出规定数量或种类的证件、拒收看起来合理真实的证件，或指定必须使用某些特定证件。这些内容不会出现在招聘启事里；招聘人员或入职团队若基于上述事由把你限定在某一份指定证件上，正是司法部 Immigrant and Employee Rights Section 受理投诉的情形。

Staleness: **low**.

## 7. `uk-check-the-public-sponsor-register-before-applying` — KEEP

Both sources verified verbatim, including the register page's publisher (UK Visas and Immigration), *"Published 13 November 2013"* and *"Last updated 7 August 2026"* — exactly as the entry states — and all four Skilled Worker eligibility bullets plus *"You must have a confirmed job offer before you apply for your visa."* No digits, no drift, no overreach; the refusal to state a salary figure and the instruction to look it up on gov.uk is the correct pattern for a fact that changes yearly.

## 8. `uk-right-to-work-check-is-universal-and-you-pick-the-evidence` — KEEP-WITH-EDIT (small)

All four quotes verified verbatim across both gov.uk pages.

**One scoping fix.** *"You can choose which option you use. Your employer cannot reject your application because you gave them an eligible immigration document instead of a share code, for example."* sits on `prove-right-to-work` under the heading **"If you're not a British or Irish citizen"**. British and Irish citizens have a different route entirely (passport or passport card; failing that, a birth/adoption/naturalisation certificate *plus* an official letter showing name and National Insurance number). As written, the entry states the choice universally. I specifically checked for an eVisa/BRP "online-only" caveat on that page and found none — the two options are presented as genuinely interchangeable for that group, so the claim is sound once scoped.

Change in `text_en`: *"but if you are not a British or Irish citizen the choice of evidence is yours: gov.uk states plainly..."*
Change in `text_zh`: `但若你不是英国或爱尔兰公民，选择用哪种证明是你的权利：gov.uk 明确写明……`

Also confirmed: the employer-side page does **not** specify timing relative to the start date beyond "before you employ them", so *"The check sits before the first day"* is a fair restatement — keep it.

Staleness: **medium** — the mechanics of proving (digital status, share codes) have been moving.

## 9. `uk-civil-service-scores-named-behaviours-not-cover-letters` — KEEP-WITH-EDIT (small)

Every quoted string verified verbatim in `csb.txt` and on the Success Profiles page, including the nine behaviour names, the STAR sentence, the assessment-method list and the reasonable-adjustments sentence. Page updated 29 January 2025, as stated.

**(a) A load-bearing claim is asserted in `text_en` but absent from `source_detail`** — that the job description names which behaviours are assessed and by which method. It *is* on the page; add these two verified sentences to `source_detail` so the row is self-defending: *"Read the job description carefully to see which behaviours are required for the job you are applying for."* and *"The job description will outline the elements required for the role and the selection method(s) that will be used."*

**(b) Inference stated as fact.** *"A general letter about why the organisation appeals to you scores nothing"* / `得不到分数`. The source never says this. Soften to: *"A general letter about why the organisation appeals to you does not evidence any named behaviour, and each one is assessed on its own evidence"* / `泛泛地写一封「为什么想加入贵机构」的求职信，无法为任何一项被点名的行为提供证据，而每一项都按其自身证据单独考核。`

**(c) Small conditional dropped.** The page says *"**If** a recruiting manager wishes to assess behaviours they will review the Civil Service Behaviours..."* — behaviours are not guaranteed to be assessed at all. `text_en`'s "the recruiting manager picks a selection of behaviours" reads as though they always do. Add "where behaviours are assessed,".

zh/en drift: none. Staleness: **low-medium**.

## 10. `uk-nhs-shortlisting-is-scored-against-the-person-specification` — KEEP-WITH-EDIT (substantive)

All three sources fetched; every quoted string verified verbatim, including the NHSBSA PDF (9 pages, HTTP 200): *"Important: Do not include personal information that could be used to identify you such as your name or contact details."* and *"'Qualifications' and 'Experience' are mandatory essential criteria."*

**(a) The entry conflates two different sections of the NHS Jobs form, and the conflation could actively mislead.** The fetched pages describe them as distinct:

- **"Supporting information"** (`nhs.txt`, jobs.nhs.uk): free text — *"The 'supporting information' section is your opportunity to sell yourself therefore make sure you use it to your advantage. You can include any information here that has not been covered elsewhere on the form."* **No anonymity instruction appears anywhere on that page.**
- **"Essential and desirable criteria"** (`nhsev.txt`, the NHSBSA guide): a separate section with per-criterion boxes — *"In the Essential criteria box, enter the details. In the Desirable criteria box, enter the details."* — and it is *this* section that carries the do-not-identify-yourself warning.

The entry attaches the criterion-box structure and the anonymity rule to the supporting-information section. A reader following it would anonymise and de-narrativise a box that NHS Jobs itself describes as their chance to sell themselves. Separate the two.

**(b) "Scored" is not sourced.** `text_en` says shortlisting *"is scored"*; `why` says the supporting section is *"graded criterion by criterion"*; `text_zh` says `逐条打分`. The source says *"judging how well your application matches"* and *"The applicants who closely match the person specification will be the ones that are shortlisted"*. Use "assessed against" / `对照…逐条评估`.

Replacement for the second half of `text_en` (from "The personal information..."):
> The personal information and monitoring sections are not used for shortlisting. Where the employer uses the essential-and-desirable-criteria section, evidence goes in criterion by criterion in separate boxes, and the official guide instructs applicants not to include personal information that could identify them, such as their name or contact details, in those boxes — so a signed narrative letter is the wrong artifact there. Write to the specification, in its order, criterion by criterion.

Corresponding `text_zh`:
> personal information 与 monitoring information 两栏不用于初筛。若雇主启用了「必备与加分条件」栏，佐证是按条目分框填写的，官方指南要求申请人不要在这些框内填入可用于识别本人身份的个人信息，例如姓名或联系方式——因此在那里放一封署名的叙述式求职信是错误的形式。请按人员规格的顺序，逐条对应地撰写。

And change the opening `NHS shortlisting is scored against` → `NHS shortlisting is assessed against`; zh `逐条打分的` → `逐条对照评估的`.

Staleness: **medium-high** on the mechanics — the NHSBSA guide is a May 2022 user guide, and jobs.nhs.uk still renders a **BETA** banner (seen in `nhs.txt`). The `applies_when` correctly scopes to NHS Jobs; keep that scoping, because many trusts recruit through other systems.

---

## Also affecting the prose fields (not conventions, but they ship)

- **`application_artifacts` carries the same fabricated `[require]` completion** as #6. Fix in both places.
- **`application_artifacts` repeats the NHS conflation**, calling the artifact *"the NHS Jobs application form with its supporting-information / supporting-evidence sections"* and then applying the anonymity rule across both. Same fix as #10.
- `interview_shape`'s UK Civil Service paragraph is fully verified against `csb.txt`, including the assessment-method list, the SJT sentence and *"Your behaviours may be assessed alongside other elements of the Success Profile."* Its claim that *"the job description tells you which will apply"* is now confirmed verbatim — add the sentence quoted in 9(a).
- The `unverified` section is unusually honest and I found no place where it overclaims. **One correction, though:** item 5 says *"US salary-history bans... I did not verify an official source for any of them."* The entry's own Colorado source contains one, verbatim in `cdle.txt` — the Act *"prohibits employers from (1) asking about an applicant's pay history or relying on pay history to determine an employee's wage rate; (2) discriminating or retaliating against a prospective employee for not disclosing their pay history"*. That is a sourced, actionable fact already paid for.

## Important and missing

1. **UK Civil Service Nationality Rules — the biggest gap.** The entry sends a job-seeker deep into Civil Service application mechanics (convention #9, plus `application_artifacts` and `interview_shape`) and never mentions that there is a nationality eligibility gate in front of all of it. Verified: gov.uk, *"Civil Service Nationality Rules"*, `https://www.gov.uk/government/publications/nationality-rules`, publisher Civil Service, last updated 8 August 2023, retrieved 2026-08-09 — *"You can apply for any job in the Civil Service as long as you are a UK national or have dual nationality with one part being British"*; most posts are also open to Commonwealth citizens and EEA nationals; *"The remainder, which require special allegiance to the state, are reserved for UK nationals."* Caveat for the caller: this names nationality, a protected trait, so it may collide with the table's constraints — but it is a published statutory-style eligibility gate, not a preference, and omitting it costs the reader more than naming it does.
2. **Colorado's pay-history ban** (verbatim above, from a page the entry already fetched). Cheap to add, sits naturally beside #5, and closes `unverified` item 5 for one state.
3. **The two suppressed thresholds** — `at least half of their work time` (#2) and `four or more employees` (#5). Both are verified and both are currently unusable as written. If the no-digit rule genuinely forbids them in `text_*`, the text must at least tell the reader the exact place to read the number, rather than gesturing at "the figure is set in the rule".

**Could not source:** a public E-Verify participating-employer lookup (`e-verify.gov` returned HTTP 403 to both WebFetch and curl, 2026-08-09). I make no claim that one exists, and #3 should not be edited to reference one.