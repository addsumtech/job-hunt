# Answer bank

## Batched GPU reconstruction on the 3T study
- serves: "tell me about an optimisation you made"; round 2 Q1
- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
- session: 2026-08-09 — mock/transcript-2.md#Q1
- S: offline recon for a 3T scanner study at the university hospital
- T: the per-slice loop was the bottleneck in the nightly batch
- A: replaced the per-slice loop with a batched GPU implementation
- R: open loop — the measured change was not stated in the room
- R2 (reflectie): write the baseline down before optimising
