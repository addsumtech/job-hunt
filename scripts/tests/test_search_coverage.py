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


def test_multiline_source_identity_can_be_excluded_with_its_own_capture(tmp_path):
    ws, data = build(tmp_path)
    source_id = "机构业务经理助理（1人） \n 国新证券"
    ref = capture(ws, [{"source_id": source_id, "title": "Asset management sales"}])
    close(ws, data, ref)
    data['leads'] = [{"site": "employer", "source_id": source_id, "status": "excluded",
                      "reason_code": "wrong_role", "reason": "Asset management sales, not IB.",
                      "evidence": ref}]
    save(ws, data)
    assert gate.inspect(ws) == []
    # A sibling capture with the same quote cannot vouch for this identity.
    other = capture(ws, [{"source_id": "other-posting", "title": "Asset management sales"}])
    data['leads'][0]['evidence'] = other
    save(ws, data)
    assert "capture must identify this lead" in gate.inspect(ws)[0]


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


def test_absolute_journal_capture_matches_relative_coverage_reference(tmp_path):
    ws, data = build(tmp_path)
    ref = capture(ws, [])
    path = ws / 'journal.jsonl'
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[-1]['stdout_file'] = str(ws / ref['file'])
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    close(ws, data, ref)
    assert gate.inspect(ws) == []


def test_capture_paths_cannot_escape_raw_directory(tmp_path):
    ws, _ = build(tmp_path)
    outside = tmp_path / 'outside.json'
    outside.write_text('[]')
    alias = ws / 'raw' / 'escape.json'
    alias.symlink_to(outside)
    inside = ws / 'raw' / 'ok.json'
    inside.write_text('[]')
    assert gate._capture_path(ws, str(inside)) == inside
    assert gate._capture_path(ws, 'raw/ok.json') == inside
    for name in [str(outside), str(alias), 'raw/escape.json', str(ws / 'brief.yaml')]:
        assert gate._capture_path(ws, name) is None
