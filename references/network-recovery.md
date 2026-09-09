# Recover an unavailable page

Use this in every research mode when a requested source will not load. This is
an agent workflow over the existing browser tools, not an automatic retry daemon.
Keep the selected browser, profile, transport and original source identity.

## Classify before repeating a read

Preserve the actual URL, time and browser/tool error under `raw/`. Import a valid
site snapshot before the next read, as described in [browser-fallback.md](browser-fallback.md).
If navigation failed without a valid site snapshot, retain the original tool
failure and record it in `recovery.md`; do not manufacture an empty successful
capture. A browser error page is not evidence that a search found zero jobs.

| Observation | Next action |
|---|---|
| Login wall, CAPTCHA, 401/403/429 or other site refusal | Stop this site across all tools and follow [user-recovery.md](user-recovery.md). No network retry or proxy change to get past it. |
| Browser/CDP connection unavailable | Check the selected connection locally under [daily-browser.md](daily-browser.md). Do not infer a website problem or restart a shared browser/daemon. |
| Page still loading or rendering | Wait once for up to 10 seconds, then inspect the same task-owned tab. Do not reload immediately or interpret missing fields as zero results. |
| Explicit DNS, connection, TLS, address-unreachable or timeout error | Follow the bounded sequence below. An error name identifies a symptom, not its cause. |
| Blank page or unexplained failure | Inspect the current tab and available task-specific error/resource evidence once. If the cause remains unknown, disclose it; do not assume a VPN problem. |

## Bounded network recovery

1. Make at most **one unchanged retry** after a short wait (about 3 seconds), only
   for a transport failure with no refusal signal. Retain the original URL and
   existing browser/profile. Use a bounded tool timeout, normally at most 30
   seconds. A repeat failure leads to diagnosis, not another identical retry.
2. Check only relevant local state: whether the selected browser uses a proxy,
   VPN or domain split-routing rule, and which route the failed hostname takes.
   Use observed task-page resource hosts when a shell loads but content does not.
   Do not read unrelated browsing history, cookies, credentials or full secret
   configuration dumps. A VPN being connected alone does not prove causation.
3. If evidence points to a route problem, explain the proposed exact host/suffix
   change. Existing explicit authorization for that routing repair is sufficient;
   otherwise ask before changing network configuration. Back up the relevant
   rule, make the smallest reversible change and verify the effective route.
   Do not disable the user's VPN, reset global proxy settings, disable TLS
   validation or add broad CDN/provider domains just to make one source load.
4. After one authorized repair, make at most **one verification read** of the
   original failed URL, using the same browser/profile. Preserve and classify its
   result before continuing. If it fails again, stop recovery for that source,
   report the remaining gap and continue independent authorized sources. A newly
   observed refusal takes precedence immediately.

The limit is the initial attempt plus at most two further network attempts per
failed URL in this consultation, including attachment navigation/download and
other workers/tools. Do not reset it by changing the backend or workspace. All
reads still consume the existing site/page/detail budgets; when those are
exhausted, this workflow grants no additional reads. A loading-state observation
does not grant another navigation attempt.

In `recovery.md`, record attempts, exact errors, diagnostic evidence, any user
authorization and route change, and the final result. Preserve failure evidence
even after success. A successful retry establishes access now; it does not prove
the original cause. An accessible announcement does not establish that its
attachment, job-specific requirements or salary were verified. Report those
separately, offering an official alternate source or a user-provided document
when useful.
