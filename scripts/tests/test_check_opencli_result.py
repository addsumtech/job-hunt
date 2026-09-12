"""Tests for scripts/check_opencli_result.py.

Every payload below is a MEASURED opencli response captured 2026-08-09, not an
invented one. The quiet cases are pinned as hard as the firing cases: a
classifier that shouts on an ordinary successful search is worse than none,
because the reader learns to skip that line.
"""
import json
import pathlib

import pytest

import check_opencli_result as coc

REPO = pathlib.Path(__file__).resolve().parents[2]
SIGNALS_FILE = REPO / "references" / "risk-control-signals.yaml"


def stderr_403(site, url):
    """The measured failure body: YAML on stderr even under -f json."""
    return (
        "ok: false\n"
        "error:\n"
        "  code: COMMAND_EXEC\n"
        f"  message: '{site} request failed: HTTP 403 Forbidden from {url}'\n"
        "  exitCode: 1\n"
    )


STDERR_1P3A_403 = stderr_403(
    "1point3acres", "https://www.1point3acres.com/bbs/forum-145-1.html"
)

STDOUT_51JOB_OK = json.dumps(
    [
        {"rank": 1, "jobId": "173198362",
         "title": "高级算法工程师（视觉调试智能化、AI方向）", "salary": "3-6万",
         "salaryMin": 30000, "salaryMax": 60000, "city": "西安",
         "district": "高新技术产业开发区", "workYear": "3年及以上", "degree": "博士",
         "company": "比亚迪汽车工业", "issueDate": "2026-08-08 10:23:15",
         "url": "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0",
         "encCoId": "VDMHY1M0BDgAZ1c9AWVWZA"},
        {"rank": 2, "jobId": "173199597", "title": "高级AI算法工程师(J10032)",
         "salary": "1.7-3.4万·15薪", "salaryMin": 17000, "salaryMax": 34000,
         "city": "海宁", "district": "", "workYear": "3年", "degree": "硕士",
         "company": "拓荆键科（海宁）半导体设备", "issueDate": "2026-08-08 14:34:16",
         "url": "https://jobs.51job.com/haining/173199597.html?s=sou_sou_soulb&t=0_0",
         "encCoId": "UjJQPFY2DzYPaVQyVDI"},
    ],
    ensure_ascii=False,
)

STDOUT_INDEED_EMPTY_TITLES = json.dumps(
    [
        {"rank": 1, "id": "152875498075cf99", "title": "", "company": "UF Health",
         "location": "Gainesville, FL 32610", "salary": "", "tags": "",
         "url": "https://www.indeed.com/viewjob?jk=152875498075cf99"},
        {"rank": 2, "id": "35fc226942cc38c0", "title": "", "company": "Orthoindy",
         "location": "Lafayette, IN 47909", "salary": "", "tags": "",
         "url": "https://www.indeed.com/viewjob?jk=35fc226942cc38c0"},
    ]
)

# Measured auth rows. Note `logged_in` is an EMPTY STRING on nowcoder, not false.
AUTH_ROWS = [
    {"site": "boss", "status": "logged_in", "logged_in": True, "checked": "quick"},
    {"site": "linkedin", "status": "logged_in", "logged_in": True, "checked": "quick"},
    {"site": "1point3acres", "status": "not_logged_in", "logged_in": False,
     "checked": "full"},
    {"site": "nowcoder", "status": "unknown", "logged_in": "", "checked": "skipped",
     "error": "quickCheck not implemented; use --full to run whoami"},
]


def test_exit0_json_array_is_ok_and_says_nothing():
    r = coc.classify("51job", "search", 0, STDOUT_51JOB_OK, "", AUTH_ROWS)
    assert r["classification"] == "ok"
    assert r["row_count"] == 2
    assert r["empty_result"] is False
    assert r["empty_identity_rows"] == []
    assert r["needs_detail_recovery"] is False
    assert r["remedy"] is None


@pytest.mark.parametrize("status", ["logged_in", "unknown", "not_logged_in"])
def test_explicit_guest_group_wall_overrides_cached_auth_status(status):
    # User-observed message, independent of stale local auth metadata.
    r = coc.classify("1point3acres", "search", 1, "",
        "抱歉，您所在的用户组(游客)无法进行此操作",
        [{"site": "1point3acres", "status": status}])
    assert r["classification"] == "not_logged_in"
    assert r["signal_id"] == "guest-login-wall"
    assert "finish login" in r["remedy"]
    assert r["empty_result"] is False


@pytest.mark.parametrize("message", [
    "请验证您是否是真人", "正在进行人机验证", "Verifying you are human",
    "验证成功。正在等待 www.upwork.com 响应",
])
def test_human_verification_messages_request_user_action_instead_of_retry(message):
    r = coc.classify("upwork", "search", 1, "", message, [], coc.load_signals(SIGNALS_FILE))
    assert r["classification"] == "platform_limit"
    assert "human verification themselves" in r["remedy"]
    assert r["empty_result"] is False


def test_exit0_with_empty_titles_stays_ok_but_demands_detail_recovery():
    r = coc.classify("indeed", "search", 0, STDOUT_INDEED_EMPTY_TITLES, "")
    assert r["classification"] == "ok"          # the rows EXIST
    assert r["row_count"] == 2
    assert r["empty_identity_rows"] == [0, 1]
    assert r["needs_detail_recovery"] is True
    assert r["detail_command"] == "opencli indeed job <id>"
    assert "never read blank fields" in r["remedy"]


def test_exit1_empty_stdout_yaml_stderr_is_not_logged_in():
    r = coc.classify("1point3acres", "forum", 1, "", STDERR_1P3A_403, AUTH_ROWS)
    assert r["classification"] == "not_logged_in"
    assert r["row_count"] == 0
    assert "HTTP 403 Forbidden" in r["error_message"]
    assert "opencli 1point3acres login" in r["remedy"]
    assert "Do not retry" in r["remedy"]


def test_exit1_on_a_site_with_no_auth_adapter_is_no_auth_adapter():
    r = coc.classify(
        "indeed", "search", 1, "",
        stderr_403("indeed", "https://www.indeed.com/jobs?q=mri"), AUTH_ROWS,
    )
    assert r["auth_state"] == "absent"
    assert r["classification"] == "no_auth_adapter"
    assert "does not exist" in r["remedy"]


def test_unknown_auth_status_is_never_collapsed_into_logged_out():
    r = coc.classify(
        "nowcoder", "search", 1, "",
        stderr_403("nowcoder", "https://www.nowcoder.com/search"), AUTH_ROWS,
    )
    assert r["auth_state"] == "unknown"
    assert r["classification"] == "not_logged_in"
    assert "--full" in r["remedy"]


def test_403_while_auth_says_logged_in_is_a_platform_limit():
    r = coc.classify(
        "boss", "search", 1, "",
        stderr_403("boss", "https://www.zhipin.com/web/geek/job"), AUTH_ROWS,
    )
    assert r["classification"] == "platform_limit"
    assert "Stop this site" in r["remedy"]


def test_empty_array_on_exit0_is_a_real_zero_result():
    r = coc.classify("51job", "search", 0, "[]", "", AUTH_ROWS)
    assert r["classification"] == "ok"
    assert r["row_count"] == 0
    assert r["empty_result"] is True


def test_exit_code_wins_over_a_parsable_stdout():
    # The JSON.parse(stdout || '[]') trap. Even when stdout is a perfectly
    # good empty array, a non-zero exit is a failure, not a zero-result.
    r = coc.classify(
        "linkedin", "search", 1, "[]",
        stderr_403("linkedin", "https://www.linkedin.com/jobs/search"), AUTH_ROWS,
    )
    assert r["classification"] != "ok"
    assert r["empty_result"] is False


def test_boss_identity_field_is_name_not_title():
    rows = json.dumps(
        [{"name": "算法工程师", "salary": "20-30K", "company": "某公司",
          "security_id": "abc123def456", "url": "https://www.zhipin.com/job_detail/x"}],
        ensure_ascii=False,
    )
    r = coc.classify("boss", "search", 0, rows, "", AUTH_ROWS)
    assert r["identity_field"] == "name"
    assert r["empty_identity_rows"] == []   # must NOT cry wolf over a missing `title`
    assert r["needs_detail_recovery"] is False


def test_signals_never_match_job_rows_only_a_failed_calls_stderr():
    signals = coc.load_signals(SIGNALS_FILE)
    assert signals, "risk-control-signals.yaml produced no patterns"
    rows = json.dumps(
        [{"jobId": "173100001", "title": "安全验证/风控算法工程师 captcha 方向"}],
        ensure_ascii=False,
    )
    quiet = coc.classify("51job", "search", 0, rows, "", AUTH_ROWS, signals)
    assert quiet["classification"] == "ok"
    assert quiet["signal_id"] is None

    loud = coc.classify(
        "51job", "search", 1, "",
        "ok: false\nerror:\n  code: COMMAND_EXEC\n"
        "  message: 'HTTP 429 Too Many Requests'\n  exitCode: 1\n",
        AUTH_ROWS, signals,
    )
    assert loud["classification"] == "platform_limit"
    assert loud["signal_id"] == "http-429-rate-limited"
    assert "do not retry" in loud["remedy"]


def test_a_signal_outside_error_message_still_fires():
    """The rule is 'matched against the STDERR of a failed call', not 'matched
    against the message field we happened to extract from it'. A body that
    carries the wall while `message` carries only a generic sentence is the
    exact shape a real risk-control page would take, and searching only the
    extracted message would classify it `transport` and let the round continue
    against a platform that just asked us to stop."""
    signals = coc.load_signals(SIGNALS_FILE)
    stderr = (
        "ok: false\n"
        "error:\n"
        "  code: COMMAND_EXEC\n"
        "  message: 'boss request failed'\n"
        "  body: '请完成安全验证后重试'\n"
        "  exitCode: 1\n"
    )
    r = coc.classify("boss", "search", 1, "", stderr, AUTH_ROWS, signals)
    assert r["error_message"] == "boss request failed"   # extraction unchanged
    assert r["classification"] == "platform_limit"
    assert r["signal_id"] == "security-verification-cn"


def test_transport_is_the_default_for_an_unrecognised_failure():
    r = coc.classify(
        "51job", "search", 1, "",
        "ok: false\nerror:\n  code: COMMAND_EXEC\n"
        "  message: 'connect ECONNREFUSED 127.0.0.1:19825'\n  exitCode: 1\n",
    )
    assert r["classification"] == "transport"
    assert "scripts/doctor.py" in r["remedy"]
    assert "daily-browser CDP" in r["remedy"]
    assert "references/network-recovery.md" in r["remedy"]
    assert "opencli doctor" not in r["remedy"]


def test_exit0_with_unparsable_stdout_is_transport_not_ok():
    r = coc.classify("51job", "search", 0, "<html>login</html>", "")
    assert r["classification"] == "transport"


def test_main_writes_exactly_one_adapter_call_record(tmp_path):
    (tmp_path / "raw").mkdir()
    out = tmp_path / "raw" / "51job-1.json"
    out.write_text(STDOUT_51JOB_OK, encoding="utf-8")
    rc = coc.main([
        "--workspace", str(tmp_path),
        "--site", "51job", "--command", "search",
        "--exit-code", "0", "--stdout-file", str(out),
        "--command-line",
        "opencli 51job search 算法工程师 --limit 2 --window background -f json",
    ])
    assert rc == 0
    lines = (tmp_path / "journal.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["action"] == "adapter_call"
    assert rec["site"] == "51job" and rec["command"] == "search"
    assert rec["exit_code"] == 0
    assert rec["classification"] == "ok"
    assert rec["row_count"] == 2
    assert rec["command_line"].startswith("opencli 51job search")


def test_main_exits_2_when_the_stdout_file_is_missing(tmp_path):
    rc = coc.main([
        "--workspace", str(tmp_path), "--site", "51job", "--command", "search",
        "--exit-code", "0", "--stdout-file", str(tmp_path / "nope.json"),
    ])
    assert rc == 2
    assert not (tmp_path / "journal.jsonl").exists()


def test_read_adapter_calls_skips_receipts_and_surfaces_bad_lines(tmp_path):
    (tmp_path / "journal.jsonl").write_text(
        json.dumps({"action": "adapter_call", "site": "51job",
                    "command": "search", "exit_code": 0}) + "\n"
        + json.dumps({"action": "gate", "gate": "check_shortlist",
                      "verdict": "pass"}) + "\n"
        + "{not json at all}\n",
        encoding="utf-8",
    )
    calls = coc.read_adapter_calls(tmp_path)
    assert [c["site"] for c in calls] == ["51job"]
    assert calls[0]["_lineno"] == 1

    records = coc.read_journal(tmp_path)
    assert len(records) == 3
    assert records[2]["_unparsable"] == "{not json at all}"
    assert records[2]["_lineno"] == 3


# ---------------------------------------------------------------------------
# A login wall the classifier does not recognise becomes `transport`, whose
# remedy diagnoses the connection — when the correct remedy is to hand the user
# `opencli <site> login`. A wrong remedy costs more than none: it sends them to
# debug a working adapter. One Chinese phrase and three English ones covered it.
# ---------------------------------------------------------------------------

_WALLS = [
    "需要登录", "请先登录后查看", "登录后查看完整信息",
    "ログインが必要です", "로그인이 필요합니다",
    "Bitte melden Sie sich an", "U bent niet ingelogd",
    "Veuillez vous connecter", "Sign in to view", "Please log in",
    "session expired", "authentication required",
]
_NOT_WALLS = [
    "HTTP 500 server error", "connection reset by peer",
    "no results found for this query", "rate limit exceeded",
]


@pytest.mark.parametrize("text", _WALLS, ids=range(len(_WALLS)))
def test_a_login_wall_is_recognised_in_the_language_the_site_answered_in(text):
    assert any(p.search(text) for p in coc.LOGIN_WALL_PATTERNS), text


@pytest.mark.parametrize("text", _NOT_WALLS, ids=range(len(_NOT_WALLS)))
def test_an_ordinary_failure_is_not_mistaken_for_one(text):
    """Misreading a real transport fault as a login wall sends the user to log
    in to a site they are already logged in to."""
    assert not any(p.search(text) for p in coc.LOGIN_WALL_PATTERNS), text


_TRANSPORT_NOT_WALLS = [
    "500 Internal Server Error while loading your sign in preferences page",
    "Connection reset while rendering the 'Log In' navbar link",
    "Timeout fetching https://example.com/signin-help",
    "recruiter@example.com invites you to sign in and view their profile",
]
_REAL_WALLS = ["Please log in", "You must sign in to continue", "Sign in to view",
               "login required", "not logged in", "需要登录", "ログインが必要です"]


@pytest.mark.parametrize("text", _TRANSPORT_NOT_WALLS,
                         ids=range(len(_TRANSPORT_NOT_WALLS)))
def test_a_bare_mention_of_signing_in_is_not_a_login_wall(text):
    """A bare `sign in` matched a 500 page and a navbar label, routing a genuine
    transport fault to "run opencli <site> login" — the wrong-remedy failure this
    list exists to prevent, pointing the other way."""
    assert not any(p.search(text) for p in coc.LOGIN_WALL_PATTERNS), text


@pytest.mark.parametrize("text", _REAL_WALLS, ids=range(len(_REAL_WALLS)))
def test_an_instruction_to_sign_in_still_is(text):
    assert any(p.search(text) for p in coc.LOGIN_WALL_PATTERNS), text
