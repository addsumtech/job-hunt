# job-hunt — 接手说明

停在这里：2026-08-10，用户因 token 成本喊停，**尚未开始构建**。下次从「立即可做的第一步」开始。

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

**存量保全这件事已经做完了**：`~/.claude/skills/job-application` 里那约 1500 行未提交工作（recruiter-screener、5 个新 reference、rirekisho 渲染器、render_cv 983 行改动）已分组提交，工作区干净，51 项测试全绿，未 push。

---

## 立即可做的第一步：历史迁移

**已在克隆体上端到端验证通过**（无冲突、32 条历史、文件路径正确、合并后 51 项测试仍全绿）：

```bash
cd ~/code_project/job-hunt
git remote add ja /Users/donghanglyu/.claude/skills/job-application
git fetch ja
git merge --allow-unrelated-histories --no-edit ja/main
python3 -m pytest scripts/tests -q     # 应为 51 passed
```

用 merge 而不是拷文件，是因为「搬运可以、改写不行」——历史就是搬运的证据。

---

## 计划的真实状态

五份计划都经过：撰写 → 对抗审计（把代码抽出来真跑）→ 修复 → 重新审计。**旧缺陷都真修好了**，重审是执行验证的：

| 计划 | 沙箱实测 | 状态 |
|---|---|---|
| 1 迁移 + P0 修复（23 任务） | **264 通过 / 0 失败** | 剩 7 条新缺陷，2 条阻塞 |
| 2 assess 模式 | 147 通过 + 8 个**设计上的红灯**（市场表尚未创建，正确的 TDD 红相） | 剩 8 条，2 条 HIGH |
| 3 discover 模式 | 补上 F1 后 **123 全过** | 剩数条 |
| 4 interview 模式 | — | 剩 6 条，2 条阻塞 |
| 5 评估重建（15 任务 / 20 场景） | 自身 lint 通过 | 新写，未审计 |

**每一条剩余缺陷都有行号和确切改法**，在 `docs/superpowers/research/2026-08-09/reaudit-{1,2,3,4}.md`。

### 三条跨计划协调缺陷（并行撰写的典型坏法）

| | 状态 |
|---|---|
| **F1** `enter_mode.mode_file` 不存在（计划 1 白纸黑字写了它不存在），真实签名 `paths.mode_file(mode, root)`，参数顺序还反着 | ✅ **已修**（这一条曾让计划 3 的 47/123 测试全红） |
| **F2** 计划 3/4 要撤回的「尚未构建」句，在计划 1 改版后已变成 `## Modes` 表，撤回目标不存在 | ❌ 未修（计划 3 剩 11 处、计划 4 剩 7 处） |
| **F3** 计划 3/4 各自整行重写同一处 skip-set，后跑的抹掉先跑的 | ❌ 未修 |

**最终跨查从未跑成**（两次都死在会话额度上）。重跑脚本已存：`docs/superpowers/research/2026-08-09/final-fix-workflow.js`，用 `Workflow({scriptPath: ...})` 调用即可，不用重新组织。

---

## 恢复工作的两条路

**A. 先修完再动工**（保守）：跑 `final-fix-workflow.js` 补掉 F2/F3 和各计划残留缺陷 + 最终跨查，然后从迁移开始。

**B. 直接动工**（更快）：计划 1 沙箱 264 项全过、剩余缺陷不阻塞前 15 个任务。先执行迁移和计划 1 的前半段，边做边修。计划 3/4 的 F2/F3 要到它们各自的最后一个任务才咬人。

不管哪条，**构建建议用 subagent-driven**：每任务派全新 subagent，任务之间人审。理由是计划 1 有好几个任务专门在修「测试全绿但功能是坏的」这类缺陷，让持有全程上下文的执行者验证自己刚写的修复，正是这类缺陷最容易蒙混过关的场景。

---

## 三件别忘了的事

1. **`check_skill_lossless.py` 是唯一能证明那 1500 行存量没在搬迁中丢失的东西**，而它自己曾经是坏的（`docs/` 被递归收进语料库，导致引用了 SKILL.md 原文的计划文件让压缩过的 SKILL.md 也报 LOSSLESS）。修复者称已修好并实跑 `LOSSLESS: 1317/1317`——**迁移后亲自跑一遍，别采信报告**。

2. **它证明的和不证明的**：它衡量字节是否还在，不是内容是否在**需要的时刻**到达上下文。唯一真正的检验是跑完整 eval 然后看输出缺了什么（这就是计划 5）。

3. **`job-application` 原仓库保留作归档，不要删**。

---

## 已知的活体缺陷（现有 skill 里，尚未修）

这些是研究阶段实测出来的，计划 1 会修：

- `render_letter.py:101` 比较裸串 `"tectonic"`，而 `render_cv.py:992` 比较 `Path(engine).name` → **动机信 PDF 永远生成不出来，而 51 项测试全绿**
- Cluster-1 个人数据互锁对 `United States (Los Angeles, CA)` 这类真实拼法**不生效**（eval-0 的场景输入字面就是这个）
- 三个评委文件都写着「orchestrator 以程序方式解析」，而**这个程序不存在**
- `assets/{cv,letter}/template.tex` 是死文件（无任何代码加载，且已与实际产出漂移）
- SKILL.md **没有 self-check 清单**——CLAUDE.md 里写的第三种 backstop 形式在现有 skill 里根本不存在
- `posting.yaml` 字段表静默丢了 `salary_range` 和 `application_type`，后者是导向 supporting-statement 分支的唯一信号
