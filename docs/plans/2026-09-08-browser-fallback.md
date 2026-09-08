# Browser fallback for discovery

Approved scope: prefer OpenCLI when its read adapter and browser connection work.
Use an available web-access browser for read-only page retrieval when the CLI is
missing, its bridge is disconnected, or the requested extraction is unsupported.
An unknown transport failure is not evidence of any of these conditions.

Keep browser captures as their own `browser_call` records, never fabricated
OpenCLI invocations. Import verbatim browser snapshot JSON plus extracted rows;
validate identifiers, URLs and card text against the snapshot, and bind both
files to the journal by SHA-256. The shortlist and no-write gates consume these
records as well as existing adapter records. Search pages, queries, counts and
stop signals remain visible across both paths. An imported snapshot is evidence
of the bytes supplied, not cryptographic proof of browser origin or of unlogged
operations; the operator must save the actual tool output and journal all reads.

A site refusal (captcha, 401/403/429, login wall or platform limit) stops that
site for this round, across tools. Never retry via another backend. No automatic
extension installation, browser reconfiguration, login, application or messaging.
If neither retrieval path is available, ask for a pasted JD/export and disclose
the missing live search rather than inventing a successful retrieval.

Validate browser-only and mixed retrieval, raw-file tampering, invented rows,
invalid actions/URLs, page/count caps, query coverage and cross-tool stop handling.
Use synthetic fixtures for deterministic refusal tests. Report live validation
separately. Existing PRs remain independent and unmerged.
