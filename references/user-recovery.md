# Pause for the user, then resume discovery

A website refusal stops automated reads from that source, not the user's whole
job search. Do not silently replace a recoverable interruption with directions.
This applies to both OpenCLI and browser retrieval, before search and mid-search.

## 1. Explain the actual obstacle and ask for the matching action

Preserve the raw response and journal it before another read. State the site,
what was actually observed, and what the user can do. Use the user's language.

| Observed state | Hand-off |
|---|---|
| A confirmed missing login | Ask the user to sign in on that site in the connected browser. Offer `opencli <site> login` only if that adapter actually has it; the user runs it. |
| A guest-group message such as `抱歉，您所在的用户组(游客)无法进行此操作` | Tell the user this site requires login. Do not call it an empty result or retry a working connection; the page's explicit guest state overrides a stale cached login flag. |
| CAPTCHA, Cloudflare challenge or slider | Ask the user to open that site in the same connected browser and complete the displayed human verification. This does not establish that a login is missing. |
| Human verification stays loading, including `验证成功。正在等待 … 响应` | Tell the user the page is still held at human verification and ask them to inspect/finish it. A tool timeout does not turn this into an ordinary loading retry. |
| Rate limit / HTTP 429 | Explain the displayed wait period, if any. Logging in is not a fix. Wait for the user to return and request continuation; no timed or background retry. |
| Permission/account denial or unexplained refusal | Quote the error and ask the user to inspect the page. Do not promise that login will fix it or label an unseen page as a CAPTCHA. |

For example, with an observed Indeed challenge:

> Indeed 返回了 Cloudflare 人机验证页，这一来源已暂停。请在当前连接的浏览器中打开 Indeed，手动完成页面上的验证；完成后回复“已完成，继续”，我会接着检查并检索。此前已取得的结果会保留。你也可以选择其他来源，或把岗位正文粘贴给我。

If the browser tool is disconnected, explain and resolve that separately. A
working bridge is not proof of a logged-in or verified website session.

## 2. Wait, while keeping completed work

Keep the original `raw/`, `journal.jsonl`, brief and collected rows unchanged.
Record the pending hand-off in `recovery.md` within that workspace: site, actual
error, requested action and `awaiting_user`. Do not store cookies or credentials.
You may continue other already-authorized sources that have not refused access.
If all sources are paused, wait for the user instead of declaring the task done.

The previous user request plus the user's explicit reply that the action is done
and they want to continue is enough; do not make them repeat their region, role
or full search brief. Elapsed time, silence, an agent's own assumption, an
unrelated “OK”, or a second tool becoming available is not that confirmation.

## 3. Resume in one new linked round

After the explicit reply, record the reply and its time in `recovery.md` and mark
it `user_confirmed`. Make a new workspace with a unique slug (e.g. suffix
`-resume-1`), retaining the original search scope and normal per-round caps.
Record `resume_from`, site, reason and the user confirmation in the new
`recovery.md`; point back to the old raw evidence and stopped journal. Run
`enter_mode.py --mode discover` for the new workspace as usual.

This is a new round in the same conversation, not permission to retry inside the
stopped journal. Never delete/reforge receipts, relabel the site, raise caps or
switch backend/profile/account/proxy to get around its stop. Use the same source
and backend that was interrupted. The confirmation documents a human action;
it is not proof that the website accepted that action.

Make one bounded read to check access, then classify and journal its real result.
Use the original search with a small result limit, or the same requested detail
read. If successful, continue the unfinished search within the new round's
remaining caps, deduplicate against prior results, and retain original source
URLs/timestamps. Do not count old rows as freshly retrieved in this round. A
combined user-facing view must identify each row's actual capture round; each
round's shortlist is validated against its own journal.

If access is refused again, record the new refusal, pause and report it. Do not
loop automatically or treat the earlier confirmation as permission for unlimited
new rounds. Ask for a new user action or offer another source/pasted JD/partial
results. Only use direction-level degraded output when the user chooses it or
recovery is unavailable, explaining which sources remain inaccessible.

## What the scripts can prove

The existing gates still reject any read after a refusal within the same round,
including source aliases and backend changes. Recovery guidance is advisory;
there is no script flag that can verify a real user reply or a completed CAPTCHA.
The agent must follow the hand-off above. A new workspace alone is not evidence
of user confirmation; retain the actual reply in the recovery notes.
