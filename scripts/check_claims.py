#!/usr/bin/env python3
"""Gate: every claim the tailoring added traces to a permitted source.

The claim-provenance checkpoint is the skill's highest-value rule and, until
claims.yaml existed, its most silent one: no provenance file, no citation column
in any required output, no script diffing the tailored CV against the master. A
run could skip it entirely and every downstream gate still passed — while every
automated signal in the system (an ATS REJECT on a missing keyword) rewarded the
dishonest edit.

Scope is a closed set of short atomic fields — skills leaves, certifications,
experience titles, education degrees — because that is where the four named
fabrication classes land and each is a string that compares exactly. Free prose
is deliberately out: rewording prose IS the skill's job, and a gate that fires on
every honest run is a gate people learn to skip.

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

import yaml

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


def normalize_term(s) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return " ".join(_PUNCT.sub(" ", s).split())


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


def tailored_terms(profile) -> list:
    """[(term, where)] over the closed set of fabrication-prone fields."""
    out = []
    skills = profile.get("skills") or {}
    if isinstance(skills, dict):
        for group, items in skills.items():
            for item in _as_list(items):
                out.append((_flat(item), f"skills.{group}"))
    else:
        for item in _as_list(skills):
            out.append((_flat(item), "skills"))
    for i, cert in enumerate(profile.get("certifications") or []):
        out.append((_flat(cert), f"certifications[{i}]"))
    for i, ex in enumerate(profile.get("experience") or []):
        if isinstance(ex, dict) and ex.get("title"):
            out.append((str(ex["title"]), f"experience[{i}].title"))
    for i, ed in enumerate(profile.get("education") or []):
        if isinstance(ed, dict) and ed.get("degree"):
            out.append((str(ed["degree"]), f"education[{i}].degree"))
    return out


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
        journal.receipt(ws, GATE, {"profile.yaml": digest}, "recorded", [])
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
    if not master.exists():
        findings.append(f"MASTER_MUTATED: {master} no longer exists — the master "
                        f"profile is never mutated by tailoring")
        master_text = ""
    else:
        now = journal.sha256_file(master)
        master_text = normalize_term(master.read_text(encoding="utf-8"))
        if now != fp["sha256"]:
            findings.append(f"MASTER_MUTATED: profile.yaml content changed during this "
                            f"run ({fp['sha256'][:12]}… → {now[:12]}…) — the master "
                            f"profile is never mutated by tailoring; tailoring works on "
                            f"the workspace copy")
        elif master.stat().st_mtime_ns != fp.get("mtime_ns"):
            findings.append(f"MASTER_TOUCHED: profile.yaml's mtime changed during this "
                            f"run though its content is identical — something wrote to "
                            f"the master; confirm nothing is editing it")

    tailored = yaml.safe_load(tailored_path.read_text(encoding="utf-8")) or {}
    claims_path = ws / "claims.yaml"
    claims = []
    if claims_path.exists():
        claims = yaml.safe_load(claims_path.read_text(encoding="utf-8")) or []
    live, retracted, claim_findings = _claim_index(claims)
    findings += claim_findings

    for term, where in tailored_terms(tailored):
        key = normalize_term(term)
        if len(key) < 2 or key in master_text:
            continue
        if key in live:
            continue
        if key in retracted:
            findings.append(f'RETRACTED_CLAIM: "{term}" at '
                            f'tailored-profile.yaml:{where} is backed only by a '
                            f'claims.yaml row marked retracted: '
                            f'{retracted[key]["retracted"]} — remove the claim or '
                            f're-source it')
            continue
        findings.append(f'UNSOURCED: "{term}" appears in '
                        f'tailored-profile.yaml:{where}, is absent from profile.yaml, '
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
