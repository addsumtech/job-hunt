# job-hunt — 接手说明

**当前进度：计划 1 已完整交付并上线；计划 2–5 未开始。**（更新于 2026-08-10）

`apply` 模式可用了：335 项测试全绿，`make check` 通过，`LOSSLESS 1317/1317`（18 条有据豁免），
仓库已软链进 `~/.claude/skills/job-hunt` 和 `~/.codex/skills/job-hunt`，两个 runtime 都能触发。

下一步是**计划 2（assess 模式）**：`docs/superpowers/plans/2026-08-09-2-assess-mode.md`。
执行方式见本文末尾「恢复工作」一节；已知的执行注意事项列在「构建中现场发现的事」。

---

## 这是什么

一个把现有 `job-application` skill 吸收进来、再加三个模式的求职 skill：

```
discover  →  assess  →  apply  →  interview
找什么       该不该投    怎么投     怎么答
```

设计定稿在 `docs/superpowers/specs/2026-08-09-job-hunt-skill-design.md`（468 行，含 14 条决策记录与理由、风险登记册、迁移纪律）。**先读它**，尤其 §2 决策记录——里面每条都写了「为什么」，那是遇到文档没枚举的情况时唯一能推广的东西。

---

## 已经完成的（都在 git 里）

| 内容 | 位置 |
|---|---|
| 设计 spec | `docs/superpowers/specs/` · commit `d4c40ce` |
| 研究产物（市场惯例取证、opencli 实测矩阵、教条保全审计、四份审计 + 四份重审 + 跨查） | `docs/superpowers/research/2026-08-09/` |
| 五份实施计划（28,030 行，约 100 个任务） | `docs/superpowers/plans/` |
| **存量保全** | `job-application` 仓库的 5 个提交 `9404bbe`..`864ad7f` |
| **计划 1 全部 23 个任务** | 已交付并上线，见下节 |

**存量保全**：`~/.claude/skills/job-application` 里那约 1500 行未提交工作（recruiter-screener、
5 个新 reference、rirekisho 渲染器、render_cv 983 行改动）已分组提交为 `9404bbe`..`864ad7f`。
那个仓库**保留作归档，不要删**——`864ad7f` 是无损校验的 baseline。

**历史迁移**已完成：用 `git merge --allow-unrelated-histories` 而不是拷文件，因为「搬运可以、
改写不行」，历史就是搬运的证据。remote `ja` 指向那个归档仓库，别删也别往它推。

---

## 计划 1 交付了什么

`apply` 模式，功能等同原 `job-application`，但六个静默缺陷全部修掉、分层就位、闸门可验证。

```
SKILL.md 530 行（layer 1，每次触发都加载）
modes/apply.md 252 行（layer 1.5，进入 apply 模式时加载）
18 个脚本 · 335 项测试 · Makefile + .github/workflows/checks.yml
```

**六个静默缺陷，每个都实测验证而非声称：**

| 缺陷 | 修复前 | 现在 |
|---|---|---|
| 动机信 PDF | 0 字节，51 测试全绿 | 6,770 字节 |
| Cluster-1 个人数据互锁 | `United States (Los Angeles, CA)` 漏出生日 | 归一化匹配；未知市场带个人数据时大声告警 |
| 判决解析器 | 三个 agent 文件都声称存在，实际不存在 | 畸形 VERDICT 行 fail-closed 成 AMBIGUOUS |
| 陈旧渲染重判 | 产出自我印证的合法判决 | 派发时哈希，不符即该轮作废 |
| claim 溯源检查点 | 不产出任何东西，无法验证是否执行过 | `claims.yaml` + `master-fingerprint.json` |
| 履历书日期 | 空白年/月，静默保存一份无效表格 | 拒绝写出，除非显式 `--allow-blank-dates` |

**外加两处构建中现场发现并关掉的：**

1. `check_skill_lossless` 的 baseline 原本是一个**只存在于本机的 tag**——在任何其他机器上都会
   exit 2，而「跑不了」和「通过了」长得一模一样。改用不可变 commit `864ad7f`，它因迁移 merge
   成了 HEAD 的祖先，任何 clone 都有。
2. SKILL.md 点名了两个不存在的脚本，而守卫只扫 `## Self-check` 段所以无人报告。新守卫扫全文 +
   所有 mode 文件，且**自撤回**：计划 2 一旦建出 `check_conventions.py`，测试立刻变红，逼你删掉
   那条「尚未构建」声明。两个方向都做过变异测试。

---

## 计划的真实状态

五份计划都经过：撰写 → 对抗审计（把代码抽出来真跑）→ 修复 → 重新审计。**旧缺陷都真修好了**，重审是执行验证的：

| 计划 | 沙箱实测 | 状态 |
|---|---|---|
| 1 迁移 + P0 修复（23 任务） | 沙箱 264 通过 → **实际交付 335 通过** | ✅ **已完成** |
| 2 assess 模式 | 147 通过 + 8 个**设计上的红灯**（市场表尚未创建，正确的 TDD 红相） | 剩 8 条，2 条 HIGH |
| 3 discover 模式 | 补上 F1 后 **123 全过** | 剩数条 |
| 4 interview 模式 | — | 剩 6 条，2 条阻塞 |
| 5 评估重建（15 任务 / 20 场景） | 自身 lint 通过 | 新写，未审计 |

**每一条剩余缺陷都有行号和确切改法**，在 `docs/superpowers/research/2026-08-09/reaudit-{1,2,3,4}.md`。

### 三条跨计划协调缺陷（并行撰写的典型坏法）

| | 状态 |
|---|---|
| **F1** `enter_mode.mode_file` 不存在（计划 1 白纸黑字写了它不存在），真实签名 `paths.mode_file(mode, root)`，参数顺序还反着 | ✅ **已修**（这一条曾让计划 3 的 47/123 测试全红） |
| **F2** 计划 3/4 要撤回的「尚未构建」句，在计划 1 改版后已变成 `## Modes` 表，撤回目标不存在 | ✅ 已修（三份计划各自改自己那一行） |
| **F3** 计划 3/4 各自整行重写同一处 skip-set，后跑的抹掉先跑的 | ✅ 已修（改成追加） |

**最终跨查已跑通**：28 条编辑全部解决，F1–F4 落实，spec §1–§12 全部有归属任务。它给出的最后
4 条精确编辑也已应用（commit `d57576c`）。重跑脚本留在
`docs/superpowers/research/2026-08-09/final-fix-workflow.js`。

---

## 恢复工作：执行计划 2

```
docs/superpowers/plans/2026-08-09-2-assess-mode.md
```

**执行方式用 subagent-driven**：每 3–5 个任务派一个全新 subagent，任务组之间人审。理由是这些计划
里有好几个任务专门在修「测试全绿但功能是坏的」这类缺陷，让持有全程上下文的执行者去验证自己刚写的
修复，正是这类缺陷最容易蒙混过关的场景。换个没有前情的 subagent 跑测试，判断更硬。

派 subagent 时必须交代的四条**现行偏离**（计划文本里没有，不说会让它困惑或改错）：

1. `scripts/tests/test_vocab.py` 是 9 个测试不是 8 个。它的守卫
   `test_no_other_script_redeclares_a_closed_set` **是活的，会扫你写的每个 `scripts/*.py`**：
   任何脚本里都不许拼出 `strong_apply`，也不许出现裸的 `MARKET_KEYS =` / `DEFECT_TAGS =`，
   唯一例外是精确别名 `MARKET_KEYS = vocab.MARKET_KEYS`。
2. baseline 用不可变 commit `864ad7f`，不是那个只存在于本机的 tag。
3. `HANDOFF.md` 在 `docs/` 下，所以无损语料库是 15 个文件（+SKILL.md 后为 16）。
4. 因为第 1 条，计划里每个累计的「Expected: N passed」都比实际低 1。**核对每个任务新增的
   delta，不要核对绝对总数。**

### 计划 2 落地时会立刻变红的几件事（计划自己写了，但值得先知道）

- `## Modes` 表里 assess 那一行的 Status 必须改成 `live — modes/assess.md`，否则自撤回测试变红。
- `## Self-check` 段和闸门表必须**追加**本计划新增的脚本与 `modes/assess.md`（追加，不是整行替换
  ——三个计划改同一行，整行替换会让后跑的抹掉先跑的）。
- `modes/assess.md` 第一步必须是 `enter_mode.py --mode assess`，且 `check_assessment` 要镜像
  `NO_MODE_ENTRY` / `MODE_FILE_CHANGED` 两个 finding。
- 建出 `check_conventions.py` 的**同一个任务**里要拆掉 Makefile 和 CI 里的
  `if [ -f scripts/check_conventions.py ]` 守卫，否则守卫测试从那一刻起一直红。
- `check_evidence_refs.py` 和 `check_conventions.py` 建出来后，要从
  `scripts/tests/test_skill_structure.py` 的 `NOT_YET_BUILT` 里删掉——那个声明也是自撤回的。

---

## 三件别忘了的事

1. **`check_skill_lossless.py` 是唯一能证明那 1500 行存量没在搬迁中丢失的东西。** 它自己曾经是
   坏的（`docs/` 被递归收进语料库，于是引用了 SKILL.md 原文的计划文件会让一个被压缩过的
   SKILL.md 也报 LOSSLESS）。已修，且亲自跑过：`LOSSLESS: 1317/1317 … 16 files, 18 waived`。
   **每次改完 SKILL.md 都重跑它，别采信任何人的报告。**

2. **它证明的和不证明的**：它衡量字节是否还在，**不是**内容是否在需要的时刻到达上下文。唯一真正
   的检验是跑完整 eval 然后看输出缺了什么——那是计划 5，还没做。所以现在还**不能**说分层没有
   造成退化，只能说没有丢字节。

3. **`~/.claude/skills/job-application` 保留作归档，不要删，不要改。** `864ad7f` 是 baseline。

---

## 已修：研究阶段实测出的活体缺陷

全部由计划 1 关闭，见上文表格。原始测量记录在
`docs/superpowers/research/2026-08-09/preserve.json` 和四份 `audit-*.md` 里，值得保留是因为它们
记录的是「什么样的检查会放过什么样的错误」，那比缺陷本身更有用。
