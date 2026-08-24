planner: 8905 chars
**VERT** — done.

## Summary

**File changed:** `src/industrial/capex_model.jl` (the only file, per the plan)

**Changes:**
1. **Inserted four financing helpers** after `compute_debt_service` (after its `return annuity`), before the `# Printing Functions` banner:
   - `validate_financing(fin)` — checks shares sum to 1 within 1e-6, all shares/rates non-negative, `debt_tenor_years >= 1`; returns `Bool`, no exception.
   - `compute_debt_schedule(capex, fin)` — level-payment (annuity) amortisation schedule, one `NamedTuple{(:year, :payment, :interest, :principal, :balance)}` per year, concretely typed `Vector{...}`; final period's principal forced to the remaining balance so it hits zero; zero-interest → straight-line principal with zero interest.
   - `total_interest_paid(capex, fin)` — sum of the schedule's interest column.
   - `print_debt_schedule(capex, fin)` — prints the table in the file's existing `@printf` style (`using Printf` already at line 18).
2. **Export addendum** — added `export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` on its own line right after `export default_financing, compute_debt_service`, matching the file's grouped-export style.

No existing struct, function body, docstring, or test file was touched.

**Gate verdict:** The first two gate calls were ORANGE — the industrial suite was cold in the persistent server and its first load (31s) exceeded the 30s budget, then the server was still warming. After the suite finished loading, the warm replay passed: **912 ok, 0 false, 0 err — VERDICT VERT** (the only green).

No failures.