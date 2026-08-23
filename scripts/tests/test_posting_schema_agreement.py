"""One posting schema, declared in four places, diffed here.

`posting.yaml`'s field list is written out in four files, because each is loaded
at a different layer and a reader of one may never see another. An audit on
2026-08-23 found all four disagreeing:

    SKILL.md                                12 names
    references/job-posting-extraction.md    11 names  (no `company`)
    modes/assess.md                         12 names
    modes/apply.md                            9 names  (no `company`,
                                                        no `salary_range`,
                                                        no `application_type`)

and `test_skill_structure.py` pinned only SKILL.md's. The omissions are silent in
opposite directions: `company` fails loudly downstream (`NO_COMPANY_IN_POSTING`),
while `application_type: structured` is the ONLY signal routing to the
supporting-statement branch — so a UK NHS or Civil Service run simply never
produced the document the panel scores, and nothing said why.

`modes/assess.md` additionally claimed its list was "byte-identical to SKILL.md's
extraction field table". It was not, and that sentence was worse than the drift
it described: it told the next maintainer the copies were in sync, so they would
not diff them. This file is the diff.
"""
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

REPO = pathlib.Path(__file__).resolve().parents[2]

CANONICAL = [
    "role_title", "company", "seniority", "location", "must_haves",
    "nice_to_haves", "responsibilities", "keywords", "company_values_tone",
    "red_flags", "salary_range", "application_type",
]

_TABLE_ROW = re.compile(r"^\|\s*`([a-z_]+)(?:\[\])?`\s*\|")
_BACKTICKED = re.compile(r"`([a-z_]+)`")


def _table_fields(path, heading):
    """Field names from the markdown table under `heading`."""
    text = (REPO / path).read_text(encoding="utf-8")
    start = text.index(heading)
    out = []
    for line in text[start:].splitlines():
        m = _TABLE_ROW.match(line)
        if m:
            out.append(m.group(1))
        elif out and not line.startswith("|"):
            break
    return out


def skill_md_table():
    return _table_fields("SKILL.md", "## Extraction field table")


def skill_md_canonical_list():
    """The fenced block SKILL.md calls "exactly these twelve names in this order"."""
    text = (REPO / "SKILL.md").read_text(encoding="utf-8")
    marker = "**The `posting.yaml` field list, and it is exactly these twelve names in this order:**"
    block = text.split(marker, 1)[1].split("```")[1]
    return [n.strip() for n in block.replace("\n", " ").split(",") if n.strip()]


def extraction_reference_table():
    return _table_fields("references/job-posting-extraction.md",
                         "Extract exactly these fields")


def assess_mode_yaml_keys():
    text = (REPO / "modes" / "assess.md").read_text(encoding="utf-8")
    block = text.split("## 3. Extract `posting.yaml`", 1)[1].split("```yaml")[1].split("```")[0]
    return [line.split(":", 1)[0].strip()
            for line in block.splitlines() if line.strip() and not line.startswith(" ")]


def apply_mode_list():
    text = (REPO / "modes" / "apply.md").read_text(encoding="utf-8")
    start = text.index("Extract the structured object")
    chunk = text[start:start + 700]
    seen, out = set(), []
    for name in _BACKTICKED.findall(chunk):
        if name in CANONICAL and name not in seen:
            seen.add(name)
            out.append(name)
    return out


DECLARATIONS = {
    "SKILL.md extraction table": skill_md_table,
    "SKILL.md canonical list": skill_md_canonical_list,
    "references/job-posting-extraction.md": extraction_reference_table,
    "modes/assess.md §3": assess_mode_yaml_keys,
    "modes/apply.md Step 2": apply_mode_list,
}


@pytest.mark.parametrize("where", sorted(DECLARATIONS))
def test_every_declaration_lists_the_same_names_in_the_same_order(where):
    """Set AND order. Order matters because three of these are presented to the
    model as "in this order", and a reader comparing two of them by eye is doing
    exactly what the byte-identity claim told them they need not do."""
    assert DECLARATIONS[where]() == CANONICAL


def test_the_parsers_are_not_finding_an_empty_list():
    """A parser that silently returns [] would make every assertion above pass by
    construction — the failure mode this whole audit kept finding."""
    for where, parse in DECLARATIONS.items():
        assert len(parse()) == 12, f"{where} parsed to {len(parse())} names"


def test_location_is_a_scalar_string_everywhere_it_is_typed():
    """SKILL.md typed `location` as `object: {city, country, arrangement}` in its
    table and, eighteen lines later, as "a scalar string ... not a {city, country,
    arrangement} mapping". No script reads a structured location, so nothing
    failed loudly — which is why it survived. The damage was that assess and apply
    wrote mutually incompatible posting.yaml files for the same posting, and
    measured downstream: given an object, render_letter's PDF address block
    printed `{'city': 'Leeds', ...}` and its .docx printed `citycountryarrangement`.
    """
    for path in ("SKILL.md", "references/job-posting-extraction.md"):
        text = (REPO / path).read_text(encoding="utf-8")
        row = next(line for line in text.splitlines()
                   if line.startswith("| `location` |"))
        assert "object" not in row, f"{path} still types location as an object"
        assert "string" in row


def test_no_json_example_still_shows_a_structured_location():
    """The reference carried two worked examples in the object form. An example
    outranks a table for a model following the file."""
    text = (REPO / "references" / "job-posting-extraction.md").read_text(encoding="utf-8")
    assert '"city":' not in text
    assert '"arrangement":' not in text


def test_assess_mode_no_longer_claims_byte_identity():
    text = (REPO / "modes" / "assess.md").read_text(encoding="utf-8")
    assert "byte-identical to `SKILL.md`" not in text
