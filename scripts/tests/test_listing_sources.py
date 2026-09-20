"""A row may only claim a posting exists if its source publishes postings.

Reproduced 2026-09-20: a 面经 thread — someone's write-up of an interview they
already sat — was given a shortlist row with `verdict: stretch`, and
check_shortlist exited 0 in silence. Every provenance anchor held, because they
all hold: the id really is in the capture, the raw_text really was copied, the
URL really came from the adapter. What none of them can see is that the thing
retrieved is not a job opening.

modes/discover.md has said "a forum thread is not a posting with a `source_id` a
row can be traced to" since the mode was written. It was prose with nothing
behind it.
"""
import json

import pytest

import check_shortlist as cs
import discover_fixtures as fx
import discovery_catalogue
import journal


def run(workspace, capsys):
    code = cs.main(["--workspace", str(workspace)])
    return code, capsys.readouterr()


def codes(out):
    return sorted({line.split(":", 1)[0] for line in out.strip().splitlines() if line})


def add_site(workspace, site, command, rows, row, *, help_yaml=True):
    """Give `workspace` a capture, a receipt, a sources entry and a row."""
    capture = f"raw/{site}-1.json"
    (workspace / capture).write_text(json.dumps(rows, ensure_ascii=False),
                                     encoding="utf-8")
    (workspace / f"raw/{site}-1.err").write_text("", encoding="utf-8")
    if help_yaml:
        (workspace / "raw" / "opencli-help" / f"{site}.yaml").write_text(
            "commands:\n  - name: %s\n    access: read\n" % command, encoding="utf-8")
    journal.append(workspace, {
        "action": "adapter_call", "site": site, "command": command,
        "classification": "ok", "exit_code": 0, "row_count": len(rows),
        "identity_field": "title", "empty_identity_rows": [],
        "stdout_file": capture, "stderr_file": f"raw/{site}-1.err",
        "command_line": f"opencli {site} {command} \"x\" -f json",
        "ts": "2026-08-09T15:00:00Z"})
    data = fx.load_shortlist(workspace)
    data["sources"].append({
        "site": site, "command": command, "access": "read",
        "login_state": "not_logged_in", "classification": "ok", "invocations": 1,
        "rows_returned": len(rows), "identity_field": "title",
        "identity_field_empty_rows": 0,
        "detail_command": f"opencli {site} detail <id>",
        "raw_files": [capture]})
    data["rows"].append(row)
    fx.save_shortlist(workspace, data)

    import yaml
    match = yaml.safe_load((workspace / "candidate-match.yaml").read_text("utf-8"))
    match["rows"].append({"id": row["id"], "basis": "card",
                          "recommendation": "review", "requirements": []})
    (workspace / "candidate-match.yaml").write_text(
        yaml.safe_dump(match, allow_unicode=True, sort_keys=False), encoding="utf-8")

    md = (workspace / "shortlist.md").read_text(encoding="utf-8")
    (workspace / "shortlist.md").write_text(
        md + f"3. **{row['title']}** — {row['company']}\n"
        f"   — `{row['verdict']}`（初判）· 未取详情 · [打开职位]({row['url']})\n"
        "   - 简历匹配：仅有职位卡，尚未读取完整要求；这是一条待核实线索，不是推荐。\n",
        encoding="utf-8")


NOWCODER_POST = {
    "id": "78451230", "title": "字节跳动 算法工程师 三面面经（已oc）",
    "author": "牛客1024号", "type": "post",
    "url": "https://www.nowcoder.com/feed/main/detail/78451230"}

NOWCODER_ROW = {
    "id": "nowcoder-78451230", "title": "字节跳动 算法工程师 三面面经（已oc）",
    "company": "字节跳动", "location": "", "salary": "",
    "url": "https://www.nowcoder.com/feed/main/detail/78451230",
    "source_site": "nowcoder", "source_id": "78451230",
    "extraction_method": "adapter_search", "retrieved_at": "2026-08-09T15:00:00Z",
    "quality": "card_only", "verification": "collected_unverified",
    "raw_text": "字节跳动 算法工程师 三面面经（已oc） | 牛客1024号",
    "why_matched": "brief.target_titles 命中「算法工程师」。",
    "verdict": "stretch", "provisional": True, "effort": "evening"}


def test_a_forum_thread_cannot_become_a_shortlist_row(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    add_site(workspace, "nowcoder", "search", [NOWCODER_POST], NOWCODER_ROW)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NOT_A_LISTING_SOURCE" in codes(captured.out)
    assert "nowcoder" in captured.out


def test_the_recruiter_side_adapter_cannot_produce_rows_either(tmp_path, capsys):
    """maimai returns people, not postings — the same claim, a different shape."""
    workspace = fx.build_workspace(tmp_path)
    person = {"id": "mm-90021", "title": "资深算法工程师",
              "company": "某大型互联网公司",
              "url": "https://maimai.cn/contact/detail/90021"}
    row = dict(NOWCODER_ROW, id="maimai-90021", source_site="maimai",
               source_id="90021", title="资深算法工程师",
               company="某大型互联网公司",
               url="https://maimai.cn/contact/detail/90021",
               raw_text="资深算法工程师 | 某大型互联网公司")
    add_site(workspace, "maimai", "search-talents", [person], row)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NOT_A_LISTING_SOURCE" in codes(captured.out)


def test_the_valid_workspace_stays_silent(tmp_path, capsys):
    """The cry-wolf control: a real 51job round must not acquire a finding."""
    workspace = fx.build_workspace(tmp_path)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_site_the_catalogue_does_not_know_is_not_refused(tmp_path, capsys):
    """modes/discover.md routes European rounds to country sites and
    market-native boards through the browser. Those are not adapters, so an
    allow-list keyed on the catalogue would refuse exactly the rows that fix
    was added to enable."""
    workspace = fx.build_workspace(tmp_path)
    posting = {"id": "at-556677", "title": "PhD candidate MRI reconstruction",
               "company": "Leiden University Medical Center",
               "url": "https://www.academictransfer.com/en/jobs/556677/"}
    row = dict(NOWCODER_ROW, id="academictransfer-556677",
               source_site="academictransfer", source_id="556677",
               title="PhD candidate MRI reconstruction",
               company="Leiden University Medical Center",
               url="https://www.academictransfer.com/en/jobs/556677/",
               raw_text="PhD candidate MRI reconstruction | "
                        "Leiden University Medical Center")
    add_site(workspace, "academictransfer", "search", [posting], row)
    code, captured = run(workspace, capsys)
    assert "NOT_A_LISTING_SOURCE" not in codes(captured.out)


def test_a_detail_only_row_on_a_listing_site_is_not_refused(tmp_path, capsys):
    """Ranking mode (discover entry condition 5) starts from pasted URLs, so the
    row's id appears only in a detail capture. Requiring a search capture would
    fire on that whole legitimate mode."""
    workspace = fx.build_workspace(tmp_path)
    detail = {"id": "4467709200", "title": "Machine Learning Python Developer",
              "company": "Pera", "location": "'s-Hertogenbosch",
              "url": "https://www.linkedin.com/jobs/view/4467709200"}
    row = dict(NOWCODER_ROW, id="linkedin-4467709200", source_site="linkedin",
               source_id="4467709200", title="Machine Learning Python Developer",
               company="Pera", location="'s-Hertogenbosch",
               url="https://www.linkedin.com/jobs/view/4467709200",
               extraction_method="user_paste",
               raw_text="Machine Learning Python Developer | Pera")
    add_site(workspace, "linkedin", "job-detail", [detail], row)
    code, captured = run(workspace, capsys)
    assert "NOT_A_LISTING_SOURCE" not in codes(captured.out)


def test_the_verdict_follows_the_catalogue_not_a_list_in_the_gate(
        tmp_path, capsys, monkeypatch):
    """Rewrite the catalogue and the gate must change its mind.

    Grepping check_shortlist.py for "nowcoder" only proves the word is absent,
    which a comment can break. This drives the real question: if a future round
    measures `opencli nowcoder jobs` and records it as a posting command, does
    the refusal lift — and does it lift only for that command?
    """
    catalogue = tmp_path / "discovery-sources.md"
    catalogue.write_text(
        "```yaml\nadapters:\n"
        "  nowcoder:\n    identity_field: title\n"
        "    listing_commands: [jobs]\n"
        "```\n", encoding="utf-8")
    monkeypatch.setattr(discovery_catalogue, "CATALOGUE", catalogue)
    discovery_catalogue.adapters.cache_clear()
    try:
        workspace = fx.build_workspace(tmp_path / "ws")
        add_site(workspace, "nowcoder", "search", [NOWCODER_POST], NOWCODER_ROW)
        code, captured = run(workspace, capsys)
        # `search` still returns 面经, so the row is still refused — but now
        # because the CATALOGUE says search is not a posting command.
        assert "NOT_A_LISTING_SOURCE" in codes(captured.out)
        assert "jobs" in captured.out, "the finding must quote the catalogue"
    finally:
        discovery_catalogue.adapters.cache_clear()


@pytest.mark.parametrize("site", ("51job", "indeed", "linkedin", "boss", "upwork"))
def test_every_job_source_declares_the_command_that_returns_postings(site):
    assert discovery_catalogue.listing_commands(site), site


@pytest.mark.parametrize("site", ("nowcoder", "maimai"))
def test_a_non_job_source_declares_no_listing_command(site):
    assert discovery_catalogue.listing_commands(site) == ()


def test_a_broken_catalogue_reports_itself_instead_of_crashing(
        tmp_path, capsys, monkeypatch):
    """This gate's contract is findings on stdout and exit 0/1, never a
    traceback. If the file it judges by is gone, the run has to say so once."""
    missing = tmp_path / "gone.md"
    monkeypatch.setattr(discovery_catalogue, "CATALOGUE", missing)
    discovery_catalogue.adapters.cache_clear()
    try:
        workspace = fx.build_workspace(tmp_path / "ws")
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "CATALOGUE_UNREADABLE" in codes(captured.out)
        assert captured.out.count("CATALOGUE_UNREADABLE") == 1, "once, not per row"
    finally:
        discovery_catalogue.adapters.cache_clear()


@pytest.mark.parametrize("spelling", ["NOWCODER", "Nowcoder", "nowcoder ", " nowcoder"])
def test_case_and_padding_do_not_switch_the_check_off(tmp_path, capsys, spelling):
    """`source_site` is written by hand, and the catalogue is keyed lowercase.

    Probed 2026-09-20: is_catalogued("NOWCODER") was False, so the site fell
    through the "not in the catalogue" branch that exists for browser-route
    boards — and a forum thread passed again. A check a capital letter turns
    off is not a check.
    """
    workspace = fx.build_workspace(tmp_path)
    row = dict(NOWCODER_ROW, source_site=spelling)
    add_site(workspace, "nowcoder", "search", [NOWCODER_POST], row)
    data = fx.load_shortlist(workspace)
    data["rows"][-1]["source_site"] = spelling
    fx.save_shortlist(workspace, data)
    _, captured = run(workspace, capsys)
    assert "NOT_A_LISTING_SOURCE" in codes(captured.out), spelling
