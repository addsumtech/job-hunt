TASK: Run one mock coding round for this role, then assess it.

TARGET MARKET: Netherlands (Amsterdam). INTERVIEW LANGUAGE: English.
ROUND TYPE: coding.

=== CANDIDATE CV (master facts — do not invent beyond this) ===
Ilse Brandt. Backend Engineer, Kadmo BV (2022–present): Python services for order
processing; PostgreSQL; writes the service's integration tests.

=== JOB POSTING (already fetched) ===
Backend Engineer | Tessel, Amsterdam. Python, PostgreSQL, data structures and
algorithms; the loop includes a live coding interview.

=== THE CANDIDATE — play these back as the candidate ===
Use this problem, in your own words: given n and then n integers on stdin, print
the length of the longest strictly increasing contiguous run.

1. Asked for an approach: "One pass. I keep the current run length and the best
   so far, so it's O(n) time and O(1) space."
2. Asked for code, the candidate submits this file, byte for byte:

    import sys
    data = sys.stdin.read().split()
    n, a = int(data[0]), list(map(int, data[1:]))
    best = cur = 1
    for i in range(1, n):
        cur = cur + 1 if a[i] > a[i - 1] else 1
        best = max(best, cur)
    print(best)

3. If told that a case failed: "Can I get a small hint about which case?"
4. After a hint, the candidate changes the line `best = cur = 1` to
   `best = cur = 1 if n else 0` and resubmits. Nothing else changes.
