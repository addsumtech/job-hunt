"""Completion is coverage of planned work, never the number of selected rows."""
import copy
import json

import pytest
import yaml

import check_search_coverage as gate
import deliver
import journal


def save(ws, data):
    (ws / gate.FILE).write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def seed_coverage(ws, rounds=None):
    """Add a BEFORE-retrieval registration to a historical test fixture only."""
    roots = rounds or [ws]
    plan = {"sources": [{"id": "jobs", "site": "51job", "label": "51job", "method": "catalog"}],
            "directions": [{"id": "engineering", "label": "Engineering"}]}
    if rounds:
        plan["rounds"] = [str(r) for r in roots]
    name = "raw/51job-1.json"
    ref = {"workspace": str(roots[0]), "file": name,
           "sha256": journal.sha256_file(roots[0] / name), "quote": "博士"}
    data = {"plan": plan, "checks": [{"source": "jobs", "direction": "engineering",
        "status": "done", "reason": "Reviewed both returned engineering positions.", "evidence": ref}],
        "leads": [{"site": "51job", "source_id": "173198362", "status": "excluded",
                   "reason_code": "eligibility", "reason": "Requires a doctorate.", "evidence": ref}]}
    save(ws, data)
    old = (ws / "journal.jsonl").read_text() if (ws / "journal.jsonl").exists() else ""
    rec = journal.sign_receipt({"action": gate.ACTION, "ts": "2026-08-09T14:01:30Z", "plan": plan})
    (ws / "journal.jsonl").write_text(json.dumps(rec) + "\n" + old)


def build(tmp_path):
    ws = tmp_path / "search"
    (ws / "raw").mkdir(parents=True)
    (ws / "brief.yaml").write_text("target_count: 18\n")
    (ws / "shortlist.yaml").write_text("rows: []\n")
    (ws / "report.md").write_text("Search report\n")
    data = {"plan": {"sources": [{"id": "a", "site": "employer", "label": "Employer", "method": "search"}],
                     "directions": [{"id": "ib", "label": "Investment banking", "query": "IB Analyst"}]},
            "checks": [], "leads": []}
    save(ws, data)
    assert gate.main(["--workspace", str(ws), "--record-plan"]) == 0
    return ws, data


def capture(ws, rows, site="employer", classification="ok", command="search"):
    name = f"raw/{site}-{len(journal._records(ws))}.json"
    value = rows if classification == "ok" else {"error": "Access denied by employer"}
    (ws / name).write_text(json.dumps(value), encoding="utf-8")
    journal.append(ws, {"action": "adapter_call", "site": site, "command": command,
        "ts": "2099-01-01T00:00:00Z", "classification": classification,
        "query": "IB Analyst", "exit_code": 0 if classification == "ok" else 1, "stdout_file": name})
    quote = "No matching jobs" if not rows else str(rows[0].get("title", "Analyst"))
    if not rows and classification == "ok":
        (ws / name).write_text(json.dumps({"message": "No matching jobs", "rows": []}))
    if classification != "ok":
        quote = "Access denied by employer"
    return {"file": name, "sha256": journal.sha256_file(ws / name), "quote": quote}


def close(ws, data, ref, status="done"):
    data["checks"] = [{"source": "a", "direction": "ib", "status": status,
                       "reason": "Reviewed current IB Analyst results.", "evidence": ref}]
    save(ws, data)


def test_complete_empty_search_and_receipt_recheck(tmp_path):
    ws, data = build(tmp_path)
    close(ws, data, capture(ws, []))
    assert gate.inspect(ws) == []
    assert gate.main(["--workspace", str(ws)]) == 0
    data["checks"][0]["status"] = "pending"
    save(ws, data)
    assert "pending" in gate.inspect(ws)[0]


def test_target_count_does_not_close_remaining_leads(tmp_path):
    ws, data = build(tmp_path)
    rows = [{"id": str(i), "title": "IB Analyst"} for i in range(19)]
    close(ws, data, capture(ws, rows))
    (ws / "shortlist.yaml").write_text(yaml.safe_dump({"rows": [
        {"source_site": "employer", "source_id": str(i), "id": str(i)} for i in range(18)]}))
    assert "employer/18" in gate.inspect(ws)[0]
    ref = copy.deepcopy(data["checks"][0]["evidence"])
    data["leads"] = [{"site": "employer", "source_id": "18", "status": "excluded",
                      "reason_code": "enough_jobs", "reason": "Target already reached", "evidence": ref}]
    save(ws, data)
    assert "exclusion reason" in gate.inspect(ws)[0]


@pytest.mark.parametrize("mutation,expected", [
    ("missing_check", "every planned"), ("pending", "pending"),
    ("hash", "hash"), ("quote", "quote"), ("query", "query"), ("query_substring", "query"),
    ("detail", "search/catalog"), ("fake_block", "access failure"),
    ("outside", "outside declared"), ("unknown_source", "unplanned source")])
def test_invalid_completion(tmp_path, mutation, expected):
    ws, data = build(tmp_path)
    ref = capture(ws, [], site="other" if mutation == "unknown_source" else "employer",
                  command="detail" if mutation == "detail" else "search")
    close(ws, data, ref)
    item = data["checks"][0]
    if mutation == "missing_check":
        data["checks"] = []
    elif mutation == "pending":
        item["status"] = "pending"
    elif mutation == "hash":
        item["evidence"]["sha256"] = "wrong"
    elif mutation == "quote":
        item["evidence"]["quote"] = "fabricated quote"
    elif mutation in {"query", "query_substring"}:
        records = journal._records(ws)
        records[-1]["query"] = "Other job" if mutation == "query" else "Senior IB Analyst"
        (ws / "journal.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    elif mutation == "fake_block":
        item["status"] = "blocked"
        (ws / "report.md").write_text(item["reason"])
    elif mutation == "outside":
        item["evidence"]["workspace"] = "../unlisted"
    save(ws, data)
    assert expected in gate.inspect(ws)[0]


def test_access_block_requires_visible_reason_and_other_directions_done(tmp_path):
    ws, data = build(tmp_path)
    data["plan"]["directions"].append({"id": "markets", "label": "Markets", "query": "Markets Analyst"})
    save(ws, data)
    gate.record_plan(ws)
    ref = capture(ws, [], classification="not_logged_in")
    close(ws, data, ref, "blocked")
    assert "every planned" in gate.inspect(ws)[0]
    second = copy.deepcopy(data["checks"][0])
    second["direction"] = "markets"
    data["checks"].append(second)
    save(ws, data)
    assert "visible" in gate.inspect(ws)[0]
    (ws / "report.md").write_text(second["reason"])
    assert gate.inspect(ws) == []


def test_scope_cannot_be_registered_late_or_reduced(tmp_path):
    ws, data = build(tmp_path)
    capture(ws, [])
    data["plan"]["sources"].append({"id": "b", "site": "second", "label": "Second", "method": "catalog"})
    save(ws, data)
    gate.record_plan(ws)
    data["plan"]["sources"].pop()
    save(ws, data)
    with pytest.raises(ValueError, match="shrink"):
        gate.record_plan(ws)
    (ws / "journal.jsonl").write_text(json.dumps({"action": "adapter_call"}) + "\n")
    assert gate.main(["--workspace", str(ws), "--record-plan"]) == 2


def test_mode_switch_and_direct_delivery_cannot_bypass(tmp_path):
    from test_deliver import discovery_delivery
    ws, _ = discovery_delivery(tmp_path, detail_only=True)
    (ws / gate.FILE).unlink()
    journal.append(ws, {"action": "mode_entry", "mode": "assess"})
    assert "preregistered" in deliver._discover_handoff_problem(ws)
    dest = tmp_path / "out"
    written, findings = deliver.deliver(ws, dest, "test", make_pdf=False)
    assert written == [] and "preregistered" in findings[0]
    assert not dest.exists()


def test_catalog_exclusion_quote_is_for_the_same_lead(tmp_path):
    ws, data = build(tmp_path)
    rows = [{"id": "job1", "title": "IB Analyst", "degree": "Masters"},
            {"id": "job2", "title": "IB Analyst", "degree": "Doctorate"}]
    ref = capture(ws, rows)
    close(ws, data, ref)
    (ws / "shortlist.yaml").write_text(yaml.safe_dump({"rows": [
        {"source_site": "employer", "source_id": "job2", "id": "retained"}]}))
    ref["quote"] = "Doctorate"
    data["leads"] = [{"site": "employer", "source_id": "job1", "status": "excluded",
                      "reason_code": "eligibility", "reason": "Requires doctorate", "evidence": ref}]
    save(ws, data)
    assert "this observed lead" in gate.inspect(ws)[0]
    ref["quote"] = "Masters"
    save(ws, data)
    assert gate.inspect(ws) == []


def test_explicit_preliminary_is_required_even_with_zero_rows(tmp_path):
    ws, data = build(tmp_path)
    (ws / "brief.yaml").write_text("report_scope: preliminary\n")
    assert "explicit request" in gate.inspect(ws)[0]
    (ws / "brief.yaml").write_text("report_scope: preliminary\npreliminary_request: Show the initial results now\n")
    assert gate.inspect(ws) == []


def test_registered_collection_rounds_cannot_disappear(tmp_path):
    ws, data = build(tmp_path)
    (ws / "collection.yaml").write_text("rounds:\n  - workspace: .\n")
    close(ws, data, capture(ws, []))
    assert "rounds cannot disappear" in gate.inspect(ws)[0]


def test_browser_capture_is_revalidated_even_after_pass(tmp_path):
    import record_browser_capture as browser
    ws, data = build(tmp_path)
    snapshot = ws / "raw/employer-browser.json"
    rows_file = ws / "raw/employer-rows.json"
    snapshot.write_text(json.dumps({"url": "https://example.com/jobs",
        "retrieved_at": "2099-01-01T00:00:00Z", "text": "No matching jobs",
        "links": []}))
    rows_file.write_text("[]")
    assert browser.main(["--workspace", str(ws), "--site", "employer",
        "--snapshot-file", str(snapshot), "--rows-file", str(rows_file),
        "--fallback-reason", "preferred_browser", "--query", "IB Analyst"]) == 0
    ref = {"file": "raw/employer-browser.json", "sha256": journal.sha256_file(snapshot),
           "quote": "No matching jobs"}
    close(ws, data, ref)
    assert gate.main(["--workspace", str(ws)]) == 0
    rows_file.write_text('[{"id": "unreviewed"}]')
    assert "invalid browser coverage evidence" in gate.inspect(ws)[0]


def test_collection_filter_cannot_hide_an_unprocessed_capture(tmp_path):
    from test_deliver import discovery_delivery
    ws, _ = discovery_delivery(tmp_path, detail_only=True)
    data = yaml.safe_load((ws / gate.FILE).read_text())
    data["leads"] = []  # The doctorate card is absent from the selected shortlist.
    save(ws, data)
    assert "173198362" in deliver._discover_handoff_problem(ws)


def test_wrong_source_capture_cannot_close_another_source(tmp_path):
    ws, data = build(tmp_path)
    data["plan"]["sources"].append({"id": "b", "site": "another", "label": "Another", "method": "catalog"})
    save(ws, data)
    gate.record_plan(ws)
    ref = capture(ws, [])
    close(ws, data, ref)
    data["checks"].append({**data["checks"][0], "source": "b"})
    save(ws, data)
    assert "same-source" in gate.inspect(ws)[0]


def test_registration_content_cannot_be_rewritten(tmp_path):
    ws, data = build(tmp_path)
    close(ws, data, capture(ws, []))
    records = journal._records(ws)
    records[0]["plan"]["directions"][0]["label"] = "Changed later"
    (ws / "journal.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    assert "registration is altered" in gate.inspect(ws)[0]


def test_adding_a_direction_cannot_reuse_an_earlier_capture(tmp_path):
    ws, data = build(tmp_path)
    ref = capture(ws, [])
    close(ws, data, ref)
    data["plan"]["directions"].append({"id": "second", "label": "Another focus", "query": "IB Analyst"})
    save(ws, data)
    gate.record_plan(ws)
    # Controlled fixture chronology: the extension follows the capture.
    records = journal._records(ws)
    records[-1] = journal.sign_receipt({**records[-1], "ts": "2099-01-02T00:00:00Z"})
    (ws / "journal.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    data["checks"].append({**data["checks"][0], "direction": "second"})
    save(ws, data)
    assert "direction was added after" in gate.inspect(ws)[0]


def test_one_failed_detail_does_not_close_the_source_search(tmp_path):
    ws, data = build(tmp_path)
    close(ws, data, capture(ws, [], classification="transport", command="detail"), "blocked")
    (ws / "report.md").write_text(data["checks"][0]["reason"])
    assert "one failed detail" in gate.inspect(ws)[0]


def test_detail_timeout_does_not_close_an_unrelated_lead(tmp_path):
    ws, data = build(tmp_path)
    close(ws, data, capture(ws, [{"id": "job1", "title": "IB Analyst"}]))
    ref = capture(ws, [], classification="transport", command="detail")
    reason = "Another detail timed out."
    data["leads"] = [{"site": "employer", "source_id": "job1", "status": "blocked",
                      "reason": reason, "evidence": ref}]
    save(ws, data)
    (ws / "report.md").write_text(reason)
    assert "does not identify this blocked lead" in gate.inspect(ws)[0]


# --- 2026-09-19 review: real adapter row shapes and capture path spellings ---

def build_for(tmp_path, site):
    ws = tmp_path / "search"
    (ws / "raw").mkdir(parents=True)
    (ws / "brief.yaml").write_text("target_count: 18\n")
    (ws / "shortlist.yaml").write_text("rows: []\n")
    (ws / "report.md").write_text("Search report\n")
    data = {"plan": {"sources": [{"id": "a", "site": site, "label": site, "method": "search"}],
                     "directions": [{"id": "ib", "label": "Investment banking", "query": "IB Analyst"}]},
            "checks": [], "leads": []}
    save(ws, data)
    assert gate.main(["--workspace", str(ws), "--record-plan"]) == 0
    return ws, data


def rewrite_last_record(ws, **fields):
    records = journal._records(ws)
    records[-1].update(fields)
    (ws / "journal.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")


def test_an_absolute_capture_path_inside_the_workspace_counts(tmp_path):
    # check_opencli_result stores the caller's spelling; discover.md never says
    # it must be relative, and check_candidate_match already accepts this.
    ws, data = build(tmp_path)
    ref = capture(ws, [])
    rewrite_last_record(ws, stdout_file=str(ws / ref["file"]))
    close(ws, data, ref)
    assert gate.inspect(ws) == []
    data["checks"][0]["evidence"]["file"] = str(ws / ref["file"])
    save(ws, data)
    assert gate.inspect(ws) == []


def test_an_absolute_capture_path_outside_the_workspace_is_refused(tmp_path):
    ws, data = build(tmp_path)
    ref = capture(ws, [])
    elsewhere = tmp_path / "elsewhere" / "raw"
    elsewhere.mkdir(parents=True)
    (elsewhere / "copy.json").write_bytes((ws / ref["file"]).read_bytes())
    rewrite_last_record(ws, stdout_file=str(elsewhere / "copy.json"))
    close(ws, data, ref)
    assert "missing raw retrieval evidence" in gate.inspect(ws)[0]


BOSS_ROW = {"name": "MRI Research Scientist", "salary": "30-50K", "company": "Example",
            "security_id": "SMzaHPdmtJoWE-M1zr66ObwG5zSONfydn5a",
            "url": "https://www.zhipin.com/job_detail/77657ebca4c7a4c90nF73ty-GVVS.html"}


def test_boss_rows_are_leads_keyed_like_the_shortlist(tmp_path):
    ws, data = build_for(tmp_path, "boss")
    ref = capture(ws, [BOSS_ROW], site="boss")
    close(ws, data, {**ref, "quote": "MRI Research Scientist"})
    assert "boss/77657ebca4c7a4c90nF73ty-GVVS" in " ".join(gate.inspect(ws))
    (ws / "shortlist.yaml").write_text(yaml.safe_dump({"rows": [
        {"source_site": "boss", "source_id": "77657ebca4c7a4c90nF73ty-GVVS",
         "id": "boss-77657ebca4c7a4c90nF73ty-GVVS"}]}))
    assert gate.inspect(ws) == []


def test_indeed_rows_with_empty_titles_are_still_leads(tmp_path):
    ws, data = build_for(tmp_path, "indeed")
    row = {"title": "", "company": "Example", "location": "Austin, TX", "salary": "",
           "id": "7f1d2c3b4a5e6f70", "url": "https://www.indeed.com/viewjob?jk=7f1d2c3b4a5e6f70"}
    ref = capture(ws, [row], site="indeed")
    ref["quote"] = "Austin, TX"
    close(ws, data, ref)
    assert "indeed/7f1d2c3b4a5e6f70" in " ".join(gate.inspect(ws))


def test_a_linkedin_search_url_and_view_url_are_one_lead(tmp_path):
    ws, data = build_for(tmp_path, "linkedin")
    rows = [{"rank": "1", "title": "ML Engineer", "company": "Example",
             "url": "https://www.linkedin.com/jobs/view/4453121690"},
            {"title": "ML Engineer", "company": "Example",
             "url": "https://www.linkedin.com/jobs/search/?currentJobId=4453121690&keywords=ml"}]
    close(ws, data, capture(ws, rows, site="linkedin"))
    assert "linkedin/4453121690" in gate.inspect(ws)[0]
    (ws / "shortlist.yaml").write_text(yaml.safe_dump({"rows": [
        {"source_site": "linkedin", "source_id": "4453121690", "id": "linkedin-4453121690"}]}))
    assert gate.inspect(ws) == []


def test_a_disposition_may_name_the_lead_by_its_url(tmp_path):
    # Runs made while the gate keyed LinkedIn leads by full URL wrote that URL
    # as source_id; the same posting must still resolve to the same lead.
    ws, data = build_for(tmp_path, "linkedin")
    rows = [{"title": "ML Engineer", "company": "Example", "location": "Delft",
             "url": "https://www.linkedin.com/jobs/view/4453121690"}]
    ref = capture(ws, rows, site="linkedin")
    close(ws, data, ref)
    data["leads"] = [{"site": "linkedin", "source_id": rows[0]["url"], "status": "excluded",
                      "reason_code": "wrong_location", "reason": "Outside the commute radius",
                      "evidence": {**ref, "quote": "Delft"}}]
    save(ws, data)
    assert gate.inspect(ws) == []


def test_an_article_lead_can_be_excluded_as_not_a_posting(tmp_path):
    ws, data = build_for(tmp_path, "weixin")
    rows = [{"rank": "1", "page": "1", "title": "2026 投行行业展望",
             "url": "https://mp.weixin.qq.com/s/AAA111bbb222", "summary": "行业分析",
             "publish_time": "2026-09-01"}]
    ref = capture(ws, rows, site="weixin")
    close(ws, data, ref)
    data["leads"] = [{"site": "weixin", "source_id": "AAA111bbb222", "status": "excluded",
                      "reason_code": "not_a_posting", "reason": "Industry commentary, no opening",
                      "evidence": {**ref, "quote": "行业分析"}}]
    save(ws, data)
    assert gate.inspect(ws) == []


def test_a_relevant_lead_left_out_must_stay_visible_in_the_report(tmp_path):
    ws, data = build(tmp_path)
    rows = [{"id": "job-1001", "title": "IB Analyst", "url": "https://example.com/jobs/job-1001"}]
    ref = capture(ws, rows)
    close(ws, data, ref)
    data["leads"] = [{"site": "employer", "source_id": "job-1001", "status": "excluded",
                      "reason_code": "not_selected", "reason": "Lower priority than retained roles",
                      "evidence": ref}]
    save(ws, data)
    assert "not_selected" in gate.inspect(ws)[0]
    (ws / "report.md").write_text("Other relevant roles: https://example.com/jobs/job-1001\n")
    assert gate.inspect(ws) == []


# 2026-09-19 review: user-recovery.md resumes a stopped search in a new linked
# round. These pin the order that references/user-recovery.md now documents.
def resume_round(tmp_path, register_first):
    owner, data = build(tmp_path)
    capture(owner, [], classification="platform_limit")  # human verification stop
    resume = tmp_path / "search-resume-1"
    (resume / "raw").mkdir(parents=True)
    (resume / "shortlist.yaml").write_text("rows: []\n")
    rounds = [".", "../search-resume-1"]
    (owner / "collection.yaml").write_text(yaml.safe_dump(
        {"rounds": [{"workspace": r} for r in rounds]}))
    if not register_first:
        ref = capture(resume, [])
    data["plan"]["rounds"] = rounds
    save(owner, data)
    gate.record_plan(owner)
    if register_first:
        ref = capture(resume, [])
    else:  # the controlled chronology of a read made before registration
        records = journal._records(resume)
        records[-1]["ts"] = "2000-01-01T00:00:00Z"
        (resume / "journal.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    close(owner, data, {**ref, "workspace": "../search-resume-1"})
    return owner


def test_a_resume_round_registered_at_the_owner_before_reading_completes(tmp_path):
    assert gate.inspect(resume_round(tmp_path, register_first=True)) == []


def test_a_resume_round_read_before_registration_cannot_complete(tmp_path):
    assert "read before" in gate.inspect(resume_round(tmp_path, register_first=False))[0]


# 2026-09-19 adversarial pass on the fixes above.
SOGOU = "https://weixin.sogou.com/link?url=dn9a_{}&type=2&query=%E6%A0%A1%E6%8B%9B"


def test_wechat_search_links_stay_distinct_leads(tmp_path):
    # opencli weixin search returns weixin.sogou.com/link?url=... for every
    # article; a path word such as "link" is not a posting id.
    ws, data = build_for(tmp_path, "weixin")
    rows = [{"title": t, "url": SOGOU.format(x), "summary": s}
            for t, x, s in [("行业评论", "AAA111", "行业分析"), ("2027校招公告", "BBB222", "招聘"),
                            ("校招补录", "CCC333", "补录")]]
    ref = capture(ws, rows, site="weixin")
    close(ws, data, ref)
    data["leads"] = [{"site": "weixin", "source_id": rows[0]["url"], "status": "excluded",
                      "reason_code": "not_a_posting", "reason": "Industry commentary",
                      "evidence": {**ref, "quote": "行业分析"}}]
    save(ws, data)
    pending = " ".join(gate.inspect(ws))
    assert "BBB222" in pending and "CCC333" in pending


def test_not_selected_lead_is_visible_through_its_clean_posting_link(tmp_path):
    ws, data = build_for(tmp_path, "51job")
    row = {"jobId": "171782851", "title": "算法工程师", "location": "北京",
           "url": "https://jobs.51job.com/beijing/171782851.html?s=sou_sou_soulb&t=0_0"}
    ref = capture(ws, [row], site="51job")
    close(ws, data, {**ref, "quote": "算法工程师"})
    data["leads"] = [{"site": "51job", "source_id": "171782851", "status": "excluded",
                      "reason_code": "not_selected", "reason": "Lower priority",
                      "evidence": {**ref, "quote": "北京"}}]
    save(ws, data)
    (ws / "report.md").write_text("其他相关岗位：[算法工程师](https://jobs.51job.com/beijing/171782851.html)\n")
    assert gate.inspect(ws) == []


def test_boss_security_id_is_an_identity_spelling(tmp_path):
    ws, data = build_for(tmp_path, "boss")
    no_url = {**BOSS_ROW, "url": ""}
    ref = capture(ws, [BOSS_ROW, {**no_url, "name": "Second Role", "security_id": "SECOND-security-99"}],
                  site="boss")
    close(ws, data, {**ref, "quote": "MRI Research Scientist"})
    assert "boss/SECOND-security-99" in " ".join(gate.inspect(ws))
    (ws / "shortlist.yaml").write_text(yaml.safe_dump({"rows": [
        {"source_site": "boss", "source_id": BOSS_ROW["security_id"], "id": "boss-a"},
        {"source_site": "boss", "source_id": "SECOND-security-99", "id": "boss-b"}]}))
    assert gate.inspect(ws) == []


def test_a_round_stopped_before_shortlisting_is_not_listed_on_resume(tmp_path):
    # The stopped round has no shortlist; only the new round is delivered. The
    # owner's own captures are still checked, so nothing it read can vanish.
    owner, data = build(tmp_path)
    (owner / "shortlist.yaml").unlink()
    capture(owner, [], classification="platform_limit")
    resume = tmp_path / "search-resume-1"
    (resume / "raw").mkdir(parents=True)
    (resume / "shortlist.yaml").write_text("rows: []\n")
    (owner / "collection.yaml").write_text(yaml.safe_dump({"rounds": [{"workspace": "../search-resume-1"}]}))
    data["plan"]["rounds"] = ["../search-resume-1"]
    save(owner, data)
    gate.record_plan(owner)
    ref = capture(resume, [])
    close(owner, data, {**ref, "workspace": "../search-resume-1"})
    assert gate.inspect(owner) == []
