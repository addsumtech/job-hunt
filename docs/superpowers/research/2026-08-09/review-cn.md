# Adversarial review — market `cn`

**Verification method.** Every `published` URL was fetched on **2026-08-09** (curl, desktop UA) and the claimed verbatim strings grepped against extracted text. Local copies: `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/src/*.txt`, 20-F at `.../scratchpad/bz20f.txt`.

**All 13 cited URLs return HTTP 200 and none redirect to a homepage.** Publisher and title match the citation in every case. The SEC filing is real: `data.sec.gov/submissions/CIK0001842827.json` lists form 20-F, accession `0001104659-26-050959`, primary doc `bz-20251231x20f.htm`, filed 2026-04-29, report date 2025-12-31 — exactly as cited. Every 20-F quote in the entry is verbatim. That is a genuinely strong sourcing baseline; the findings below are about the gap between what the pages say and what the shipped text claims.

---

## 1. `cn-boss-profile-is-the-screen` — KEEP-WITH-EDIT

Constraints clean (no digit, no percent, no protected trait). Source solid: all three 20-F quotes verbatim, and "deliver resumes upon mutual consent" (which I found separately) backs the "both sides agree" wording.

**zh/en drift, and an unsourced terminology claim.** `text_zh` says 「平台自己的说法是「迷你简历」」 — asserting 迷你简历 is BOSS直聘's *own Chinese term*. The only source is the English phrase "mini resume" in an SEC filing. `迷你简历` appears **0 times** in the zhipin.com homepage HTML I fetched. The platform's own Chinese help page is titled 「BOSS直聘如何填写/修改**在线简历**」 (`https://www.zhipin.com/help/89e3b4ba1117aca61XY~.html` — I could not read it, it served a 安全验证 captcha page on 2026-08-09). So the zh version turns an English SEC coinage into a claimed Chinese product term, and adjacent evidence points the other way. Cut it.

```
text_en: On BOSS直聘 the recruiter does not see your CV file first. What they see is the
structured profile you filled in at registration — the operator's own SEC filing calls it a
mini resume — and your full CV and contact details reach them only on mutual consent inside
the chat. Treat those profile fields as the actual screening document and write them for a
reader who will decide from them alone.

text_zh: 在 BOSS 直聘上，招聘方一开始看不到你的简历附件，只能看到你注册时填写的在线简历；完整简历和
联系方式要等双方在聊天中互相同意后才会送达。所以真正被筛的是在线资料的那几栏，要按「对方只看这些就下
判断」来写。
```

---

## 2. `cn-salary-expectation-declared-up-front` — KEEP-WITH-EDIT

Constraints clean. The registration quote is verbatim (it sits inside the identity-verification passage, not a product description, but it does say "required").

**Overreach — the load-bearing half of this entry is not in the source.** "that figure feeds the matching that decides which roles you are shown and who is shown you" / 「这个数字会进入匹配推荐」. I searched the full 907k-character filing: `salary expectation` occurs **exactly once**, nowhere near any recommendation text. The filing's own named recommendation inputs are *"career development goals, occupation inclination, job position preferences of job seekers and the recruiting needs of enterprises"* and behavioural signals *"candidate and job post views, chat initiation, mutual consent and interview feedback"*. Salary appears in neither list. The `source_detail` glosses this ("matching … driven by two-way recommendations over job-seeker and job-post profile data") in a way that reads as support and is not. The closing line "it is filtering you silently from the moment you sign up" is the same inference restated as the payoff.

```
text_en: BOSS直聘 requires a salary expectation as part of the information you supply when you
register — before you have spoken to anyone. There is no holding the number back until an
offer conversation the way an apply-button market allows. Settle on it deliberately before you
sign up, and treat it as a figure the other side may already have when a chat opens.

text_zh: BOSS 直聘在注册环节就要求填写期望薪资——那时你还没和任何人聊过。这里没有「等谈 offer 时再说」
的空间。所以注册前就要把这个数想清楚，并且默认对方在开聊时可能已经看到了它。
```

---

## 3. `cn-campus-track-is-cohort-gated-and-early` — KEEP-WITH-EDIT (the strongest claim is refuted by the entry's own other source)

Constraints: clean, except zh 「两条独立的通道」 is a written-out number.

Source integrity, two problems:
- `ncss.cn/ncss/zt/jqqh.shtml` loads but is a **Vue SPA with no rendered prose**. The entire evidentiary content is the title 「2026届高校毕业生金秋启航校园招聘月」 plus a hardcoded template string `时间 2025年{{item.kssj}}-{{item.jssj}}` in the offline-events block. The autumn-2025-for-the-2026-cohort claim is *inferable* from that, but the page does not state it, and `source_detail` presents it as though it does.
- The 20-F "fall/spring recruitment season" quotes both describe **Kanzhun's own CSR events** (Spirited Recruitment Festival), not market structure. Adjacent, not direct.

**Overreach — refuted.** "A 校招 posting … is reserved for its cohort" / 「它只面向本届开放」 and 「没有「补投校招」这一说」 are contradicted by pages this very entry set already cites:
- `ncss.cn/ncss/zt/yjbyszc.shtml`: 「国有企业2026届校园招聘…**许多国有企业同时面向26届和25届离校未就业高校毕业生**。今年中国航天科技集团2026校招提前批招聘就面向26届高校毕业生和25届未就业高校毕业生。」 — and it names 「企业秋招春招**补录**」 as a job-search window, which is precisely the "late 校招" the entry says does not exist.
- MOE 教就业厅函〔2026〕8号 对象范围: 「2026届普通高校毕业生，**2024、2025届离校未就业毕业生**等重点群体」.

The zh is *stronger* than the en here, so the drift compounds the error. The 51job observations are fine — I confirmed the exact ad titles 「中科芯2027届校园招聘」 and 「龙湖集团2027届仕官生校园招聘」 (also 「芯原股份2027届校园招聘」) and 19 `campus.51job.com` links in the homepage HTML on 2026-08-09.

**Staleness: high** — cohort year rolls annually; the 51job evidence is a same-day snapshot.

```
text_en: 校招 is a separate track from 社招 and is labelled by graduation cohort, and it opens
long before that cohort graduates — autumn campaigns for a cohort run in the academic year
before its graduation, with a spring round after. So check which cohort a posting names, not
just how junior it looks. Cohort labels are not always exclusive: some employers, state-owned
ones in particular, open a cohort's campaign to the previous cohort's graduates who are still
unplaced, and supplementary rounds happen. Read the eligibility line rather than assuming
either way.

text_zh: 校招和社招是彼此独立的通道，校招按「届」标注，而且开得很早：某一届的秋招在其毕业前的那个学年
就已经启动，之后还有春招。所以要看岗位写的是哪一届，而不只是看它「初不初级」。届别限制并非一律排他：
有些用人单位（尤其国企）会让某届校招同时面向上一届离校未就业的毕业生，也存在补录轮次。别自行假设，
直接读岗位的资格条件那一行。
```

---

## 4. `cn-fresh-graduate-status-is-administrative` — KEEP-WITH-EDIT

Constraints clean. Sources verify well: the NCSS page carries 「近两年多省放宽应届生身份限制。如明确将应届生认定范围从"毕业当年"拓展至"离校2年内未就业"，取消社保缴纳等门槛」, 「有过工作经历和缴纳社保情况不再作为应届毕业生的否定项」, and exactly the nine regions listed. The 工人日报/新华网 quote 「不对高校毕业生是否有工作经历、缴纳社保作限制」 is verbatim.

**Overreach — a national baseline is being written out of existence.** "Each province sets its own definition" / 「各省自行规定」 is stronger than the source, which quotes a *central* rule on the same page: 《中央机关及其直属机构2025年度考试录用公务员报考指南》, 「国家规定择业期为**二年**」. Provinces adjust *on top of* that. The same page hedges 「**部分**省份规定不受…限制」, which the zh 「各省自行规定」 flattens. Relatedly, the entry directs the reader to the provincial 人社 authority, but its own `applies_when` includes 公务员 — where the governing definition comes from the 报考指南, not a 人社 notice.

**Staleness: high, by construction** — the entry's whole point is that this is moving.

```
text_en: 应届生 is an administrative status with eligibility rules attached, not a way of
describing yourself. There is a central baseline — the civil-service recruitment guide treats
graduates still within the official post-graduation job-seeking window as 应届 — and provinces
have been adjusting their own definitions on top of it, several of them recently dropping
prior work experience and social-insurance contributions as disqualifiers. Whole categories of
posting are open only to people who hold the status, so check the rule that governs the
specific intake you are applying to — the announcement's own eligibility text, or the current
notice from the relevant 人社 authority — rather than assuming you do or do not qualify.

text_zh: 「应届生」是一个有认定标准的行政身份，不是一句自我描述。全国层面有基准口径（公务员录用报考
指南把仍在国家规定择业期内的毕业生按应届对待），各省又在此之上各自调整，近年已有多地不再把有过工作
经历、缴过社保作为否定项。由于有大量岗位只面向具备该身份的人开放，别凭印象判断自己有没有：以你所投的
那次招录的资格条款、或相关人社部门现行发布的通知为准。
```

---

## 5. `cn-three-party-agreement-is-not-the-employment-contract` — KEEP

All six quoted strings verbatim across both sources; constraints clean; zh and en aligned; hedging correct ("you *may* owe"). One correction to `source_detail` only, not to shipped text: the 学职平台 page's own footer reads 主办单位：**教育部学生服务与素质发展中心**, not 全国高等学校学生信息咨询与就业指导中心, and the article is 来源：微信公众号大学生就业资讯（ID：ncssweb）**综合整理** — an official-platform explainer, not a primary instrument. Worth saying, since the entry leans on it for the liquidated-damages point.

---

## 6. `cn-state-organised-recruitment-channel` — KEEP-WITH-EDIT

**Constraint violation:** `text_en` contains **"51job"** — digits `5` and `1`. (`text_zh` says 前程无忧, no digit — so the two versions also diverge on this.)

The MOE notice verifies completely: 教就业厅函〔2026〕8号, eight named 办公厅, signed 2026年5月6日, published 2026-05-22, 「加强个人信息保护，杜绝求职者信息泄露」 and 「招转培」 both verbatim. Minor: the notice names **nine** platforms; the entry lists eight, omitting 全国一体化退役军人网上服务平台（"退役军人服务"APP）.

**Overreach, three counts:**
1. Framing it as a state/SOE channel misdescribes the document. Its opening rationale is 「充分发挥国有企业就业引领作用**和民营企业在稳就业中的重要作用**」, and it tasks 工商联 with 「引导广大民营企业积极参与…组织行业头部企业在"国聘行动"平台发布更多岗位资源」.
2. "are directed to publish" / 「**被要求**把岗位发布到那里」 overstates the verbs actually used — 鼓励、引导、组织动员; 国资委 is told to 「**指导**所监管企业充分挖掘岗位资源」. The zh 「被要求」 is stronger than the en, so this is drift as well as overreach.
3. "Those postings do not necessarily also appear on the commercial boards" is nowhere in the notice — pure inference presented as fact in shipped text. So is the `why` field's "a large employer segment concentrates" there.

**Staleness: high** — annual reissue, per-cycle platform list, 活动时间 2026年5月—2026年12月.

```
text_en: Alongside the commercial apps there is a state-organised recruitment channel: an
inter-ministry campaign, reissued each cycle, that names its own official platforms and
organises employers — state-owned and private both — to publish vacancies there. Check whether
the current cycle's platforms carry anything your usual apps do not, because each cycle's
notice names them, so the list is lookup-able rather than guesswork.

text_zh: 在商业招聘 App 之外，还有一条国家组织的招聘通道：由多部门联合开展、按年度重新发文，指定自己的
官方招聘平台，并组织用人单位（国企和民企都在内）在那里发布岗位。值得去当期指定的平台上核对一下，看有
没有你常用 App 上没有的岗位——每年度的通知里都列明了平台名单，可以直接查到，不用靠猜。
```

---

## 7. `cn-posting-salary-is-not-a-defined-quantity` — KEEP-WITH-EDIT

Constraints clean. Both sources verify: 第四条's six components including 奖金, the promulgation line, and the Wuhan page's three-branch rule.

**Source-fit problem.** 《关于工资总额组成的规定》 第二条 scopes itself explicitly: 「在**计划、统计、会计**上有关工资总额范围的计算，均应遵守本规定」. It is a statistics-bureau accounting definition and creates no entitlement. Using it to open a paragraph about what an employer contractually owes is a category slip — and the sentence "Bonus does count as part of total wages" does no work for the reader anyway.

**Overreach.** The Wuhan page's established-practice branch reads 「有发放惯例——**可主张**发」 with 「法院会结合多年发放惯例综合判断」. The entry converts 可主张 (you can assert a claim, weighed by a court) into 「才成为**必须履行**的约定」 / "it becomes owed". Also worth labelling in `source_detail`: this is a municipal-portal explainer sourced to 湖北省总工会 / 武汉发布 — official-adjacent commentary on 司法实践, not law.

**Credit where due:** `unverified` item 9 is correct. I fetched `https://www.court.gov.cn/shenpan-xiangqing-364671.html` on 2026-08-09 and it serves the SPC error page 「哎呀,出错了！ … 抱歉，找不到您要的页面」. (Technically a soft-404 — HTTP 200 with an error body — but the entry's decision to drop the citation was right.)

```
text_en: A single monthly or annual figure in a posting is not a defined quantity. Chinese law
does not compel an employer to pay a year-end bonus at all; it becomes enforceable where the
contract, the offer or lawfully adopted company rules set out its conditions and amount, and
where an employer has paid one consistently year after year a claim can be argued on that
established practice. So the question to settle before you accept is not how much, but which
parts are contractual and which are the employer's discretion, and where each is written down.

text_zh: 招聘信息上那个月薪或年薪数字，并不是一个有明确定义的量。法律并不强制用人单位必须发年终奖；
只有当劳动合同、offer 或依法制定的规章制度写明了发放条件和金额时，它才是可强制执行的约定；若单位历年
稳定发放，可以据既成惯例主张。所以接 offer 前要问清的不是「多少钱」，而是「哪些是约定必付、哪些是公司
自主决定，分别写在哪里」。
```

---

## 8. `cn-what-an-employer-may-ask-and-what-truthfulness-costs` — KEEP-WITH-EDIT

Constraints clean, and notably well handled: PIPL 第二十八条 enumerates 宗教信仰、特定身份、医疗健康 as 敏感个人信息, and the entry deliberately refers to the *category* without naming any protected trait. Correct call.

All quotes verbatim. The SAMR copy is the current 2012-amended text (「根据2012年12月28日…修正」). Beijing item 78 verbatim including 「提供虚假学历证书、假身份证、假护照等个人重要证件」.

**Scope slip that reaches the shipped text.** Item 78 answers a narrow question — 「用人单位依据《劳动合同法》第三十九条第一项的规定解除劳动合同的，如何处理？」 — i.e. **dismissal during 试用期 for 不符合录用条件**, with fake credentials as one listed situation. The entry's "fabricated credentials are treated as grounds to act against you" is both broader and vaguer than that, and — the real problem — `source_detail` carries a correct Beijing-only SCOPE NOTE that **the job-seeker will never see**, while `text_en`/`text_zh` carry no locality marker at all. Only the final clause needs changing.

Nit for `source_detail`: 劳动合同法 cited via SAMR (a market-regulation agency) is a real official page but an odd canonical home; npc.gov.cn or gov.cn would be the better citation on a page rendered to a job-seeker.

```
text_en (final sentence only): On the other side, a material misstatement about something
job-relevant is not harmless polish: a contract entered into by deception can be held invalid
nationwide, and fake diplomas or identity documents are listed in Beijing's court-and-
arbitration guidance among the grounds for dismissing someone during probation for not meeting
the hiring conditions.

text_zh (final sentence only): 另一面是，在与岗位相关的事项上作实质性虚假陈述不是「美化」：以欺诈手段
订立的劳动合同可被认定无效（全国适用），而伪造学历、身份证件等，在北京法院与仲裁的裁审口径中被列为
试用期「不符合录用条件」解除的情形之一。
```

---

## 9. `cn-hukou-application-is-filed-by-the-employer` — KEEP-WITH-EDIT (most defective entry; do not ship as written)

Constraints clean. The Shanghai page loads and is the right document.

**(a) Unsourced concrete detail.** "only employers meeting that city's own conditions, **such as being locally registered by the cut-off the city sets**, can file at all" / 「例如在其设定的截止日前已在本地注册登记」. Nothing in the fetched 沪教委学〔2025〕15号 states any registration cut-off. The employer-eligibility conditions live in 附件3 《…申请本市户籍办法》, which the entry admits it did not retrieve — and I could not source it either. This is a checkable-sounding specific with zero provenance. It must go.

**(b) Overreach.** "Where a city runs a settlement scheme … the application is filed by the employer" is a cross-city rule verified for Shanghai only. Again the honest scope note is in `source_detail`, invisible to the reader.

**(c) Staleness — already stale, today.** The cited 2025 notice is superseded. 沪教委学〔2026〕13号 exists (attached as 附件1 at `https://yjs.shou.edu.cn/2026/0513/c18626a352701/page.htm`, retrieved 2026-08-09). Per 上海交通大学电气工程学院 (`https://see.sjtu.edu.cn/xsgz_tzgg/2395.html`, retrieved 2026-08-09) the 2026 window ran **2026年5月11日至2026年7月3日**, extended to 2026年12月31日 for doctoral graduates — so for non-PhD graduates this cycle has already closed. A table rendered today must not point at the 2025 document.

**(d) Three sourced facts the entry missed, two of them more useful than what it has.** From the SJTU page: 「用人单位是非上海生源毕业生进沪就业申请落户的**申请主体**」 — a far more direct statement of the mechanic than the 2025 wording the entry strains; and 「须由用人单位**一次性**提交申请材料。**如未通过落户申请，不再受理由其他用人单位提交的申请材料**」 — one filing per graduate per cycle, no retry through another employer. From the 2025 notice itself, unused: 「用人单位在与高校毕业生签订就业协议时…应**如实告知**本单位是否具备为非上海生源毕业生申请本市户籍的资格」 and 「用人单位**不得**在协议中规定"毕业生如未能办妥落户手续则与其解除就业协议"」. The entry frames asking as "a fair and answerable question" — in Shanghai it is a disclosure the employer owes you.

Transcription nit: the quoted sentence in `source_detail` drops the leading 「各」 from 「**各**用人单位应按照…」 while presented as verbatim.

```
text_en: Where a city runs a settlement (落户) scheme for fresh graduates, the applying party
can be the employer rather than you — in Shanghai it is, the employer files the materials and
only an employer that itself qualifies under that year's municipal rules can file at all.
Whether a role can actually carry 落户 is therefore a fact about that specific employer and
that year's scheme, with its own application window; in Shanghai the employer must tell you
truthfully, when you sign the 就业协议, whether it qualifies. Ask before accepting, and read
the operative year's municipal notice — these are city-by-city, reissued annually, and not a
nationwide entitlement.

text_zh: 在设有应届生落户通道的城市，申请主体可能是用人单位而不是你本人——上海就是如此：材料由单位提交，
且只有本身符合该市当年规定条件的单位才有申报资格。所以一个岗位到底能不能落户，取决于这家单位和该市
当年的政策，还有各自的申请受理期；在上海，单位在与你签就业协议时须如实告知本单位是否具备该资格。
接受 offer 前就问，并以当年度的市级通知为准——此类政策按城市制定、逐年重新发布，全国没有统一待遇。
```

---

## 10. `cn-internship-is-usually-not-an-employment-relationship` — KEEP

Constraints clean; hedging ("generally" / 「一般」) matches in both languages; both quotes verbatim; the SOURCING CAVEAT is accurate and appropriately humble.

One precision note for `source_detail` (not shipped text): the statutory sentence quoted covers 「在校生利用**业余时间勤工助学**」 — spare-time work-study — which is narrower than 实习 generally. In the article, the broad proposition rests on lawyer and judge commentary (赵琰; 北京三中院 龚勇超) plus two contrasting court outcomes, not on that sentence. Also, the same article notes that for 在校实习 the host 「单位仍须承担安全保障义务，学校负连带责任」 — so "the statute will not fill those gaps" is very slightly overstated; there is a floor, it just isn't the 劳动合同 one.

---

## Notes on the free-text fields (these ship too)

- `application_artifacts` §3 asserts "an official verification endpoint at wq.ncss.cn". Both `wq.ncss.cn` and `dj.ncss.cn` are live and both serve 全国高校毕业生毕业去向登记系统 (fetched 2026-08-09), but only `wq.ncss.cn` is named in the MOE announcement, and "verification endpoint" is not language any source uses. Restate or cut.
- `interview_shape` and `unverified` are honest and I found no fabrication in them. The 20-F does capture "interview feedback" as a signal; 第十九条 does cap probation; the SPC 404 is real; the zhipin 海归 channel is real (`<a class="nav-overseas-new" href="https://www.zhipin.com/returnee_jobs/">海归</a>` in the header nav).

---

## IMPORTANT AND MISSING

1. **劳动合同法 第九条 — the single biggest gap.** 「用人单位招用劳动者，不得扣押劳动者的居民身份证和其他证件，不得要求劳动者提供担保或者以其他名义向劳动者收取财物。」 China-wide, invisible on any posting, and it is the exact legal hook for the 「招转培」 fraud pattern the entry already flags. A job-seeker being asked for their 身份证原件 or a deposit needs this line and the table does not have it.
2. **The 第八条 duty running the other way.** The entry cites 第八条 but only the half that binds the candidate. The same article obliges the employer to 如实告知 工作内容、工作条件、工作地点、职业危害、安全生产状况、劳动报酬 and 劳动者要求了解的其他情况 — i.e. you may ask, and they must answer honestly. Shipping only the candidate-side duty is a slanted reading of a sentence the entry has already quoted in full.
3. **The 国聘行动 notice's ban on certain screening conditions**, sitting unused in a document the entry already cites: 「不得将毕业院校、国（境）外学习经历、学习方式（全日制和非全日制）、本单位实习期限等作为限制条件。」 Directly actionable for this reader. Scope it honestly — it is an instruction to participants in that campaign, not a market-wide prohibition.
4. **The one-shot 落户 filing rule** (Shanghai, sourced above): a failed employer filing cannot be re-submitted by a different employer in the same cycle. Higher-stakes than anything currently in entry 9.
5. **劳动合同法 第十条** — a written 劳动合同 must be concluded within one month of work starting. Pairs with the internship entry and gives the reader a concrete date to watch after joining.