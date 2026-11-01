# Online presence: ask once, watch for updates, confirm, write back

Status: design, 2026-11-01. Owner decisions are marked **(user)**; the author's calls
are marked **(call)** and can be overturned.

## Why

A candidate's CV lags behind what they have already made public. In the SKIM apply
run on 2026-11-01, the strongest evidence for the posting's core must-have was a
public GitHub project (slides_maker, 646 stars) that the English master did not
mention. The run found it only because the agent happened to know the repository and
asked the user, one question at a time. The skill itself had no record that the user
has a GitHub account, no memory of what was there last time, and no step that looks.

The aim is that a user states their public profiles **once**, and from then on the
skill checks those profiles itself, notices what changed since the last look, asks
the user to confirm anything new, and keeps the confirmed facts in the master
profile so the next run starts from them.

## Goals

1. **Ask once (user).** Before a mode needs it, check whether this person has
   already given their public profiles. If not, ask once. Record every answer,
   including "none" and "prefer not to say", and do not ask again unless the user
   asks to change it.
2. **Sources (user).** GitHub, Google Scholar and a personal website. LinkedIn is
   out.
3. **Changes over time (user).** Each check keeps a snapshot; the next check is
   compared with it, so the skill can say what is new since the last look (a new
   repository, a new release, a new paper, a changed page), not only what exists.
4. **Confirm before use (user).** Nothing found online enters a CV, a letter, a
   match verdict or the master until the user confirms it. Unconfirmed findings
   only appear as questions.
5. **Write back (user).** Confirmed findings are written into the master profile,
   so later runs do not ask about them again.
6. **Modes (user).** apply, discover and assess use it. interview does not.
7. **Not every run (user).** Re-check only when the last snapshot is older than a
   threshold. **(call)** 14 days, overridable per run when the user says they just
   published something.

## Non-goals

- LinkedIn, or any page that needs a login **(user)**.
- Replacing the supplementary questions. Work that is not public (the Qwen2.5-VL
  project in the SKIM run) is still found by asking **(user)**.
- Merging candidates the store already splits (this user has both `donghang-lyu`
  and `donghang-lyu-llm`). The record lives in one profile directory; joining
  directories is a separate change **(call)**.
- Other scholarly sources (ORCID, DBLP, Semantic Scholar) **(call)**; they can be
  added later behind the same interface.

## Anti-goals: it fails even if it runs

- An online fact reaches a CV, letter or verdict without the user's confirmation.
- The user is asked the same profile question twice, or a declined finding keeps
  coming back unchanged.
- A blocked site is retried, routed around or treated as "nothing new".
- Every mode entry gets slower by a full fetch when nothing could have changed.
- A finding is credited to the user beyond their real part (a co-authored paper or
  a shared repository stated as theirs alone).

## Constraints from the existing skill

- `references/source-policy.md`: public pages without login only; a 403, captcha
  or rate limit stops that site for that check, with no retry and no bypass, and is
  reported as "could not check", never as "no updates".
- Honest-only and claim provenance (`references/gap-analysis.md`, `check_claims.py`):
  a confirmed finding written into the master becomes an ordinary `profile-line`
  source. An unconfirmed one may be cited only as a question.
- The master is never edited by hand: write through `scripts/save_profile.py`,
  which makes a dated backup. One master per language.
- Order inside a mode: the presence step must finish (and any write-back happen)
  **before** the profile is frozen: `snapshot_profile.py` in discover, the master
  fingerprint (`check_claims.py --record`) in apply, the assessment's profile read
  in assess. Otherwise the run checks against the pre-update master.
- Python 3.10+, standard library plus the existing requirements; runnable from any
  host. Network access goes through what the skill already uses for public reads.
- Tests must fail on the old code (the repository's discrimination rule).

## How it works

### 1. The record (call)

One file per person: `<profile_dir>/online-presence.yaml`, resolved through
`scripts/paths.py`. It holds:

- the profiles the user gave: GitHub username, Google Scholar profile URL,
  personal website URL. GitHub also takes **extra repositories or organisations**
  the user names, because a profile page does not list repositories that belong to
  an organisation (slides_maker lives under `addsumtech`, not the user's account);
- the ask status of each source: `given`, `none`, `declined`, with the date and
  the user's words;
- the last check per source: date, outcome (`ok`, `refused`, `failed`) and the
  snapshot file;
- the findings log: each finding with its status (`pending`, `confirmed`,
  `ignored`), the user's verbatim answer, and which master(s) it was written into.

"Already given" is true when this file has an answer for the source **or** a
master's `contact.links` already holds that link; in the second case the link is
copied into the record without asking.

### 2. Snapshots and the diff (call)

Snapshots go under `<profile_dir>/online-presence/snapshots/<date>-<source>.json`,
with the raw responses beside them, never edited. The diff compares the new
snapshot with the previous one for that source:

- **GitHub** (public REST API; `gh` when present): per repository the name,
  description, creation and last-push dates, stars, forks, latest release and
  topics. Findings: new repositories, new releases, notable star/fork changes, and
  the user's role (owner, top contributor, contributor) taken from the API, not
  assumed.
- **Google Scholar**: title, venue, year and author list per paper. Findings: new
  papers, with the user's author position. Scholar often refuses automated reads;
  that is a refusal under the source policy and is reported to the user.
- **Personal website**: the rendered text of the given page. Findings: added or
  changed passages, quoted.

The first check has no previous snapshot: everything found that the master does
not already mention is a candidate finding.

### 3. Confirmation (user decision, call on the shape)

After a check, the agent shows the findings in one message with selectable
options per finding: **add to my profile**, **not relevant / ignore**, **add, but
correct it** (with a note). Wording questions the master needs (the user's role,
dates) are asked in the same message. An ignored finding is not offered again
unless it changes (for example a new release of the same repository).

### 4. Write-back (user decision, call on the details)

Confirmed findings are written into the master **in the language of the current
run** through `save_profile.py`: a repository becomes a `projects` entry with its
link, a paper becomes a `publications` entry, a GitHub or website link goes into
`contact.links`. The record notes which master received each finding. When a run
later uses another language's master, confirmed findings it lacks are offered for
that master too; the facts are not re-confirmed, only the wording.

### 5. Wiring into the modes (call)

- One script, `scripts/online_presence.py`, with subcommands: `status` (given?,
  asked?, stale?), `record` (store the user's answer), `check` (fetch and snapshot
  stale sources, print findings), `confirm` (record the user's decision), and
  `writeback` (apply confirmed findings through `save_profile.py`).
- `SKILL.md` "Enter a full mode" gains one step; apply, discover and assess each
  call it at the point named in the constraints above. The step writes a journal
  record, so a later gate can tell that it ran.
- Gates only notice; they never block delivery because a site refused or the user
  declined. **(call)** `check_apply.py` and `check_shortlist.py` emit a NOTICE when
  the step left no journal record.

## Decisions after the builder check (call)

1. **Who fetches.** GitHub is read by the script itself through the public REST API
   (urllib, or `gh api` when present), and each call is journaled like the existing
   search receipts. Google Scholar and the personal website are read by the agent
   through the existing capture path (`run_tool.py browser` /
   `record_browser_capture.py`, or a host fetch tool saved under `raw/`); `check`
   only ingests those raw files, snapshots and diffs. So the step still works on a
   host without a browser: GitHub is checked, and the other two report "not checked
   on this host".
2. **Write-back while an application is open.** Write-back is allowed from apply,
   discover and assess, always through `save_profile.py` and always as a journaled
   `master_writeback` record. Resuming an apply workspace whose master fingerprint no
   longer matches checks the journal: if the only change is a recorded write-back,
   it tells the user what was added and re-records the fingerprint after the user
   agrees; any other change stays a blocking `MASTER_MUTATED`. `modes/assess.md`'s
   "never writes profile.yaml" changes to "never writes it except through a
   confirmed online-presence write-back".
3. **Verification walls.** `source-policy.md` and `user-recovery.md` win. Because
   this step runs at mode entry and is not what the user came for, it does not
   hold the mode hostage: it names the site and page, offers the recovery hand-off
   once, and the mode continues without that source. The source is recorded as
   `refused` with the capture, and the next run re-offers it only if the user
   completed the verification. Never a retry or a different route.
4. **The first check.** It is a baseline. Forks, archived repositories and
   repositories where the API shows no commit by the user are left out. Findings
   are ranked (recent activity, owned over contributed, stars) and at most four are
   shown per run, matching the question tool; the rest stay `pending` and are
   listed by count with an offer to see them. Pending findings are never folded
   into the baseline, so they cannot disappear.
5. **No master yet.** The record and the ask still happen (they belong to the
   person, not to a CV). Confirmed findings wait as `confirmed_unwritten` and are
   written when a master is first saved. In a run whose evidence is a pasted CV,
   a confirmed finding counts as a `session-answer` for that run only.
6. **Volatile numbers.** Stars, forks and release numbers are never written into
   the master. The master gets the durable facts (what the project is, the user's
   role, the link). A run that wants a count reads it from the newest snapshot and
   cites it as a `fetched-artifact` with its date. A change to an entry the user
   already wrote is offered as a finding; the user's own text is never edited
   without confirmation.
7. **Split directories.** The record is per profile directory. When a mode starts in
   a directory without a record while another directory already has one, the agent
   asks once whether they are the same person; if yes, the record is shared by
   reference, so the profile question itself is not asked again.

## Left to the builder

- Exact YAML/JSON schemas, subcommand flags and the snapshot file naming.
- The thresholds for a "notable" star or fork change.
- How the personal-website diff groups changed passages.
- The fixtures used to test the fetchers without network access.
