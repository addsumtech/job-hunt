# job-hunt — 接手说明

**更新于 2026-10-24（1.3.0 发布当天）。** 这份文件以前在 8 月里过时了两次，接手的人信了旧状态就会重建已经存在的东西。
**先跑一次 `make check`，再信任这里的任何一句话。**

---

## 当前状态

- 四个模式（apply、assess、discover、interview）都已上线；`evals/` 已建成。
- 版本：1.3.1（2026-10-24）。1.3.0 见 PR #34；1.2.1 到 1.2.3 没有单独打 tag，修复并入 1.3.0。
- `make check`（2026-10-24，Python 3.11 venv）：

```
5837 passed, 8 skipped
LOSSLESS: 1317/1317 baseline lines accounted for across 57 files, 88 waived
check_conventions --ci: exit 0
NO_HIDDEN_CHARS
```

跑测试需要一个装了 `requirements.txt` 和 pytest 的 Python 3.10+（README 里有 venv 命令）；macOS 自带的
`python3` 是 3.9，脚本会以 `PYTHON_TOO_OLD` 退出 2。

---

## `make check` 绿色证明了什么，以及不证明什么

**它证明的：**单元测试彼此自洽；市场表通过 lint；迁移前那份 skill 没有丢任何一行字节；源码和文档里没有
隐藏字符。

**它不证明的：**内容有没有在需要的时刻到达模型的上下文。行为评估在 `evals/`：第 2 轮（2026-09-05/06）
对 15 个场景分别跑了带 skill 和不带 skill 的版本，每组一次（n = 1），记录在 `evals/iterations/`。
1.3.0 大幅改写了模式文件和闸门，**之后没有重跑行为评估**；要说 1.3.0 的行为比 1.2.x 好，得先跑一轮
（`evals/run.md`，结果用 `make eval-verify RESULTS=<dir>` 评分）。

---

## 审计记录

**2026-08-23/24 的对抗审计**（8 个维度，每条发现派独立 agent 反驳，外加 421 个变异体）修掉了五簇问题，
详见当时的提交 `8a5ca6f..cc537ff`。

**2026-10-24 的全面审查 → 1.3.0。** 三路并行审查（脚本正确性、给 agent 的指令、用户文档和安装），
每条发现都先复现再修。要点：

- 防造假：check_claims 拦下截短的头衔、雇主名、学位与论文状态。
- 防预测：lint_no_prediction 拦下不带数字的确定性预测（九种语言），同时减少了一批误报。
- 交付：多个工作区交付到同一目录不再互相覆盖；不再生成冒牌的简历 PDF；能检出缺字方块。
- 可照做：解释器与 cwd 约定写进 SKILL.md；修正 discover 的 `--workspace .` 等照做必失败的指令；
  脚本拒绝把技能目录当工作区。
- 上下文：discover 80KB → 58KB，report-writing 42KB → 30KB；assess 用 `convention_cards.py`；
  apply 评审按文件路径读取。

**判别力规则继续执行**：每条修复的新测试都要先在旧代码上确认会失败（把旧版脚本拷到临时副本跑新测试）。

---

## 还没做完的

- **变异测试**：1.3.0 合并后在 CI 跑了一次（run 40056907221）。check_apply.py 通过；check_claims.py 的
  29 个新存活体已在 1.3.1 补齐（本地全量：141 个变异体，存活 15，其中 13 条旧债、2 条等价，均记入基线）；
  **render_cv.py 的结果在 1.3.1 发布时还没出来**，出来后按同样方法处理。基线文件是
  `scripts/mutants-baseline.json`，只有本地 `make mutants-record` 能改它（它会重写整个文件，记得把其他
  目标的条目合并回来），每条都要写理由。
- **真实模拟测试**：材料已备好，在 `~/code_project/job-hunt-workspace/sim-1.3.x-20261024/`
  （`SIM-PLAN.md`、`CODEX-DISCOVER-PROMPT.md`，只用虚构候选人），尚未开跑。
- **行为评估**：见上一节，1.3.0 之后没有重跑。
- **安装体积**：仓库根目录就是 skill，`npx skills add` 会把整个仓库（含 docs、evals、tests，约 10MB）
  拷进用户目录，且不支持排除文件。要彻底解决只能把 skill 挪进子目录，会牵动两条安装路径和一批测试。
- **SkillHub / ClawHub 上架版本**需要各自的账号重新发布。

---

## 三件别忘了的事

1. **`check_skill_lossless.py` 是唯一能证明迁移前那 1317 行存量没丢的东西。** 每次改完 SKILL.md、README、
   modes、references、agents 都重跑它。删掉一行是可以的，但必须进 `scripts/lossless-allowlist.json`
   并**写下理由**，现在有 88 条豁免。别为了让闸门变绿而批量豁免；能保留原句就保留原句。

2. **`864ad7f` 是无损基线**（迁移前 job-application 的最后一个提交，迁移合并让它成为 HEAD 的祖先），
   任何克隆里都能解析，不需要额外的 remote 或 tag。

3. **规矩**：只 stage 具名路径（不要 `git add -A`）；用自己的 git identity，不要用 `-c` 冒用别人的；
   发版时 main 上 CI 绿了再打 tag；**tag 推送后不再移动**，发版后的修复进下一个补丁版本。
   `git fetch` 默认不会更新已有 tag，挪过的 tag 会让同一个版本号在不同人手里是不同代码
   （v1.0.0、v1.1.0 都发生过）。

---

## 设计上不可回退的决定

理由写在 `docs/superpowers/specs/2026-08-09-job-hunt-skill-design.md` §2 的 14 条决策记录里，
**理由比结论更重要**——遇到文档没枚举的情况时，能推广的只有理由。

- 不输出任何概率或 0–100 分（D2）。执行者是 `lint_no_prediction.py`。
- 全流程只有一套五档词表（D3）。`vocab.py` 有活守卫，禁止任何脚本重新拼出这个闭集。
- 发现层完全只读（D7）。`check_no_write.py` + `access: read` 允许名单。
- 四个模式不自动串联（D9）。
- 市场识别直接问用户，不做地名匹配器（D14）。
- layer 1.5：`modes/*.md` 强制加载 + 内容哈希进 `journal.jsonl`（D11）。
