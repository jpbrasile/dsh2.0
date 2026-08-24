Good. I have everything I need. Let me now write the plan.

---

## Plan: Add financing cash-flow helpers to `src/industrial/capex_model.jl`

### (1) Goal

Add four new financing functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to the existing `capex_model.jl` file, export them, and verify correctness by running the existing `test/industrial/runtests.jl` (which includes `test_capex_model.jl`) for a VERT verdict, supplemented by a self-check of the schedule invariants.

### (2) Files to touch

| File | What changes | Why |
|------|-------------|-----|
| `src/industrial/capex_model.jl` | Insert four new functions after `compute_debt_service` (after line 446), before the `# Printing Functions` section; add their exports to the export block (lines 566–573); add a using import for `NamedTuple` if needed (it is not—`NamedTuple` is built-in in Julia, no import required). | These are the four required functions. The existing `compute_debt_service` already computes the annuity; the schedule builder reuses that same annuity formula. |
| *(no other files)* | — | The task explicitly says the coder may NOT create or edit tests, so the test file is read-only for this plan. |

### (3) Ordered steps for the coder

1. **Read `src/industrial/capex_model.jl`** to get the exact current state (already done above, but the coder should re-read it to have line numbers in their session).

2. **Insert the four functions** immediately after line 446 (the `end` of `compute_debt_service`) and before line 448 (the `# Printing Functions` divider). Insert the following block:

   ```julia
   """
       validate_financing(fin::FinancingStructure) -> Bool

   Validate that the financing structure sums to 1 and has sensible values.

   Returns `true` when:
   - `equity_pct + debt_pct + grant_pct == 1` within 1e-6,
   - every share and rate is non-negative,
   - `debt_tenor_years >= 1`.
   Returns `false` otherwise (does not throw).
   """
   function validate_financing(fin::FinancingStructure)
       # Sum check with tolerance
       if abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) > 1e-6
           return false
       end
       # Non-negativity
       if fin.equity_pct < 0 || fin.debt_pct < 0 || fin.grant_pct < 0 ||
          fin.debt_interest < 0 || fin.equity_irr_target < 0
           return false
       end
       # Tenor minimum
       if fin.debt_tenor_years < 1
           return false
       end
       return true
   end

   """
       compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

   Compute the amortization schedule for the debt portion of CAPEX.

   Returns one entry per year 1..debt_tenor_years, each a NamedTuple with fields
   `(year, payment, interest, principal, balance)`. Uses the same annuity formula as
   `compute_debt_service`. Zero interest = straight-line principal. The final balance
   is zero within 1e-6 and the sum of principal equals the debt amount.
   """
   function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
       debt_amount = capex * fin.debt_pct
       r = fin.debt_interest
       n = fin.debt_tenor_years

       # Same annuity formula as compute_debt_service
       if r > 0
           annuity = debt_amount * r * (1 + r)^n / ((1 + r)^n - 1)
       else
           annuity = debt_amount / n
       end

       schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}}(undef, n)
       balance = debt_amount

       for year in 1:n
           if r > 0
               interest = balance * r
               principal = annuity - interest
           else
               interest = 0.0
               principal = annuity  # straight-line
           end
           balance -= principal
           schedule[year] = (year=year, payment=annuity, interest=interest, principal=principal, balance=max(balance, 0.0))
       end

       return schedule
   end

   """
       total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64

   Sum of the interest column of the debt schedule.
   """
   function total_interest_paid(capex::Float64, fin::FinancingStructure)
       schedule = compute_debt_schedule(capex, fin)
       return sum(row.interest for row in schedule)
   end

   """
       print_debt_schedule(capex::Float64, fin::FinancingStructure)

   Print the amortization schedule as a formatted table.
   """
   function print_debt_schedule(capex::Float64, fin::FinancingStructure)
       schedule = compute_debt_schedule(capex, fin)
       debt_amount = capex * fin.debt_pct

       println("="^70)
       println("DEBT AMORTIZATION SCHEDULE")
       println("="^70)
       @printf("  Debt amount:      €%.2f M\n", debt_amount / 1e6)
       @printf("  Interest rate:    %.2f%%\n", fin.debt_interest * 100)
       @printf("  Tenor:            %d years\n", fin.debt_tenor_years)
       @printf("  Annual payment:   €%.0f\n", schedule[1].payment)
       println("-"^70)
       @printf("%5s | %12s | %12s | %12s | %12s\n",
           "Year", "Payment €", "Interest €", "Principal €", "Balance €")
       println("-"^70)
       for row in schedule
           @printf("%5d | %12.0f | %12.0f | %12.0f | %12.0f\n",
               row.year, row.payment, row.interest, row.principal, row.balance)
       end
       println("-"^70)
       @printf("  Total interest:   €%.0f\n", total_interest_paid(capex, fin))
       println("="^70)
   end
   ```

   The style mirrors `print_phase_capex` (lines 457–471) and `print_phased_capex_summary` (lines 478–520): banner with `=` and `-` separators, `@printf` with column headers, and a summary metric at the end.

3. **Add the four exports** to the export block. On line 571, after `export default_financing, compute_debt_service`, add a new line:

   ```julia
   export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
   ```

   The final export block (lines 566–573) should become:

   ```julia
   export ModularCAPEX, DeploymentPhase, PhaseCAPEX, CumulativeCAPEX
   export FinancingStructure
   export default_capex_model, optimistic_capex_model, conservative_capex_model
   export default_deployment_phases
   export compute_phase_capex, compute_phased_capex, compute_cumulative_capex
   export default_financing, compute_debt_service
   export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
   export print_phase_capex, print_phased_capex_summary
   export demo_capex_model
   ```

4. **Run the gate**: call `julia_gate` on `test/industrial/runtests.jl`. The test file is `test/industrial/runtests.jl` — it includes `test_capex_model.jl` (line 52). The acceptance criterion is **gate verdict VERT** on that test file plus a manual invariant self-check the coder must perform (see below).

5. **Self-check of invariants** (the coder must verify these logically or through inline inspection; they cannot add test code). For `compute_debt_schedule(capex, fin)` with `capex > 0` and `validate_financing(fin) == true`:
   - Length of schedule == `fin.debt_tenor_years`.
   - The final `balance` field (last entry) is within 1e-6 of zero.
   - The sum of all `principal` fields equals `capex * fin.debt_pct` within 1e-6.
   - For zero interest (`fin.debt_interest == 0`), every `principal` equals `capex * fin.debt_pct / fin.debt_tenor_years`.
   - For positive interest, every `interest + principal` equals the constant annuity (`compute_debt_service(capex, fin)`).
   - `total_interest_paid(capex, fin)` equals the sum of the interest column.
   - `validate_financing(default_financing())` returns `true`.
   - `validate_financing(FinancingStructure(0.5, 0.5, 0.1, 0.05, 15, 0.12))` returns `false` (doesn't sum to 1).
   - `validate_financing(FinancingStructure(0.3, 0.4, 0.3, -0.01, 15, 0.12))` returns `false` (negative rate).
   - `validate_financing(FinancingStructure(0.3, 0.4, 0.3, 0.05, 0, 0.12))` returns `false` (tenor < 1).

### (4) Targeted tests and acceptance criterion

- **Test file to replay**: `test/industrial/runtests.jl` (which includes `test/industrial/test_capex_model.jl` at line 52).
- **Acceptance criterion**: Gate verdict **VERT** on that test file. The existing tests in `test_capex_model.jl` already check `FinancingStructure` construction (line 162–173: fields, sum-to-one) and `compute_debt_service` (lines 175–197: annuity positive, total payments exceed debt, zero-interest case). The new functions do not change any existing behavior, so existing tests must still pass. The invariants listed in step 5 above must also hold; the coder verifies them manually (they cannot add test code).

### (5) Risks and what NOT to touch

- **Do NOT modify** `test_capex_model.jl` or any other test file. The task explicitly forbids the coder from creating or editing tests.
- **Do NOT modify** `compute_debt_service` (lines 433–446). The new `compute_debt_schedule` independently replicates the same annuity formula; do not refactor one to call the other — keeping them independent avoids any risk of changing existing behavior.
- **Do NOT touch** the `FinancingStructure` struct (lines 403–410). It already has all the fields needed.
- **Risk: `NamedTuple` type annotation**: Julia's `Vector{NamedTuple}` return type annotation on `compute_debt_schedule` uses a concrete `NamedTuple` parameterization. The codepoint in the implementation above uses the fully-specified type `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}`. If the coder finds this verbose or problematic, a simpler `Vector{@NamedTuple{year::Int, payment::Float64, interest::Float64, principal::Float64, balance::Float64}}` is acceptable but requires no additional imports in Julia ≥ 1.9. Alternatively, dropping the concrete type annotation and just returning the vector (letting inference handle it) is also acceptable — the docstring already documents the return shape.
- **Risk: `NamedTuple` import**: `NamedTuple` is a Julia built-in core type; no `import` or `using` is needed. Do not add any import statements.
- **Risk: `balance` going slightly negative** on the final year due to floating-point. The implementation above uses `max(balance, 0.0)` as a clamp. The invariant says the final balance must be zero within 1e-6, which this satisfies.