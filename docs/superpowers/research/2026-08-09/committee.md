# What is genuinely additive in AI-Career-Committee-OS-v1 vs. the `job-application` skill

**Provenance note.** Every quote below is byte-copied from the file and line range named above it. I read: `prompts/00`–`12` (13 files), `quality/scoring_rubric.md`, `quality/evaluator_checklist.md`, `quality/anti_hallucination_rules.md`, all 5 `templates/*.md`, `examples/sample_final_report.md`, `inputs/job_search_preferences.md`, `inputs/INPUT_OPTIONS.md`. For the comparison side I read `/Users/donghanglyu/.claude/skills/job-application/SKILL.md` (218 lines), `references/interview-prep.md`, `references/gap-analysis.md` §4 FIT SNAPSHOT, and grepped the whole skill for salary/discovery/roadmap coverage. Absence claims are backed by that grep, whose command and output are shown in section 8.

---

## 0. Headline

| Product component | Verdict |
|---|---|
| Job DISCOVERY pipeline (prompt 12 + shortlist template + preferences input + risk-control rules) | **Genuinely additive.** Nothing in `job-application` searches for jobs. |
| Boss-Zhipin risk-control / platform-limit handling | **Genuinely additive and the single best-written thing in the product.** |
| Score-consistency gates (`scoring_rubric.md:56–67`) | **Additive as a verdict gate**, not as a score gate. Reusable after a mechanical re-anchoring. |
| `anti_hallucination_rules.md` job-collection section | **Additive.** Discovery-specific provenance rules `job-application` has no analogue for. |
| Salary negotiator (07) | **Additive but thin.** Worth a reference file, not a judge. |
| Career coach (06) + 30/60/90 + 6-month roadmap | **Additive.** `job-application` ends at the application; nothing plans beyond it. |
| Industry analyst (08) | **Mostly filler.** Explicitly forbidden from having data, then asked to forecast. |
| Technical lead (05) | **~70% redundant** with the Hiring Manager judge. The 30% that isn't is mock-interview fuel. |
| Debate moderator (09) | **Structurally redundant** with the existing actor–critic merge, and carries a quota that manufactures theatre. |
| Interview probability bands | **Rejected by the owner** — and note this is load-bearing for the JD-fit gate (§3). |
| ATS screener (02), HR recruiter (03), hiring manager (04), report writer (10), PDF packager (11), input-options (INPUT_OPTIONS.md) | **Redundant.** Do not carry over. See §8. |

---

## 1. The committee roles beyond ATS / recruiter / hiring-manager

### 1.1 Technical / professional reviewer — `prompts/05_technical_lead.md`

**Unique question it answers:** *Is the technical evidence on this CV real, and where will the candidate be broken open in the technical interview?*

**What the prompt actually instructs** (`05_technical_lead.md:9–42`): three assessment axes — 技术真实性 (project realism: "是否只是课程项目或教程复刻", "是否能解释架构、权衡、失败和优化"), 技术深度 (fundamentals, system design, engineering practice, data/experiment/eval, debugging, security/perf/maintainability awareness), 面试风险. It outputs a 0–100 准备度 score with 5 bands, a **项目真实性检查** table with the columns `| 项目 | 可信证据 | 可疑点 | 面试追问 |` (`05:62–64`), a **最可能被问倒的问题** list of 5, and a 本周/30/60/90 remediation ladder (`05:73–78`). Line 7 generalises it off software: "如果目标岗位不是技术岗，你仍然要评估岗位所需的硬技能、工具能力、分析能力或作品能力."

**Verdict — sceptical.** The *judging* half is already covered. `job-application`'s Hiring Manager judge scores `evidence` and `credibility` explicitly including "**no scope inflation** (claimed seniority/leadership/ownership the evidence doesn't support)" and "no suspected fabrication" (`agents/hiring-manager.md:37,39`). Adding a fourth judge whose job is "is this project real" duplicates that lane and will produce correlated verdicts — you would be paying a subagent to agree with the Hiring Manager.

What is **not** duplicated is the two output artifacts: the 项目真实性检查 table (per-project 可疑点 → 面试追问) and the "top 5 questions that will break you". Those are exactly the raw material the **MOCK INTERVIEW** module needs, and `job-application` deliberately refuses to produce them — `references/interview-prep.md:38` reads verbatim:

> - **Keep it thin.** This is a defense brief generated from data you already hold — not a mock-interview module. A page or less.

**Recommendation:** do **not** add a tech-lead judge. Lift the 项目真实性检查 table and the "最可能被问倒的问题" generator into the mock-interview module as a question-source, fed by the Hiring Manager's existing evidence/credibility findings.

### 1.2 Career strategy coach — `prompts/06_career_coach.md`

**Unique question it answers:** *Given this person's constraints and opportunity cost, should they apply at all right now — or reposition, ramp, or pivot first?*

**What the prompt actually instructs** (`06:17–41`): 路径匹配 (narrative coherence of a pivot, whether the role is a usable next step), 机会成本 (time, cash-flow risk, market window, **签证/身份/地域约束**, family, psychological load), and then it **forces a single main strategy** from a closed set of five (`06:35–41`):

> - 边投边补：快速投递测试市场反馈
> - 重新定位：先重写职业定位再投递
> - 能力冲刺：先集中补 30-90 天
> - 相邻岗位切入：换更容易进入的相邻岗位
> - 方向重置：重新选择职业方向

Output includes 最适合的岗位类型 (3), **不建议优先投递的岗位** (3), a 30/60/90 table with 验收标准, a 6-month roadmap, and "如果只能做 3 件事". The prohibitions are good (`06:74–78`): "不要空泛鼓励 / 不要忽略现实约束 / 不要把所有路径都说成可行".

**Verdict — genuinely additive, and it is the natural home of the FIT ASSESSMENT module's *second half*.** `job-application`'s FIT SNAPSHOT already answers "should I apply to *this* posting" via its APPLY VERDICT (`gap-analysis.md:267`: `strong apply / worth applying / stretch / likely screen-out`). It answers nothing about *what to do instead*, and nothing survives the application. The five-way 主策略 forced choice is a good mechanism — it prevents the "here are seven options, all viable" non-answer that the prompt itself bans at line 78.

**Caveat:** the closed set overlaps `job-application`'s existing apply verdict (边投边补 ≈ strong apply; 能力冲刺 ≈ stretch/likely screen-out). If you carry both, reconcile them into one axis or the user sees two verdicts that can disagree — the same failure mode `gap-analysis.md:276` already warns about for two coverage numbers.

### 1.3 Salary & negotiation advisor — `prompts/07_salary_negotiator.md`

**Unique question it answers:** *What is this candidate's leverage, and what will get them lowballed?*

**What the prompt actually instructs** (`07:8–30`): a hard boundary first — "如果缺少地区、行业、级别或公司信息，不要编造精确数字" — then it outputs **grades, not numbers**:

> - 薪资定位等级：偏低 / 市场中位 / 中高 / 高竞争力
> - 谈薪筹码：强 / 中 / 弱
> - 风险：可能被压价的原因
> - 准备材料：谈薪前需要整理的证据

and gates numeric ranges behind evidence (`07:30`): "只有当输入中有明确地区、岗位和级别时，才可以谨慎给出区间，并声明这是估算." Prohibitions (`07:61–65`): "不要编造市场薪资数据 / 不要承诺用户一定能拿到某个薪资 / 不要鼓励虚报薪资." Output also has a three-phase 谈薪策略 (面试前 / Offer 前 / Offer 后).

**Verdict — additive, but not a judge.** `job-application` touches salary in exactly two places, both passive: `references/job-posting-extraction.md:35` ("if `salary_range` is present, ask the user **once** whether it fits their expectation … if no range is stated, don't ask") and the Recruiter judge's `logistics` score (`agents/recruiter-screener.md:41`). Neither builds leverage or prepares a negotiation.

**But be sceptical about scope.** Negotiation happens *after* an offer, which is outside the arc of a skill that ends at "interview-ready package." Bolting a negotiator judge onto the review loop would have it evaluate a CV, which is not what it is for. The genuinely reusable core is small and belongs as a reference file invoked on demand: the **grade-not-number rule** (07:25–30), the **可能被压价的原因** enumeration, and the fact that grades degrade gracefully when region/level are unknown — which is precisely the pattern the owner is applying to interview probability. It is the same doctrine, already implemented, and worth quoting as precedent.

### 1.4 Industry & role-trend analyst — `prompts/08_industry_analyst.md`

**Unique question it answers:** *Is this role a career accelerator or a detour over 6–12 months?*

**What the prompt actually instructs** (`08:8–46`): it opens by removing its own evidence base —

> 如果没有实时联网数据，不要声称自己掌握最新市场事实。只能基于用户输入、常识性行业逻辑和明确标注的不确定性进行分析。

— then asks for judgments on 岗位是否处于增长方向, 行业门槛是否变高, **AI 自动化是否影响岗位**, market window. Its one real mechanism is a five-way 路径价值 classification (`08:42–46`): 职业加速器 / 稳健台阶 / 过渡桥 / 高风险押注 / 低价值绕路. Prohibitions: "不要装作有实时市场数据 / 不要把热门行业等同于适合用户".

**Verdict — largely filler, and the most hallucination-prone role in the product.** A prompt that forbids itself real data and then asks for "未来 6-12 个月风险" is structurally an invitation to produce confident-sounding market commentary with no provenance — the exact defect class the owner's `no-fake-info-in-content` doctrine targets. Note the product's own `anti_hallucination_rules.md:31` bans 招聘政策 and `:30` bans 市场薪资, but nothing bans "this field is growing" — the analyst sits in the one gap the anti-hallucination file leaves open.

**Salvage:** the 路径价值 five-way label is a legitimately useful one-line output *if and only if* it is grounded — either in the posting text itself (`job-application` already extracts `responsibilities`, `keywords`, `red_flags` per `SKILL.md:71`) or in a live `WebSearch` with cited URLs. As a standalone LLM-opinion agent, cut it.

### 1.5 Committee debate moderator — `prompts/09_committee_debate.md`

**Unique question it answers:** *Where do the reviewers actually disagree, and which initial judgment was wrong?*

**What the prompt actually instructs** (`09:19–52`): five **named, pre-scripted cross-examinations**, not a generic "debate now". Verbatim examples:

> ### ATS 机器筛选官质疑 HR 初筛官
> 如果 HR 推荐进入面试，但 ATS 分数低，必须解释：
> - 为什么机器筛选可能先挡住用户？
> - 简历应该如何改才能让 HR 看到？

> ### 用人经理质疑职业策略教练
> 如果职业策略教练建议转型或投递，用人经理必须质疑：
> - 用户是否能在真实团队中立刻创造价值？
> - 转型叙事是否可信？

Output: a 主要分歧 table `| 分歧点 | 支持观点 | 反对观点 | 最终修正 |`, plus 被下调的判断 / 被上调的判断 / 仍然无法确定的事项. Requirements at `09:80–82`:

> - 至少提出 3 个真实质疑
> - 至少修正 1 个初始判断，除非所有证据都非常一致
> - 不要为了形式而辩论

**Verdict — structurally redundant, with one idea worth stealing.** `job-application` already resolves cross-judge conflict, just without ceremony: `SKILL.md:154` makes the orchestrator the actor, and `SKILL.md:181` instructs it to "Merge the `TOP_FEEDBACK` from all three judges … and apply edits that address **only the flagged points**." Adding a moderator agent inserts a serialisation point into a loop whose whole speed argument is parallelism ("The speed comes from parallel critics + targeted edits, not from spawning more agents" — `SKILL.md:154`).

Be sceptical of the quota too: "至少修正 1 个初始判断" instructs the model to change *something* whether or not anything is wrong. That manufactures a revision to satisfy a counter — the same lint-dodging pattern the owner has flagged before. And the "不要为了形式而辩论" line at `09:82` directly contradicts the quota two lines above it.

**Worth stealing:** the *conditional* conflict rules — specifically the ATS-vs-HR one, which encodes a real asymmetry (a human reviewer approving a CV a machine will never surface). That is one `if` statement in the orchestrator's merge step, not an agent.

---

## 2. Score-consistency gates — `quality/scoring_rubric.md:56–67`, verbatim

```markdown
## 分数一致性要求

如果给出高分，必须出现强证据。

如果出现以下情况，不得给高分：

- 没有 JD
- 没有简历
- 简历或 JD 文件无法读取
- 主要材料来自模糊、裁切或缺页截图
- 简历只有技能列表没有项目证据
- 岗位核心技能完全缺失
- 目标岗位和背景跨度过大且无转型证据
```

**Why this is the reusable part.** Every item is a *material* precondition, not a score calibration. Six of the seven describe an input defect or an evidence void; none require a number to be meaningful. Read them as: **"a confident positive verdict is forbidden when the inputs cannot support one."** They are the missing floor under `job-application`'s APPLY VERDICT — which today has no rule preventing "strong apply" from being emitted off a blurry screenshot.

**How they translate once numeric scores are dropped.** The clean mapping is gate → verdict ceiling, i.e. these conditions cap the FIT verdict at `stretch` / `insufficient evidence` and block `PASS` from any judge:

| Gate condition (verbatim) | Already covered in `job-application`? |
|---|---|
| 没有 JD | Partly — `SKILL.md:70` already terminates: "if no posting can be obtained at all … stop gracefully and say so — never invent a posting". |
| 没有简历 | Covered — Step 1 builds one by interview (`SKILL.md:53–56`). |
| 简历或 JD 文件无法读取 | **Partly.** `SKILL.md:69` catches the login-wall case for postings only. No rule for an unreadable CV file. |
| 主要材料来自模糊、裁切或缺页截图 | **NOT covered.** No OCR/screenshot path exists in `job-application` at all. |
| 简历只有技能列表没有项目证据 | **Nearly covered** — `gap-analysis.md:276`: "a keyword in the Skills list with no supporting bullet is partial, not strong". That rule grades a single must-have; it does not cap the overall verdict when the *whole CV* is a skills list. |
| 岗位核心技能完全缺失 | Covered by the honest-gap early-stop (`SKILL.md:186`). |
| 目标岗位和背景跨度过大且无转型证据 | Partly — `candidate-situations.md` handles domain switches; nothing hard-blocks a high verdict. |

**Two of the seven are genuinely new capability, and both come from the screenshot/OCR input path** the product supports and `job-application` does not. If the new skill accepts screenshots (it must, for the Boss-Zhipin discovery path), these two gates are mandatory, not optional.

**Do not carry over** the five band tables above them (`scoring_rubric.md:5–53`, 简历表达分 / ATS 匹配分 / 岗位匹配分 / 技术准备度 / 职业适配分) — those are the numeric scores being dropped. The 建议等级映射 at `:69–75` is also number-anchored ("多数分数 80+") and dies with them.

---

## 3. The JD-fit gate that auto-triggers job collection

This gate exists in **two places with two different condition lists**, and they do not match. Both verbatim.

### 3.1 Master controller — `prompts/00_master_controller.md:58–82`

```markdown
## 目标 JD 适配性闸门

如果用户提供了目标 JD、目标公司、岗位截图或额外求职背景，必须先完成当前 JD 的适配性判断，然后再决定是否搜集替代岗位。

必须输出：

- JD 岗位匹配分
- ATS 匹配分
- 技术/专业准备度
- 职业路径匹配分
- 面试概率区间
- 最终投递建议
- 是否触发岗位搜集
- 触发原因

以下任一情况出现时，判定为「不适合或低适配」，必须自动触发岗位搜集：

- 最终建议为「暂不建议」
- 最终建议为「方向不匹配」
- `JD 岗位匹配分 < 65`
- 面试概率区间为 `0-10%` 或 `10-25%`
- 最终建议为「可以冲刺」且 `JD 岗位匹配分 < 70`

触发岗位搜集后，应优先使用 Boss 直聘 MCP 搜集约 15 个更匹配岗位。如果当前环境没有 MCP，先尝试自动设置；只有无法完成时才使用手动岗位材料降级。
```

### 3.2 Job collector — `prompts/12_boss_zhipin_job_collector.md:36–47`

```markdown
## 触发条件

在以下任一情况出现时，必须运行本岗位搜集官：

1. 目标 JD 被判定为「暂不建议」或「方向不匹配」。
2. `JD 岗位匹配分 < 65`。
3. 面试概率区间为 `0-10%` 或 `10-25%`。
4. 目标 JD 为「可以冲刺」且 `JD 岗位匹配分 < 70`。
5. 用户主动启用了岗位搜集。
6. 用户提供了多个候选岗位、岗位截图或岗位列表。

运行时必须先说明触发原因，例如「原 JD 低适配，因此自动搜索更合适岗位」。
```

Prompt 12 has conditions 5 and 6 (user-enabled, multiple JDs supplied) that prompt 00 omits; prompt 00 folds them into a looser clause at `00:19–21`. `inputs/job_search_preferences.md:13–19` adds the third input: `是否启用：自动 / 是 / 否`, where 否 still allows a trigger ("但如果当前 JD 明显不适合，系统仍会建议并可触发替代岗位搜索").

**The mechanism is the additive part — the thresholds are not portable as written.** Three of the five auto-trigger conditions reference the two things being dropped: `JD 岗位匹配分 < 65` / `< 70` (numeric score) and `面试概率区间为 0-10% 或 10-25%` (rejected probability bands). Carried over literally, the gate never fires.

The honest re-anchoring uses what `job-application` already produces — `gap-analysis.md:267`'s four-way APPLY VERDICT, which is a categorical version of the same axis:

- `likely screen-out` → auto-trigger discovery (maps to 「暂不建议」/「方向不匹配」)
- `stretch` → auto-trigger (maps to the 「可以冲刺」且 <70 clause)
- honest-gap early-stop fired (`SKILL.md:186`) → auto-trigger; the candidate genuinely lacks must-haves, which is exactly "岗位核心技能完全缺失" from §2
- user-enabled, or ≥2 postings supplied → run discovery in ranking mode

**Keep verbatim regardless of thresholds:** `12:47` — "运行时必须先说明触发原因" — and the 触发原因 field in the report (`final_report_template.md:25`, `job_shortlist_template.md:13–19`). A gate that fires silently is indistinguishable from a model that felt like searching.

---

## 4. Job-shortlist template and A/B/C/D prioritisation

**File:** `templates/job_shortlist_template.md` (207 lines). Section structure: `0. 搜索来源与读取质量` → `0.1 触发原因` → `1. 用户岗位画像` → `2. 搜索策略` → `3. Top 候选岗位总表` → `3.1 Top 15 岗位完整详情` → `4.–7. A/B/C/D` → `8. 简历微调方向` → `9. 打招呼话术草稿` → `10. 今天可以做的 5 件事` → `11. 不确定性`.

### 4.1 Fields

**Summary table** (`job_shortlist_template.md:58–59`) — 11 columns:

```
| 排名 | 推荐等级 | 岗位 | 公司 | 城市 | 薪资 | 经验 | 匹配度 | 回音可能性 | 成长价值 | 岗位链接/来源 |
```

**Per-job detail block** (`:80–94`), with the anti-fabrication instruction at `:78` — "每个岗位都必须填写；如果某个字段缺失，写「未显示」，不要编造":

```
- 推荐等级：
- 城市：
- 薪资：
- 经验要求：
- 学历要求：
- 技能/关键词：
- 招聘者/来源标识：
- 岗位链接或可追溯来源：
- 岗位摘要：
- 为什么匹配：
- 主要风险：
- 简历微调：
- 下一步动作：
```

### 4.2 Ranking logic — `prompts/12:136–146`

```markdown
## 岗位评分维度

每个岗位必须给出以下分数：

| 维度 | 分数 | 说明 |
|---|---:|---|
| 岗位匹配度 | 0-100 | 简历证据与岗位要求的匹配程度 |
| 回音可能性 | 0-100 | 基于经验、薪资、城市、JD 门槛的推断，不是保证 |
| 成长价值 | 0-100 | 对未来 6-12 个月能力和履历的帮助 |
| 投递优先级 | A/B/C/D | A 最高，D 不建议 |

如果原 JD 被判定为不适合，本轮候选岗位必须明显比原 JD 更稳，不能只是标题相似。
```

That last line (`12:146`) is the real ranking constraint and the one worth keeping verbatim — it blocks the failure mode where "find me better-fitting jobs" returns fifteen postings with the same title as the one that just failed.

**The four buckets are defined by their table columns, not by score cutoffs** — each class asks a different question, which is why the classification survives the loss of 0–100 scores:

| Class | Definition line | Columns (= what the class is *for*) |
|---|---|---|
| A 优先尝试 | `:132–137` "这些岗位应该优先投递或优先沟通" | `\| 岗位 \| 为什么优先 \| 简历要改哪里 \| 打招呼重点 \|` |
| B 可以尝试 | `:140–145` "可以投，但不应占用过多准备时间" | `\| 岗位 \| 适合点 \| 不确定性 \| 投递策略 \|` |
| C 冲刺 | `:148–153` "有机会，但当前证据不足或门槛偏高" | `\| 岗位 \| 冲刺原因 \| 最大缺口 \| 补强动作 \|` |
| D 暂不建议 | `:156–160` | `\| 岗位 \| 不建议原因 \| 替代方向 \|` |

**Assessment.** A/B/C/D is not effort-allocation garnish — B's column is 投递策略 (spend less time), C's is 补强动作 (close a gap first), D's is 替代方向 (go elsewhere). It maps cleanly onto `job-application`'s existing four-way apply verdict (`strong apply / worth applying / stretch / likely screen-out`), so the new skill should **use one vocabulary for both**, not two. `回音可能性 0-100` should be dropped with the probability bands — it is a fabricated number by construction ("基于……的推断，不是保证" is a disclaimer, not a source), and `anti_hallucination_rules.md:106` already forbids treating it as real. 匹配度 and 成长价值 survive as ordinal labels.

**Two rules here are additive and safety-relevant** — `12:163–174`:

```markdown
## 打招呼规则

默认只生成话术草稿，不自动发送。

如果用户要求发送打招呼，必须先输出：

1. 准备发送的岗位。
2. 招聘者名称或标识。
3. 完整话术。
4. 可能风险。

然后明确询问用户是否确认发送。没有确认，不得调用发送或打招呼工具。
```

---

## 5. `quality/anti_hallucination_rules.md` and `quality/evaluator_checklist.md` — in full

### 5.1 `quality/anti_hallucination_rules.md` (lines 1–114, complete)

```markdown
# 防幻觉规则

## 基本原则

没有输入证据，就不要当事实。

## 必须标注不确定性的情况

以下情况必须写明「无法准确判断」或「需要补充信息」：

- 没有目标 JD
- 没有目标地区
- 没有目标公司
- 没有工作年限
- 没有项目细节
- 没有薪资地区和级别
- 没有明确职业目标
- 没有时间和现金流约束
- PDF/DOCX 无法读取或只读取到部分内容
- 截图模糊、裁切、缺页或 OCR 不确定

## 不允许编造

禁止编造：

- 学校排名
- 公司背景
- 市场薪资
- 招聘政策
- 签证政策
- 岗位真实 HC
- 面试流程
- 用户没有写过的项目成果
- 用户没有写过的技术能力
- 图片中无法识别的文字
- PDF/DOCX 中没有成功读取到的内容
- 未实际读取到的招聘岗位
- 未确认仍然开放的岗位状态
- 未提供来源的公司招聘需求
- 招聘者回复概率或面试结果

## 可以合理推断

可以推断，但必须标注为推断：

- JD 隐含要求
- 简历中可能被追问的风险
- HR 可能担心的问题
- 用人经理可能看重的业务价值
- 技术面可能追问的方向

示例：

```text
根据 JD 中反复出现的 X 和 Y，可以推断该岗位可能重视 Z，但由于没有公司内部信息，这一点需要在面试或招聘页面进一步确认。
```

## 薪资规则

没有明确地区、级别、公司类型时，不要给具体薪资数字。

可以给：

- 薪资定位等级
- 谈薪筹码判断
- 谈薪风险
- 需要补充的数据

## 概率规则

不要输出精确概率，比如 37%。

只允许输出区间：

- 0-10%
- 10-25%
- 25-45%
- 45-65%
- 65-80%
- 80%+

## 文件和截图规则

如果用户提供的是截图或图片：

- 只能基于可读文字分析
- 必须说明是否存在识别不确定性
- 不要补全被截掉的内容
- 不要猜测没有显示的岗位要求

如果用户提供的是 PDF/DOCX：

- 如果能提取文字，按文字证据分析
- 如果只能看到版式但读不到内容，要求用户重新上传或粘贴文字
- 如果格式影响 ATS 解析，必须写入 ATS 风险

## 岗位搜集规则

如果岗位搜集被触发或用户启用了岗位搜集：

- 必须写明岗位来源，例如 Boss 直聘 MCP、用户粘贴文本、PDF、DOCX 或截图。
- 必须写明读取时间或本轮分析时间。
- 如果岗位来自截图或复制文本，必须提醒岗位状态可能已经变化。
- 不得编造没有读取到的岗位、公司、薪资、地点、招聘者或 JD 内容。
- 不得编造岗位链接。没有链接时，写明可追溯来源标识，例如 `security_id`、`job_id`、招聘者标识或截图文件名。
- 不得把「回音可能性」写成真实承诺。
- 不得承诺招聘者会回复、会面试或会录用。
- 不得鼓励绕过平台规则、验证码、风控或访问限制。
- 不得在用户未确认的情况下自动打招呼或批量联系招聘者。
- 如果 Boss 直聘 MCP 未安装或不可用，应先尝试按指南自动设置；如果自动设置失败，必须说明失败步骤，再改用用户提供的岗位材料。
- 如果 Boss 直聘 MCP 返回「账户存在异常行为」、安全验证、风控、请求受限或访问过于频繁，必须立即停止自动搜索，不得继续重试或绕过。
- 如果目标是输出 15 个岗位但实际不足 15 个，必须说明不足原因，不要凑数。
- 如果因风控没有拿到真实岗位列表，只能输出岗位方向级 shortlist、搜索关键词和手动采集模板，不能伪造岗位。
- 如果使用 Boss 直聘 MCP 搜集岗位，最终报告和 PDF 必须包含岗位详情和链接/来源标识。
```

**Carry-over judgment on this file:**
- `## 概率规则` (lines 70–80) — **delete.** This is the rejected feature; the file itself is where the bands are defined.
- `## 基本原则`, `## 不允许编造`, `## 可以合理推断` — **conceptually redundant** with `job-application`'s claim-provenance checkpoint (`SKILL.md:89`, `gap-analysis.md:141`), which is stricter (it requires a *named source line*, not just an inference label). Keep the sharper existing rule; the one genuinely new item in the 禁止编造 list is **`- 岗位真实 HC`** (whether a headcount actually exists) plus the four job-posting items — all discovery-specific.
- `## 文件和截图规则` — **additive.** No screenshot/OCR path exists in `job-application`.
- `## 岗位搜集规则` (lines 97–114) — **the most additive block in the whole product.** Every line is a discovery-mode rule with no counterpart, and the two that matter most are `必须写明读取时间或本轮分析时间` (job listings decay) and `不得编造岗位链接。没有链接时，写明可追溯来源标识` (the fabricated-URL defect).
- `## 薪资规则` — additive, small, matches the grade-not-number doctrine.

### 5.2 `quality/evaluator_checklist.md` (lines 1–59, complete)

```markdown
# 最终报告检查清单

生成最终报告前，逐项检查。

## 证据检查

- 是否说明了输入来源：粘贴文字、PDF/DOCX、截图或额外材料？
- 如果使用图片/OCR，是否说明了识别质量？
- 是否引用了简历中的具体项目、技能或经历？
- 是否引用了 JD 中的具体要求？
- 是否说明了哪些判断缺证据？
- 是否区分事实、推断和建议？
- 如果触发了岗位搜集，是否说明了岗位来源、读取质量、MCP 自动设置状态和岗位可能过期？
- 如果使用 Boss 直聘 MCP，是否保留岗位链接或可追溯来源标识？

## 结论检查

- 是否有一句话结论？
- 是否给了明确投递建议？
- 是否给了面试概率区间？
- 是否给了各专家投票？
- 是否说明了最大风险？
- 是否说明了最大优势？
- 是否说明了目标 JD 适配性闸门分数和是否触发岗位搜集？
- 如果触发了岗位搜集，是否给出了约 15 个候选岗位和 A/B/C/D 优先级？

## 可执行性检查

- 简历修改建议是否具体？
- 面试准备建议是否具体？
- 30/60/90 天计划是否有验收标准？
- 岗位推荐是否具体到岗位、公司、城市、薪资、经验、链接/来源、风险和下一步动作？
- 如果生成 PDF，PDF 是否包含 Top 15 岗位详情，而不是只引用 `outputs/job_shortlist.md`？
- 最后的 5 件事是否当天能开始？

## 反泛化检查

删除或重写以下空话：

- 提升综合能力
- 加强学习
- 多准备面试
- 多投递
- 优化简历
- 增强竞争力

每一句都要改成具体动作。

## 风险检查

- 是否避免承诺录用或 Offer？
- 是否避免编造薪资？
- 是否避免虚构公司信息？
- 是否避免虚构招聘岗位或岗位仍然开放？
- 是否避免虚构岗位链接？
- 是否避免承诺招聘者回复或面试？
- 是否避免未确认就自动打招呼？
- 是否避免鼓励用户造假？
- 是否提醒用户结合现实情况判断？
```

**Carry-over judgment:** `## 反泛化检查` is the best section — it is a **named banned-phrase list**, which is the only form of anti-vagueness rule that can be mechanically checked (a grep, i.e. the owner's layer 3). `job-application` bans clichés for CV bullets (`SKILL.md:108`: "results-driven", "proven track record", "synergy", "leveraged") but has no equivalent for *advice* text, which is where the new modules will produce filler. `## 风险检查` is discovery/outreach-specific and additive. Drop the `面试概率区间` line and the `闸门分数` line (numeric). `## 结论检查`'s "是否有一句话结论" is worth keeping as an output shape rule.

---

## 6. The 30/60/90 roadmap template structure

The 30/60/90 pattern appears in **four places**, at three different granularities. Precisely:

**(a) The canonical 30/60/90 table — `templates/final_report_template.md:101–107`:**

```markdown
## 10. 30/60/90 天计划

| 时间 | 目标 | 具体行动 | 验收标准 |
|---|---|---|---|
| 30 天 |  |  |  |
| 60 天 |  |  |  |
| 90 天 |  |  |  |
```

Four columns; the load-bearing one is **验收标准** (acceptance criterion), which is what stops a plan from being a wish list. `evaluator_checklist.md:31` enforces it: "30/60/90 天计划是否有验收标准？". A filled example exists at `examples/sample_final_report.md:134–138` — e.g. `| 30 天 | 修好简历和补 A/B test | 重写电商实习；做 1 个 A/B test 案例；准备 10 道 SQL 题 | 简历可覆盖 JD 80% 关键词 |`.

**(b) Career-coach variant — `prompts/06_career_coach.md:62–64`:** identical four columns, headed `| 时间 | 目标 | 行动 | 验收标准 |`.

**(c) Technical remediation ladder — `prompts/05_technical_lead.md:73–78`:** adds a **本周** rung before 30, which is the better shape for a skill-gap ramp:

```markdown
### 技术补强路线
- 本周：
- 30 天：
- 60 天：
- 90 天：
```

**(d) The separate 6-month roadmap — `templates/career_roadmap_template.md` (42 lines, complete structure):**

- `## 目标` — four target fields: 岗位 / 能力 / 作品 / 投递结果
- `## 月度计划` — `| 月份 | 主目标 | 关键行动 | 输出物 | 验收标准 |`, rows 第 1 月 … 第 6 月 (five columns — adds **输出物**, a required artifact per month)
- `## 每周节奏` — 周一…周末 slots
- `## 作品/项目补强` — `| 项目 | 为什么做 | 要展示的能力 | 完成标准 |`
- `## 投递策略` — 冲刺岗位 / 主投岗位 / 保底岗位 / 不建议投递

The final report also carries a prose 6-month section (`final_report_template.md:109–115`: 第 1-2 / 3-4 / 5-6 个月).

**Assessment.** Genuinely additive — `job-application` produces nothing that lives past submission (its last step is the interview brief, `SKILL.md:208–210`). The two structural ideas worth keeping verbatim are **验收标准** and **输出物**: they convert advice into something checkable, which is exactly the property the `反泛化检查` list is trying to enforce from the other side. The 投递策略 三档 (冲刺/主投/保底) is also the same axis as A/B/C/D — again, unify to one vocabulary.

---

## 7. Boss-Zhipin risk-control handling — verbatim

### 7.1 `prompts/12_boss_zhipin_job_collector.md:86–116` (complete section)

```markdown
## Boss 风控或账号异常时

如果 Boss 直聘 MCP 返回以下信息，必须立即停止自动搜索：

- `账户存在异常行为`
- `您的账户存在异常行为`
- `安全验证`
- `风控`
- `访问过于频繁`
- `请求受限`
- 任何类似平台限制、账号异常或反爬提示

处理规则：

1. 不要继续重试职位接口。
2. 不要切换参数反复请求。
3. 不要尝试绕过验证码、风控、Cookie、设备指纹或平台限制。
4. 不要编造 15 个岗位。
5. 在 `outputs/job_shortlist.md` 和最终报告中写明：Boss 直聘 MCP 已登录，但职位接口被平台限制，本轮未获取真实岗位列表。
6. 输出「岗位方向级 shortlist」，也就是岗位方向、搜索关键词、城市/薪资/经验筛选建议，而不是伪造岗位。
7. 引导用户按 `inputs/jd_files/manual_job_collection_template.md` 手动补 15-30 个岗位。
8. 告诉用户补充岗位后，可以再次运行系统，系统会继续生成 Top 15 真实岗位排序和 PDF。

岗位方向级 shortlist 至少包含：

- 3-5 个主攻岗位方向
- 每个方向的搜索关键词
- 推荐筛选条件
- 为什么这个方向比原 JD 更稳
- 应避开的岗位标题或 JD 信号
- 手动采集岗位时的优先顺序
```

### 7.2 The forced-disclosure form — `templates/final_report_template.md:136–146`

```markdown
### 如果 Boss 风控导致未拿到真实岗位

必须写明：

- 本轮是否成功登录：
- 职位接口返回的信息：
- 是否继续重试：否
- 是否绕过平台限制：否
- 本轮是否生成真实岗位 Top 15：否
- 降级输出类型：岗位方向级 shortlist
- 用户下一步需要补充：使用 `inputs/jd_files/manual_job_collection_template.md` 手动收集 15-30 个岗位
```

### 7.3 Reinforcements elsewhere

- `anti_hallucination_rules.md:111` — "如果 Boss 直聘 MCP 返回「账户存在异常行为」、安全验证、风控、请求受限或访问过于频繁，必须立即停止自动搜索，不得继续重试或绕过。"
- `anti_hallucination_rules.md:112` — "如果目标是输出 15 个岗位但实际不足 15 个，必须说明不足原因，不要凑数。"
- `prompts/12:213` — "遇到平台风控或账号异常时，不要为了满足 15 个岗位目标而编造岗位。"

**Why this is the best-engineered part of the product and should be carried over nearly byte-for-byte.** It is the only place in the product that solves the actual hard problem — *what the model does when it has been told to produce 15 items and cannot get any*. It does four things right at once: (1) a **literal trigger string list**, not "if it seems blocked", so detection is mechanical; (2) an explicit ban on the two escalation instincts (retry, vary parameters) *and* on circumvention (captcha/cookie/device fingerprint); (3) a **named degraded output** — 岗位方向级 shortlist with six required fields — so the model has somewhere to go other than fabrication; and (4) a **pre-filled disclosure form whose answers are hardcoded to 否**, which makes concealment require actively overwriting the template.

That fourth point is the transferable design pattern, independent of Boss-Zhipin: the failure disclosure is a *required artifact with pre-set answers*, so silence is impossible. It generalises directly to LinkedIn/Indeed/any scraped source, and it is the exact backstop shape the owner's own doctrine asks for. `job-application` has one weak analogue (`SKILL.md:69`, the login-wall sanity check) and nothing for rate-limiting, account flags, or degraded output.

**Rename on carry-over:** the trigger strings are Boss-specific and Chinese-only. Keep them as a *platform profile* (a per-source list), with the generic rule — stop on any platform-limit signal, never retry, never circumvent, emit the direction-level fallback, fill the disclosure form — as the source-agnostic layer.

---

## 8. What is redundant and should NOT be carried over

**Evidence for the absence claims.** Command run: `grep -rniE 'salary|compensation|negotiat|薪|30/60/90|roadmap|mock interview|job search|job discovery|shortlist|boss|find jobs|other roles' --include='*.md' .` in `/Users/donghanglyu/.claude/skills/job-application`. Total hits: 10, all shown in the session — 4 salary (posting `salary_range` field + recruiter `logistics` score), 1 exec-search prose, 2 NHS shortlisting prose, 3 candidate-situations/summary. **Zero** hits for job search, job discovery, shortlist, Boss, mock interview, roadmap, 30/60/90.

| Product component | Redundant with | Verdict |
|---|---|---|
| `prompts/02_ats_screener.md` | `agents/ats-screener.md`; `SKILL.md:156` | **Drop.** The existing judge has a structured verdict contract (`VERDICT`/`COVERAGE`/`MISSING_OR_WEAK`/`FORMAT_ISSUES`) and a stated coverage formula (`gap-analysis.md:276`: `(present + 0.5·partial)/total`). Prompt 02 is a prose 0–100 band. Strictly weaker. |
| `prompts/03_hr_recruiter.md` | `agents/recruiter-screener.md`; `SKILL.md:157` | **Drop.** The existing judge additionally owns logistics/eligibility (work authorization, relocation, seniority band) — `recruiter-screener.md:41`. Prompt 03 mentions 签证/入职时间 only as a bullet with no scoring hook. |
| `prompts/04_hiring_manager.md` | `agents/hiring-manager.md`; `SKILL.md:158` | **Drop.** Existing judge covers requirement_match / evidence / clarity / credibility / letter_fit plus `LEVELING` and `STANDOUT_SIGNAL`. Prompt 04's 岗位-经历匹配矩阵 is a subset of the gap table (`gap-analysis.md:21`). |
| `prompts/05_technical_lead.md` (judging half) | Hiring Manager `evidence` + `credibility` (`agents/hiring-manager.md:37,39`) | **Drop as a judge; keep the two output artifacts as mock-interview inputs.** See §1.1. |
| `prompts/09_committee_debate.md` | Orchestrator merge step, `SKILL.md:181`; parallel-critic rationale `SKILL.md:154` | **Drop.** Keep only the ATS-vs-HR conditional as one merge rule. The "至少修正 1 个初始判断" quota should not be carried in any form. |
| `prompts/01_intake_interviewer.md` | Step 0 `AskUserQuestion` (`SKILL.md:32–38`) + Step 1 profile parse (`SKILL.md:43–60`) + Step 2 extraction (`SKILL.md:64–74`) | **Mostly drop.** Exception: the **输入来源清单** table (`01:74–76`) and the conflict rule at `01:30` ("如果同一信息在文字和截图中冲突，优先使用更清晰、更完整、更新的来源") are needed if screenshots become an input. |
| `prompts/10_final_report_writer.md` §"最终评分" (`10:39–49`) | — | **Drop.** Six of seven listed outputs are the numeric scores + probability band being rejected. |
| `prompts/11_pdf_report_packager.md` + `tools/md_to_pdf.py` | `scripts/render_cv.py` / `render_letter.py`, `SKILL.md:112–119` | **Drop the packager.** The existing skill already renders md/docx/pdf with a LaTeX fallback that ships the `.tex`. Prompt 11's genuine rule — `11:55` "不要在没有生成 PDF 时声称已经生成" — is already covered by `SKILL.md:119`. |
| `inputs/INPUT_OPTIONS.md` (Methods A/B/C, `inputs/*.md` file slots) | Conversational intake, `SKILL.md:32–56` | **Drop the whole file-slot ceremony.** It exists because the product is a copy-paste-into-DeepSeek bundle with no filesystem agency. A Claude Code skill reads paths the user names. The one line worth keeping is the accuracy ordering at `INPUT_OPTIONS.md:54–61`: 可复制文字 > PDF/DOCX > 清晰截图 > 模糊截图, plus "如果同时提供文字和文件，AI 应优先使用文字". |
| `templates/resume_rewrite_template.md` | AMPLIFY/REFRAME/KEYWORD-INSERT/HONEST-GAPS plan (`SKILL.md:85`, `gap-analysis.md:196–247`) + `profile.yaml` schema | **Drop.** A Markdown fill-in form is strictly worse than a YAML schema that renders to three formats. Its 项目故事库 table (`:75`) belongs in mock-interview, not here. |
| `templates/interview_plan_template.md` | Partially `references/interview-prep.md` | **Partially additive.** The existing brief is deliberately a claim-defense doc, not a question bank (`interview-prep.md:38`). The template's `| 问题 \| 面试官意图 \| 好答案要点 \| 当前准备情况 \|` table and 项目深挖 table are real MOCK INTERVIEW scaffolding. The 7 天冲刺计划 is filler. |
| `examples/sample_final_report.md` | — | **Do not carry over as an example.** Its numbers (`| 简历表达分 | 72 |`, `| ATS 匹配分 | 76 |`, `面试概率区间 25-45%`, `简历修改后可提升到 45-65%`) are exactly the fabricated-precision pattern being rejected. Retained as a *counter*-example it is useful; shipped as a template it teaches the defect. |
| `inputs/job_search_preferences.md` | — | **Additive but restructure.** The content (city / direction / salary floor / experience & 应届-社招 / industry / company-stage / 外包-驻场 / 大小周 tolerance) is a real discovery-preferences schema `job-application` has no equivalent of, and it belongs in the reusable master profile (`~/.claude/job-profiles/<name>/`), not a fill-in file. Its `是否允许系统自动发送打招呼：默认否，必须单独确认` (`:72`) should become a hard rule, not a preference. |

---

## 9. UNVERIFIED / COULD NOT SOURCE

- I did not read `BOSS_ZHIPIN_MCP_GUIDE_CN.md`, `tools/setup_boss_zhipin_mcp.py`, `START_HERE.md`, `USER_GUIDE_CN.md`, `PRODUCT_MANIFEST.md`, `audits/PRODUCT_SELF_AUDIT_CN.md`, or `seller_assets/*` — outside the requested scope. Any claim about whether the Boss-Zhipin MCP auto-setup **actually works** is therefore unverified; §7 describes only what the prompts *instruct*, not observed behavior. `prompts/12:69–71` names `python3 tools/setup_boss_zhipin_mcp.py` and a `--python` flag, which I read in prompt 12 but did not confirm against the script's own argument parser.
- I have not run any part of either the product or the `job-application` skill. All comparisons are static reads of instruction text. Whether `job-application`'s three-judge loop behaves as its SKILL.md describes is not something this review measured.
- Whether the Boss-Zhipin platform actually returns the six literal trigger strings at `12:88–95` is unverified — I have no access to that API and did not search for it.
- I read only the `## Dimension` table and lane-boundary lines of `agents/hiring-manager.md` and `agents/recruiter-screener.md` (via grep), not those files end to end. Redundancy claims for prompts 03/04/05 rest on those excerpts plus `SKILL.md:152–160`; a full read could surface additional overlap or additional gaps.
- The `travel-buddy` skill is listed twice in this session's skill roster (once unscoped, once scoped to `Documents/career_product/`), which suggests something under `Documents/career_product/` is being treated as a skill directory. I did not investigate; it is unrelated to this analysis but may confuse skill resolution when the new skill is installed there.
