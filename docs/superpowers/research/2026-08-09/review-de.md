Verification complete. All ten source URLs fetched today (2026-08-09); results below.

# Market conventions review — `de`

**Verification method.** Every `published` URL was fetched with `curl -sL` and the page text extracted and grepped (files under `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/v_*`). All ten cited URLs returned HTTP 200. One redirects (SECO). Two additional URLs were fetched to test claims the entry makes indirectly (`__23.html` KSchG, RIS GlBG §9), and the two URLs the entry reports as unreachable were re-tested and confirmed unreachable.

**Mechanical constraint scan (ran over all twenty text bodies).** Zero digits. Zero percent signs. Zero protected traits named. One hard defect: **Cyrillic contamination** in `de-application-is-a-file-not-a-cv`. "Written-out number" hits are all grammatical articles/quantifiers (`一份`, `一段`, "one of"), except four true counting words flagged below.

---

### 1. `de-arbeitszeugnis-is-a-graded-document` — **KEEP-WITH-EDIT**

Sources verify strongly. § 109 GewO retrieved verbatim: `(1) … Das Zeugnis muss mindestens Angaben zu Art und Dauer der Tätigkeit (einfaches Zeugnis) enthalten. Der Arbeitnehmer kann verlangen, dass sich die Angaben darüber hinaus auf Leistung und Verhalten … erstrecken. (2) … Es darf keine Merkmale oder Formulierungen enthalten, die den Zweck haben, eine andere als aus der äußeren Form oder aus dem Wortlaut ersichtliche Aussage über den Arbeitnehmer zu treffen.` BAG 9 AZR 584/13 verifies at a higher level of detail than the entry claims: `Zufriedenheitsskala … Skala, die von "sehr gut" bis hin zu "mangelhaft" reicht`; `"zur vollen Zufriedenheit" … wird das der Note "befriedigend" zugerechnet`; and the Leitsatz on burden of proof exactly as quoted.

Two defects:

**(a) "automatically" is wrong.** § 109(1) sentence 1 reads `Der Arbeitnehmer hat … Anspruch auf ein schriftliches Zeugnis` — an entitlement you assert, not something issued unprompted. The entry's whole point is that people fail to ask; saying the simple version arrives automatically undercuts it and is not what the statute says.

**(b) The reinforcer rule is stated loosely and the loose version is the trap.** The court: `"Gut" im Sinne der Zufriedenheitsskala ist ein Arbeitnehmer nur dann, wenn ihm bescheinigt wird, er habe "stets" … Zufriedenheit des Arbeitgebers gearbeitet` — and separately, `"stets zur Zufriedenheit"` *without* "vollen" is still rated at the middle. A candidate who sees "stets" alone and concludes "good" makes exactly the error this entry exists to prevent.

Replacement `text_en`:

> German employers read the written reference from each of your previous jobs (Arbeitszeugnis) as a graded assessment, not a formality. On leaving a job you have a legal claim to a written certificate, but you have to assert it, and by default it need only cover the kind and length of the work; the fuller version covering performance and conduct is issued only if you ask for it — so if you never asked, you do not hold the document recruiters expect to see. Federal labour case law places the standard "performed the duties to our full satisfaction" wording in the middle of a school-style satisfaction scale running from very good to poor, and holds that the grade above it needs the constancy word ("stets") and the word "full" together — a reinforcing word on its own does not lift the grade — while the burden sits on you to show facts justifying a better closing assessment. The same statute forbids wording that carries a hidden message about you, which is your ground for demanding a change. Read every reference against that scale before you attach it, and ask a former employer to correct it while the relationship is still workable.

Replacement `text_zh`:

> 德国雇主会把你每段过往工作的书面证明（Arbeitszeugnis）当作一份带评分的鉴定来读，而不是走过场。离职时法律赋予你索取书面证明的请求权，但需要你主动主张；默认版本只写工作内容和时长，含「表现与行为」评价的完整版必须你提出要求才会出具——没提过，就等于没有招聘方期待看到的那份文件。联邦劳动法院把「完全令我们满意地完成工作」这类标准措辞定位在一把「满意度刻度」的中间档，这把刻度从「很好」一直到「差」；要够到上一档，必须「始终」（stets）与「完全」（vollen）同时出现——只有强化词、没有「完全」，档次并不上升。而且，想要更好的总评，举证责任在你身上。同一部法律也禁止在证明里夹带暗示性表述，这正是你要求修改的法律依据。因此，附上任何一份证明之前，先按这把刻度读一遍；要改，趁与前雇主关系还谈得动的时候提。

*Staleness: low. Statute and 2014 precedent, both stable.*

---

### 2. `de-degree-classification-is-a-separate-procedure` — **KEEP-WITH-EDIT**

anabin verifies fully, including the marker set the entry names: `Weitere Informationen zum Status finden Sie mit Klick auf den Status (H+, H+/-, H-)`, plus `Diese Hochschulen sind in der Datenbank anabin mit dem Status H+ gekennzeichnet` and `In diesem Fall hat die Institution den Status H+/-`. ZAB verifies the regulated-profession limit verbatim (`sie berechtigt aber nicht zur Studienzulassung, zu weiterführenden Studien oder zum Arbeiten in einem reglementierten Beruf`) and the visa/Blue Card use.

Three defects:

**(a) "It is voluntary" is not on the cited page.** I grepped the full ZAB page text (6,169 chars) for `freiwillig` — zero hits. The `source_detail` asserts the page "states that the Zeugnisbewertung is … voluntary". It does not. Either drop the word or source it elsewhere.

**(b) "public-sector employers commonly require it" is a narrowing of a broader, vaguer sentence.** The page says `Viele Arbeitgebende verlangen eine Zeugnisbewertung als Voraussetzung für die Bewerbung – zum Beispiel im öffentlichen Dienst` — *many employers*, public service given as an example. The entry converts an example into a sector rule with a frequency word. The direction of the error is toward more confidence than the source carries.

**(c) A material caveat sitting on the cited page is omitted.** anabin: `Die anabin-Datenbank erhebt keinen Anspruch auf Vollständigkeit. Daher kann es vorkommen, dass Ihr Abschluss/Abschlusstyp in anabin noch nicht aufgeführt oder bewertet ist.` A candidate who searches anabin, finds nothing, and concludes their degree is unrecognised has drawn the wrong conclusion — and the fix (apply for a Zeugnisbewertung) is on the same page. This is the single most actionable line on the source and it did not make the entry.

Also: "no recruiter can waive it" is confused — for a private employer there is nothing to waive, since the document is not required there. Cut it.

Replacement for the third sentence onward in `text_en`:

> Separately, the central office for foreign education (ZAB) issues an official statement of comparability, the Zeugnisbewertung. Many employers ask for it as a precondition for an application, the public service among them, and visa and Blue Card EU files require you to evidence comparability. It does not by itself entitle you to practise a regulated profession or to enrol in further study — those need a separate recognition from the responsible body. Note that anabin does not claim to be complete: if your degree or degree type is simply absent, that is not a verdict on it, and a Zeugnisbewertung is the route. Start it early — it is an administrative queue.

Replacement for the corresponding `text_zh`:

> 另有中央外国教育办公室（ZAB）出具的官方等值说明，称为 Zeugnisbewertung。不少雇主把它列为投递的前提条件，公共部门即在其列；申请签证或欧盟蓝卡时，也必须凭它证明学位的可比性。它本身并不赋予你从事受管制职业或继续升学的资格——那要向对口主管机构另行申请职业资格承认。另需注意：anabin 明确声明数据库并不追求收录完整，你的学位或学位类型查不到，并不等于不被认可，此时正确的做法是申请 Zeugnisbewertung。这件事要尽早启动：它是行政排队流程。

*Constraint note: `two different things … two different bodies` / `两回事…两套机构` are literal written-out-number hits. Semantically harmless, but if the linter is mechanical, use "are not the same thing, and are run by different bodies" / "不是一回事，分属不同机构".*

*Staleness: low for the mechanism; the individual anabin record for any given degree can change.*

---

### 3. `de-employer-drives-the-permit-not-you` — **KEEP-WITH-EDIT**

§ 81a AufenthG verifies precisely: employer applies `in Vollmacht des Ausländers` at the `zuständige Ausländerbehörde`; the `Vereinbarung` covers `vorzulegende Nachweise`, the authority's power to `das Verfahren zur Feststellung der Gleichwertigkeit … einleiten und betreiben`, and the employer's duty per Nr. 4. § 18g(7) verifies verbatim: `Das Bundesministerium des Innern und für Heimat gibt die Mindestgehälter … für jedes Kalenderjahr … im Bundesanzeiger bekannt.` Good call keeping the percentages out.

**zh/en drift — the Chinese is stronger than both the English and the statute.** ZH: `有义务保证求职者配合` = "obliged to *guarantee* the applicant cooperates". Statute Nr. 4: `Verpflichtung des Arbeitgebers, auf die Einhaltung der Mitwirkungspflicht des Ausländers … hinzuwirken` = obliged to *work toward* compliance. EN's "keep the worker cooperating" is already loose; ZH's 保证 is a materially different obligation. Replace `有义务保证求职者配合` with `有义务督促求职者履行配合义务`.

**Scope overreach:** § 81a(1) is available only for entry under `§§ 16a, 16d, 18a, 18b, 18c Absatz 3 und § 18g` (plus, per (5), other qualified employees). "Statute provides an accelerated skilled-worker procedure" reads as generally available. Add: "for the skilled-worker and study-related residence purposes the provision lists".

**Missing and material for this table's user:** § 18g(1) sentence 2 sets a *lower* threshold for named ISCO occupation groups and for recent graduates, and § 18g(4) governs job changes on an existing Blue Card. See "missing" list below — a candidate reading "its minimum salary carries a threshold" (singular) may wrongly rule themselves out.

*Staleness: **high, yearly.** The euro figures are re-announced every calendar year by ministry notice. The entry handles this correctly by refusing to print one — keep it that way on every future edit.*

---

### 4. `de-works-council-must-consent-to-the-hire` — **KEEP-WITH-EDIT**

§ 99 BetrVG verifies on every point, including the two refusal grounds selected (Nr. 5 `eine nach § 93 erforderliche Ausschreibung im Betrieb unterblieben ist`; Nr. 3 `dass … im Betrieb beschäftigte Arbeitnehmer gekündigt werden oder sonstige Nachteile erleiden`) and `den in Aussicht genommenen Arbeitsplatz und die vorgesehene Eingruppierung mitzuteilen`.

**Overreach in `applies_when`: "most non-startup employers".** § 99 binds `In Unternehmen mit in der Regel mehr als zwanzig wahlberechtigten Arbeitnehmern` — but only where a works council actually exists, and German works councils are elected on employee initiative, not mandated by size. The entry asserts a prevalence ("most") that nothing cited supports and that is plausibly false across the Mittelstand and tech sectors. Replace `applies_when` with:

> Applying to a German company or public body that has a works council or staff council — common in larger and long-established employers, but not automatic above the size threshold, so treat it as a possibility rather than a certainty.

**Overreach in the practical inference.** § 99(3) caps the exposure: `Teilt der Betriebsrat dem Arbeitgeber die Verweigerung seiner Zustimmung nicht innerhalb der Frist schriftlich mit, so gilt die Zustimmung als erteilt` — the council's window to object is one week, after which consent is deemed given. As written, the entry invites a candidate to attribute a months-long silence to the works council. That is a false reassurance, and it is contradicted by the very provision cited. Also worth one clause: § 99(1) sentence 3 imposes a confidentiality duty on council members, which is the natural answer to the worry the entry raises.

Replacement for the final part of `text_en` (also fixes the literal "Two"):

> … or that the hire would disadvantage existing staff. That has practical consequences: an offer can sit between the verbal yes and the signed contract for reasons that have nothing to do with you, and your file is seen by people outside HR — who are bound by a statutory duty of confidentiality over what they read. The council's window to object in writing is short, and consent counts as given if it lets that window pass, so this stage does not explain a long silence on its own. Do not read a gap as a rejection; ask where in the process it is.

Corresponding `text_zh` tail:

> ……或该录用会使现有员工受到不利影响。这带来的实际后果是：口头确认到合同签署之间，offer 可能因为与你完全无关的原因卡住；你的材料也会被 HR 之外的人看到——而这些人依法负有保密义务。职工委员会书面提出异议的期限很短，逾期未提即视为同意，所以单靠这一环节并不足以解释长时间的杳无音信。不要把沉默当成婉拒，直接问流程走到哪一步了。

*Staleness: low.*

---

### 5. `de-your-notice-period-sets-the-start-date` — **KEEP-WITH-EDIT (substantive legal error)**

This is the most serious defect in the entry. § 622 BGB as retrieved:

- `(1) Das Arbeitsverhältnis … kann mit einer Frist von vier Wochen zum Fünfzehnten oder zum Ende eines Kalendermonats gekündigt werden.`
- `(2) **Für eine Kündigung durch den Arbeitgeber** beträgt die Kündigungsfrist, wenn das Arbeitsverhältnis … [ladder by years of service]`

The ladder that lengthens with length of service is **employer-side only**. An employee resigning falls under (1) regardless of tenure, unless a contract or collective agreement extends it (permitted by (4) and (5), and bounded by (6): the employee's period may not exceed the employer's). The entry's own `source_detail` states this correctly — "the **employer's** notice periods graduated by length of service" — and then `text_en` and `text_zh` both collapse it into a rule about the candidate's own resignation. A long-tenured candidate following this entry will name a start date months later than the law requires and lose offers over a period they do not owe. Both languages carry the same error, so this is not drift — it is a shared miss between the source note and the rendered text.

Second gap: § 1 KSchG verifies (`ohne Unterbrechung länger als sechs Monate`), but protection also requires clearing the small-business threshold in § 23 KSchG, which I fetched (HTTP 200, `https://www.gesetze-im-internet.de/kschg/__23.html`) and which excludes establishments at or below ten employees for employment begun after 2003. For a candidate weighing a startup against a large employer, "protection switches on after the waiting period" is simply untrue at the startup.

Replacement `text_en`:

> "Earliest possible start date" is not a preference question in Germany, it is a legal one. Your own resignation runs on a statutory default notice tied to the middle or the end of a calendar month; the longer notice periods that grow with length of service are the ones the EMPLOYER owes you, and they bind your side only where your contract or an applicable collective agreement says so — which is common enough that you must read the clause rather than assume the default. During an agreed probationary period a much shorter notice applies in both directions, and statutory protection against socially unjustified dismissal begins only after an initial continuous waiting period AND only in establishments above a small-business size threshold — so the early phase of a new job, and a job at a very small employer, are genuinely different legal states. Work out your own notice from your contract before you name a date, and treat the probation clause and the notice terms in the new contract as negotiable items alongside pay.

Replacement `text_zh`:

> 在德国，「最早可入职时间」不是偏好题，是法律题。你自己辞职适用的是法定默认通知期，以日历月的月中或月末为终点；而随工龄延长的那套更长的通知期，是雇主解雇你时须遵守的，只有当你的劳动合同或适用的集体合同如此约定，才同样约束你一方——这种约定并不少见，所以务必去读条款，别默认按法定最短算。在约定的试用期内，双方适用远短得多的通知期；针对「社会性不当解雇」的法定解雇保护，既要连续雇佣满一段等待期才生效，也只适用于规模超过「小企业」门槛的单位——也就是说，新工作的最初阶段，以及在极小规模雇主处的工作，在法律上确实是另一种状态。报日期之前，先按你的合同算清自己的通知期；并且把新合同里的试用期条款和通知期条款，与薪资一起当作可谈判事项。

Add to `source_detail`: `Bundesministerium der Justiz / juris, "§ 23 KSchG - Einzelnorm", https://www.gesetze-im-internet.de/kschg/__23.html, retrieved 2026-08-09 — the first section of the Act does not apply in establishments at or below the stated small-business size for employment begun after the stated date.`

*Staleness: low.*

---

### 6. `de-public-sector-pay-is-classified-not-negotiated` — **KEEP-WITH-EDIT (source labelling)**

Both sources verify. BVA Definitionskatalog PDF retrieved (22 pages, `Köln im Juli 2022`, `Zehnte Auflage`, `Stand: 30.08.2022` — publisher, title, edition and status date all match the citation), section 1 verbatim: `Die/Der Beschäftigte ist in der Entgeltgruppe eingruppiert (Tarifautomatik), deren Tätigkeitsmerkmalen die gesamte von ihr/ihm nicht nur vorübergehend auszuübende Tätigkeit entspricht.` BAG 6 AZR 205/20 verifies verbatim on both limbs.

**Source-integrity flag: the two sources cover different collective agreements and the citation does not say so.** The BVA catalogue is federal — `§ 12 TVöD` / `TV EntgO Bund`. The BAG Leitsatz is expressly `§ 16 Abs. 2 **TV-L**` (the *Länder* agreement — the one that actually governs German universities and state research institutes, i.e. the most likely target for this user). The claim generalises fine in substance because the two together span Bund and Länder, but a reader checking the citation will find a TVöD source and a TV-L case presented as one authority. Amend `source_detail` to name `§ 16 Abs. 2 TV-L` for the BAG case and to state that the BVA catalogue covers the federal agreement.

The entry is otherwise disciplined: no pay groups, no steps, no numbers, and the `unverified` note correctly refuses to claim discretionary recognition of *förderliche Zeiten* on an unreachable circular. That restraint is right — keep it.

*Staleness: medium. The Definitionskatalog is a versioned publication (note the URL filename still reads `20150722` while the content is the tenth edition); the URL will eventually serve a newer edition or move.*

---

### 7. `de-application-is-a-file-not-a-cv` — **KEEP-WITH-EDIT (ship-blocker)**

Both Bundesagentur pages verify the quoted strings exactly: `Arbeitszeugnisse: Diese sollten Sie möglichst von jedem ehemaligen Arbeitgeber vorlegen.`; `Konzentrieren Sie sich auf das, was für die jeweilige Stellenanzeige wichtig ist.`; `In der Stellenanzeige erfahren Sie, wie Sie sich bewerben sollen…`; `Scannen Sie Zeugnisse und Bescheinigungen ein. Bei einer Bewerbung per Post verschicken Sie keine Originale sondern Kopien.`; `Originale bleiben stets bei dir.`; and the optional Deckblatt / Motivationsschreiben / Anlagenverzeichnis list.

**(a) SHIP-BLOCKER: Cyrillic contamination in `text_zh`.** The string reads `「证明материалы可另行索取」`. `материалы` is Russian. This renders verbatim to the job-seeker. Fix to `「证明材料可另行索取」`.

**(b) The entry quotes half of a two-part instruction and drops the half that pulls the other way.** Immediately above the sentence the entry cites, the same page says `Weisen Sie Ihre Qualifikationen mit Zeugnissen, Zertifikaten oder Arbeitsproben nach. **Beschränken Sie sich dabei auf die für den Job notwendigen Nachweise.**` The agency says attach references from every former employer *and* limit yourself to what the job needs. The entry renders only the maximalist half, which will push a candidate toward a bloated pack. Add the counterweight.

**(c) Unsourced perception claim.** "A bare CV with references 'available on request' reads *here* as an incomplete file" — no source. It is a plausible inference from the guidance, but it is stated as a fact about how German readers react. Recast as guidance, or move to `unverified`.

**(d) Partial duplication with `application_artifacts`,** which covers the same composition in more detail with the same citations. Not a defect, but the convention should carry the *reading* (the letter is screened against the ad; missing references register as a gap) and let the artifacts field carry the inventory. The sentence "Send scans and keep your originals, and use the channel the employer specifies" is submission mechanics, already in `application_artifacts`, and is the closest thing in this table to a layout rule — cut it here.

Replacement final sentences of `text_en`:

> … and says work references should ideally be supplied from every former employer, together with the qualification and further-training certificates relevant to the post — while also telling you to limit the attachments to the evidence the job actually needs, so the pack is complete rather than merely thick. Treat a bare CV with references "available on request" as an incomplete file by the standard this guidance sets, not as a normal submission.

Replacement final sentences of `text_zh`:

> ……同时说明工作证明最好能提供每一位前雇主出具的那一份，另附与该岗位相关的学历与进修证书；但同一份指引也要求把附件限制在这份工作确实需要的凭证范围内——要的是「齐全」，不是「厚」。按这份指引的标准，一份光秃秃的履历加上一句「证明材料可另行索取」，属于材料不齐，而非常规做法。

*Staleness: medium. Agency guidance pages get rewritten; the quoted strings should be re-greppable before each ship.*

---

### 8. `de-dach-reference-letters-do-not-transfer` — **KEEP-WITH-EDIT**

The Austrian half is verified verbatim at RIS, exactly as the entry's parenthetical claims (`Der Dienstgeber ist verpflichtet, bei Beendigung des Dienstverhältnisses dem Angestellten auf Verlangen ein schriftliches Zeugnis über die Dauer und die Art der Dienstleistung auszustellen. Eintragungen und Anmerkungen im Zeugnisse, durch die dem Angestellten die Erlangung einer neuen Stelle erschwert wird, sind unzulässig.`, `Zuletzt aktualisiert am 06.07.2023`). The Swiss half verifies fully at SECO: Art. 330a OR, `jederzeit`, Vollzeugnis vs Arbeitsbestätigung, `wahrheitsgetreue Aussagen`, `wohlwollende Formulierung`, and rejection of `Zeugniscodes`.

**Overreach — the statute is made to say more than it says.** § 39 AngG sets a *minimum* content and bars *harmful* entries. It does not bar a favourable performance assessment, and nothing cited supports "pressing for one graded German-style asks for something the statute discourages." What the statute discourages is content that makes it harder to find work — the opposite of a positive grading. "Conventionally carries no performance grading at all" is additionally an unsourced prevalence claim about Austrian practice; ZH's `根本不含` ("contains absolutely none") is, if anything, firmer than the English. Both need softening to what § 39 actually establishes: the *entitlement* covers only duration and kind, so a grading is not something you can demand.

Also worth adding from SECO, since the entry's "truthful and benevolent" could mislead: `Negative Tatsachen dürfen im Zeugnis erwähnt werden, sofern sie für die Gesamtbeurteilung des Arbeitnehmers erheblich sind` — a Swiss certificate may carry negatives where material.

Replacement for the Austrian clause in `text_en`:

> … and it expressly prohibits entries and annotations that would make it harder for you to obtain a new position. So what you can *demand* in Austria is duration and kind — a performance grading is not part of the entitlement, and an Austrian certificate that carries none is a compliant document, not a withheld one.

Replacement for the Austrian clause in `text_zh`:

> ……并且明文禁止写入任何会使你更难找到新工作的记载与批注。因此在奥地利，你能够「要求」到的内容就是时长与种类——表现评级不在请求权范围内；一份不含评级的奥地利证明是合规文件，不是雇主有意扣着不给。

Same softening applies to the `DACH CAVEAT` paragraph in `application_artifacts`, which repeats the inference.

*Staleness: low.* **Link-rot flag:** the SECO URL now 301s to `https://www.seco.admin.ch/de/faq-arbeitszeugnis`. The cited URL still resolves, but update it.

---

### 9. `de-dach-ch-permit-is-employer-filed-and-capped` — **KEEP**

Both sources verify on every limb. SEM: `Der Arbeitgeber hat nachzuweisen, dass auf dem inländischen Arbeitsmarkt … und auf den Arbeitsmärkten der EU/EFTA-Länder keine für die zu besetzende Stelle geeigneten Personen zur Verfügung stehen`; `Führungskräfte, Spezialistinnen und Spezialisten sowie andere qualifizierte Arbeitskräfte`; `orts-, berufs- und branchenüblichen`; annual `Höchstzahlen`. Kanton Zürich: `Das Gesuch … ist vom Arbeitgeber beim Amt für Wirtschaft (AWI) einzureichen`; `Kontingente sind Höchstzahlen die jährlich vom Bundesrat festgelegt werden`. Clean scan — the only entry with zero number-word hits in either language.

*Staleness: **high, yearly**, and demonstrably so — the SEM page links `Höchstzahlen für die Kontingentsperiode 2026 (19.11.2025)` while the Kanton Zürich page still prints 2025 quota figures. The entry is right to carry no numbers; that is what keeps it shippable.*

---

### 10. `de-dach-at-advertised-pay-is-a-floor` — **KEEP-WITH-EDIT (source upgrade available now)**

The 2013 GAW leaflet verifies verbatim (`In der Ausschreibung ist das durch Gesetz, Kollektivvertrag oder andere Normen der kollektiven Rechtsgestaltung festgelegte Mindestentgelt als Betrag anzugeben und auf eine Bereitschaft zur Überzahlung hinzuweisen, wenn eine solche besteht`; `Der bloße Hinweis auf den anzuwendenden Kollektivvertrag ("Bezahlung laut Kollektivvertrag") oder vage Angaben … sind unzulässig`; `Stand August 2013`).

**The entry's own unverified item 7 can be closed right now.** I fetched the current consolidated GlBG § 9 at RIS (HTTP 200): the obligation is live and the wording matches. Better, the statute contains a sentence stronger than anything the leaflet offers and directly on the entry's thesis: `In der Stellenausschreibung ist jenes Entgelt anzugeben, das als **Mindestgrundlage für die Arbeitsvertragsverhandlungen** zur Vereinbarung des Entgelts dienen soll.` That is the statute itself saying the printed figure is the floor of the negotiation. Replace the primary citation with:

> Rechtsinformationssystem des Bundes (RIS), "Gleichbehandlungsgesetz § 9", Bundesrecht konsolidiert, https://www.ris.bka.gv.at/NormDokument.wxe?Abfrage=Bundesnormen&Gesetzesnummer=20003395&Paragraf=9, retrieved 2026-08-09 — § 9 Abs. 2 obliges the employer or recruiter to state in the advertisement the minimum pay applicable under the collective agreement, statute or other norms of collective regulation and to point out a willingness to overpay where one exists; the pay stated is the one that is to serve as the minimum basis for the contract negotiations; the duty extends to sectors without such a minimum, excepting employees under § 10 Abs. 2 Z 2 Arbeiterkammergesetz. GAW leaflet retained as a plain-language gloss on non-compliant formulations.

**Overreach:** the duty is stated flatly, but the statute carves out senior executives (`ausgenommen Arbeitnehmer/innen gemäß § 10 Abs. 2 Z 2 Arbeiterkammergesetz 1992`) in sectors with no collective minimum. Add one clause: "the exception runs to senior executive roles in sectors that have no collective minimum, so a management posting without a figure is not automatically non-compliant."

**zh/en drift:** ZH `并注明雇主是否愿意在此之上加付` = "state *whether* the employer is willing to pay above it", implying a duty to declare either way. Statute and EN both condition it: `wenn eine solche besteht` / "any willingness". Replace with `并在雇主确有加付意愿时予以注明`.

*Staleness: low once re-anchored on RIS.*

---

## Cross-cutting

- **Scope:** three of ten entries (`dach-reference-letters`, `dach-ch-permit`, `dach-at-advertised-pay`) are not about Germany. Each has a gating `applies_when`, which is the right mitigation — but if the renderer prints the whole `de` table regardless, a German-market applicant reads Swiss quota advice as if it applied to them. Confirm the renderer honours `applies_when` before shipping, or prefix those three visibly.
- **Number-word linting:** if the constraint is checked mechanically, whitelist grammatical `一`/`两` and English articles, or you will get unactionable noise on nine of ten entries. The true counting hits are only: `two different things` / `two different bodies` / `两回事` / `两套机构` (entry 2) and `Two practical consequences` / `两个实际后果` (entry 4), both fixed above.
- **Honesty audit of the `unverified` section: it holds up.** I re-tested both "unreachable" URLs. `bmi.bund.de/…/RdSchr_20240530.html` still returns HTTP 400. `make-it-in-germany.com/…/bewerbung` returns HTTP 200 but the body is a Radware interstitial (confirmed by grep), not content. The entry's account is accurate.
- **One `unverified` item is wrong, though:** item 4/the artifacts field claim no official source could be found on the Bewerbungsfoto. The source is the page the entry already cites: `Ein Bewerbungsfoto ist zwar keine Pflicht mehr, jedoch in vielen Branchen weiterhin üblich. In Deutschland wollen die meisten Personalverantwortlichen immer noch vorab sehen, mit wem sie es zu tun haben.` Correct the note. Whether it becomes a convention is a separate judgement — a CV photo is arguably a layout matter, and the same page's treatment of anonymised CVs turns on gender and origin, so an entry built here risks the protected-trait constraint. Flagging rather than prescribing.

## Important and missing

1. **Blue Card lower salary threshold.** § 18g(1) sentence 2 (verified today) sets a reduced threshold for named ISCO occupation groups — which include ICT and engineering families — and for anyone whose degree is recent. Entry 3 says "a threshold", singular. A candidate below the general figure may wrongly conclude they are ineligible when they sit in a shortage group. Highest-value gap in the set.
2. **Job change while holding a Blue Card.** § 18g(4) (verified today): no immigration-authority permission is needed for a job change, but during the first months of employment the authority may suspend and refuse it. This table's user is by definition someone applying to a new employer; a Blue Card holder applying out of their current job has a hard constraint here and nothing in the entry mentions it.
3. **KSchG small-business exclusion (§ 23).** Covered above under entry 5; listing separately because it also changes how a candidate should price probation and notice terms at a small employer.
4. **§ 81a is not universally available** — restricted to the residence purposes the provision enumerates, and it is initiated by agreement between employer and authority, so an employer with no such Vereinbarung cannot simply opt in late. Entry 3 reads as if the route is always on the table.
5. **The Anschreiben's status at international employers.** The entry flags this honestly in `unverified` item 3 and then writes the convention as though the letter is universally screened. Since large international tech employers in Germany routinely run CV-only ATS flows, the gap between "the federal agency treats it as standard" and "this employer wants one" is the operative question — and `applies_when` already half-concedes it ("not routed through an employer portal which explicitly asks for a CV only"). Either source the practice or move the strength of the claim into `applies_when`.