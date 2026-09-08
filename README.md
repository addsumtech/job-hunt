# job-hunt：让每一份申请，都有真实经历支撑

<p align="center">
  <a href="README.md"><strong>简体中文</strong></a> ·
  <a href="README_EN.md">English</a> ·
  <a href="README_JA.md">日本語</a> ·
  <a href="README_KO.md">한국어</a> ·
  <a href="README_ES.md">Español</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="许可证：MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="适用于 Claude Code 和 Codex" src="https://img.shields.io/badge/agents-Claude_Code_·_Codex-5b5bd6">
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="版本：v1.0.0" src="https://img.shields.io/badge/release-v1.0.0-1f883d"></a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="简历中的条目分别连接到论文、笔记、证书和项目等来源">
</p>

**找岗位、判断是否值得投、定制申请材料、练习面试。把你做过的事讲清楚，也把尚未具备的条件摆清楚。**

job-hunt 是运行在 Claude Code 或 Codex 中的求职 Skill。你提供求职目标、简历或岗位信息，Agent 负责读取材料、核对证据、调整表达、排版和评审，Python 脚本负责检查来源、文件一致性和交付条件。它适用于技术、研究及其他职业方向，也提供转行、职业空档、应届生和跨国求职等情境的指导。

目标是让简历里的每一行，都能在面试中用真实经历解释清楚。

## 从你当前需要的一步开始

| 模式 | 适合什么时候用 | 主要产出 |
|---|---|---|
| **discover · 找岗** | 有方向，想知道有哪些岗位值得看 | 带真实岗位来源、读取状态和初步判断的候选清单 |
| **assess · 评估** | 有岗位，想判断是否值得投入时间 | 逐项要求与证据对照、硬性门槛、差距和申请建议 |
| **apply · 准备申请** | 确定目标，需要一套有针对性的材料 | 定制简历、可选求职信、评审记录和面试准备提纲 |
| **interview · 模拟面试** | 有岗位与简历，想练习回答并复盘 | 一轮模拟面试、逐字记录、两次独立评估和待补充事项 |

四个模式可以分别使用。每轮结束后会给出下一步选项，由你决定是否继续；找到一批岗位不会自动生成一批简历。申请材料交付后，由你决定并完成投递。

安装后，可以直接这样说：

```text
使用 job-hunt，帮我找荷兰的 MRI 图像重建相关岗位。
使用 job-hunt，这是岗位链接和我的简历，帮我判断值不值得投。
使用 job-hunt，针对这个岗位调整简历，并写一封求职信。
使用 job-hunt，根据这个岗位和我的简历，做一轮技术模拟面试。
```

Agent 会先确认本轮模式和目标地区，再询问必要的偏好与材料。目标地区由你确认，不会根据过去的工作地点或对话语言推断。

## 真实经历如何进入申请材料

**每项主张都有来源。** 新增的技能、工具、职责或成果，需要指向原始档案中的具体内容、本轮对话中你的回答，或实际读取过的本人论文与项目。可重排、突出和改写已有经历；缺少依据的内容留在差距清单中。`claims.yaml` 记录这些对应关系，定制过程操作档案副本，保留原始档案。

**评估逐项展示依据。** 必备条件分别标为证据充分、部分支持或缺失，工作许可、执照等硬性门槛优先列出。材料不足时返回 `insufficient_evidence`，说明缺什么。项目禁止把评估包装成面试或录用概率，也不生成凭空设定的 0–100 匹配分；相关检查覆盖所支持的九种简历语言中的预设预测词句。ATS 关键词覆盖率描述的是文本覆盖情况，不代表录用机会。

**普通简历申请经过三个独立 AI 评审。** ATS 评审看关键词与可解析性，招聘人员评审看快速阅读与基本条件，用人经理评审看经验、职责和可信度。每个评审使用独立上下文，全部 `PASS` 才算通过这套内部评审。可修正的问题进入修改与复审，最多三轮；只剩无法靠真实改写补齐的差距时提前结束，并说明原因。

**面试复盘检验你实际说出的内容。** 一个评估检查回答本身，另一个核对事实来源。它帮助你组织已有经历，追问不清楚的细节；无法支撑的简历表述会进入待修正清单。

## 安装

需要能够运行本地命令、读写文件的 Agent 环境，以及 **Python 3.10+**。使用 `npx` 安装时还需要 Node.js/npm。下面三种安装方式任选一种。

### 方式一：通过 `npx skills` 安装

```bash
npx skills add addsumtech/job-hunt
```

按提示选择 Agent 和安装范围。可用 `-g` 安装到用户级，用 `-a claude-code` 或 `-a codex` 指定 Agent，用 `-y` 跳过交互确认。仓库根目录就是 Skill，脚本和参考文件需要一起安装。

### 方式二：作为 Claude Code 插件安装

在 Claude Code 中执行：

```text
/plugin marketplace add addsumtech/job-hunt
/plugin install job-hunt@job-hunt
/reload-plugins
```

安装后通过 `/job-hunt:job-hunt` 调用。更新 marketplace 可运行 `/plugin marketplace update job-hunt`。如果同时安装手动副本和插件，同一个 Skill 可能出现两次。

### 方式三：克隆仓库并建立符号链接

适合需要阅读或修改源码的用户。以下示例注册到 Claude Code：

```bash
git clone https://github.com/addsumtech/job-hunt.git
cd job-hunt
mkdir -p ~/.claude/skills
ln -s "$PWD" ~/.claude/skills/job-hunt
```

使用 Codex 时，将最后两行的 `~/.claude/skills` 换成 `~/.codex/skills`。目标位置已经存在时，先检查已有安装。

### 安装依赖并检查环境

进入安装后的 **job-hunt 根目录**（包含 `SKILL.md` 和 `requirements.txt` 的目录），在 Python 3.10+ 环境中运行：

```bash
python3 -m venv ~/.venvs/job-hunt
source ~/.venvs/job-hunt/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/doctor.py
```

以上激活命令适用于 macOS/Linux；Windows 使用虚拟环境中的 `Scripts` 激活脚本。让 Agent 执行项目脚本时也使用这个 Python 环境。基础依赖为 `PyYAML` 和 `python-docx`；`doctor.py --install` 可以补装当前 Python 环境中缺少的包。

| 能力 | 额外依赖 | 缺少时的影响 |
|---|---|---|
| 简历和求职信 PDF | LaTeX 引擎，推荐 `tectonic` | 仍可生成 Markdown、Word 和供后续编译的 `.tex` |
| Markdown 报告转 PDF | `pandoc`＋LaTeX 引擎 | 下载目录中的报告可能只有 Markdown |
| PDF 文字回读与校验 | Poppler 的 `pdftotext` | 无法完成 PDF 文字完整性验证 |
| 实时岗位检索 | `opencli` 及对应浏览器环境 | 可以用粘贴的岗位正文继续评估、准备申请和模拟面试 |
| 中、日、韩 PDF | 对应语言的字体 | 需要先补齐字体才能可靠排版 |

`doctor.py` 会尝试实际生成 PDF，并说明缺少的能力。它的 `--install` 只安装 Python 包，系统工具按报告中的指引安装。

## 地区、平台与语言

找岗流程通过 `opencli` 适配器读取岗位。仓库的来源目录包含 51job、Indeed、LinkedIn 和 BOSS 直聘等平台，并区分登录要求、岗位来源与面经来源。平台能否读取，以运行时状态为准。当前记录的 Indeed 适配器面向美国站，其他市场不能仅改城市名就假定检索正确。详见[来源目录](references/discovery-sources.md)和[来源使用规则](references/source-policy.md)（英文）。

中国市场还会询问大型私企、中小型私企、国企、外企等雇主偏好。这些偏好影响排序，不会悄悄过滤其他类型。牛客和一亩三分地用于面经与流程参考，论坛内容不会当作真实岗位填入清单。

需要登录时由你完成。遇到验证码、限流或平台拒绝，流程停止该站点本轮读取并说明情况；无法获取真实岗位时，交付明确标注的方向建议。整个找岗流程只读，不发送消息、不修改在线资料、不自动投递。

**地区规则与输出语言分别处理。** 简历渲染器包含英语、荷兰语、德语、法语、西班牙语、意大利语、中文、日语和韩语的标题与个人信息标签。目前 `discover`、`assess` 的部分必需文案与统计卡片只支持中英文，纯日语、韩语或西班牙语报告可能被校验拦截，需要保留英文或中文结构。五语 README 不代表所有流程均已本地化；PDF 也需要输出语言对应的字体。

项目附带美国、英国、德国、荷兰和中国的 **5 张市场惯例表，共 38 条记录**，带有来源及复核日期。超过复核日期时会标注；没有对应表时会说明缺少数据。惯例表用于提供有出处的背景信息，仍需按条目的适用范围理解。

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="仓库渲染示例：美国目标简历省略个人信息，德国目标简历保留已提供的照片与出生日期">
</p>

个人信息由目标地区规则控制：面向美国、加拿大、英国、爱尔兰、澳大利亚和新西兰的普通简历，渲染器会抑制照片和 `contact.personal` 字段，并说明处理情况；无法识别地区时也采用省略策略。其他已识别地区可按规则展示你提供的信息。上图展示项目的渲染行为，不表示某个国家的所有雇主都要求同一种格式。

## 你会拿到什么

| 材料 | 格式与说明 |
|---|---|
| 定制简历 | Markdown、Word（`.docx`）、PDF；PDF 排版同时保留 `.tex` |
| 求职信／动机信 | 按需生成，支持 Markdown、Word 和 PDF |
| 日本履历书（履歴書） | 独立表单渲染器，输出 Markdown 预览和可编辑 `.docx`；表单 PDF 通过 Word 或 LibreOffice 导出 |
| 结构化申请说明 | 面向 NHS、公务员体系等按条件评分的申请，逐项组织证明材料并检查字数限制 |
| 评估与面试材料 | 岗位清单、匹配评估、面试提纲、模拟面试记录和复盘 |

结构化申请按雇主给定的条件审查 supporting statement；如果同时需要普通简历，再对简历运行三方评审。日本履历书检查表单完整性，配套的职业经历文档按普通简历流程审查。

每轮可读材料默认交付到 `~/Downloads`，例如 `<company>-<role>-<date>-cv.md` 和对应 PDF。PDF 能否生成并验证取决于工具链，交付结果会说明缺失文件或未完成的验证。

## 文件保存在什么位置

源档案、申请工作区和检查记录默认保存在 `~/.claude/job-profiles/`，使用 Codex 时也沿用这一位置。可以通过 `JOBHUNT_PROFILES_ROOT` 指定其他根目录。

每位用户可保留不同语言的源档案，例如 `profile.zh.yaml` 和 `profile.en.yaml`；旧的 `profile.yaml` 仍受支持。申请材料按岗位分开保存，来源记录和 `journal.jsonl` 用于追溯检查过程。完整结构见 [REFERENCE.md](REFERENCE.md)（英文）。

文件保存在本地；模型调用和网页访问仍取决于你所使用的 Agent 及其服务配置。

## 验证与项目资料

自动化检查覆盖证据引用、源档案保护、评审结果解析、个人信息处理、排版和模式交接等环节：

```bash
python3 -m pip install pytest
make check
make eval-lint
```

`make check` 包含 Python 测试、迁移内容保留检查和市场惯例表检查。部分测试会检查本机的 Skill 安装与外部工具，结果需要结合运行环境阅读。**检查通过不等于产物正确**，也不能用来证明求职效果。

[`evals/`](evals/README.md) 收录 20 个行为评估场景。仓库记录的第 2 轮评估（2026-09-05/06）对 15 个场景进行了带 Skill 与不带 Skill 的配对运行，其中 10 项用于区分两组的行为检查，从基线的 `FAIL` 变为带 Skill 的 `PASS`。**每个场景、每组只有一次运行，n = 1**；这不代表稳定成功率，也不提供求职结果预测。完整记录还列出了未覆盖项和无效场景结果，见[评估记录](evals/iterations/iteration-2-with-skill.md)。

仓库还记录了 2026-09-06 通过 `codex exec` 运行三个简历评审的验证。其他 Agent 的运行机制与验证范围见[跨 Agent 使用说明](references/portability.md)；不把尚未测试的宿主列为已验证兼容。

- [SKILL.md](SKILL.md)：模式路由与核心规则。
- [REFERENCE.md](REFERENCE.md)：架构、工作区、数据结构和脚本用法。
- [档案示例](assets/profile.example.yaml)与[主张来源示例](assets/claims.example.yaml)：结构化数据格式。
- [行为评估说明](evals/README.md)：评估方法与限制。

以上技术资料目前主要为英文。项目采用 [MIT License](LICENSE)。
