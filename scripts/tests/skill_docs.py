"""Test the runtime documentation graph instead of forcing rules into SKILL.md."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENTRY = ROOT / "SKILL.md"
_REFERENCE = re.compile(r"(?<![\w/-])((?:references|modes|agents)/[\w./-]+\.(?:md|yaml))")


def reachable_docs():
    pending, found = [ENTRY], {}
    while pending:
        path = pending.pop()
        if path in found:
            continue
        text = path.read_text(encoding="utf-8")
        found[path] = text
        for name in _REFERENCE.findall(text):
            reference = ROOT / name
            if reference.is_file() and reference not in found:
                pending.append(reference)
    return found


def read_guidance(relative):
    path = ROOT / relative
    docs = reachable_docs()
    assert path in docs, f"SKILL.md has no runtime route to {relative}"
    return docs[path]


def skill_context():
    return "\n\n".join(reachable_docs().values())
