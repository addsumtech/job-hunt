# job-hunt — 接手说明

**更新于 2026-08-24。** 这份文件在 2026-08-10 到 2026-08-23 之间一直是错的：它写着「计划 2–5 未
开始」，而计划 2/3/4 早在 8 月 16 日前就建完并上线了。接手的人如果信它，会去重建已经存在的东西。
**先跑一次 `make check`，再信任这里的任何一句话。**

---

## 当前状态

```
计划 1  迁移 + P0 修复（apply）    ✅ 已交付
计划 2  assess 模式                ✅ 已交付
计划 3  discover 模式              ✅ 已交付
计划 4  interview 模式             ✅ 已交付
计划 5  行为 eval（evals/）        ❌ 0 / 94 任务 —— 目录不存在
```

`make check` 现在跑出来是：

```
1199 passed, 1 skipped
LOSSLESS: 1317/1317 baseline lines accounted for across 32 files, 24 waived
check_conventions --ci: exit 0
```

四个模式都软链进 `~/.claude/skills/job-hunt` 和 `~/.codex/skills/job-hunt`，两个 runtime 都能触发。

---

## `make check` 绿色证明了什么，以及不证明什么

**它证明的：**单元测试彼此自洽；市场表通过 lint；迁移前那份 skill 没有丢任何一行字节。

**它不证明的：**任何模式被对照 baseline 臂测量过。计划 5 从未建成，所以这个 skill **从未跑过一次
端到端行为评估**。`check_skill_lossless.py` 衡量的是字节还在不在，**不是内容有没有在需要的时刻到达
上下文**——只有真跑一轮才能回答第二个问题，而仓库里没有任何东西会跑它。

这句话请原样保留在 README 里。仓库从来没有声称自己被评估过（对 README/SKILL/modes 全文 grep
`benchmark` / `baseline arm` / `pass rate` 是零命中），所以没有任何不诚实的东西发货——这是流程债，
不是活体缺陷。但它是完整性判断上的决定性一条。

---

## 2026-08-23/24 的对抗审计与五轮修复

做了一次 8 维度对抗审计（每条发现派独立 agent 反驳，外加 421 个变异体的变异测试），报告
[artifact](https://claude.ai/code/artifact/82fe0378-d852-49a6-aa65-9edba0ceb735)。38 条发现存活。
已按损害顺序修掉五簇并推送到 main：

| 遍 | 修了什么 | commit |
|---|---|---|
| 1 | 交付产物（PDF/docx）是全仓被验证最少的对象 | `8a5ca6f..e3330d8` |
| 2 | interview 的证据检查不检查它声称检查的东西 | `e3330d8..b5ae658` |
| 3 | discover 的溯源锚点停在没人读的文件上 | `b5ae658..1303beb` |
| 4 | 预测禁令在它默认输出的语言里没有执行 | `1303beb..f746066` |
| 5 | 收据是关于「某个时刻」的断言，不是关于字节的 | `f746066..cc537ff` |

**每一遍的新测试都拿 `8a5ca6f` 回归验证过判别力**（`git checkout 8a5ca6f -- <改过的脚本>`，
确认新测试在旧代码上变红）。这一条请继续做下去：第一遍写的测试里有两条在旧代码上也通过，
一条是 fixture 太弱（DOI 只到 548.8pt 根本没出血），一条是**在 `MISSING_CHARACTERS` 上 skip
——而那正是 bug 本身，等于测试在它本该失败的时候把自己跳过了**。

---

## 还没修的（按审计的修复顺序）

- **第 6 遍（本次进行中）** 文档漂移：posting schema 四份声明已统一并由
  `scripts/tests/test_posting_schema_agreement.py` 逐一 diff；`claims.yaml` 已在
  `modes/apply.md` Step 4、`references/gap-analysis.md` 和 `assets/claims.example.yaml` 写明；
  SKILL.md 已把模式路由提到最前面。
- **第 7 遍** 测试基础设施：变异测试进 `make mutants` 并在 CI 上对**新增**存活体报错；一条参数化的
  「缺主输入 → exit 2 且恰好一条 could_not_run 收据」契约测试（能一次关掉整类）；断言 finding
  **代码在行首**而不是自由子串。
- **第 8 遍** 建 `evals/`（计划 5，94 个任务）。
- **零散**：`modes/discover.md` 仍硬编码 `--workspace .`（从别的 cwd 跑会把整轮产物写进 agent 的当前
  目录，而三个脚本都 exit 0）；`paths.slugify()` 对西里尔/希腊/阿拉伯/泰文返回空串；
  `check_conventions --ci` 枚举 `MARKET_KEYS` 而不是 glob 目录，新市场表落地即无人 lint。

---

## 三件别忘了的事

1. **`check_skill_lossless.py` 是唯一能证明那 1500 行存量没在搬迁中丢失的东西。** 每次改完
   SKILL.md / README.md / references 都重跑它。删掉一行是可以的，但必须进
   `scripts/lossless-allowlist.json` 并**写下理由**——现在有 24 条豁免，每条都有一段话说明为什么
   那行该消失。别为了让闸门变绿而批量豁免。

2. **`~/.claude/skills/job-application` 保留作归档，不要删，不要改。** `864ad7f` 是无损基线，
   remote `ja` 指向它，别往它推。

3. **规矩**：只 stage 具名路径（不要 `git add -A`）；不要用 `-c` 覆盖 git identity
   （`dong845 <ldh199803@gmail.com>`）；**除非当次明确要求，否则不 push**。
   发版：main 上 CI 绿了再打 tag；**tag 推送后不再移动**，发版后的修复进下一个补丁版本。
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
