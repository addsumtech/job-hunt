#!/usr/bin/env python3
"""Gate: every claim the tailoring added traces to a permitted source.

The claim-provenance checkpoint is the skill's highest-value rule and, until
claims.yaml existed, its most silent one: no provenance file, no citation column
in any required output, no script diffing the tailored CV against the master. A
run could skip it entirely and every downstream gate still passed — while every
automated signal in the system (an ATS REJECT on a missing keyword) rewarded the
dishonest edit.

Scope is a closed set of short atomic fields — skills leaves, certifications,
experience titles and orgs, education degrees and institutions, project roles,
publications, awards, volunteer and board lines — because that is where the named
fabrication classes land: each is one fact that is either true or fabricated, with
no middle. Free prose is deliberately out (bullets, summary, achievements, project
descriptions): rewording prose IS the skill's job, and a gate that fires on every
honest run is a gate people learn to skip. Which section is which is written down
in SCANNED_SECTIONS / OUT_OF_SCOPE_SECTIONS below, and a test derives that
partition from render_cv's rendered sections — so a section added to the CV cannot
be silently left unscanned, which is how org, institution, publications, awards,
project roles, volunteer and board sat unchecked next to the fields that were.

The master side is PARSED, and matched on whole tokens. `key in master_text` over
the raw file made a claim "sourced" by any substring hit anywhere in it: `Go` by
`django`, `Java` by `JavaScript`, `AI` by `email` — which every profile using the
canonical schema contains, so `AI` was permanently unfalsifiable — a fabricated
`MSc` certification by the real degree `MSc Computer Science`, and `PhD` by a YAML
COMMENT in the shipped example profile. Parsing to leaves is what kills the comment
class (a comment's words are still words, so word boundaries alone do not); whole
tokens are what kill the sub-word class. Neither alone does both. A tailored term
is sourced when it equals a master leaf, appears as a whole phrase inside one of
the candidate's own prose leaves, is a phrase of a master leaf **of its own kind**
(so "Acme" from "Acme BV" and the de-escalation "Senior ML Engineer" → "ML
Engineer" stay quiet, while a fabricated `MSc` *certification* is not sourced by a
*degree*), or has a claims.yaml row. `links` are excluded from the permitted set:
an account on a service is not a skill. (Whole-token matching already makes a bare
URL inert — one URL is one token — so what the exclusion still buys is the
`{label, url}` form, whose label is a leaf like any other.)

QUALIFIER_STRIPPED is deliberately narrow — only a dropped STATUS marker from a
closed vocabulary ("(in progress)", "(expired 2023)", "(B1)", ", in progress"),
where deleting it upgrades a real credential into a stronger one. It is NOT "the
tailored term is a substring of a master leaf": that version fires on `Senior ML
Engineer` → `ML Engineer` and on `PyTorch Lightning` → `PyTorch`, the truthful
reframings this skill exists to permit, and a check that cries wolf on ordinary
output is worse than no check, because the reader learns to skip the line.

Also fails if profile.yaml changed during the run. Overwriting the master is
destructive and unrecoverable, and the damage only surfaces on the NEXT
application, when the "master" has already been narrowed to the previous job.

Exit 0 = clean. Exit 1 = findings. Exit 2 = nothing recorded to check against.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import unicodedata


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import journal

GATE = "check_claims"
FINGERPRINT = "master-fingerprint.json"
SOURCE_KINDS = ("profile-line", "session-answer", "fetched-artifact")
CLAIM_KEYS = ("term", "where", "source_kind", "source_ref", "session_date",
              "retracted")
# `retracted` is a PRESENCE check, not a non-empty check: null is what a live
# claim looks like, and demanding a value would make every honest row invalid.
# It is still required to be there — in a schema where "absent" and "not
# retracted" are indistinguishable, a withdrawn claim leaves no scar, and the
# scar is the entire reason the field exists. Plan 4's check_mock.py requires
# the same six keys; a row that satisfied one and failed the other would make
# the two gates disagree about a shared artifact.
PRESENCE_ONLY_KEYS = ("retracted",)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PUNCT = re.compile(r"[^\w\s+#./-]", re.UNICODE)

# ── the scope registry ───────────────────────────────────────────────────────
# Keyed on render_cv's section keys, and scripts/tests/test_check_claims.py
# asserts the two sets are the same set. Adding a section to the CV without
# deciding whether it is checked now fails a test instead of passing silently.

SCANNED_SECTIONS = {
    "skills":         "skills.<group>[] — the invented-tool class",
    "certifications": "certifications[] — the claimed-credential class",
    "experience":     "experience[].title (inflated title), experience[].org "
                      "(fabricated employer)",
    "education":      "education[].degree (degree not held), "
                      "education[].institution (fabricated alma mater)",
    "projects":       "projects[].role — the same seniority claim as a job title",
    "publications":   "publications[] — a fabricated paper is the most checkable "
                      "lie on an academic CV",
    "awards":         "awards[] — the same shape of credential as a certification",
    "volunteer":      "volunteer[] — names a real post at a real organisation",
    "board":          "board[] — a board seat is verifiable and often public record",
}

OUT_OF_SCOPE_SECTIONS = {
    "summary": "Free prose. Rewording it is the skill's job (gap-analysis.md §2 "
               "ALLOWED), so diffing it would fire on every honest run. Recorded "
               "deliberately in docs/superpowers/plans/"
               "2026-08-09-1-migration-and-p0-fixes.md, 'Scope, chosen deliberately'.",
    "achievements": "The executive CV's bullet band — 3-5 quantified statements "
                    "about work the candidate really did (cv-craft.md §1 'Senior "
                    "leader / Executive', candidate-situations.md §6). "
                    "gap-analysis.md §2 names "
                    "'rewording real achievements using the posting's exact "
                    "terminology' as ALLOWED, so scanning it fires on exactly the "
                    "operation the skill exists to perform. Same class as bullets, "
                    "same decision — and, like bullets, it is a permitted SOURCE.",
}

# Fields inside a scanned section that are still not scanned, and why. Not
# machine-checked (a field is not a section), but written down for the same
# reason: the next person should inherit a decision, not an omission.
OUT_OF_SCOPE_FIELDS = {
    "experience[].bullets":    "prose the candidate wrote about work they did",
    "education[].details":     "prose ('Thesis on X; GPA 8.5/10')",
    "projects[].description":  "prose",
    "projects[].name":         "the candidate's own label for their own work, "
                               "routinely renamed for readability; the checkable "
                               "facts in a project are the role and the links",
    "*.links":                 "a URL is not a claim, and is excluded from the "
                               "permitted source set for the same reason",
    "meta.headline":           "the positioning line, rewritten per posting by "
                               "design; same class as summary",
    "*.start / *.end":         "dates are not claims this gate models. Altering "
                               "them is forbidden (gap-analysis.md §2 NOT-ALLOWED) "
                               "but a date is sourced by any other date in the "
                               "file, so scanning them here would be theatre — a "
                               "field-wise diff of master vs tailored is the check "
                               "that would work, and does not exist yet",
}

# Free-prose keys, matched by key name at any depth. These are the candidate's own
# narrative about work they did, and they are the reason the bullet-only mention of
# a real tool ("Built a PyTorch pipeline") sources surfacing it into Skills — the
# cry-wolf guard this gate is pinned against. `publications` is here as well as in
# the scanned set: gap-analysis.md §1 names the candidate's own papers as valid
# evidence for a technical-depth claim.
PROSE_KEYS = ("summary", "bullets", "details", "description", "highlights",
              "notes", "achievements", "publications")
LINK_KEYS = ("links",)

# Qualifiers whose REMOVAL upgrades the claim. A CLOSED VOCABULARY, deliberately
# not "any dropped text": dropping "(2024)" off a certification, "(native)" off a
# language, "BV" off an employer or "(maternity cover)" off a title loses nothing a
# reader would have believed, and firing on those is how a gate gets ignored.
# `learning` and `studying` are deliberately absent though they name the class —
# they would fire on the master idiom `PyTorch (deep learning)` → `PyTorch`, and a
# rule that misfires on an ordinary ML CV is worse than a rule that misses
# "(learning)", which `in progress` / `in training` / `coursework` already cover.
#
# The list covers the languages this skill renders CVs in. Measured 2026-09-05:
# with English and Simplified Chinese only, an unfinished degree written
# `MSc Informatik (in Bearbeitung, voraussichtlich 2027)` -> `MSc Informatik`
# came back `sourced`, i.e. the honesty gate let a German, Dutch, Japanese or
# Korean candidate present a degree they do not hold. That is the load-bearing
# rule of the whole skill failing on language rather than on substance.
_STATUS_TOKENS = frozenset("""
    progress training ongoing expected anticipated planned pending prospective
    partial incomplete unfinished discontinued withdrawn paused deferred
    expired lapsed revoked suspended provisional candidate coursework audited
    self-taught taught beginner basic elementary intermediate conversational
    a1 a2 b1 b2 c1 c2 n1 n2 n3 n4 n5
    bearbeitung voraussichtlich laufend geplant angestrebt abgebrochen
    grundkenntnisse anfaenger anfänger fortgeschritten unvollstaendig
    unvollständig ausstehend abgelaufen
    verwacht lopend onafgerond gepland beginner basiskennis
    gevorderd verlopen bezig
    cours prevu prévu attendu inacheve inachevé debutant débutant notions
    intermediaire intermédiaire
    curso previsto esperado inacabado principiante nociones basico básico
    corso previsto incompleto principiante
""".split())
# Matched by containment, not equality: CJK writes without delimiters, so
# "预计2027" is one token and set membership would miss it. The Japanese and
# Korean entries are here for the same reason -- `修了見込み` and `졸업예정`
# never appear as separate whitespace tokens.
_STATUS_CJK = (
    "在读", "在讀", "在学", "在學", "预计", "預計", "已过期", "已失效", "待考",
    "初级", "初級", "入门", "入門", "肄业", "肄業", "未完成", "修读中", "修讀中",
    # Japanese
    "見込", "見込み", "在学中", "履修中", "取得予定", "予定", "中退", "失効",
    "初級", "日常会話",
    # Korean
    "재학", "재학중", "예정", "졸업예정", "수료", "중퇴", "이수중", "만료",
    "초급", "기초",
)
# Tokens that carry no claim either way, so their presence in the dropped material
# neither triggers the finding nor blocks it. Anything with a digit is here (a year,
# a date) — checked AFTER the status test, so the CEFR levels above still win.
# The connectives of the other languages this skill writes CVs in are here for
# exactly the reason the English ones are: `dropped_status` requires the WHOLE
# dropped span to be status-or-nothing, so one unlisted preposition silences the
# finding. Measured: `Master Informatique (en cours, prévu 2027)` came back
# `sourced` because of the word `en`, and the Dutch case because of `nog niet`.
_IGNORABLE_TOKENS = frozenset(
    ("in of the to as at by on for and or level status since until from est "
     "approx approximately self grade "
     # de / nl
     "im am und oder bis seit ab noch nicht nog niet en van het op voor tot "
     "afgerond abgeschlossen "
     # fr
     "du la le les et ou a pour depuis dans "
     # es / it
     "el los las y para desde con di da del della nel su "
     # zh / ja / ko connectives that survive tokenisation
     "年 月 版").split())

# Scripts written without word delimiters. See `phrase_in`.
_UNSEGMENTED_RE = re.compile(r"[฀-๿　-鿿가-힯豈-﫿]")

SOURCED, QUALIFIER = "sourced", "qualifier"


def normalize_term(s) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return " ".join(_PUNCT.sub(" ", s).split())


def _token_list(text) -> list:
    """Whole tokens of `text`, trailing sentence punctuation trimmed.

    normalize_term keeps `+ # . / -` so that C++, C#, .NET and CI/CD survive as
    themselves — the cost is that a term ending a sentence normalizes to
    "kubernetes." and would then match nothing. Trailing dots are trimmed;
    leading ones are not, because ".NET" is a name.
    """
    return [t for t in (tok.rstrip(".") for tok in normalize_term(text).split()) if t]


def phrase_in(term, text) -> bool:
    """True when `term` occurs in `text` as whole tokens, never inside a word.

    Word boundaries are what stop `Java` being sourced by `JavaScript`, but they
    are a property of space-delimited scripts. Chinese, Japanese, Korean and Thai
    write without them, so a whole bullet is a single token and a token test would
    report every skill on every CJK CV as unsourced — the cry-wolf failure, not a
    fix. For a term in those scripts the test is containment within a single leaf,
    which is still far narrower than the whole-file substring it replaces.
    """
    t = normalize_term(term)
    if not t:
        return False
    if _UNSEGMENTED_RE.search(t):
        return t in normalize_term(text)
    wanted, have = _token_list(term), _token_list(text)
    n = len(wanted)
    return bool(n) and any(have[i:i + n] == wanted for i in range(len(have) - n + 1))


def _is_status(token) -> bool:
    return token in _STATUS_TOKENS or any(w in token for w in _STATUS_CJK)


def _is_ignorable(token) -> bool:
    return token in _IGNORABLE_TOKENS or any(ch.isdigit() for ch in token)


def dropped_status(term, leaf):
    """The status marker `term` drops off `leaf`, or None.

    What the term dropped must be a status and NOTHING BUT a status (plus dates
    and connectives, which say nothing either way). Both halves are load-bearing:

    * "MSc Computer Science" off "MSc Computer Science (in progress, expected
      2027)" drops `progress` + `expected` and two ignorables → fires.
    * "ML Engineer" off "Senior ML Engineer" drops `senior`, "Acme" off "Acme BV"
      drops `bv`, "AWS … Practitioner" off "… (2024)" drops a year → no status,
      no finding. These are the honest reframings the gate must stay silent on.
    * "Engineer" off "Engineer, Basic Materials Group" drops `basic` — a status
      word — but also `materials` and `group`, which are not, so the dropped text
      is a department name and not a qualifier. Requiring the whole dropped span
      to be status is what tells those apart; a bare `contains a status word`
      test fires on it.

    Punctuation is whitespace by the time we compare, so "(B1)", ", in progress"
    and " — expected 2027" are one rule rather than three, and a master that
    writes the qualifier without brackets is not a way through.
    """
    wanted, have = _token_list(term), _token_list(leaf)
    n = len(wanted)
    if not n or len(have) <= n:
        return None
    at = next((i for i in range(len(have) - n + 1) if have[i:i + n] == wanted), None)
    if at is None:
        return None
    dropped = have[:at] + have[at + n:]
    if not any(_is_status(t) for t in dropped):
        return None
    if any(not _is_status(t) and not _is_ignorable(t) for t in dropped):
        return None
    return " ".join(dropped)


def relation(term, leaf):
    """How `term` relates to one master leaf of the same family.

    SOURCED, QUALIFIER (the leaf says the same thing, and the term dropped a
    status marker off it), or None.
    """
    if normalize_term(term) == normalize_term(leaf):
        return SOURCED
    if not phrase_in(term, leaf):
        return None
    return QUALIFIER if dropped_status(term, leaf) else SOURCED


def _as_list(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return v
    return []


def _flat(v):
    if isinstance(v, dict):
        return " ".join(str(x) for x in v.values())
    return str(v)


def atomic_claims(profile) -> list:
    """[(term, field_path, family)] over the closed set of atomic claim fields.

    ONE walker, run over both profiles: the tailored side supplies the claims to
    check, the master side supplies the evidence they are checked against. Two
    walkers is two things to drift — and the drift that already happened here was
    `experience[].title` being scanned while `experience[].org`, the adjacent key
    in the same dict, was not.
    """
    profile = profile if isinstance(profile, dict) else {}
    out = []
    skills = profile.get("skills") or {}
    if isinstance(skills, dict):
        for group, items in skills.items():
            for item in _as_list(items):
                out.append((_flat(item), f"skills.{group}", "skills"))
    else:
        for item in _as_list(skills):
            out.append((_flat(item), "skills", "skills"))
    for i, ex in enumerate(_as_list(profile.get("experience"))):
        if not isinstance(ex, dict):
            continue
        for field in ("title", "org"):
            if ex.get(field):
                out.append((_flat(ex[field]), f"experience[{i}].{field}",
                            f"experience.{field}"))
    for i, ed in enumerate(_as_list(profile.get("education"))):
        if not isinstance(ed, dict):
            continue
        for field in ("degree", "institution"):
            if ed.get(field):
                out.append((_flat(ed[field]), f"education[{i}].{field}",
                            f"education.{field}"))
    for i, pr in enumerate(_as_list(profile.get("projects"))):
        if isinstance(pr, dict) and pr.get("role"):
            out.append((_flat(pr["role"]), f"projects[{i}].role", "projects.role"))
    for section in ("certifications", "publications", "awards", "volunteer", "board"):
        for i, item in enumerate(_as_list(profile.get(section))):
            out.append((_flat(item), f"{section}[{i}]", section))
    return out


def _leaf_strings(node):
    """Every scalar leaf under `node`, as raw strings. `links` excluded.

    The exclusion is one line here and covers both `contact.links` and
    `projects[].links`, including the `{label, url}` form: the label of a link is
    the name of a service, not evidence that the candidate has a skill.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).strip().lower() not in LINK_KEYS:
                yield from _leaf_strings(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _leaf_strings(item)
    elif node is not None and not isinstance(node, bool):
        yield str(node)


def _prose_strings(node):
    """Every leaf under a free-prose key — the candidate's own narrative.

    Only leaves *under* a PROSE_KEYS key are yielded, and they are collected by
    `_leaf_strings`, so a `links:` list nested under one is dropped there rather
    than needing a second guard here.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            name = str(key).strip().lower()
            yield from (_leaf_strings(value) if name in PROSE_KEYS
                        else _prose_strings(value))
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _prose_strings(item)


def master_sources(profile):
    """(exact, prose, families) — the permitted evidence, parsed from leaves.

    `exact` is every leaf normalized, so a term that is a whole field ANYWHERE in
    the master is sourced wherever the tailoring puts it. That is a provenance
    answer, not a semantic one: it says the candidate's own file states this exact
    string. It is what lets a skill be regrouped, and what keeps a PhD candidate's
    university quiet when it is both their `education[].institution` and their
    `experience[].org`. Its cost, accepted knowingly: moving a `projects[].role`
    verbatim into `experience[].title` is quiet too, and whether that restructure
    is *appropriate* is a question this gate cannot answer without guessing — the
    recruiter judge and the human read the CV for that.

    `prose` is the free-text leaves, matched by whole phrase. `families` keeps each
    atomic leaf under its own kind, because the looser phrase match is only safe
    within a kind — a degree does not source a certification.
    """
    exact = {normalize_term(s) for s in _leaf_strings(profile)}
    exact.discard("")
    prose = [s for s in _prose_strings(profile) if normalize_term(s)]
    families = {}
    for term, _where, family in atomic_claims(profile):
        families.setdefault(family, []).append(term)
    return exact, prose, families


def _claim_index(claims):
    """{normalized term: row} for live rows, plus findings for malformed ones."""
    live, retracted, findings = {}, {}, []
    for i, row in enumerate(claims or []):
        if not isinstance(row, dict):
            findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] is not a mapping")
            continue
        for key in CLAIM_KEYS:
            if key not in row:
                findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] is missing required "
                                f"key {key!r}")
            elif key not in PRESENCE_ONLY_KEYS and not str(row.get(key) or "").strip():
                findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] has an empty "
                                f"required key {key!r}")
        if row.get("source_kind") and row["source_kind"] not in SOURCE_KINDS:
            findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] source_kind "
                            f"{row['source_kind']!r} is not one of "
                            f"{', '.join(SOURCE_KINDS)} — there is no fourth source")
        if row.get("session_date") and not _DATE_RE.match(str(row["session_date"])):
            findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] session_date "
                            f"{row['session_date']!r} is not YYYY-MM-DD")
        key = normalize_term(row.get("term"))
        if not key:
            continue
        (retracted if row.get("retracted") else live)[key] = row
    return live, retracted, findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--master", default=None)
    ap.add_argument("--record", action="store_true",
                    help="fingerprint the master profile at apply-mode entry")
    args = ap.parse_args(argv)
    ws = pathlib.Path(args.workspace)
    if not ws.is_dir():
        # journal.receipt() would mkdir it, and a gate that creates the
        # workspace it is auditing has manufactured its own evidence.
        print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
        return 2
    fp_path = ws / FINGERPRINT

    if args.record:
        if not args.master or not pathlib.Path(args.master).exists():
            journal.receipt(ws, GATE, {}, "could_not_run",
                            [f"MISSING_INPUT: master {args.master}"])
            print(f"cannot run {GATE}: --master must point at an existing profile.yaml",
                  file=sys.stderr)
            return 2
        master = pathlib.Path(args.master).resolve()
        digest = journal.sha256_file(master)
        ws.mkdir(parents=True, exist_ok=True)
        fp_path.write_text(json.dumps({
            "path": str(master), "sha256": digest,
            "mtime_ns": master.stat().st_mtime_ns}, indent=2) + "\n", encoding="utf-8")
        # "baseline_recorded", not "recorded": this path fingerprints the master
        # and checks nothing at all. While it shared "recorded" with the gates that
        # DO check, check_apply.py counted it as a pass — so a run that did only
        # this documented mode-entry step delivered a package whose claims nobody
        # had verified, and a `--record` re-run on resume erased a real failure.
        journal.receipt(ws, GATE, {"profile.yaml": digest}, "baseline_recorded", [])
        return 0

    tailored_path = ws / "tailored-profile.yaml"
    if not fp_path.exists() or not tailored_path.exists():
        missing = FINGERPRINT if not fp_path.exists() else "tailored-profile.yaml"
        code = "NO_MASTER_FINGERPRINT" if missing == FINGERPRINT else "MISSING_INPUT"
        journal.receipt(ws, GATE, {}, "could_not_run", [f"{code}: {ws / missing}"])
        print(f"cannot run {GATE}: {code} — {ws / missing} does not exist; run with "
              f"--record --master <profile.yaml> at apply-mode entry", file=sys.stderr)
        return 2

    fp = json.loads(fp_path.read_text(encoding="utf-8"))
    master = pathlib.Path(fp["path"])
    findings = []
    master_profile, readable = {}, False
    if not master.exists():
        findings.append(f"MASTER_MUTATED: {master} no longer exists — the master "
                        f"profile is never mutated by tailoring")
    else:
        now = journal.sha256_file(master)
        try:
            master_profile = journal.load_yaml(master)
            readable = True
        except journal.YamlUnreadable as exc:
            # The gate compares against PARSED fields, so a master it cannot parse
            # is a gate that verified nothing. Say that, and do not then emit an
            # UNSOURCED line for every term in the CV: a flood derived from a file
            # nobody could read is noise, and noise is what makes findings ignorable.
            #
            # A finding rather than exit 2, and that is the deliberate divergence:
            # the master lives OUTSIDE the workspace, MASTER_MUTATED and
            # MASTER_TOUCHED below are findings about that same file, and the other
            # half of this gate — the claims index, the tailored profile — still has
            # something to say. `readable` stays False, so nothing downstream treats
            # the empty mapping as a verified master.
            findings.append(f"MASTER_UNREADABLE: {exc.reason} — no claim was verified "
                            f"against {master}; fix the master and re-run")
        if now != fp["sha256"]:
            findings.append(f"MASTER_MUTATED: profile.yaml content changed during this "
                            f"run ({fp['sha256'][:12]}… → {now[:12]}…) — the master "
                            f"profile is never mutated by tailoring; tailoring works on "
                            f"the workspace copy")
        elif master.stat().st_mtime_ns != fp.get("mtime_ns"):
            findings.append(f"MASTER_TOUCHED: profile.yaml's mtime changed during this "
                            f"run though its content is identical — something wrote to "
                            f"the master; confirm nothing is editing it")

    # Both exit 2, unlike the master above, and for the reason the master is the
    # exception: these two ARE the comparison. A claims.yaml that is present and
    # unreadable is not the same as one that is absent — absent honestly means
    # "nothing was sourced" and every UNSOURCED line that follows is true, while
    # unreadable would print that same flood about a file that may well have sourced
    # every one of them.
    try:
        tailored = journal.load_yaml(tailored_path)
        claims_path = ws / "claims.yaml"
        claims = (journal.load_yaml(claims_path, expect=list)
                  if claims_path.exists() else [])
    except journal.YamlUnreadable as exc:
        journal.receipt(ws, GATE, {}, "could_not_run", [exc.finding])
        print(f"cannot run {GATE}: {exc}", file=sys.stderr)
        return 2
    live, retracted, claim_findings = _claim_index(claims)
    findings += claim_findings

    exact, prose, families = master_sources(master_profile)
    # No readable master, nothing to check against: the MASTER_* finding above is
    # the answer, and it already fails the gate.
    for term, where, family in (atomic_claims(tailored) if readable else []):
        key = normalize_term(term)
        if not key or key in exact:
            continue
        if any(phrase_in(term, leaf) for leaf in prose):
            continue
        kin = [(relation(term, leaf), leaf) for leaf in families.get(family, ())]
        if any(rel == SOURCED for rel, _leaf in kin):
            continue
        if key in live:
            continue
        stripped = next((leaf for rel, leaf in kin if rel == QUALIFIER), None)
        if stripped is not None:
            findings.append(f'QUALIFIER_STRIPPED: "{term}" at '
                            f'tailored-profile.yaml:{where} drops the status '
                            f'qualifier off profile.yaml\'s "{stripped}" — the '
                            f'unqualified form reads as a completed, current '
                            f'credential. Keep the qualifier, or add a claims.yaml '
                            f'row for the fact that it no longer applies')
            continue
        if key in retracted:
            findings.append(f'RETRACTED_CLAIM: "{term}" at '
                            f'tailored-profile.yaml:{where} is backed only by a '
                            f'claims.yaml row marked retracted: '
                            f'{retracted[key]["retracted"]} — remove the claim or '
                            f're-source it')
            continue
        # The master's real name, not the literal 'profile.yaml'. One candidate
        # can have several masters now, and a finding that names the wrong file
        # sends the reader to check a document the gate never read.
        findings.append(f'UNSOURCED: "{term}" appears in '
                        f'tailored-profile.yaml:{where}, is absent from '
                        f'{master.name}, '
                        f'and has no claims.yaml row. A keyword that appears in the job '
                        f'description is not evidence the candidate has it — source it '
                        f'or move it to HONEST-GAPS')

    for f in findings:
        print(f)
    journal.receipt(ws, GATE,
                    {"tailored-profile.yaml": journal.sha256_file(tailored_path)},
                    "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
