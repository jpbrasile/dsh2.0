planner: 6779 chars
Done. VERT on the first pass.

**File changed:** `src/industrial/capex_model.jl`
- Inserted four new functions between `compute_debt_service` (end of the Financing Model section) and the `# ===== Printing Functions =====` block:
  1. `validate_financing(fin::FinancingStructure) -> Bool` — checks shares sum to 1.0 within 1e-6, all shares ≥ 0, `debt_interest` ≥ 0, `equity_irr_target` ≥ 0, `debt_tenor_years` ≥ 1; returns `false` on any violation, no throws.
  2. `compute_debt_schedule(capex, fin) -> Vector{NamedTuple}` — annuity `A` computed with the formula character-identical to `compute_debt_service` (`r > 0 ? debt*r*(1+r)^n/((1+r)^n-1) : debt/n`); year loop with `interest = balance*r`, `principal = A - interest`, `balance` updated per year; zero-interest branch uses `principal = debt/n`. Entries are `(year::Int, payment, interest, principal, balance::Float64)`. Static invariant check: each year `balance = prev_balance - principal` and `sum(principal) = debt_amount` implies final balance ≈ 0.
  3. `total_interest_paid(capex, fin) -> Float64` — sums the `interest` field of the schedule.
  4. `print_debt_schedule(capex, fin)` — mirrors `print_phase_capex`/`print_phased_capex_summary` style: `"="^90` header, column headers (Year, Payment, Interest, Principal, Balance), `@printf` rows to two decimals, `"-"^90` separator, total interest paid line, closing `"="^90`.
- Extended the export line: `export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`.

No existing functions were modified, and no test files were touched.

**Last gate verdict:** **VERT** — `test/industrial/runtests.jl` replayed, 912 ok / 0 failed / 0 errors, no uncovered files.