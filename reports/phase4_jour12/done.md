# DONE.md — Phase 21 Ar* jet chemistry test suite

## What was done

Wrote the missing dedicated CPU-only test suite for
`src/gpu3d_integration/ar_jet_chemistry_3d.jl` (Phase 21 Ar* jet chemistry:
metastable quenching, excimer formation, VUV photolysis, Penning O and OH
sources; 511-line source with no dedicated test file before this run).

Executed as two delegations in order:

1. **planner** (one call) — read exactly the three allowed files
   (`src/gpu3d_integration/ar_jet_chemistry_3d.jl`,
   `test/gpu3d_integration/chemistry/test_ozone_3d.jl`,
   `test/gpu3d_integration/runtests.jl`), produced the full implementation
   plan, spooled to `PLAN_3.md`.
2. **coder** (one call, with the plan reference `PLAN_3.md`) — read the plan
   and the same three source files, wrote both deliverables, and ran the
   `julia_gate` tool exactly once after both files were written. No extra
   verification steps were performed after the coder finished.

The new test suite covers contract items a)–j) in `@testset` blocks mirroring
those letters (configuration constants, derived rates, state allocation/reset,
single-cell step with measured anchors and direction checks, H₂O sensitivity
directional, positivity, pure-air X_Ar=0 cell, diagnostics NamedTuple keys,
`vuv_radial_redistribute!`, determinism). CPU-only throughout
(`use_gpu=false`; `CUDA.functional()` never required). 55 `@test` macros
(written count), exceeding the ≥ 40 target. Conventions (header docstring,
include-if-not-defined guard, testset structure) mirror the neighbour
`test/gpu3d_integration/chemistry/test_ozone_3d.jl`.

## Gate verdict (VERBATIM)

```
VERDICT ORANGE (code 2, 1 tests replayed in 31s, 0 not replayed, 0 uncovered)
fichiers modifies (2) :
  test\gpu3d_integration\chemistry\test_ar_jet_chemistry_3d.jl
  test\gpu3d_integration\runtests.jl
tests cibles : 1 (precis 1, paquet entier 0) ; budget 30s
  depasse     0 ok    0 faux   0 err   31.0s  test\gpu3d_integration\runtests.jl
  serveur laisse sur ce fichier (il le chauffe) : la prochaine porte le rejouera a chaud
VERDICT : ORANGE  (1 tests rejoues en 31.0s ; 0 non rejoues ; 0 fichiers non couverts)
```

Interpretation per the known gate behaviour: the full GPU3DIntegration replay
exceeded the gate's 30 s budget (31.0 s), so the verdict is **ORANGE with ZERO
failures (0 ok / 0 faux / 0 err)** — the expected and acceptable outcome. The
gate was not called again. Not green: heavier suites are still pending; the
gate's server keeps the file warm for the next run.

## Files changed (exact list)

- created: `test/gpu3d_integration/chemistry/test_ar_jet_chemistry_3d.jl`
- modified: `test/gpu3d_integration/runtests.jl` (one include line added in
  the chemistry testset, style of the neighbours)
- created: `DONE.md` (this file)

No other files were read or written. `src/` was not touched.