# Weekly job digest: search on a schedule, email only what is new

Status: design, 2026-11-02. Owner decisions are marked **(user)**; the author's calls
are marked **(call)** and can be overturned.

## Why

`discover` finds roles only when the user sits down and asks. The market moves every
week, and a user who is not actively searching misses roles that fit them. The user
wants the skill to look once a week on its own, using what it already knows about
them (master profile, search preferences, a search direction they chose), and to
email them the roles that are new and fit, each with a short reason and the link.
What they do next is up to them.

## Goals

1. **Recipient (user).** The user themself. Each user gets a digest built from their
   own profile, sent to their own mailbox from their own account. No one else.
2. **Cadence (user).** Once a week at a set weekday and hour. If the computer is off
   or asleep then, the run happens at the next opportunity (wake or login), not
   skipped. Due rule **(call)**: the digest is due at the first scheduled slot
   (weekday + hour, system time zone) that is at least 6 days after the last digest
   actually sent. Missed weeks produce one digest, never a catch-up burst.
3. **Content (user).** A short list of suitable roles new since the last digest:
   title, company, location, why it fits, real gaps, original link. No fit score, no
   interview or offer probability (`lint_no_prediction.py`). **(call)** At most 5
   roles per email, best first; the rest wait for next week. Five is discover's own
   `max_match_reviews` ceiling, so every sent role gets the full posting-to-profile
   mapping and no existing cap is raised.
4. **Read the full posting (user).** Every sent role's full posting is read before
   its reason is written; the reason rests on the posting's actual requirements and
   names hard barriers (language, work authorisation, degree).
5. **Only new (user).** A role already sent is never sent again (see Seen ledger).
6. **Loud about gaps (user).** A source that could not be checked (login wall, human
   verification, site refused, network) is named in the email with the reason. It
   never reads as "nothing new". It is retried next week.
7. **Public sources only when unattended (user).** The scheduled run uses only
   sources that need no login: public employer career pages and public job APIs
   (`source-policy.md` Green), and no-login opencli adapters such as `indeed`.
   LinkedIn, BOSS and every other logged-in source are never read by the scheduled
   run. Each email says so in one line and that the user can search them in a
   conversation. A no-login source that unexpectedly shows a login or verification
   wall is stopped for that run and reported (goal 6); the run never waits for a
   human and never routes around a stop.
8. **Send directly (user).** Sent to the user's own address, not left as a draft.
9. **Cancel and pause by reply (user).** Replying "取消推送" / "unsubscribe" stops
   the digest; "暂停 N 周" / "pause N weeks" pauses it, resuming after. Saying it in
   a conversation, or running `digest.py cancel`, works too. A cancel is honoured
   before any search: one short confirmation email, schedule removed.
10. **Feedback needs confirmation (user).** A reply like "第 3 个不相关，因为要德语"
    is recorded; the next digest asks "add 'requires German' to your exclusions?
    reply yes". Preferences change only after that yes.
11. **Empty weeks still send (call).** A week with nothing new sends a short email
    saying which sources were checked, so "no email" can only mean "something broke".

## Non-goals

- No logged-in source in the scheduled run (goal 7).
- No clickable unsubscribe link: it would need a server.
- No cloud scheduling: the profile store is local (`~/.claude/job-profiles`).
- No applying, no messages to employers, no other mode started by the digest.
- No Windows scheduler in v1. **(call)** macOS launchd and Linux user crontab.
- No paid API use in the scheduled run (no Monid runs, no paid keys) **(call)**:
  the user's rule is to ask before every paid run, and nobody is there to ask.
- No new search logic: discover's sources, row schema, evidence rules and gates.

## Policy change (user)

`references/source-policy.md` Red currently forbids "background or unattended
operation while the user is not present". It is narrowed to: unattended operation
is allowed **only** for the weekly digest, **only** on Green sources and no-login
adapters, under the round caps, with every stop signal ending that source for the
run (no retry, no alternative route) and reported in the email. Unattended use of a
logged-in source stays Red. The policy states the account-risk reason for keeping
logged-in sources out. `check_digest.py` enforces it: a digest run whose captures
include a logged-in adapter fails (`DIGEST_LOGGED_IN_SOURCE`).

## Anti-goals

- Irrelevant roles: reasons trace to the posting and the profile, as in discover.
- Repeats: goal 5.
- Ignoring a cancel (the worst one): goal 9 and the inbox rule.
- Silent failure: a run that cannot finish leaves a desktop notification and a log.
- Surprise spend: a per-run budget cap set at setup; no paid APIs.

## How it works

### Setup (interactive, in a conversation)

1. Needs a master profile and `search-preferences.yaml` (if absent, run discover's
   preference questions first).
2. Asks, as selectable options where they are choices: the search direction (one of
   the user's earlier discover `brief.yaml` files, or a new brief built with
   discover's brief questions; copied into `digest.yaml` as the standing brief, with
   logged-in sources removed); weekday and hour; the address (default: the master's
   contact email, confirmed); the per-run budget cap.
3. Checks the agent has an email tool that can send and search mail (this user: the
   Gmail MCP server configured for the user's home directory). Without one, v1 offers the
   fallback **(call)**: an HTML digest in `~/Downloads/job-digest/` plus a desktop
   notification; cancel is then by conversation or `digest.py cancel`.
4. Records answers verbatim in `digest.yaml`, installs the schedule
   (`digest.py install`), and **(call)** runs the first digest in the conversation —
   a real email that counts as `last_sent`.

### Tick (deterministic, no agent)

launchd (`StartInterval` 3600 + `RunAtLoad`) or an hourly cron line runs
`digest.py tick`. It takes a lock (stale after 3 hours), and returns at once unless
due (enabled, not cancelled, not paused, due rule met, attempt budget left). When
due it starts the agent headless with the absolute paths recorded at install (no
reliance on a login shell's PATH), from the directory recorded at setup as holding
the email tool's config, with a fixed prompt naming the `digest` mode and profile.
For Claude Code: `claude -p "<prompt>" --max-budget-usd <cap>` with an explicit
`--allowedTools` list: the skill's scripts through Bash, file read/write, the email
tool's search/read/send, and nothing else (no browser, no Monid). **(call)** Failed
runs: at most 3 attempts per day; after 3 failed days a notification says the digest
is stuck and tick waits for the next weekly slot. The agent command is configurable;
v1 tests Claude Code only, a Codex command is allowed in config but untested.

### The run (`modes/digest.md`)

1. **Inbox first.** The agent searches mail for messages from the recipient address
   in threads of earlier digests (the thread ids are recorded at send) and passes
   their bodies to `digest.py inbox`. The script, not the agent, classifies them
   **(call)**: quoted text is stripped (lines starting with `>`, and everything from
   an "On … wrote:" / "在 … 写道：" / "-----Original Message-----" line on);
   keyword rules find cancel, pause N weeks, yes, and role feedback ("第 N 个" /
   "#N" plus text). Any cancel keyword wins over everything else in the same reply.
   Cancel → confirmation email, uninstall, stop. Pause → `paused_until`, stop.
   **If the inbox cannot be read, stop without sending** (a cancel might be unread),
   notify, log; it counts as a failed attempt.
2. **Search.** A discover round from the standing brief in a fresh
   `digest-runs/<date>/` workspace, with discover's caps and capture/journal rules,
   Green and no-login sources only, no interview and no recovery pause.
3. **Only new.** `digest.py filter` drops rows already in the seen ledger.
4. **Read and explain.** Fetch the full posting for the best new rows within
   discover's detail-fetch band, up to 5 entering the posting-to-profile mapping
   (`check_candidate_match.py`). A row whose page cannot be read is not sent; it
   stays unseen for next week and the email counts it.
5. **Compose and check.** `digest.py compose` renders the email: roles, sources
   checked and unchecked with reasons, the logged-in-sources line, any pending
   preference question, and reply instructions. `check_digest.py` gates it (each
   role has a link and a traceable reason, no prediction language, none already
   in the ledger, every unchecked source named, no logged-in capture). A failing
   gate sends nothing and counts as a failed attempt.
6. **Send and record.** Send; `digest.py sent --message-id … --thread-id …` adds the
   rows to the ledger and sets `last_sent`. A failed send leaves the ledger as is.

### Seen ledger (`digest-seen.yaml`) (call)

- Identity: normalised company (casefold, accents folded, legal suffixes such as
  B.V., N.V., GmbH, Ltd, Inc removed) + normalised title (casefold, punctuation
  removed, Sr/Jr expanded) + location (casefold city; "remote" and multi-location
  postings match any location of the same company+title). Every URL seen for a role
  is kept and an exact URL match always counts as seen.
- A repost or edited posting of a sent role is not sent again in v1. A wrong merge
  can hide a role, a wrong split repeats one; the rules above lean towards merging
  only on exact normalised matches, so near-identical titles are treated as new.
- Entries older than 180 days are dropped.

### Preference feedback (call)

Feedback can change only the `avoid` list in `search-preferences.yaml`. The question
text says the change also applies to later discover runs, because the file is
shared. A yes writes through a dated backup (`search-preferences.yaml.bak-<date>`)
and bumps `updated`, keeping the reply as the user's words. A question unanswered in
two digests is dropped.

### Files (under the profile directory, never in the skill)

`digest.yaml` (settings, standing brief, state, answers), `digest-seen.yaml`,
`digest-runs/<date>/` (workspace, rendered email, run log).

## Testing

- Unit: due rule (missed weeks, pause, cancel, attempt cap, lock), ledger identity
  (cross-site, remote, suffixes, bilingual titles), inbox parsing (quoted
  instructions do not cancel, cancel wins, wrong sender and wrong thread ignored),
  compose and `check_digest.py` (incl. `DIGEST_LOGGED_IN_SOURCE`), generated launchd
  plist and cron line, policy text.
- Real: one end-to-end run on this machine sending to the user's own address; the
  inbox-unreadable stop and the no-email fallback, each once.

## Left to the builder

Further file and function names, email wording and layout, the subject tag, the
prompt wording, the exact keyword lists (Chinese, English, Dutch at least), log
format.

## Revision 2026-11-02: remind, then run with the user present (user)

A real run on the user's machine found three blockers for an unattended run: every
browser session (opencli adapters included) waits for a Chrome consent click; a
headless agent with a strict allowlist cannot write under `~/.claude/job-profiles`;
and the Gmail tool's login had expired. The user chose:

- At the weekly slot, the hourly tick shows a dialog: "Run this week's digest now?"
  **Run now** opens a Terminal with an interactive Claude Code session that follows
  `references/weekly-digest.md`. **Later**, or no answer within 30 minutes, asks again
  after 3 hours; at most 3 reminders a day; three days without a digest stop the
  reminders until the next weekly slot (the existing attempt/stuck rules).
- Because the user is present, the run is an ordinary discover round with the standing
  brief: login hand-offs, consent clicks and logged-in sources (LinkedIn) are allowed
  under the normal source policy. The Red-line exception for unattended runs and
  `DIGEST_LOGGED_IN_SOURCE` are withdrawn; no per-run budget or tool allowlist.
- Unchanged: only new roles (ledger), at most five, full posting read, cancel / pause /
  feedback by reply, `check_digest.py`, presend → send → confirm, empty weeks still send.
- macOS shows the dialog; on Linux the tick sends a desktop notification with the
  command to start the session.
