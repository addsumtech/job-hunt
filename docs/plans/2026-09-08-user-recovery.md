# User-confirmed recovery after website refusal

The user requested a login/verification prompt and continuation after they finish,
instead of abandoning discovery. The current main is the base (`d6ec5aa`).

Considered: clearing a site's stop inside its current journal, or retaining the
stop and continuing in a new linked round after the user's explicit reply. Use
the second: it preserves Leo's source-alias stop guard and existing gate contracts.
No automatic retry or browser reconfiguration is introduced.

Implement actionable classifier/browser guidance, a shared hand-off reference,
and aligned discover/source-policy/core/five-language README instructions.
Distinguish missing login, verification, rate limit and unknown denial. Preserve
partial results. “Done, continue” counts as the new-round request after the
hand-off; no additional repetition of the original brief is required.

Acceptance: both backend refusal paths explain the recovery option; the paused
round continues to reject reads and aliases; a newly confirmed round can record
a successful capture; a second refusal pauses again. Test these with fresh
synthetic inputs and separately report live platform behavior. No historical
output is used as a current test result.
