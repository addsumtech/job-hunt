# Bounded page recovery

The user requested retries and investigation of VPN/split-routing problems after
the main review and fixes. Implement this as a shared skill workflow using the
existing browser connection and evidence files. A new retry service or global
proxy manager would add state and permissions beyond the request.

The workflow distinguishes site refusals, disconnected browser tools, loading
pages and transport failures. Allow one unchanged retry and one verification
after an authorized, narrowly scoped route repair, within existing read budgets.
Record failures and outcomes; never equate unreachable pages with no results.

Validation: review against source refusal locks, per-site budgets and immediate
capture/import rules; run the existing browser and skill structure regressions.
This documentation does not claim automatic detection of every VPN problem or
automatic enforcement of the new retry count by the capture recorder.
