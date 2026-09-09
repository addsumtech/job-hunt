"""The reference catalogue must stay in sync with the code that depends on it."""
import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
SOURCES = REPO / "references" / "discovery-sources.md"
SIGNALS = REPO / "references" / "risk-control-signals.yaml"
SKILL = REPO / "SKILL.md"

INLINED = ("51job", "indeed", "linkedin", "boss")
NON_INLINED = ("upwork", "nowcoder", "1point3acres", "maimai")


def adapters():
    text = SOURCES.read_text(encoding="utf-8")
    match = re.search(r"```yaml\n(.*?)\n```", text, re.S)
    assert match, "discovery-sources.md has no fenced yaml block"
    block = yaml.safe_load(match.group(1))
    return block["adapters"]


def test_every_adapter_in_the_capability_matrix_is_catalogued():
    table = adapters()
    for site in INLINED + NON_INLINED:
        assert site in table, f"{site} is missing from the adapters block"


def test_every_adapter_entry_carries_the_fields_the_source_report_needs():
    for site, entry in adapters().items():
        for field in ("identity_field", "detail_command",
                      "login_state_2026_08_09", "runtime_verified",
                      "search_command", "pagination", "caps"):
            assert field in entry, f"{site}.{field} missing"
        assert entry["login_state_2026_08_09"] in (
            "logged_in", "not_logged_in", "unknown", "no_auth_adapter")
        assert isinstance(entry["runtime_verified"], bool)


def test_boss_identity_field_matches_the_classifier():
    import check_opencli_result as coc
    table = adapters()
    for site, entry in table.items():
        expected = coc.IDENTITY_FIELD.get(site, coc.IDENTITY_FIELD_DEFAULT)
        if entry["identity_field"] != "n/a":
            assert entry["identity_field"] == expected, (
                f"{site}: catalogue says {entry['identity_field']!r}, "
                f"check_opencli_result says {expected!r}")


def test_every_risk_control_signal_string_appears_in_the_catalogue():
    text = SOURCES.read_text(encoding="utf-8")
    data = yaml.safe_load(SIGNALS.read_text(encoding="utf-8"))
    for signal in data["signals"]:
        assert signal["pattern"] in text, (
            f"signal {signal['id']!r} pattern {signal['pattern']!r} is not "
            "documented in references/discovery-sources.md")
        assert signal["id"] in text


def test_the_catalogue_states_which_adapters_were_never_run():
    table = adapters()
    # Measured 2026-08-09: only 51job, indeed and 1point3acres were executed.
    assert table["51job"]["runtime_verified"] is True
    assert table["indeed"]["runtime_verified"] is True
    assert table["boss"]["runtime_verified"] is False
    assert table["linkedin"]["runtime_verified"] is False


def test_maimai_is_marked_as_having_no_job_search():
    text = SOURCES.read_text(encoding="utf-8")
    assert "maimai has no job-search capability" in text
    assert adapters()["maimai"]["search_command"] is None


def test_the_degraded_fallback_field_list_is_present():
    text = SOURCES.read_text(encoding="utf-8")
    for field in ("目标方向", "检索词", "建议筛选条件", "为何比原 JD 更稳",
                  "要避开的标题与信号", "手动收集优先序"):
        assert field in text


def test_skill_md_carries_the_discovery_trigger():
    text = SKILL.read_text(encoding="utf-8")
    assert "<!-- BEGIN discover-inserts (plan 3) -->" in text
    assert "<!-- END discover-inserts (plan 3) -->" in text
    assert "references/discovery-sources.md" in text
    assert "about to call an adapter other than the four" in text
    for site in INLINED:
        assert site in text


def test_the_trigger_sentence_survives_line_wrapping_in_both_files():
    # It is one evaluable sentence, and it is load-bearing in two files. A
    # newline dropped into the middle of it deletes the assertion above
    # without deleting the paragraph a reader sees, which is the worst
    # possible failure shape for a layer-2 trigger.
    phrase = "about to call an adapter other than the four"
    assert phrase in SKILL.read_text(encoding="utf-8")
    assert phrase in SOURCES.read_text(encoding="utf-8")


def test_skill_md_states_the_exit_code_rule_the_write_ban_and_the_stop_rule():
    text = SKILL.read_text(encoding="utf-8")
    assert "branch on the exit code before you read stdout" in text
    assert "access:` is `write" in text
    # spec §6 lists the platform-limit stop rule as layer-1 content: the
    # per-platform trigger strings are data, this dogma is not. All six
    # clauses, because dropping any one of them is how "stop" quietly becomes
    # "stop, then try a smaller limit".
    assert "Stop that site for that round." in text
    assert "Do not retry." in text
    assert "Do not change parameters and retry" in text
    assert "Do not route around it" in text
    assert "direction-level degraded output" in text
    assert "disclosure table" in text


def test_discovery_backend_selection_is_opencli_first_and_one_way():
    """A browser is a diagnosed fallback, never an equally preferred backend."""
    mode = (REPO / "modes" / "discover.md").read_text(encoding="utf-8")
    fallback = (REPO / "references" / "browser-fallback.md").read_text(
        encoding="utf-8")
    skill = SKILL.read_text(encoding="utf-8")

    assert "OpenCLI first; one-way web-access fallback" in mode
    assert "run `opencli doctor`" in mode
    assert "web-access-to-OpenCLI fallback for the same round" in mode
    assert "Use **OpenCLI** when the required read adapter" in fallback
    assert re.search(r"Web-access is a one-way\s+fallback", fallback)
    assert "Begin every discovery round with OpenCLI" in skill
    assert "do not switch back to\nOpenCLI for the same round" in skill


def test_sandbox_local_bridge_diagnosis_precedes_browser_fallback():
    """A runner that cannot bind localhost is not evidence that the site refused."""
    mode = (REPO / "modes" / "discover.md").read_text(encoding="utf-8")
    fallback = (REPO / "references" / "browser-fallback.md").read_text(
        encoding="utf-8")
    for text in (mode, fallback):
        assert "BROWSER_CONNECT" in text
        assert "127.0.0.1:19825" in text
        assert "host-local or unsandboxed" in text
        assert "site refusal" in text
        assert "EADDRINUSE" in text
