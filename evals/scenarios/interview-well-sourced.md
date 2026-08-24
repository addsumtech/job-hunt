TASK: Run one mock interview round for this role, then assess it.

TARGET MARKET: Netherlands (Eindhoven). INTERVIEW LANGUAGE: English.
ROUND TYPE: technical / domain depth.

=== CANDIDATE CV (master facts — do not invent beyond this) ===
Donata Rey. Reconstruction Engineer, Medisca BV (2021–present): offline
reconstruction pipeline in C++17; CUDA gridding; nightly Slurm regressions on a
12-node cluster; mentors two juniors.

=== JOB POSTING (already fetched) ===
Senior Reconstruction Engineer | Philips IGT, Eindhoven. C++, CUDA, MRI physics.

=== THE CANDIDATE'S ANSWERS, VERBATIM — play these back as the candidate ===
Q1: "I own the offline reconstruction pipeline — C++17, and I ported the gridding
step to CUDA." Q2 (asked for a concrete instance): "The nightly regression suite
runs on our Slurm cluster; I wrote the job templates and I still maintain them."
Q3 (probed on the CUDA port): "I profiled the gridding kernel, moved the
scatter-add off the critical path, and re-ran the suite to check nothing drifted."
