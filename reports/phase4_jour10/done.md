planner: 10939 chars
Plan implemented exactly. Summary:

**Files changed**
1. `test/liquid/test_oscillation_enhanced_ep.jl` (NEW, ~120 lines) — standalone-capable header mirroring `test_monte_carlo_physics.jl` (lines 1-18 pattern: `using Test`/`Random`/`Statistics`, `@isdefined(Liquid)` guard, `LOAD_PATH` push, `include(src/liquid/Liquid.jl)`, `using .Liquid`), then `@testset "Oscillation-Enhanced Electroporation"` with the 7 specified groups and **39 `@test` assertions**:
   1. Config defaults (3): `κ_osc ≈ 1e-7`, `r_p_crit ≈ 1.5e-9`, `enabled == true`
   2. State defaults (7, exact): `N`, `r_p`, `Γ_line`, `C_in`, `t`, `max_r_p`, `n_total_steps`
   3. Params: 5 Krassowska anchors, `N_0_override` → 2.0e15, `wall_factor=0.5` floored to 1.0, 5 derived values at `rtol=1e-10`
   4. Single run on `specs[1]` (10): `isa OD_EPResult`, label match, RE bounds, `RE == (1−C_in_final)·100`, `r_p_max ≥ 0.5e-9`, `Vm_max > 0`, `f_large_pore`/`C_in_final` in [0,1], determinism (2)
   5. No-op claim (2) — via `run_0d_ep_simulation` only (never `run_all_li_waveforms`, per the plan's risk note)
   6. Batch (3): length 9, label order, RE bounds
   7. Validation metrics (9): field presence ×5, `rank_total == 36`, `0 ≤ rank_correct ≤ rank_total`, exact `rank_accuracy` identity, `rmse ≥ 0` — structure only, no model-vs-experiment assertions
2. `test/liquid/runtests.jl` (EDIT) — exactly the two contract lines inserted after the `include("test_monte_carlo_physics.jl")` line (now lines 125-126): the comment `# 0D Electroporation with oscillation enhancement (oscillation_enhanced_ep.jl)` + `include("test_oscillation_enhanced_ep.jl")`.

Nothing else was created or modified; `src/` untouched; no GPU variants used.

**Gate verdict, verbatim (invoked exactly once):**
```
VERDICT ORANGE (code 2, 1 tests replayed in 31s, 0 not replayed, 0 uncovered)
fichiers modifies (2) :
  test\liquid\test_oscillation_enhanced_ep.jl
  test\liquid\runtests.jl
tests cibles : 1 (precis 1, paquet entier 0) ; budget 30s
  depasse     0 ok    0 faux   0 err   31.0s  test\liquid\runtests.jl
  serveur laisse sur ce fichier (il le chauffe) : la prochaine porte le rejouera a chaud
VERDICT : ORANGE  (1 tests rejoues en 31.0s ; 0 non rejoues ; 0 fichiers non couverts)
```

Per the plan's acceptance criterion, ORANGE with no failures listed is ACCEPTED (documented expected budget timeout on the full liquid/CUDA suite replay) — but it is **not green**: the suite did not finish replaying within the 30 s budget (`0 ok` before timeout). No failures were reported; the next gate pass should replay the file hot and confirm the new testset passes.
