# job-hunt：找岗位、改简历、练面试

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

job-hunt 是 Claude Code 和 Codex 的求职 Skill，帮你找岗位、判断是否适合申请、准备简历和求职信，也能陪你做模拟面试。

把求职目标、简历或岗位链接发给 Agent，它会整理材料，核对岗位要求和你的经历，完成改写、排版与评审。技术与研究岗位、转行、职业空档、应届生和跨国求职等情况都有对应指导。

## 从你当前需要的一步开始

| 模式 | 适合什么时候用 | 主要产出 |
|---|---|---|
| **discover · 找岗** | 有方向，想找到值得看的岗位 | 岗位清单、原始链接和初步建议 |
| **assess · 评估** | 有岗位，想判断是否值得投入时间 | 逐项要求与证据对照、硬性门槛、差距和申请建议 |
| **apply · 准备申请** | 确定目标，需要一套有针对性的材料 | 定制简历、可选求职信、评审记录和面试准备提纲 |
| **interview · 模拟面试** | 有岗位与简历，想练习回答并复盘 | 模拟面试、对话记录、两次独立评估和改进建议 |

四个模式可以分别使用。每轮结束后，Agent 会给出下一步建议，由你选择是否继续。准备好的申请材料由你投递。

安装后，可以直接这样说：

```text
使用 job-hunt，帮我找荷兰的 MRI 图像重建相关岗位。
使用 job-hunt，这是岗位链接和我的简历，帮我判断值不值得投。
使用 job-hunt，针对这个岗位调整简历，并写一封求职信。
使用 job-hunt，根据这个岗位和我的简历，做一轮技术模拟面试。
```

Agent 会先确认你想做什么、准备在哪个地区求职，再补问需要的材料和偏好。

## 怎么帮你准备申请

改简历时，Agent 会从你的档案、回答、论文和项目中核对经历，调整内容顺序和表述。缺少依据的技能或成果会列为待补充项，原始档案保留，改稿使用副本。

评估岗位时，Agent 会把要求与你的经历逐项对照，列出符合、部分符合和缺少证据的条件。工作许可、执照等硬性门槛优先说明，最后给出申请建议和需要补充的材料。

普通简历会经过三个独立 AI 评审：ATS 评审检查关键词和文件解析，招聘人员评审看简历是否易读、基本条件是否符合，用人经理评审看经验和职责是否清楚。发现问题后修改并复审，最多三轮；需要补充真实经历才能解决的问题，会单独列出。

交付前还会逐页审查 Word/PDF 格式，对照你提供的模板及后续调整，检查字体字号、页边距、横线、日期对齐、段落间距、内容顺序和分页。未经审查或仍有未解决的格式差异时，不会标记为完成；修改文件后须重新审查。

模拟面试结束后，你会收到两份独立评估，分别检查回答质量和事实依据，指出哪些细节值得补充、哪些简历表述需要调整。

## 安装

需要能够运行本地命令、读写文件的 Agent 环境，以及 **Python 3.10+**。使用 `npx` 安装时还需要 Node.js/npm。下面四种安装方式任选一种。

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

### 方式四：通过 SkillHub 或 ClawHub 安装

在 [SkillHub](https://skillhub.cn/skills/user_f486c577/best-job-hunt) 或 [ClawHub](https://clawhub.ai/dong845/skills/job-hunt) 打开 job-hunt 的页面，按平台提示安装。

### 首次使用：让 Agent 完成环境配置

安装后告诉 Agent：“帮我配置 job-hunt，并使用我的日常浏览器开始任务。”

只需安装这个 skill。AnySearch 客户端和浏览器读取脚本已内置，Agent 会通过统一安装入口自动准备 Python 包、Node.js 和带 CDP 补丁的 OpenCLI，无需你单独安装其他 skill 或浏览器扩展。常规求职报告 PDF 默认使用内置字体；明确指定的字体优先采用，不会静默替换；简历模板需要的排版工具按需自动安装。**浏览器通过 CDP 连接。** Agent 先验证 OpenCLI，遇到已确认的不兼容问题时，才使用内置 CDP 读取脚本。


Agent 优先连接你平时使用的浏览器，沿用已有登录状态。首次使用时，可能需要你在 `chrome://inspect/#remote-debugging` 开启远程调试，并确认 Chrome 的连接请求。Agent 会检测浏览器是否支持，说明需要你完成的操作。

AnySearch 通过 HTTP API 搜索，可以匿名使用，无需申请 API Key。浏览器操作默认通过 CDP 连接你选择的日常 Chrome 或 Edge，并在同一任务中复用连接，避免每条命令重复弹出授权。浏览器需要提供可用的调试端点；只有你明确要求时才使用独立浏览器。多个独立来源会尽可能同时检索，缩短等待时间。网站登录、验证码和浏览器授权由你完成。

详细步骤见[环境配置](references/agent-setup.md)和[浏览器连接与并行检索](references/daily-browser.md)。

### 招聘网站读取问题

遇到 Indeed、51job 的已知兼容问题，Agent 会检查并应用适用的修复。当前补丁对应 OpenCLI 1.8.7，其他版本按实际情况处理。

你也可以让 Agent 直接使用招聘网站的搜索框查找岗位。需要排查时，告诉它“检查招聘网站兼容补丁”或“撤销兼容补丁”。[检查与回退方法](references/opencli-compat.md)。

## 地区、平台与语言

Agent 会根据目标地区选择岗位来源，通过浏览器或可用的 OpenCLI 适配器读取。来源目录包括 51job、Indeed、LinkedIn 和 BOSS 直聘等平台。Indeed 适配器目前连接美国站，其他市场优先使用当地来源。[来源目录](references/discovery-sources.md)列出了各平台的登录要求和用途，[来源使用规则](references/source-policy.md)说明了读取范围。

在中国求职时，Agent 会询问你对大型私企、中小型私企、国企、外企等雇主的偏好，并据此排序。牛客和一亩三分地用于了解面试经验与招聘流程。

遇到登录或验证页面，Agent 会暂停该网站并提示你处理。完成后回复“已完成，继续”，它会接着检查。暂时无法访问的来源，可以稍后再试，也可以粘贴岗位正文或先查看已有结果。

简历支持英语、荷兰语、德语、法语、西班牙语、意大利语、中文、日语和韩语的标题与个人信息标签。找岗和评估报告支持中文、英文、日语、韩语和西班牙语，使用[报告语言模板](references/report-localization.md)。部分内部资料仍为英文，PDF 所需字体由 Agent 在配置时检查。

项目附带美国、英国、德国、荷兰和中国的 5 张市场惯例表，共 38 条记录，每条都有来源、适用范围和复核日期。Agent 会提示过期或缺失的资料，具体申请仍以雇主要求为准。

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="仓库渲染示例：美国目标简历省略个人信息，德国目标简历保留已提供的照片与出生日期">
</p>

简历会按目标地区处理照片和个人信息。美国、加拿大、英国、爱尔兰、澳大利亚和新西兰的普通简历默认省略这些内容；其他已识别地区按相应规则展示你提供的信息。地区尚未确认时，先省略。

## 你会拿到什么

| 材料 | 格式与说明 |
|---|---|
| 定制简历 | Markdown、Word（`.docx`）、PDF；PDF 排版同时保留 `.tex` |
| 求职信／动机信 | 按需生成，支持 Markdown、Word 和 PDF |
| 日本履历书（履歴書） | 独立表单渲染器，输出 Markdown 预览和可编辑 `.docx`；表单 PDF 通过 Word 或 LibreOffice 导出 |
| 结构化申请说明 | 面向 NHS、公务员体系等按条件评分的申请，逐项组织证明材料并检查字数限制 |
| 评估与面试材料 | 岗位清单、匹配评估、面试提纲、模拟面试记录和复盘 |

结构化申请按雇主给定的条件审查 supporting statement；如果同时需要普通简历，再对简历运行三方评审。日本履历书检查表单完整性，配套的职业经历文档按普通简历流程审查。

每次咨询都会生成一份 PDF 报告，汇总求职分析、参考依据和待确认事项。报告与简历等材料保存在同一个 `~/Downloads/<workspace-name>/` 文件夹，多阶段咨询沿用同一位置。求职信和模拟面试按你的需要安排。

交付文件分为 `简历/` 和 `报告/` 两个子文件夹，名称如“简历.docx”“简历.pdf”“求职建议报告.pdf”。

需要了解公司或行业时，Agent 还可以查询官网、新闻、微信公众号，以及与问题相关的 GitHub 项目，见[补充信息源](references/supplementary-sources.md)。

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

`make check` 运行 Python 测试、迁移内容保留检查和市场惯例表检查。涉及外部工具的测试需要相应环境，本机安装检查可按需开启。

[`evals/`](evals/README.md) 收录 20 个行为评估场景。第 2 轮评估（2026-09-05/06）对 15 个场景分别运行带 Skill 和不带 Skill 的版本，每组运行一次（n = 1）。其中 10 项行为检查从基线的 `FAIL` 变为带 Skill 的 `PASS`。详细结果、未覆盖项和无效场景见[评估记录](evals/iterations/iteration-2-with-skill.md)。

三个简历评审已于 2026-09-06 通过 `codex exec` 验证。其他 Agent 的配置方法与测试范围见[跨 Agent 使用说明](references/portability.md)。

- [SKILL.md](SKILL.md)：模式路由与核心规则。
- [REFERENCE.md](REFERENCE.md)：架构、工作区、数据结构和脚本用法。
- [档案示例](assets/profile.example.yaml)与[主张来源示例](assets/claims.example.yaml)：结构化数据格式。
- [行为评估说明](evals/README.md)：评估方法与限制。

以上技术资料目前主要为英文。项目采用 [MIT License](LICENSE)。
