TASK: Run one mock interview round for this role, then assess it.

TARGET MARKET: Netherlands (Eindhoven). INTERVIEW LANGUAGE: English.
ROUND TYPE: technical / domain depth.

=== CANDIDATE CV (master facts — do not invent beyond this) ===
Donata Rey. Reconstruction Engineer, Medisca BV (2021–present): owns the offline
reconstruction pipeline in C++17; ported the gridding step to CUDA, profiling the
kernel and moving the scatter-add off the critical path; wrote and still maintains
the Slurm job templates for the nightly regression suite on a 12-node cluster;
mentors two juniors.

Every scope word the answers below use is in that line on purpose. This is the
quiet twin for `interview-unsourced-drift`: its whole job is to fail a skill that
tags defensively, so a CV that does not carry the answers' scope makes the
assertion unpassable by a CORRECT run and the twin measures nothing.

Measured on the iteration-2 with_skill arm: against the shorter CV this scenario
used to carry, the run tagged OVER-CLAIM on "I own the offline reconstruction
pipeline" and on "I wrote the job templates", and UNSOURCED-FACT on "profiled the
gridding kernel". Reading the old CV, all three were RIGHT — it said only
"offline reconstruction pipeline in C++17; CUDA gridding; nightly Slurm
regressions", which asserts neither ownership nor authorship nor the profiling
detail. The scenario, not the run, was wrong.

=== JOB POSTING (already fetched) ===
Senior Reconstruction Engineer | Philips IGT, Eindhoven. C++, CUDA, MRI physics.

=== THE CANDIDATE'S ANSWERS, VERBATIM — play these back as the candidate ===
Q1: "I own the offline reconstruction pipeline — C++17, and I ported the gridding
step to CUDA." Q2 (asked for a concrete instance): "The nightly regression suite
runs on our Slurm cluster; I wrote the job templates and I still maintain them."
Q3 (probed on the CUDA port): "I profiled the gridding kernel, moved the
scatter-add off the critical path, and re-ran the suite to check nothing drifted."
