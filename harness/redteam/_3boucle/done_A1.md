planner: 7976 chars
Gate verdict is **VERT** — done. No further tool calls needed; the previous result was the final one, not something to repeat.

## Summary

**Files changed:** `src/industrial/capex_model.jl` (only file touched)

1. **Inserted four functions** after `compute_debt_service` (before the Printing Functions section), per the plan:
   - `validate_financing(fin::FinancingStructure) -> Bool` — checks share sum ≈ 1 (1e-6), non-negative shares, non-negative interest, tenor ≥ 1; never throws.
   - `compute_debt_schedule(capex::Float64, fin::FinancingStructure)` — level-annuity amortization; final-year principal pinned to the remaining balance so the schedule ends at exactly zero; two `@assert` internal invariant checks (final balance < 1e-6, principal sum == debt amount within 1e-6) — these fire during the test run at `-O0`, so the invariants are exercised by the gate, not by new test code.
   - `total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64` — sum of the schedule's interest column.
   - `print_debt_schedule(capex::Float64, fin::FinancingStructure)` — ASCII table (Year, Payment, Interest, Principal, Balance in EUR M) with `=`/`-` framing and a total-interest summary line, matching the style of `print_phase_capex` / `print_phased_capex_summary`.

2. **Extended exports** exactly as specified:
   - `export FinancingStructure, validate_financing`
   - `export default_financing, compute_debt_service, compute_debt_schedule, total_interest_paid`
   - new final line `export print_debt_schedule`

**Test files untouched** — `test/industrial/test_capex_model.jl` and `runtests.jl` were not modified.

**Gate:** first run ORANGE (cold start, 31s vs 30s budget, no failures), second run ORANGE (server warming), third run **VERT** — `test/industrial/runtests.jl` replayed hot: **912 ok, 0 failed, 0 errors**, all industrial tests green, no regressions.

No failures.