"""Assert on a finding CODE, never on a free substring of the output.

Every gate in this skill prints findings one per line, each prefixed with a
stable UPPERCASE code. Tests that assert `"SOME_CODE" in out` look equivalent to
tests that assert the code was actually emitted, and are not: the codes and their
explanations appear inside OTHER findings' message text.

The measured case. `test_a_rejected_round_without_an_honest_stop_fails` asserted
three substrings — "NO_PASS_NO_STOP", "poorly_built", "honest_stretch" — all of
which also occur in a NEIGHBOURING finding's prose, so deleting the branch that
emits NO_PASS_NO_STOP left all 49 tests in that file passing. The branch it
guards is the one that tells a stretch candidate whether their application was
badly built or simply a reach; check_apply's own docstring says the two "emit the
identical machine signal" and that "a stretch candidate told failed abandons an
application they should have sent".

I hit the same thing writing these fixes: an assertion that
`"check_word_limits" not in out` failed because the phrase appears inside
UNREADABLE_POSTING's own explanation, and a README test asserting `"baseline arm"
is absent` failed because the honest paragraph uses those words to say the
measurement never happened. A bare substring cannot tell a claim from its
negation, or a code from a mention of a code.

Use these instead:

    assert_finding(out, "STALE_RECEIPT", about="cv.md")
    assert_no_finding(out, "MISSING_RECEIPT")
    assert codes(out) == {"UNREADABLE_POSTING"}
"""
from __future__ import annotations


def finding_lines(out: str) -> list:
    """Every non-blank output line, stripped."""
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def codes(out: str) -> set:
    """The set of finding CODES actually emitted — the token before the first colon.

    Only counts a line that STARTS with the code, which is the contract every
    gate in this skill writes to.
    """
    found = set()
    for line in finding_lines(out):
        head = line.split(":", 1)[0]
        if head and head == head.upper() and head.replace("_", "").isalnum():
            found.add(head)
    return found


def lines_for(out: str, code: str) -> list:
    """Every finding line whose code is `code`, at line start."""
    return [line for line in finding_lines(out) if line.startswith(f"{code}:")]


def assert_finding(out: str, code: str, about: str = None) -> str:
    """Assert `code` was emitted, at line start. Returns the line.

    `about` additionally requires that finding to mention a specific subject —
    the file, gate or term it is reporting on — so a test cannot be satisfied by
    the right code fired for the wrong reason.
    """
    hits = lines_for(out, code)
    assert hits, (
        f"{code} was not emitted at the start of any line.\n"
        f"Codes present: {sorted(codes(out)) or '(none)'}\n"
        f"Output:\n{out}")
    if about is not None:
        matching = [line for line in hits if about in line]
        assert matching, (
            f"{code} fired, but no occurrence mentions {about!r} — the right code "
            f"for the wrong subject.\nLines:\n" + "\n".join(hits))
        return matching[0]
    return hits[0]


def assert_no_finding(out: str, code: str) -> None:
    """Assert `code` was NOT emitted.

    Deliberately not `code not in out`: the code appears inside other findings'
    explanations, so the substring form fails on output that is entirely correct.
    """
    hits = lines_for(out, code)
    assert not hits, f"{code} was emitted:\n" + "\n".join(hits)


def assert_clean(out: str) -> None:
    """Assert no finding at all — the quiet case, which is worth pinning as hard
    as the firing one. A gate that fires on an honest run teaches its reader to
    skip the line that matters."""
    present = sorted(codes(out))
    assert not present, f"expected no findings, got {present}:\n{out}"
