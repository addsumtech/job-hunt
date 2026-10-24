"""convention_cards.py replaces reading a whole market table in assess mode.

It is only a saving if the run still copies text the gate accepts, so the
contract is pinned from three sides: every id and the exact reader text are in
the output (and check_assessment.py accepts a card copied from it), the stale
banner appears exactly when the gate will demand it, and nothing from the
provenance half of the table leaks into the output.
"""
import copy
import datetime
import re
import subprocess
import sys

import pytest

import check_assessment as ca
import check_conventions as conventions
import convention_cards as cards
import report_locales as locales
import test_check_assessment as tca
import vocab

SCRIPT = conventions.SKILL_ROOT / "scripts" / "convention_cards.py"
EARLY, LATE = "2000-01-01", "2099-01-01"   # before every review_by / after every one
LABELS = {"applies_when:", "review_by:", "text_zh:", "text_en:"}


def run(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8")
    return proc


def entries(market):
    return conventions.load_market_file(
        conventions.CONVENTIONS_DIR / f"{market}.yaml")["conventions"]


def block(output, entry_id):
    """The lines printed for one entry, from its `[id]` header to the next."""
    return output.split(f"[{entry_id}]\n", 1)[1].split("\n\n[", 1)[0]


@pytest.mark.parametrize("market", vocab.MARKET_KEYS)
@pytest.mark.parametrize("lang, field", [("zh", "text_zh"), ("en", "text_en")])
def test_every_id_and_its_exact_text_is_printed(market, lang, field):
    proc = run("--market", market, "--lang", lang, "--today", EARLY)
    assert proc.returncode == 0, proc.stderr
    assert entries(market), f"{market}.yaml has no entries; the test would pass on nothing"
    for entry in entries(market):
        assert f"[{entry['id']}]" in proc.stdout
        # Exact, not squeezed: the run copies these bytes, so they must be the YAML's.
        assert entry[field] in proc.stdout, f"{entry['id']}.{field} is not verbatim"
        assert f"applies_when: {entry['applies_when'].strip()}" in proc.stdout
        assert f"review_by: {entry['review_by']}" in proc.stdout


@pytest.mark.parametrize("market", vocab.MARKET_KEYS)
def test_nothing_from_the_provenance_half_is_printed(market):
    """Remove every runtime value and the fixed labels; nothing may be left."""
    proc = run("--market", market, "--lang", "en", "--text", "both", "--today", EARLY)
    rest = proc.stdout.split("\n", 1)[1]          # the one-line header
    for entry in entries(market):
        for value in (f"[{entry['id']}]", entry["applies_when"].strip(),
                      str(entry["review_by"]), entry["text_en"], entry["text_zh"]):
            assert value in rest
            rest = rest.replace(value, "", 1)
    leftover = set(rest.split()) - LABELS
    assert not leftover, f"{market}: printed something that is not a runtime field: {leftover}"
    # The same thing asked the other way round, by value. A short title or quote
    # ("Success Profiles", "algemeen verbindend verklaard, AVV") can be how the
    # reader text itself names the thing, so a value the entry's own text
    # contains is not a leak.
    for entry in entries(market):
        source, texts = entry["source"], entry["text_en"] + entry["text_zh"]
        provenance = [entry["why"], entry.get("protected_trait_note"), source.get("note")]
        for citation in [source] + list(source.get("also") or []):
            provenance += [citation.get(key) for key in ("url", "quote", "title", "publisher")]
        for value in filter(None, (str(v or "").strip() for v in provenance)):
            assert value in texts or value not in proc.stdout, (market, entry["id"], value)


def test_the_default_text_follows_the_report_language():
    zh = run("--market", "nl", "--lang", "zh", "--today", EARLY).stdout
    en = run("--market", "nl", "--lang", "en", "--today", EARLY).stdout
    ja = run("--market", "nl", "--lang", "ja", "--today", EARLY).stdout
    assert "text_zh:" in zh and "text_en:" not in zh
    assert "text_en:" in en and "text_zh:" not in en
    assert "text_en:" in ja and "text_zh:" in ja, "ja/ko/es quote a sourced text; offer both"


@pytest.mark.parametrize("lang", locales.LANGUAGES)
def test_the_stale_banner_appears_exactly_when_the_gate_demands_it(lang):
    banner = locales.GATE_TEXT[lang]["stale"]
    assert banner in ca.STALE_BANNER, "the banner must be one the gate accepts"
    late = run("--market", "nl", "--lang", lang, "--today", LATE).stdout
    early = run("--market", "nl", "--lang", lang, "--today", EARLY).stdout
    for entry in entries("nl"):
        assert banner in block(late, entry["id"]), entry["id"]
    assert banner not in early


def test_staleness_is_the_gate_s_own_answer_on_the_boundary():
    """On the day after the earliest review_by, only the entries due that day are stale,
    and the set is the one check_assessment derives from check_file."""
    table = conventions.CONVENTIONS_DIR / "nl.yaml"
    first = min(datetime.date.fromisoformat(e["review_by"]) for e in entries("nl"))
    today = first + datetime.timedelta(days=1)
    due = {e["id"] for e in entries("nl") if e["review_by"] == first.isoformat()}
    assert due and due != {e["id"] for e in entries("nl")}, "the boundary must split the table"
    assert cards.expired_ids(table, today) == due
    out = run("--market", "nl", "--lang", "zh", "--today", today.isoformat()).stdout
    for entry in entries("nl"):
        assert (("已过复核期" in block(out, entry["id"])) == (entry["id"] in due)), entry["id"]


def _workspace_with_card(tmp_path, card_text):
    entry = entries("nl")[0]
    assessment = copy.deepcopy(tca.ASSESSMENT)
    assessment["conventions_rendered"] = [entry["id"]]
    ws, _, root = tca.build(tmp_path, assessment=assessment)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    md = md.replace(tca.CONVENTION_ZH.replace("\n", ""), card_text)
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    return ws, root, entry


def _gate(ws, root, today):
    return [f for f in ca.check(ws, conventions.CONVENTIONS_DIR, today, root)
            if f.startswith(("CONVENTION_", "MISSING_STALE_BANNER"))]


def test_a_card_copied_from_the_output_passes_the_real_gate(tmp_path):
    """End to end against the shipped table, on a day every entry is stale."""
    late = datetime.date.fromisoformat(LATE)
    first_id = entries("nl")[0]["id"]
    out = run("--market", "nl", "--lang", "zh", "--today", LATE).stdout
    ws, root, entry = _workspace_with_card(tmp_path, block(out, first_id))
    assert _gate(ws, root, late) == []


def test_the_end_to_end_check_can_fail(tmp_path):
    """The negative controls: a dropped character and a dropped banner both fail."""
    late = datetime.date.fromisoformat(LATE)
    first_id = entries("nl")[0]["id"]
    out = block(run("--market", "nl", "--lang", "zh", "--today", LATE).stdout, first_id)
    text = entries("nl")[0]["text_zh"]
    ws, root, _ = _workspace_with_card(tmp_path / "a", out.replace(text, text[1:]))
    assert any(f.startswith("CONVENTION_PARAPHRASED") for f in _gate(ws, root, late))
    no_banner = "\n".join(line for line in out.split("\n") if "已过复核期" not in line)
    ws, root, _ = _workspace_with_card(tmp_path / "b", no_banner)
    assert any(f.startswith("MISSING_STALE_BANNER") for f in _gate(ws, root, late))


def test_a_session_named_table_is_read_with_table():
    """Eval 13 names evals/fixtures/conventions/expired-nl.yaml as the session's nl
    table; a run following assess §9 must be able to print that file's cards."""
    fixture = conventions.SKILL_ROOT / "evals" / "fixtures" / "conventions" / "expired-nl.yaml"
    entry = conventions.load_market_file(fixture)["conventions"][0]
    proc = run("--market", "nl", "--lang", "en", "--table", str(fixture), "--today", "2026-08-09")
    assert proc.returncode == 0, proc.stderr
    assert f"[{entry['id']}]" in proc.stdout and entry["text_en"] in proc.stdout
    assert "past its review date" in block(proc.stdout, entry["id"])


def test_market_other_prints_one_line_and_no_card():
    proc = run("--market", vocab.NO_MARKET)
    assert proc.returncode == 0
    assert proc.stdout.count("\n") == 1 and "no convention card" in proc.stdout


def test_an_absent_or_broken_table_exits_2_with_nothing_on_stdout(tmp_path):
    proc = run("--market", "nl", "--market-dir", str(tmp_path))
    assert proc.returncode == 2 and proc.stdout == "" and "NO_INPUT" in proc.stderr
    (tmp_path / "nl.yaml").write_text("conventions: [\n", encoding="utf-8")
    proc = run("--market", "nl", "--market-dir", str(tmp_path))
    assert proc.returncode == 2 and proc.stdout == ""
    assert "UNREADABLE_INPUT" in proc.stderr


def test_it_writes_nothing_and_needs_no_workspace():
    """A lookup, not a gate: there is no --workspace to journal into."""
    help_text = run("--help").stdout
    assert "--workspace" not in help_text
    assert not re.search(r"journal\.receipt\(", SCRIPT.read_text(encoding="utf-8"))
