# DONE — ozone_yield_g_per_kwh test hardening

## What was done

Mandated sequence executed in order, then stopped: **planner (1x) → coder (1x, with plan reference) → DONE.md**.

- **Plan**: the planner delegation produced the full plan (spooled to `PLAN_4.md` in the workspace root), quoting verified facts from both files: constant definitions (src lines 470–478), kwarg `f_n2a_branch` defaulting to `OZONE_F_N2A_BRANCH` (line 512), R_O3 formula (line 517), return field names (line 530), degenerate guards (lines 520–522), insertion point, and the gate protocol.
- **Implementation**: the coder delegation read `PLAN_4.md` + the two task files (one read each, nothing else) and made exactly one targeted edit to `test/gpu3d_integration/chemistry/test_ozone_3d.jl`: appended ONE new `@testset "First-principles G-value (ozone_yield_g_per_kwh)"` after the last existing inner testset (after line 397, before the top-level `end`). In the updated file the new block occupies lines 399–452 (file grew 401 → 455 lines). No existing testset or existing line was touched; no runtests.jl change.
- **New tests**: **23 @test macros** (target ≥ 12) in the one new block, covering the full contract:
  - (a) `OZONE_F_N2A_BRANCH == 1.2` exactly; `OZONE_G_FACTOR_G_PER_KWH ≈ 1.7909876587e3` (rtol 1e-6) and `== 48.0 * 3.6e6 / (6.022e23 * 1.602176634e-19)` (its defining expression).
  - (b) Nominal call **through the default kwarg** (`ozone_yield_g_per_kwh(1.0e8, 5.0e6, 2.0e7, 1.0e5, 200.0, 2.4463134e25)`): `R_O3 ≈ 2.29e8`, `G_g_kWh ≈ 8.3827397962e-1`, `eV_per_O3 ≈ 2.1365182533e3`, `eta_dissoc ≈ 1.2263351049e-3` (rtol 1e-6).
  - (c) Default-equals-explicit identity: call with `f_n2a_branch = 1.2` explicit — all four NamedTuple fields `==` the default-kwarg fields.
  - (d) Sensitivity: `f_n2a_branch = 1.3` → `R_O3 ≈ 2.31e8`, `G_g_kWh ≈ 8.4559514974e-1` (rtol 1e-6), both **strictly greater** than the (b) defaults.
  - (e) Both degenerate guards (`R_O3 < 1e-3` with `1e-9, 0.0, 0.0`; `v_d < 1.0` with `0.5`) return exactly `(G_g_kWh = 0.0, eV_per_O3 = Inf, eta_dissoc = 0.0, R_O3 = 0.0)`.
- **Mutation coverage**: with `OZONE_F_N2A_BRANCH` mutated 1.2 → 1.3, tests (a), (b), and (d) all fail — the 25/08 blind spot (76 tests stayed green) is closed.
- **Gate**: `julia_gate` was called **exactly once** (files = `["test/gpu3d_integration/chemistry/test_ozone_3d.jl"]`). No ROUGE path, so no second call. No other test commands were run, and no extra verification was performed after the coder finished. Plan-vs-reality discrepancies reported by the coder: **none**.

## Gate verdict — quoted VERBATIM (single call)

```
VERDICT VERT (code 0, 1 tests replayed in 3.2s, 0 not replayed, 0 uncovered)
serveur occupe depuis 1669s (> 900s) ou mort : on le relance
serveur absent sur 8077 : lancement (chargement du paquet)...
serveur pret en 39s (paquet charge en 35.1s)
fichiers modifies (1) :
  test\gpu3d_integration\chemistry\test_ozone_3d.jl
tests cibles : 1 (precis 1, paquet entier 0) ; budget 30s
  ok         99 ok    0 faux   0 err    3.1s  test\gpu3d_integration\chemistry\test_ozone_3d.jl
VERDICT : VERT  (1 tests rejoues en 3.2s ; 0 non rejoues ; 0 fichiers non couverts)
```

**Verdict: VERT** — all 99 tests in the file passed (76 existing + 23 new), 0 failures, 0 errors.

## Exact list of files changed

1. `test/gpu3d_integration/chemistry/test_ozone_3d.jl` — the only source file modified (one @testset / 23 @test macros appended; existing testsets untouched).
2. `DONE.md` — this file (mandatory report).
3. `PLAN_4.md` — planning artefact spooled by the planner delegation; used as the read-only plan reference by the coder. Not a code change.
