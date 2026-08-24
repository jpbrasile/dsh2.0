planner: 13214 chars
VERT on the first round. Implementation complete — the plan was implemented exactly, and the gate is green.

## Summary

**Files changed (2):**

1. **`test/industrial/test_biorefinery_symbiosis.jl`** (new) — 14 `@test` assertions, matching the plan's test-file content exactly:
   - Hand-computed values: `biomass_kg ≈ 0.08`, `protein_kg ≈ 0.0324`, `daily_profit ≈ 0.8097946666666667` (atol=1e-10), `fertilizer_revenue ≈ 0.000032`, `estimate_biorefinery_capex(0.0) ≈ 110_000.0`, `r_zero.daily_profit ≈ 0.0`
   - Cost structure: `co2_cost == 0.0`, `heat_cost == 0.0`, `methanizer_savings > 0`, `r_standalone.co2_cost > 0`, `r_100.total_cost < r_standalone.total_cost`
   - Bound: `0.0 < protein_kg/biomass_kg <= _SYM_PROTEIN_YIELD`
   - Monotonicity: `r_200.biomass_kg > r_100.biomass_kg`, `capex(200) > capex(100)`

2. **`test/industrial/runtests.jl`** — one line added: `include("test_biorefinery_symbiosis.jl")` between the algae_pef_chain include and the `if HAS_CUDA` block, as specified.

**Source untouched** — `src/industrial/biorefinery_symbiosis.jl` was only read (constants, fields, and signatures all confirmed consistent with the plan's derivations before writing).

**Gate:** `julia_gate` → **VERT** (code 0, 1 test replayed in 4.3s, 0 not replayed, 0 uncovered; 926 ok / 0 failed / 0 errors in `test/industrial/runtests.jl`). No failures, no residual work.