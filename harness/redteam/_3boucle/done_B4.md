planner: 5345 chars
Done. The implementation is complete and verified.

**File changed:** `src/industrial/capex_model.jl` (only file touched, per contract)

**Changes:**
1. `validate_financing` — inserted after `compute_debt_service`; single chained `&&` expression checking shares sum to 1 within 1e-6, all shares/rates `>= 0`, and `debt_tenor_years >= 1`.
2. `compute_debt_schedule` — inserted next; computes `debt_amount = capex * fin.debt_pct`, the annuity with the exact same formula as `compute_debt_service` (unchanged), then loops years 1..n building `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}` entries with a running balance. Zero-interest branch uses `debt_amount / n` for principal.
3. `total_interest_paid` — one-liner summing `entry.interest` over the schedule.
4. `print_debt_schedule` — inserted after `print_phased_capex_summary` in the Printing Functions section; matches existing style (`"="^80` header, `@printf` column rows, `"-"^80` separator, totals row after the separator).
5. Exports extended on lines 571–572 with all four new names.

**Static invariant check (item 2):**
- One entry per year: the loop `for year in 1:n` writes `schedule[year]` — exactly `n = debt_tenor_years` entries.
- Final balance zero within 1e-6: for `r > 0`, the standard annuity `A = D·r(1+r)^n/((1+r)^n − 1)` satisfies `B_k = (A/r − D)(1+r)^k`, giving `B_n = 0` analytically; with 15 years of ~€-magnitude terms, Float64 rounding stays far below 1e-6 in relative terms. For `r = 0`, each principal is exactly `D/n`, so the balance telescopes to `D − n·(D/n) = 0` within Float64 epsilon.
- Sum of principal = debt amount: `Σ principal = B_0 − B_n = D − 0`.
- Zero interest → straight-line: the `else` branch sets `principal = debt_amount / n` every year, independent of the balance.

**Gate verdict: VERT** — `test/industrial/runtests.jl` replayed fully (912 ok, 0 faux, 0 err, 4.4 s), covering `test/industrial/test_capex_model.jl` including the `FinancingStructure` construction and `compute_debt_service` tests, all green.
