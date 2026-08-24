planner: 19620 chars
## Final report

**Files changed:**
1. **NEW** `test/liquid/test_monte_carlo_physics.jl` — CPU-only deterministic tests for `src/liquid/monte_carlo_physics.jl`: `PhysicsUQParam` convenience-constructor defaults; 13 default params with the four literature anchors (`f_irrev_max`, `E_threshold_kJ_m3`, `w_TS`, `tau2`) and all 9 config defaults; plateau overrides (`lo == hi` on the three pulse params, `t_peak_us` unchanged); `_sample_physics_param` fixed/normal/lognormal/triangular bound checks; `_sample_all_params` dict size/type + seed reproducibility; EROEI hand-computed anchor `≈ 9.509375 atol=1e-12` and zero-energy → 0; `run_physics_monte_carlo_proxy` (n=300) structural checks + reproducibility; `physics_uq_convergence_check` NamedTuple keys and RSE ≥ 0; `physics_uq_to_dict` round-trip keys. Well over the 15-assertion floor.
2. **EDIT** `test/liquid/runtests.jl` — inserted `# Monte Carlo Physics UQ` comment + `include("test_monte_carlo_physics.jl")` immediately after the `test_waveform_library.jl` include (former line 120).
3. `DONE.md` — verdict + self-check (per plan step 5).

**Last gate verdict (verbatim, single call as the plan requires):**
```
VERDICT ORANGE (code 2, 1 tests replayed in 31s, 0 not replayed, 0 uncovered)
fichiers modifies (2) :
  test\liquid\test_monte_carlo_physics.jl
  test\liquid\runtests.jl
tests cibles : 1 (precis 1, paquet entier 0) ; budget 30s
  depasse     0 ok    0 faux   0 err   31.0s  test\liquid\runtests.jl
  serveur laisse sur ce fichier (il le chauffe) : la prochaine porte le rejouera a chaud
VERDICT : ORANGE  (1 tests rejoues en 31.0s ; 0 non rejoues ; 0 fichiers non couverts)
```

**Interpretation:** ORANGE, exactly as the plan predicted — the full liquid suite (including the CUDA portion) exceeded the 30 s budget, with 0 failures and 0 errors. This is NOT green: heavier suites are still pending, and the new test file's assertions were not individually confirmed green within budget. Per the plan's risk section, no retry was performed. `src/` was not touched; only the proxy path is exercised.
