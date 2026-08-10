# Adversarial review — market `nl_weu`

All ten sources fetched 2026-08-09. Every URL in the entry loads; none 404s or redirects to a homepage. Verbatim quotes are almost all exact — the failures are in what the entries *build on top of* the quotes.

---

## 1. `nl-weu-recognised-sponsor-gate` — **KEEP-WITH-EDIT**

**Source: verified.** `https://ind.nl/en/residence-permits/work/highly-skilled-migrant` returns verbatim "Only an employer recognised by the IND can apply for your permit." `https://ind.nl/en/about-us/background-articles/national-highly-skilled-migrant-scheme` returns verbatim "The future employer does this for the highly skilled migrant. Only companies recognised by the IND can submit such an application." The Work register page returns verbatim "You can use this register to check if the organisation has been recognised by the IND as a sponsor" and "The public registers are updated once a month", and it does display KvK numbers next to names (e.g. "Alexia Kliniek Echt B.V." / 17214152), so the Chamber-of-Commerce claim holds.

**Attribution slip:** that verbatim sentence is attributed in `source_detail` to *both* register URLs. The landing page `https://ind.nl/en/public-register-recognised-sponsors` actually reads "You can use this register to check if **a company, school or organisation** has been recognised by the IND as a sponsor." Attribute the quote to the Work register page only.

**Overreach 1 (material).** The opening generalises past what the sources support: "For a Netherlands role that needs a work-related residence permit, the deciding factor is the employer, not you." This is falsified by another work-related IND permit. `https://ind.nl/en/residence-permits/work/residence-permit-for-orientation-year` (fetched 2026-08-09): the applicant submits the application themselves, and "Your employer does not need a work permit (in Dutch: *tewerkstellingsvergunning* or TWV). You may also work freely as an independent entrepreneur, self-employed person or freelancer." A recent graduate of an eligible programme reading this entry would wrongly filter out every non-sponsor employer.

**Overreach 2.** "a posting almost never states sponsor status either way" — unsourced empirical claim with a near-absolute quantifier. Nothing measured.

**Constraint:** no digits, no percent, no protected trait. "in the first contact" is an ordinal.

**Replacement `text_en`:**
> For many Netherlands roles that need a work-related residence permit, the deciding factor is the employer, not you. Under the highly skilled migrant (kennismigrant) scheme the IND says: "Only an employer recognised by the IND can apply for your permit" — the employer files it, and you cannot file it yourself. IND publishes a public register of recognised sponsors that anyone can search, listing organisations by name and Chamber of Commerce number. Check the company in that register before you invest in a tailored application; if it is not listed, ask the recruiter at the earliest contact whether they sponsor, because a posting often says nothing either way. Not every route works like this — the IND orientation year permit for graduates of eligible programmes is one you apply for yourself, and during it your employer needs no work permit — so establish which route applies to you before assuming the sponsor gate is the only one. Treat sponsor status as a fact about what the employer is set up to do administratively, not as a fact about you.

**Replacement `text_zh`:**
> 荷兰不少需要工作居留许可的岗位，决定权在雇主而不在你。在"高技能移民"(kennismigrant) 路径下，IND 明确写着：只有被 IND 认定为"认可担保方"(recognised sponsor) 的雇主才能提交该许可申请——由雇主提交，你自己无法申请。IND 有一份公开的认可担保方名录，任何人都能查，按公司名和商会注册号列出。投递前先在名录里查这家公司；查不到就尽早直接问对方是否办理担保，因为招聘广告常常两边都不写。但并非所有路径都如此——面向符合条件项目毕业生的 IND"找工作年"(orientation year) 许可由你本人申请，持有期间雇主无需办理工作许可——所以先确认自己适用哪条路径，再判断雇主门槛是否是唯一门槛。担保资质是关于雇主具备什么行政能力的事实，不是关于你本人的判断。

**Add to `source_detail`:** IND, "Residence permit for orientation year", `https://ind.nl/en/residence-permits/work/residence-permit-for-orientation-year` — applicant submits the application; verbatim: "Your employer does not need a work permit (in Dutch: tewerkstellingsvergunning or TWV)." Retrieved 2026-08-09.

**Staleness:** low for the mechanism; the register content changes monthly (sourced).

---

## 2. `nl-weu-salary-criterion-reset-annually` — **KEEP-WITH-EDIT**

**Source: verified verbatim, all three sentences,** at `https://ind.nl/en/required-amounts-income-requirements`: "The required amounts change every year on January 1"; "The highly skilled migrant must meet the required amount that applies on the date of the application"; "The highly skilled migrant must then meet the required amount applicable on the date on which the employment contract with the new employer commences." The entry's `unverified` item 7 (July indexation) is handled honestly — the page does show other permit categories on "from 1 July 2026 up to and including 31 December 2026" windows, so restricting the claim to the highly-skilled-migrant amount was the right call and should stay restricted.

**Gap that changes the advice.** The HSM page carries a *second* salary test the entry omits: "The agreed salary is in line with the market rate. In line with the market rate means that you earn the same as what people in the same job earn on average." A candidate told only to clear the published figure can clear it and still fail. Worth one sentence.

**Constraint:** clean — no digits, no percent, no trait. **zh/en drift:** none; "提交申请当天"/"新合同生效日" track the English exactly.

**Replacement `text_en`** (insert the third sentence, rest unchanged):
> The highly skilled migrant route carries a salary criterion published by the IND, and the amounts change annually. The amount that counts is the one in force on the date the application is filed; when someone moves to a new employer it is the amount in force on the date the new contract starts. A second test sits alongside the amount: the IND also requires that "The agreed salary is in line with the market rate", which it defines as earning the same as what people in the same job earn on average. So the posted salary band is not only a pay question, it is part of whether the permit application can succeed at all — and a posting can be entirely genuine while its band sits under the criterion for that route. Look up the current figure on the IND "Required amounts income requirements" page before you negotiate, rather than relying on a figure someone quoted last year.

**Replacement `text_zh`** (insert correspondingly):
> …则是新合同生效日的数额。除数额之外还有第二道检验：IND 同时要求"约定薪资须符合市场行情"，其定义是你的薪资与从事同一工作的人的平均水平相当。因此招聘上写的薪资区间…

**Staleness: HIGH — changes every 1 January by the source's own words.** This entry must carry a review date.

---

## 3. `nl-weu-expat-scheme-is-an-employer-filing` — **KEEP-WITH-EDIT**

**Source: verified verbatim, all four Belastingdienst pages.** Conditions page uses "expatregeling" throughout and lists "Wij hebben een beschikking afgegeven waaruit blijkt dat u van de expatregeling gebruik kunt maken." Application page: "Voldoet u aan alle voorwaarden, vul het aanvraagformulier dan samen met uw werkgever in." Beschikking page: "De nieuwe werkgever moet dan samen met de werknemer een nieuw verzoek indienen" and "U moet tijdens de looptijd van de beschikking toetsen of de werknemer nog aan de inkomensnorm voldoet"; it also states a maximum looptijd, so "a capped term" is fair. Definition page confirms both a prior-residence duration condition and a distance-from-the-border condition; the entry's decision not to reproduce the thresholds is correct.

**Constraint violation (the clearest in the entry).** `text_en` contains "30% ruling" twice and `text_zh` contains "30% 规则" twice — a digit **and** a percent sign in both languages.

**Staleness, and it is not hypothetical.** `https://business.gov.nl/amendments/30-percent-ruling-compensation-down-to-27-percent/` (fetched 2026-08-09) states "The tax advantage of the 30% ruling (expat ruling) will go down. It will be 27% from 2027", effective "1 January 2027", with the standard threshold rising from €46,107 to €50,436 — and that page also flags the change as "not yet final", "subject to its passing through the Lower and Upper Houses". The Belastingdienst content page I fetched (`.../inhoud_van_de_regeling/inhoud_van_de_regeling`) discusses only the current year and does not mention any future reduction. Net effect: the entry hardcodes a percentage into the *name* of the thing, at the exact moment that percentage is scheduled to stop being true. Removing the numeral fixes the constraint and the staleness in the same edit.

**Replacement `text_en`:**
> The tax break widely known by an old percentage nickname is administered by the Belastingdienst under the name expatregeling, and it is not a benefit you claim on arrival. You and the employer complete the request together, and it applies only once the Belastingdienst has issued a decision (beschikking). That decision runs for a capped term, the employer must keep re-testing the income norm while it runs, and moving to a new employer means the new employer and the employee must file a fresh joint request. There is also a prior-residence condition attached to the scheme's definition of an incoming employee, so not every internationally recruited hire qualifies. The exempt percentage and the income thresholds are set per year and a reduction has been announced for a future year, so a rate quoted from an older source can already be wrong. Read any net-pay figure quoted "with the expat ruling" as conditional until the decision exists, ask whether this employer routinely files it, and check the Belastingdienst page for the year your contract would start.

**Replacement `text_zh`:**
> 通常被以旧的百分比昵称称呼的这项税收优惠，荷兰税务局以 expatregeling（来荷雇员优惠）之名管理，它不是你入职后自己去领的福利。必须由你和雇主共同填写申请，并且只有在税务局下发正式决定 (beschikking) 之后才能适用。该决定有最长期限，期间雇主还要持续核验收入门槛；换雇主时，新雇主要和你重新共同提出申请。此外，该制度对"来荷雇员"的定义还附带入职前居住地条件，因此并非所有从境外招聘的人都符合。免税比例和收入门槛按年度设定，且已宣布将在未来某一年下调，所以从旧资料里抄来的比例可能已经不对。雇主报出的"含该优惠"的税后数字，在决定书下来之前都只是条件性的；面试时可以直接问这家雇主是否惯例办理，并按你实际入职的年度到税务局页面核对当年的比例和门槛。

**Add to `source_detail`:** Business.gov.nl, "30% ruling: compensation for expats down to 27%", `https://business.gov.nl/amendments/30-percent-ruling-compensation-down-to-27-percent/` — announces a reduced percentage and raised thresholds from 1 January 2027 and states the change "is not yet final". Retrieved 2026-08-09.

---

## 4. `nl-weu-be-single-permit-is-regional` — **KEEP-WITH-EDIT**

**Source: verified.** `https://dofi.ibz.be/en/themas/onderdanen-van-derde-landen/werk/single-permit` confirms "The application has to be done by an employer based in Belgium", the Region examining work authorisation, the Immigration Office deciding stay beyond 90 days, and issuance on acceptance.

**Factual incompleteness — the fetch contradicts the entry's own list.** The page enumerates **four** competent entities with four separate links, not three: Brussels-Capital Region; Flemish Region; "Walloon Region (**without the German Community**)"; and the German Community (site in German, ostbelgienlive.be). The entry's "Brussels-Capital, Flanders and Wallonia run their own work-authorisation regimes" drops one competent authority and mis-states Wallonia's scope. For an entry whose whole point is "candidates read Belgium as one jurisdiction", getting the sub-jurisdictions wrong is disqualifying as written.

**Two smaller overreaches.** (a) "changes the applicable rules and **the timetable**" — the page gives a single examination period beginning once the file is declared complete; regional variation in *timetable* is not on the page. (b) The page notes some categories (it names au pairs, and stays under 90 days) follow different procedures, so the flat "must be made by an employer based in Belgium" needs the exception acknowledged.

**Constraint:** clean. **zh/en drift:** none.

**Replacement `text_en`:**
> Belgium's employer-side gate is the single permit (gecombineerde vergunning / permis unique). For work and residence beyond the short-stay limit, the application must be made by an employer based in Belgium; the competent Region examines whether the person may be authorised to work, and the federal Immigration Office decides the residence side, issuing the permit if the application is accepted. Some categories of worker follow a different procedure, so confirm which one applies to you. Which authority is competent depends on where the work sits: the Immigration Office directs applicants to the Brussels-Capital Region, the Flemish Region, the Walloon Region excluding the German Community, and the German-speaking Community, each with its own work-authorisation site. A Belgian posting rarely says which of these governs the role or whether the employer has filed before, and it is worth asking both.

**Replacement `text_zh`:**
> 比利时的雇主端门槛是 single permit（gecombineerde vergunning / permis unique，工作与居留合一许可）。超过短期停留期限的工作＋居留，必须由设在比利时的雇主提出申请；由主管大区 (Region) 审查能否获准工作，联邦移民局审查居留并在申请获批后签发许可。部分类别的劳动者适用不同程序，请先确认自己属于哪一类。管辖机构取决于工作所在地：移民局把申请人分别指向布鲁塞尔首都大区、佛兰德斯大区、瓦隆大区（不含德语区）以及德语区，各自有独立的工作许可网站。比利时的招聘广告很少说明该岗位归哪个机构管、雇主此前是否办理过，这两点都值得直接问。

---

## 5. `nl-weu-sector-agreement-sets-the-band` — **KEEP-WITH-EDIT**

**Source: verified.** `https://business.gov.nl/regulations/cao/` returns verbatim "If the CAO and an employment contract contradict each other, the CAO prevails", describes the Ministry of Social Affairs and Employment declaring a CAO binding to a sector ("algemeen verbindend verklaard, AVV"), and links cao.minszw.nl. `https://werk.belgie.be/nl/themas/verloning/minimumlonen-paritair-subcomite` is published by the Federale Overheidsdienst Werkgelegenheid, returns "In de databank staat een actueel overzicht van de geldende sectorale minimumloonbarema's", and links minimumlonen.be. *Not confirmed verbatim by my fetch:* the second Belgian quote, "De databank verzamelt de brutoloongegevens en past ze aan zoals voorgeschreven door de sectorale cao's" — the fetch surfaced only the first sentence. Either re-confirm it or drop it from `source_detail`.

**Overreach — and it contradicts the entry's own `unverified` item 4.** `unverified` says "whether CAO-bound employers negotiate scale step in practice. Not sourced." Yet `text_en` asserts "the real conversation is often about placement in a scale", and `why` asserts candidates "negotiate hard against a number nobody in the room is allowed to change". Neither is in either source: "the CAO prevails on contradiction" does not establish that pay above a scale is impossible, nor that scale placement is the live lever.

**Overreach — Belgium.** "Belgium runs **the same mechanism**" implies the AVV-style generally-binding extension. The Belgian source only establishes that sectoral minimum scales exist per joint committee and are published. The extension mechanism is not sourced.

**Overreach — `applies_when`.** The sector list "(healthcare, education, public sector, research institutes, manufacturing, logistics)" as "sectors with strong collective bargaining" is an unsourced enumeration. Whether a CAO applies is checkable per employer, which is better advice than a memorised list.

**Constraint:** clean. **zh/en drift:** none of substance; both carry the same unsourced "真正可谈的往往是定在哪一级".

**Replacement `text_en`:**
> The salary band may not be the employer's to move. In the Netherlands a collective labour agreement (CAO) can fix pay and other terms for the role, and where the CAO and the individual employment contract contradict each other, the CAO prevails. An employer can be bound to a sector CAO without belonging to the employers' organisation that negotiated it, because the Ministry of Social Affairs and Employment can declare a CAO generally binding for the sector (algemeen verbindend verklaard, AVV). In Belgium, sectoral minimum pay scales are set per joint committee (paritair comité / commission paritaire) and published in a government database. Find out which CAO or joint committee covers the job, and read the scale, before you name a number — then ask the employer directly which parts of the package it still controls.

**Replacement `text_zh`:**
> 薪资区间未必由雇主说了算。在荷兰，集体劳动协议 (CAO) 可以规定该岗位的工资和其他条件；当 CAO 与个人劳动合同冲突时，以 CAO 为准。即使雇主不是签订该 CAO 的雇主协会成员，社会事务与就业部也可以宣布该 CAO 对整个行业"普遍适用"(algemeen verbindend verklaard, AVV)，雇主同样必须执行。在比利时，行业最低工资表按"联合委员会"(paritair comité / commission paritaire) 设定，并由政府数据库公布。报价之前先弄清这份工作归哪个 CAO 或哪个联合委员会、并读一下工资表，然后直接问雇主：待遇里还有哪些部分是他们能决定的。

**Replacement `applies_when`:** "Before any salary discussion for a Netherlands or Belgium role. Whether a CAO or a joint committee covers the job is checkable per employer and sector through the government lookups cited below — check, rather than inferring from the sector."

---

## 6. `nl-weu-motivation-letter-is-scored` — **KEEP-WITH-EDIT**

**Source: verified, with one misquote.** `https://eures.europa.eu/.../living-and-working-conditions-netherlands_en` confirms: motivation is "one of the most important selection criteria for Dutch employers"; "for jobs at a qualified and highly qualified level, an application letter with a CV is the standard procedure"; letter "in Dutch (unless indicated otherwise)"; the three-part structure; unsolicited applications "very common in the Netherlands"; CV adapted to the position.

**The `source_detail` presents as verbatim a sentence the page does not contain.** Entry: "It is not unusual to phone the company beforehand." Page: "it is not uncommon to phone a company beforehand; however, make sure you have first prepared a number of clear questions". Same gist, but a quoted-verbatim field must be exact — and the page's conditional clause ("first prepared clear questions") is dropped, which is the part that makes the advice safe to act on.

**Unsourced closing claim, and zh is stronger than en.** "A letter that restates the CV, or one letter sent to several employers, is a genuine rejection risk even when the CV matches" is nowhere in EURES. The Chinese goes further: "即使简历匹配也**很可能被刷掉**" ("very likely to be rejected") vs English "is a genuine rejection risk". Drift in the direction of a stronger unsourced claim.

**`applies_when` contradicts `unverified` item 5.** It asserts that in Belgium "the language of the letter follows the workplace's language regime" — `unverified` says Belgian letter conventions were not sourced at all.

**Constraint:** "one letter" is a written-out number in `text_en`; "一封信" in `text_zh`.

**Replacement `text_en`:**
> For qualified and highly qualified positions the letter is a selection instrument, not a cover note. EURES's Netherlands guidance says that for jobs at a qualified and highly qualified level an application letter with a CV is the standard procedure, that motivation is one of the most important selection criteria for Dutch employers, and that the letter should set out why you are applying, then why you are suitable and motivated, then ask for an interview. It also says the letter is expected in Dutch unless the employer indicates otherwise, that unsolicited applications are very common, and that it is not uncommon to phone a company beforehand provided you have prepared clear questions first. Write to that structure and to this employer, rather than reusing the same letter across employers.

**Replacement `text_zh`:**
> 对中高级岗位而言，求职信是选拔工具，不是附言。欧盟 EURES 的荷兰指南写明：中高级岗位的标准投递方式是求职信＋简历；动机是荷兰雇主最重要的筛选标准之一；信里应先说明你为什么应聘，再说明你为什么合适、为什么有动力，最后请求面谈。指南还说明：除非雇主另有说明，求职信默认用荷兰语写；主动投递（未招聘岗位的自荐）在荷兰非常普遍；事先打电话给公司也不算稀奇，前提是你先准备好了明确的问题。请照这个结构、针对这家雇主来写，而不是把同样的信重复投给多家。

**Replacement `applies_when`:** "Any qualified or highly qualified application in the Netherlands. Not sourced for Belgium — do not carry the Dutch-language default or these letter conventions across the border without checking."

**Fix `source_detail`:** replace the phone sentence with the exact text above, and add the verbatim "for jobs at a qualified and highly qualified level, an application letter with a CV is the standard procedure".

---

## 7. `nl-weu-language-requirement-must-be-justified` — **KEEP-WITH-EDIT (heavy); DROP is defensible**

This is the weakest entry in the set. The source is real and the quotes are exact, but the entry generalises a single non-binding opinion into a market-wide reading rule.

**Source: verified.** `https://oordelen.mensenrechten.nl/oordeel/2022-55`, 23 May 2022, respondent Stichting Hoger Beroepsonderwijs Haaglanden, a senior-lecturer (hogeschooldocent) vacancy requiring "uitstekende communicatieve vaardigheden in zowel het Nederlands als het Engels". The test quoted in the entry is verbatim on the page.

**The ruling is narrower than the entry implies.** The College *accepted* the employer's aim as legitimate and *accepted* that some Dutch ability was relevant to coordination between programmes; what it found not necessary was the demand for **excellent** proficiency in **both** languages for that role. The entry's flat "the employer could not show the requirement was objectively justified" reads as though any Dutch requirement fails.

**Undisclosed source status.** `https://www.mensenrechten.nl/mensenrechten-voor-jou/discriminatie-en-gelijke-behandeling/discriminatieklachten-en-verzoek` states verbatim: "Een oordeel van het College is niet juridisch bindend, maar wel gezaghebbend"; "Het College kan geen straffen of maatregelen kan opleggen"; "De rechter moet rekening houden met het oordeel van het College." The entry's SOURCE-QUALITY NOTE labels NVP and EURES as non-statutory and lists the official/statutory sources — and omits the College from **both** lists. A job-seeker reads "ruled … prohibited" as binding law.

**Two unsourced claims, one with a quantifier.** (a) "which is part of why so many read 'Dutch is a plus' rather than 'Dutch required'" — a causal claim about employer drafting behaviour, from nothing. (b) "Practical reading: 'a plus' is **usually** a genuine plus rather than a coded bar" — an empirical generalisation with a frequency word, derived from a single opinion about one lecturer vacancy. This directly contradicts the entry's own `unverified` item 1, which says no source was found for how "Dutch is a plus" behaves in practice. Both appear identically in `text_zh` ("通常就是真的加分项").

**Constraint:** "in the first conversation" is an ordinal; no protected trait is named in the text (the ruling's ground was race / national-ethnic origin — correctly kept out).

**Replacement `text_en`:**
> A language requirement in a Dutch vacancy can be challenged, which makes it a fair thing to ask about. The Netherlands Institute for Human Rights examined a vacancy for a lecturer post that demanded excellent communication skills in both Dutch and English. It applied the test that indirect discrimination is not prohibited where it is objectively justified by a legitimate aim and the means of achieving it are appropriate and necessary; it accepted the employer's aim as legitimate, and still found that demanding excellent proficiency in both languages was not necessary for that role. Its opinions are authoritative but not legally binding, and that opinion does not tell you how any other employer means its language line. So ask early which specific parts of the work run in Dutch — customers, colleagues, suppliers, documentation — instead of guessing whether the line is decorative or disqualifying.

**Replacement `text_zh`:**
> 荷兰招聘广告里的语言要求是可以被质疑的，所以直接问它是合理的。荷兰人权研究所曾审查一则高校讲师岗位的招聘广告，其要求"荷兰语和英语都具备出色沟通能力"。研究所适用的检验标准是：间接区别对待若具备正当目的、且实现该目的的手段适当且必要，则不被禁止；它认可雇主的目的正当，但仍认定"两种语言都要出色"对该岗位并非必要。该机构的裁定具有权威性但不具法律约束力，而且这一份裁定并不能告诉你其他雇主的语言要求是什么意思。所以请尽早直接问：这份工作具体哪些部分要用荷兰语——客户、同事、供应商，还是文档——而不是去猜那行字是摆设还是硬门槛。

**Add to `source_detail` and to the SOURCE-QUALITY NOTE:** College voor de Rechten van de Mens, "Wat gebeurt er bij het aanvragen van een oordeel bij het College?", `https://www.mensenrechten.nl/mensenrechten-voor-jou/discriminatie-en-gelijke-behandeling/discriminatieklachten-en-verzoek` — verbatim: "Een oordeel van het College is niet juridisch bindend, maar wel gezaghebbend"; "De rechter moet rekening houden met het oordeel van het College." Retrieved 2026-08-09.

**If the shipper will not take the shortened version, DROP it.** The actionable core ("ask which parts of the work run in Dutch") does not actually depend on the case law, and the case law as currently written invites a candidate to argue with an employer from a misread of a non-binding opinion.

---

## 8. `nl-weu-references-only-with-prior-permission` — **KEEP-WITH-EDIT**

**Source: verified verbatim against the PDF** (fetched, extracted with `pdftotext`; text at `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/nvp.txt`). Clause 4.1 both sentences are exact, character for character. "De code is opgesteld in overleg met de Stichting van de Arbeid" is on the first page. Edition line: "NVP, HR-netwerk in Nederland – januari 2020". The Klachteninstantie is real (6.1–6.5). Good sourcing.

**Unsourced timing claim, and it contradicts the entry's own `unverified` item 3.** `unverified` says: "The code establishes the prior-permission rule; it does not say references are contacted only after an offer. The claim in the conventions table is limited to what the code supports." It is not. `text_en` opens "References are approached **late**"; `text_zh` opens "背景调查/推荐人核实**是在后期进行的**" — a flat assertion. The code places 4.1 under "Nader onderzoek", after Selectie, but states no timing for references. (It *does* state timing for a meeloopdagdeel — "in de eindfase" — and for a medical examination — "uitsluitend nadat alle overige beoordelingen van geschiktheid hebben plaatsgevonden". Not for references.) Likewise "you can withhold it for a current employer **until the offer stage**": the withholding follows from 4.1, the offer-stage framing does not.

**Misattributed clause.** "Where such legally required screening applies, the code says **the vacancy** must mention it." The nearest support is clause 2.3, which requires the **wervingsprofiel** to state, "indien van toepassing: … en/of een verplicht antecedentenonderzoek". Clause 2.3 is not cited in `source_detail` at all. The code's "wordt daarvan uitdrukkelijk melding gemaakt in de vacature" language is clause 2.6, and it concerns age limits and preference policy — a different subject.

**Constraint:** clean. **Provenance handling of the code's status:** correctly labelled as self-regulatory in `source_detail`, but that caveat should be inside `text_en`/`text_zh`, since those are what render to the user.

**Replacement `text_en`:**
> References are taken with your prior permission, not quietly in the background. The NVP Sollicitatiecode — the Dutch recruitment code of conduct, drawn up in consultation with the Stichting van de Arbeid — provides that where a reference is requested from third parties, or further investigation is necessary, the organisation must ask the applicant for permission in advance, unless permission is not required by law or further regulation. The same code says a mandatory background check, where it applies, belongs in the recruitment profile the organisation draws up for the role, and that information obtained via the internet or social media must, if relevant, be discussed with you with the source explicitly named and with an opportunity to respond. So line up referees before you need them, expect to be asked, and remember the permission is yours to give — you can withhold it for a current employer. The code is a self-regulatory code of conduct with its own complaints body, not a statute: it sets a norm, not an enforceable right.

**Replacement `text_zh`:**
> 向第三方索取推荐意见必须事先得到你的同意，不会在背后悄悄做。荷兰招聘行为准则 NVP Sollicitatiecode（与劳动基金会 Stichting van de Arbeid 协商制定）规定：向第三方索取推荐意见、或需要进一步调查时，必须事先征得求职者同意——除非法律或相关法规规定无需征得同意。同一准则还规定：若该岗位存在强制性的背景调查，应写入招聘方为该岗位制定的招聘画像 (wervingsprofiel)；通过互联网或社交媒体获得的信息，如与岗位相关，必须注明来源与你讨论，并给你回应的机会。所以：提前备好推荐人，预期会被征询；同意权在你手上，你可以不同意联系现任雇主。请注意该准则是带投诉机构的行业自律准则，不是法律：它确立的是规范，不是可强制执行的权利。

**Add clause 2.3 verbatim to `source_detail`**, or delete the background-check sentence.

---

## 9. `nl-weu-pay-range-not-pay-history` — **KEEP-WITH-EDIT**

**Source: verified verbatim.** NVP clause 1.1 bullet reads exactly "van de sollicitant wordt geen salarisstrook van de huidige of vorige werkgever verlangd". EUR-Lex CELEX:32023L0970 Article 5(1)(a),(b) and 5(2) are quoted exactly; Article 34: "Member States shall bring into force the laws, regulations and administrative provisions necessary to comply with this Directive by 7 June 2026." Wetgevingskalender WGK025384 is titled "Implementatie richtlijn loontransparantie" and shows "Wetsvoorstel ingediend bij Tweede Kamer" on 21-05-2026, preparatory documents 22-05-2026, i.e. still in parliament. Excellent sourcing — the honest "check the current national position" is exactly right.

**Constraint violations:** `text_en` and `text_zh` both contain "2023/970" (digits — a legal citation, not a quantity, so this is arguably the benign class, but it is a literal violation). Both also contain "gender-neutral" / "性别中立", naming a protected trait — inside a quoted legal standard describing the *employer's* criteria, not a candidate attribute, so I would allow it; flagging because the rule is stated absolutely.

**Overreach in `applies_when`.** "in the Netherlands, Belgium and the wider EU/EEA" bundles three different reaches: the NVP payslip rule is Netherlands-only and non-statutory; the directive binds EU member states through national law; **EEA applicability was not verified by me and is not verified in the entry**. Drop "EEA" or source it.

**Missing operative fact the entry already holds the pieces for.** The transposition deadline (7 June 2026) had **already passed** at the retrieval date (2026-08-09) while the Dutch bill was still before the Tweede Kamer. The entry cites both facts and never joins them, which is the one thing a candidate needs: the right may not yet exist in Dutch law, and the state is past its deadline.

**Replacement `text_en`** (change the middle only):
> …That right reaches you through national implementing law, and implementation is uneven across member states — the directive's transposition deadline had already passed while the Dutch implementing bill was still before the Tweede Kamer, so check the current national position rather than assuming the right is in force. Practically: ask for the range and the applicable collective-agreement scale, and treat a payslip request as something you may decline.

**Replacement `text_zh`** (same change):
> …该权利需通过各国国内立法落地，而各成员国进度不一——该指令的转化期限已过，而荷兰的实施法案当时仍在众议院 (Tweede Kamer) 审议，因此请核对当下的国内法状态，不要假定该权利已生效。实务上：主动索要薪资区间和适用的集体协议工资级别；被要求提供工资单时，你可以拒绝。

**Replacement `applies_when`:** "At first recruiter contact and at every pay discussion in the Netherlands. The payslip rule is a Netherlands-specific self-regulatory norm; the EU directive layer applies across EU member states via national implementing law — do not assume it for non-EU EEA states without checking."

**Staleness: HIGH.** The Dutch implementation status will change; this entry needs a dated review trigger.

---

## 10. `nl-weu-regulated-profession-needs-formal-recognition` — **KEEP-WITH-EDIT**

**Source: verified, with two precision slips.** `https://business.gov.nl/regulations/professional-qualifications/` returns "Only people who meet the requirements are allowed to work in a regulated profession"; "You can have your foreign diploma or certificate evaluated by the Information centre for credential evaluation (IDW), but this is not required"; "You apply for recognition of your professional qualifications with the competent authority for your profession."

Slip (a): the page says "You can find **all regulated professions** in the Netherlands in the European Union's Regulated Professions Database" — it does **not**, on the text I fetched, say the database is how you identify the *competent authority*. The entry's "You identify the competent authority through the EU's Regulated Professions Database, by profession and country" states more than the cited page does.

Slip (b): Nuffic appears on the page in a different role than the entry assigns it — as the National Contact Point that "can also inform you about the status of your national diploma", and as the issuer of an "AC declaration for regulated professions". Lumping "a credential evaluation by Nuffic or IDW" conflates instruments; only the IDW evaluation is the thing the page marks as not required.

**Overreach:** "Employers in these fields **will not and cannot** start you" — "cannot" is supported; "will not" is an unsourced employer-behaviour claim. "begin the recognition track in parallel with applying rather than after an offer" is unsourced procedural advice (some recognition procedures may themselves depend on an employer or a post).

**Constraint:** "two different steps" / "两个不同步骤" is a written-out number in both languages; "一是…二是…" in `text_zh`.

**Replacement `text_en`:**
> If the role is a regulated profession, a diploma evaluation is not the thing that unlocks it. Business.gov.nl separates the credential evaluation from the recognition: having a foreign diploma evaluated by the Information centre for credential evaluation (IDW) is, in its words, not required, whereas you apply for recognition of your professional qualifications with the competent authority for your profession — and only people who meet the requirements are allowed to work in a regulated profession. The same page points to the European Union's Regulated Professions Database for which professions are regulated in the Netherlands, and to Nuffic's National Contact Point for the status of a foreign diploma. So find the competent authority and what its procedure requires before you rely on any start date: no amount of employer goodwill substitutes for the recognition.

**Replacement `text_zh`:**
> 如果岗位属于"受管制职业"(regulated profession)，学历认证并不等于执业资格。荷兰官方 Business.gov.nl 把学历评估和资格承认分开：把国外文凭交给学历评估机构 IDW 评估，按其原话是"并非必需"；而要执业，你需要向该职业的主管机构申请对你专业资格的正式承认——因为只有符合要求的人才被允许从事受管制职业。同一页面指向欧盟 Regulated Professions Database 查询荷兰哪些职业受管制，并指向 Nuffic 的国家联络点了解国外文凭在荷兰的地位。所以请先找到主管机构、弄清其程序要求，再去承诺任何入职日期：雇主再有诚意也替代不了这项承认。

---

# Important and missing

1. **The orientation year permit (verified, and it breaks convention 1's frame).** `https://ind.nl/en/residence-permits/work/residence-permit-for-orientation-year`: the applicant files it themselves, and "Your employer does not need a work permit (in Dutch: *tewerkstellingsvergunning* or TWV)." For a recent graduate of an eligible programme this removes the recognised-sponsor gate entirely and widens the employer pool. The entry's `unverified` list does not mention it either — it is not a known gap, it is an unknown one.

2. **The expat scheme's announced reduction.** Covered in convention 3 above. Independently of the constraint problem, an entry that teaches a candidate to evaluate net pay must not silently fix the percentage in the scheme's name during the year before it changes.

3. **College oordelen are not legally binding.** Verified verbatim. The SOURCE-QUALITY NOTE lists NVP and EURES as non-statutory and lists seven sources as official/statutory — and leaves the College out of both lists, so the one source whose status most affects how a candidate acts is the one with no label.

4. **The EU Blue Card.** `unverified` item 9 correctly refuses to describe it from memory. But its absence means a candidate whose salary clears one route's criterion and not the other's has no way to know a second route exists. Research it or state its existence and stop there — the current silence reads as "the highly skilled migrant route is the route".

5. **NVP clause 5.3 — what happens to your data after rejection.** "Voor zover van toepassing worden gegevens afkomstig van een sollicitant binnen vier weken na de afwijzing teruggezonden of vernietigd, tenzij expliciet anders met de sollicitant is overeengekomen", with a re-consent step after a year for retained data and a destruction duty for agencies once mediation ends. This is candidate-facing, concrete, in a source already fetched, and absent from both `application_artifacts` and `interview_shape`.

6. **NVP clause 3.2 — you may ask for a deviation.** Where an organisation uses internet or video applications, or confronts you with other candidates, "mag de sollicitant in het kader van de vertrouwelijkheid om afwijking van de procedure verzoeken." A candidate who does not know a one-way video interview is refusable-with-a-reason cannot exercise it. `interview_shape` covers 3.4 (algorithmic pre-selection) but skips 3.2.

7. **NVP clause 2.6 — how to read an age limit or preference policy in a Dutch posting.** Only permitted where legally allowed, and then "wordt daarvan uitdrukkelijk melding gemaakt in de vacature en wordt de reden daarvan aangegeven". Useful for reading postings; note it names a protected trait, so the shipper must decide whether the constraint blocks it.

8. **Belgium remains thin, as the entry admits.** Two sourced facts total, no application artifacts, no interview shape, no language expectations. The `unverified` section says so plainly — but `market_key` is `nl_weu` and conventions 6, 8 and 9 are Netherlands-only while reading as regional. Either scope the market key to NL, or source Belgium.

**One cross-cutting defect worth naming separately:** in three places (conventions 5, 6, 7, 8) the `unverified` section correctly states that a claim is not sourced, and the rendered `text_en`/`text_zh` makes that exact claim anyway. Since the table renders verbatim with no source text beside it, the `unverified` section provides zero protection at the point of reading. Every claim that `unverified` disclaims must be removed from the rendered text, not just footnoted.