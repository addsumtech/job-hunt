"""A valid discover workspace, built from the real 2026-08-09 51job capture.

Tests mutate exactly ONE thing away from valid. That makes the quiet case
structural rather than aspirational: a gate that starts crying wolf on ordinary
output breaks every test in both shortlist modules at once.
"""
import json
import pathlib

import yaml

import hashlib

REPO = pathlib.Path(__file__).resolve().parents[2]
MODE_FILE = REPO / "modes" / "discover.md"


def mode_entry_record():
    """The record scripts/enter_mode.py writes on entering discover.

    The hash is computed from the real modes/discover.md rather than pinned, so
    editing the mode file never turns every shortlist test red for a reason
    that has nothing to do with the shortlist.
    """
    return {"ts": "2026-08-09T14:01:00Z", "action": "mode_entry",
            "mode": "discover", "mode_file": "modes/discover.md",
            "mode_file_sha256": hashlib.sha256(
                MODE_FILE.read_bytes()).hexdigest()}


RAW_51JOB_SEARCH = [
    {"rank": 1, "jobId": "173198362",
     "title": "高级算法工程师（视觉调试智能化、AI方向）", "salary": "3-6万",
     "salaryMin": 30000, "salaryMax": 60000, "city": "西安",
     "district": "高新技术产业开发区", "workYear": "3年及以上", "degree": "博士",
     "tags": "3年及以上,博士,c++,人工智能,图像处理,深度学习,opencv",
     "company": "比亚迪汽车工业", "companyFull": "比亚迪汽车工业有限公司",
     "companyType": "民营", "companySize": "10000人以上", "industry": "汽车",
     "hr": "王女士·行政实习生", "issueDate": "2026-08-08 10:23:15",
     "url": "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0",
     "companyUrl": "https://jobs.51job.com/all/coVDMHY1M0BDgAZ1c9AWVWZA.html",
     "encCoId": "VDMHY1M0BDgAZ1c9AWVWZA"},
    {"rank": 2, "jobId": "173199597", "title": "高级AI算法工程师(J10032)",
     "salary": "1.7-3.4万·15薪", "salaryMin": 17000, "salaryMax": 34000,
     "city": "海宁", "district": "", "workYear": "3年", "degree": "硕士",
     "tags": "3年,硕士,数字孪生,ai模型训练,ai算法,五险一金",
     "company": "拓荆键科（海宁）半导体设备",
     "companyFull": "拓荆键科（海宁）半导体设备有限公司", "companyType": "民营",
     "companySize": "150-500人", "industry": "电子技术/半导体/集成电路",
     "hr": "周女士·人事", "issueDate": "2026-08-08 14:34:16",
     "url": "https://jobs.51job.com/haining/173199597.html?s=sou_sou_soulb&t=0_0",
     "companyUrl": "https://jobs.51job.com/all/coUjJQPFY2DzYPaVQyVDI.html",
     "encCoId": "UjJQPFY2DzYPaVQyVDI"},
]

RAW_51JOB_DETAIL = [
    {"jobId": "173199597", "title": "高级AI算法工程师(J10032)",
     "salary": "1.7-3.4万·15薪", "location": "海宁", "workYear": "3年",
     "degree": "硕士", "category": "算法工程师",
     "address": "浙江省海宁市经济开发区",
     "description": "负责数字孪生方向的 AI 算法研发；熟悉 Python/C++；有半导体设备经验优先。",
     "welfare": "五险一金 带薪年假 年终奖金",
     "company": "拓荆键科（海宁）半导体设备", "companyType": "民营",
     "companySize": "150-500人", "companyIndustry": "电子技术/半导体/集成电路",
     "url": "https://jobs.51job.com/haining/173199597.html"},
]

# A trimmed copy of `opencli 51job --help -f yaml` so check_no_write can run
# against this workspace without shelling out.
HELP_51JOB = """site: 51job
command_count: 4
commands:
  - name: company
    access: read
  - name: detail
    access: read
  - name: hot
    access: read
  - name: search
    access: read
"""

BRIEF = {
    "slug": "2026-08-09-suanfa-shanghai",
    "created": "2026-08-09",
    "trigger_reason": (
        "用户要求本轮检索：上一份 JD 被 assess 判为 likely_screen_out（缺 C++ 生产经验），"
        "因此在同方向上找更稳的岗位。本轮候选必须肉眼可见地比它更稳，而不只是标题相似。"),
    "target_titles": ["算法工程师", "algorithm engineer"],
    "markets": ["cn"],
    "locations": ["上海", "西安", "海宁"],
    "seniority": "mid",
    "employment_types": ["full_time"],
    "work_models": ["onsite", "hybrid"],
    "languages": ["Chinese", "English"],
    "must_have_constraints": ["work authorization: 中国公民，无需担保"],
    "nice_to_have": ["计算机视觉", "医疗影像"],
    "avoid": ["外包", "销售导向岗位"],
    "target_count": 2,
    "max_rows_per_round": 25,
    "max_pages_per_site": 2,
    "max_age_days": 30,
}

ROWS = [
    {"id": "51job-173198362",
     "title": "高级算法工程师（视觉调试智能化、AI方向）",
     "company": "比亚迪汽车工业",
     "location": "西安 · 高新技术产业开发区",
     "salary": "3-6万",
     "url": "https://jobs.51job.com/xian-gxjs/173198362.html",
     "source_site": "51job",
     "source_id": "173198362",
     "extraction_method": "adapter_search",
     "retrieved_at": "2026-08-09T14:02:11Z",
     "quality": "card_only",
     "verification": "collected_unverified",
     "raw_text": ("高级算法工程师（视觉调试智能化、AI方向） | 比亚迪汽车工业 | 西安 | "
                  "3-6万 | 博士 | 3年及以上 | c++,图像处理,深度学习,opencv"),
     "why_matched": ("brief.target_titles 命中「算法工程师」；raw salaryMin 30000 在 brief "
                     "薪资区间内；raw city 西安 在 brief.locations 内。raw degree 为「博士」，"
                     "档案为硕士，已计入分档。仅卡片信息，未取详情。"),
     "verdict": "worth_applying",
     "provisional": True,
     "effort": "evening"},
    {"id": "51job-173199597",
     "title": "高级AI算法工程师(J10032)",
     "company": "拓荆键科（海宁）半导体设备",
     "location": "海宁",
     "salary": "1.7-3.4万·15薪",
     "url": "https://jobs.51job.com/haining/173199597.html",
     "source_site": "51job",
     "source_id": "173199597",
     "extraction_method": "adapter_detail",
     "retrieved_at": "2026-08-09T14:03:40Z",
     "quality": "complete",
     "verification": "fresh_verified",
     "raw_text": ("高级AI算法工程师(J10032) | 拓荆键科（海宁）半导体设备 | 海宁 | "
                  "1.7-3.4万·15薪 | 硕士 | 3年 | 负责数字孪生方向的 AI 算法研发；"
                  "熟悉 Python/C++"),
     "why_matched": ("brief.target_titles 命中「算法工程师」；详情页 description 点名 "
                     "Python/C++ 与档案主线一致；raw degree 硕士 与档案一致。"),
     "verdict": "strong_apply",
     "provisional": True,
     "effort": "quick"},
]

SHORTLIST = {
    "search_slug": "2026-08-09-suanfa-shanghai",
    "brief": "brief.yaml",
    "shortfall_reason": None,
    "detail_fetch_exceptions": [],
    "sources": [
        {"site": "51job",
         "command": "search",
         "access": "read",
         "login_state": "no_auth_adapter",
         "classification": "ok",
         "invocations": 1,
         "rows_returned": 2,
         "identity_field": "title",
         "identity_field_empty_rows": 0,
         "detail_command": "opencli 51job detail <jobId>",
         "raw_files": ["raw/51job-1.json", "raw/51job-detail-173199597.json"]},
    ],
    "rows": ROWS,
}

SHORTLIST_MD = """# Shortlist — 2026-08-09 · 算法工程师 · 上海/西安/海宁

## §0 来源与读取质量

| site | command | access | 登录态 | 调用 | 返回行 | 标识字段 | 空标识行 | 详情命令 | 分类 |
|---|---|---|---|---|---|---|---|---|---|
| 51job | search | read | 无 auth adapter | 1 | 2 | `title` | 0 | `opencli 51job detail <jobId>` | ok |

原始捕获：`raw/51job-1.json`、`raw/51job-detail-173199597.json`。
每一行的来源终点都在这两个文件里；它们永不编辑。

## §0.1 触发原因

上一份 JD 被 assess 判为 `likely_screen_out`（缺 C++ 生产经验），用户要求在同方向上
找更稳的岗位。本轮候选必须肉眼可见地比它更稳，而不只是标题相似。

## §1 候选（全部为基于卡片信息的初判 · provisional）

1. **高级AI算法工程师(J10032)** — 拓荆键科（海宁）半导体设备 · 海宁 · 1.7-3.4万·15薪
   — `strong_apply`（初判）
2. **高级算法工程师（视觉调试智能化、AI方向）** — 比亚迪汽车工业 · 西安 · 3-6万
   — `worth_applying`（初判）· 未取详情
"""

JOURNAL = [
    {"ts": "2026-08-09T14:02:11Z", "mode": "discover", "action": "adapter_call",
     "site": "51job", "command": "search", "exit_code": 0, "classification": "ok",
     "row_count": 2, "empty_result": False, "identity_field": "title",
     "empty_identity_rows": [], "needs_detail_recovery": False,
     "detail_command": "opencli 51job detail <jobId>", "auth_state": "absent",
     "signal_id": None, "error_message": None, "remedy": None,
     "stdout_file": "raw/51job-1.json", "stderr_file": "raw/51job-1.err",
     "command_line": ("opencli 51job search 算法工程师 --area 上海 --page 1 "
                      "--limit 25 --window background -f json")},
    {"ts": "2026-08-09T14:03:40Z", "mode": "discover", "action": "adapter_call",
     "site": "51job", "command": "detail", "exit_code": 0, "classification": "ok",
     "row_count": 1, "empty_result": False, "identity_field": "title",
     "empty_identity_rows": [], "needs_detail_recovery": False,
     "detail_command": "opencli 51job detail <jobId>", "auth_state": "absent",
     "signal_id": None, "error_message": None, "remedy": None,
     "stdout_file": "raw/51job-detail-173199597.json", "stderr_file": None,
     "command_line": ("opencli 51job detail 173199597 --window background "
                      "-f json")},
]


def _dump_yaml(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def build_workspace(root):
    """Create a VALID search workspace under `root` and return its path."""
    import textwrap
    workspace = pathlib.Path(root) / "2026-08-09-suanfa-shanghai"
    (workspace / "raw" / "opencli-help").mkdir(parents=True)
    (workspace / "raw" / "51job-1.json").write_text(
        json.dumps(RAW_51JOB_SEARCH, ensure_ascii=False, indent=2), encoding="utf-8")
    (workspace / "raw" / "51job-detail-173199597.json").write_text(
        json.dumps(RAW_51JOB_DETAIL, ensure_ascii=False, indent=2), encoding="utf-8")
    (workspace / "raw" / "51job-1.err").write_text("", encoding="utf-8")
    (workspace / "raw" / "opencli-help" / "51job.yaml").write_text(
        textwrap.dedent(HELP_51JOB), encoding="utf-8")
    _dump_yaml(workspace / "brief.yaml", BRIEF)
    _dump_yaml(workspace / "shortlist.yaml", SHORTLIST)
    (workspace / "shortlist.md").write_text(
        textwrap.dedent(SHORTLIST_MD), encoding="utf-8")
    write_journal(workspace, JOURNAL)
    return workspace


# --------------------------------------------------------------- the English round
#
# 「shortlist 跟用户走」 (spec §10): the shortlist follows the USER's language, not
# the market's. So a monolingual English round is an ordinary output, not an edge
# case, and it gets a whole workspace rather than a translated constant — the two
# gate-required literals are only worth pairing if a document that uses the
# English spellings actually passes end to end.

RAW_LINKEDIN_SEARCH = [
    {"rank": 1, "title": "MRI Reconstruction Scientist",
     "company": "Philips Research", "location": "Eindhoven, North Brabant",
     "listed": "3 days ago", "salary": "",
     "url": "https://www.linkedin.com/jobs/view/3987654321/"},
    {"rank": 2, "title": "Senior Image Reconstruction Engineer",
     "company": "Amsterdam UMC", "location": "Amsterdam, Noord-Holland",
     "listed": "1 week ago", "salary": "€5,800 - €7,200 per month",
     "url": "https://www.linkedin.com/jobs/view/3912345678/"},
]

HELP_LINKEDIN = """site: linkedin
command_count: 3
commands:
  - name: search
    access: read
  - name: job-detail
    access: read
  - name: jobs-preferences
    access: read
"""

BRIEF_EN = {
    "slug": "2026-08-16-mri-recon-nl",
    "created": "2026-08-16",
    "trigger_reason": (
        "The user asked for a first round in the Dutch market: the previous posting "
        "was assessed likely_screen_out for missing production C++, so this round "
        "has to surface roles that are visibly steadier, not merely similarly titled."),
    "target_titles": ["MRI reconstruction", "beeldreconstructie onderzoeker",
                      "image reconstruction engineer"],
    "markets": ["nl"],
    "locations": ["Amsterdam", "Eindhoven", "Utrecht"],
    "seniority": "mid",
    "employment_types": ["full_time"],
    "work_models": ["onsite", "hybrid"],
    "languages": ["English"],
    "must_have_constraints": ["work authorization: EU work permit required"],
    "nice_to_have": ["compressed sensing", "PyTorch"],
    "avoid": ["agency and staffing intermediaries"],
    "target_count": 2,
    "max_rows_per_round": 25,
    "max_pages_per_site": 2,
    "max_age_days": 30,
}

ROWS_EN = [
    {"id": "linkedin-3987654321",
     "title": "MRI Reconstruction Scientist",
     "company": "Philips Research",
     "location": "Eindhoven, North Brabant",
     "salary": "",
     "url": "https://www.linkedin.com/jobs/view/3987654321/",
     "source_site": "linkedin",
     "source_id": "3987654321",
     "extraction_method": "adapter_search",
     "retrieved_at": "2026-08-16T09:14:02Z",
     "quality": "card_only",
     "verification": "collected_unverified",
     "raw_text": ("MRI Reconstruction Scientist | Philips Research | "
                  "Eindhoven, North Brabant | 3 days ago"),
     "why_matched": ("brief.target_titles matches «MRI reconstruction»; raw location "
                     "Eindhoven is in brief.locations. Card only, no detail fetched, "
                     "so the salary field is empty in the capture too."),
     "verdict": "worth_applying",
     "provisional": True,
     "effort": "evening"},
    {"id": "linkedin-3912345678",
     "title": "Senior Image Reconstruction Engineer",
     "company": "Amsterdam UMC",
     "location": "Amsterdam, Noord-Holland",
     "salary": "€5,800 - €7,200 per month",
     "url": "https://www.linkedin.com/jobs/view/3912345678/",
     "source_site": "linkedin",
     "source_id": "3912345678",
     "extraction_method": "adapter_search",
     "retrieved_at": "2026-08-16T09:14:02Z",
     "quality": "card_only",
     "verification": "collected_unverified",
     "raw_text": ("Senior Image Reconstruction Engineer | Amsterdam UMC | "
                  "Amsterdam, Noord-Holland | €5,800 - €7,200 per month | "
                  "1 week ago"),
     "why_matched": ("brief.target_titles matches «image reconstruction engineer»; "
                     "raw location Amsterdam is in brief.locations; the card's "
                     "monthly band clears brief salary_floor."),
     "verdict": "strong_apply",
     "provisional": True,
     "effort": "quick"},
]

SHORTLIST_EN = {
    "search_slug": "2026-08-16-mri-recon-nl",
    "brief": "brief.yaml",
    "shortfall_reason": None,
    "detail_fetch_exceptions": [],
    "sources": [
        {"site": "linkedin",
         "command": "search",
         "access": "read",
         "login_state": "logged_in",
         "classification": "ok",
         "invocations": 1,
         "rows_returned": 2,
         "identity_field": "title",
         "identity_field_empty_rows": 0,
         "detail_command": "opencli linkedin job-detail <job-url>",
         "raw_files": ["raw/linkedin-1.json"]},
    ],
    "rows": ROWS_EN,
}

SHORTLIST_MD_EN = """# Shortlist — 2026-08-16 · MRI reconstruction · Netherlands

## §0 Sources and read quality

| site | command | access | login | calls | rows | identity field | empty identity | detail command | classification |
|---|---|---|---|---|---|---|---|---|---|
| linkedin | search | read | logged in | 1 | 2 | `title` | 0 | `opencli linkedin job-detail <job-url>` | ok |

Raw captures: `raw/linkedin-1.json`. Every row's provenance ends in that file, and
it is never edited. `indeed` was skipped for this round: it serves the US site and
resolves `--location` against a US gazetteer, so it cannot search the Netherlands.

## §0.1 Trigger

The previous posting was assessed `likely_screen_out` for missing production C++,
and the user asked for a Dutch-market round of visibly steadier roles.

## §1 Candidates (all provisional, from card data only)

1. **Senior Image Reconstruction Engineer** — Amsterdam UMC · Amsterdam,
   Noord-Holland · €5,800 - €7,200 per month — `strong_apply` (provisional) ·
   effort: quick
2. **MRI Reconstruction Scientist** — Philips Research · Eindhoven, North Brabant
   — `worth_applying` (provisional) · effort: evening · no detail fetched
"""

JOURNAL_EN = [
    {"ts": "2026-08-16T09:14:02Z", "mode": "discover", "action": "adapter_call",
     "site": "linkedin", "command": "search", "exit_code": 0,
     "classification": "ok", "row_count": 2, "empty_result": False,
     "identity_field": "title", "empty_identity_rows": [],
     "needs_detail_recovery": False,
     "detail_command": "opencli linkedin job-detail <job-url>",
     "auth_state": "logged_in", "signal_id": None, "error_message": None,
     "remedy": None, "stdout_file": "raw/linkedin-1.json",
     "stderr_file": "raw/linkedin-1.err",
     "command_line": ('opencli linkedin search "MRI reconstruction" --location '
                      '"Netherlands" --date-posted week --start 0 --limit 10 '
                      "--window background -f json")},
]

DISCLOSURE_MD_EN = """# Shortlist — 2026-08-16 · degraded output

## §0 Sources and read quality

No adapter returned a posting this round; see the disclosure below. The output is
a direction-level shortlist.

## §0.1 Trigger

The user asked for a Dutch-market round of MRI reconstruction roles.

## §0.2 Disclosure

Logged in this session:         no
Adapter returned:               linkedin request failed: HTTP 403 Forbidden
Retried after a stop signal:    no
Bypassed any platform control:  no
Obtained real postings:         no
Degraded output type:           direction-level shortlist

## §1 Direction-level shortlist

1. Image reconstruction (clinical MRI vendors) — search terms «MRI reconstruction»,
   «beeldreconstructie» — …
"""


def build_english_workspace(root):
    """A VALID English search workspace: an English capture, English rows, an
    English shortlist.md. The acceptance test for the paired gate literals."""
    import textwrap
    workspace = pathlib.Path(root) / "2026-08-16-mri-recon-nl"
    (workspace / "raw" / "opencli-help").mkdir(parents=True)
    (workspace / "raw" / "linkedin-1.json").write_text(
        json.dumps(RAW_LINKEDIN_SEARCH, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (workspace / "raw" / "linkedin-1.err").write_text("", encoding="utf-8")
    (workspace / "raw" / "opencli-help" / "linkedin.yaml").write_text(
        textwrap.dedent(HELP_LINKEDIN), encoding="utf-8")
    _dump_yaml(workspace / "brief.yaml", BRIEF_EN)
    _dump_yaml(workspace / "shortlist.yaml", SHORTLIST_EN)
    (workspace / "shortlist.md").write_text(SHORTLIST_MD_EN, encoding="utf-8")
    write_journal(workspace, JOURNAL_EN)
    return workspace


def load_shortlist(workspace):
    return yaml.safe_load((workspace / "shortlist.yaml").read_text(encoding="utf-8"))


def save_shortlist(workspace, data):
    _dump_yaml(workspace / "shortlist.yaml", data)


def load_brief(workspace):
    return yaml.safe_load((workspace / "brief.yaml").read_text(encoding="utf-8"))


def save_brief(workspace, data):
    _dump_yaml(workspace / "brief.yaml", data)


def write_md(workspace, text):
    (workspace / "shortlist.md").write_text(text, encoding="utf-8")


def write_journal(workspace, records, mode_entry=True):
    """Rewrite journal.jsonl, keeping the workspace valid in every other respect.

    The mode_entry record is prepended by default: a test that mutates the
    adapter history is not also trying to assert that the mode was never
    entered, and if it had to remember to re-add the entry every time, the
    NO_MODE_ENTRY finding would show up in half the suite as noise.
    """
    head = []
    if mode_entry and not any(
            isinstance(r, dict) and r.get("action") == "mode_entry"
            for r in records):
        head = [mode_entry_record()]
    with (workspace / "journal.jsonl").open("w", encoding="utf-8") as handle:
        for record in head + list(records):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
