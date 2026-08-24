planner: 6545 chars
Done. Verdict: **VERT** (green).

**Files changed**
- `src/industrial/capex_model.jl`:
  - Inserted four new functions after `compute_debt_service` and before the "Printing Functions" divider, under a `# --- Debt schedule helpers` comment:
    - `validate_financing(fin::FinancingStructure) -> Bool` — returns `false` (no exception) unless the split sums to 1 within 1e-6, all ratios/rates are ≥ 0, and `debt_tenor_years >= 1`.
    - `compute_debt_schedule(capex::Float64, fin::FinancingStructure)` — returns the strongly typed `Vector{NamedTuple{(:year,:payment,:interest,:principal,:balance), Tuple{Int64,Float64,Float64,Float64,Float64}}}` using the same annuity formula as `compute_debt_service` (straight-line when `r == 0`), one entry per year.
    - `total_interest_paid(capex, fin)` — sum of `interest` over the schedule.
    - `print_debt_schedule(capex, fin)` — `@printf`-aligned table (Year, Payment, Interest, Principal, Balance in EUR `%.2f`) with `=`/`-` separators and a totals footer.
  - Added a new export line: `export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` after the `default_financing, compute_debt_service` line.

Nothing else was touched — no existing functions, structs, exports, or test files were modified.

**Gate result**: `julia_gate` on `src/industrial/capex_model.jl` → **VERT** — `test/industrial/runtests.jl` replayed, 912 assertions ok, 0 failures, 0 errors, all coverage met.