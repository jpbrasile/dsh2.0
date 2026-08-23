Good. I have everything I need. Here is the plan:

---

## Plan

### 1. Goal
Add four financing cash-flow helpers (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) next to `FinancingStructure` and `compute_debt_service` in `src/industrial/capex_model.jl`, plus export them.

### 2. Files to touch

**`src/industrial/capex_model.jl`** — the only file modified.

| Change | Why |
|---|---|
| Add `validate_financing(fin::FinancingStructure) -> Bool` | New function (line ~447, after `compute_debt_service` end on line 446, before `# === Printing Functions ===` on line 448) |
| Add `compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}` | Same location |
| Add `total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64` | Same location |
| Add `print_debt_schedule(capex::Float64, fin::FinancingStructure)` | Same location |
| Add four names to export lines (lines 566–573) | So the symbols are visible |

No other files are touched. No test files are modified.

### 3. Ordered steps for the coder

1. **Insert `validate_financing`** after line 446 (after `end` of `compute_debt_service`, before blank line 447 then `# === Printing Functions ===` on line 448). Implementation:

   ```julia
   """
       validate_financing(fin::FinancingStructure) -> Bool

   Validate that a FinancingStructure is internally consistent.

   Returns `true` when:
   - `equity_pct + debt_pct + grant_pct == 1` within 1e-6,
   - every share and rate is non-negative, and
   - `debt_tenor_years >= 1`.

   Returns `false` otherwise (no exception).
   """
   function validate_financing(fin::FinancingStructure)
       eq = fin.equity_pct; de = fin.debt_pct; gr = fin.grant_pct
       (eq + de + gr ≈ 1.0) || return false
       eq >= 0 || return false
       de >= 0 || return false
       gr >= 0 || return false
       fin.debt_interest >= 0 || return false
       fin.equity_irr_target >= 0 || return false
       fin.debt_tenor_years >= 1 || return false
       return true
   end
   ```

   The `≈` operator uses `≈(x, y; atol=1e-6)` by default in Julia. Confirm that is sufficient (it uses `atol=sqrt(eps()) ≈ 1.49e-8` by default actually — no, Julia's `≈` is `isapprox(x, y; rtol=sqrt(eps()), atol=0.0)`. But `1.0 ≈ 1.0` is fine. The task says "within 1e-6", so use `isapprox(eq + de + gr, 1.0; atol=1e-6)` to be explicit.

   Wait — re-reading: the standard Julia `≈` uses `rtol=sqrt(eps())` with `atol=0`. For sum-of-three-equals-one, floating error is typically < 1e-15, so `≈` would work. But the spec says "within 1e-6", so use that explicit tolerance to match the spec precisely.

2. **Insert `compute_debt_schedule`** after `validate_financing`. Implementation:

   ```julia
   """
       compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

   Compute the year-by-year amortization schedule for debt financing.

   Returns one entry per year 1..debt_tenor_years, each a NamedTuple with fields
   `(year, payment, interest, principal, balance)`, amortizing the debt amount
   `capex * debt_pct` using the same annuity formula as `compute_debt_service`.
   Zero interest produces straight-line principal. The final balance is zero
   within 1e-6 and the sum of principal equals the debt amount.
   """
   function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
       debt_amount = capex * fin.debt_pct
       r = fin.debt_interest
       n = fin.debt_tenor_years

       # Same annuity as compute_debt_service
       if r > 0
           annuity = debt_amount * r * (1 + r)^n / ((1 + r)^n - 1)
       else
           annuity = debt_amount / n
       end

       schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int,Float64,Float64,Float64,Float64}}}(undef, n)
       balance = debt_amount
       for yr in 1:n
           interest = balance * r
           principal = annuity - interest
           balance -= principal
           schedule[yr] = (year=yr, payment=annuity, interest=interest, principal=principal, balance=balance)
       end
       return schedule
   end
   ```

3. **Insert `total_interest_paid`** after `compute_debt_schedule`:

   ```julia
   """
       total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64

   Total interest over the life of the debt = sum of the interest column
   of `compute_debt_schedule`.
   """
   function total_interest_paid(capex::Float64, fin::FinancingStructure)
       sched = compute_debt_schedule(capex, fin)
       return sum(row.interest for row in sched)
   end
   ```

4. **Insert `print_debt_schedule`** after `total_interest_paid`, following the style of `print_phase_capex` (using `@printf`, `"="^N` separators, `"-"^N` dividers):

   ```julia
   """
       print_debt_schedule(capex::Float64, fin::FinancingStructure)

   Print the debt amortization table.
   """
   function print_debt_schedule(capex::Float64, fin::FinancingStructure)
       sched = compute_debt_schedule(capex, fin)
       debt_amount = capex * fin.debt_pct
       println("="^70)
       println("DEBT AMORTIZATION SCHEDULE")
       println("="^70)
       @printf("  Debt amount:     €%.2f M\n", debt_amount / 1e6)
       @printf("  Interest rate:   %.2f%%\n", fin.debt_interest * 100)
       @printf("  Tenor:           %d years\n", fin.debt_tenor_years)
       @printf("  Annual payment:  €%.2f M\n", sched[1].payment / 1e6)
       println("-"^70)
       @printf("%-6s | %12s | %12s | %12s | %12s\n",
           "Year", "Payment", "Interest", "Principal", "Balance")
       println("-"^70)
       for row in sched
           @printf("%-6d | %12.2f | %12.2f | %12.2f | %12.2f\n",
               row.year,
               row.payment / 1e6,
               row.interest / 1e6,
               row.principal / 1e6,
               row.balance / 1e6)
       end
       println("="^70)
   end
   ```

5. **Add exports** — on the existing export lines:

   - Line 567 (`export FinancingStructure`): add `validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` to this line (the financing-related exports), or start a new export line after it. Simplest: append them to the line:

     ```
     export FinancingStructure, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
     ```

   Actually, looking at the style, line 567 exports only the struct `FinancingStructure`, and line 571 exports the functions `default_financing, compute_debt_service`. Per the task "Export the four names on the existing export lines", add them to the function export line 571:

     ```
     export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
     ```

   Or split to a new line. The cleanest approach matching the existing pattern (structs on one line, functions on another) is to extend line 571. But line 571 is `export default_financing, compute_debt_service`. Adding four names makes it long. Either way is fine per the task. Add them to line 571.

### 4. Targeted tests and acceptance criterion

**Test file replayed by gate**: `test/industrial/runtests.jl` (which includes `test_capex_model.jl`)

The existing tests in `test_capex_model.jl` verify exports (lines 3–19), `FinancingStructure` construction (lines 162–173), and `compute_debt_service` (lines 175–197). After the coder adds exports for the four new names, the existing "exports and types" testset on lines 3–19 will need those four names added (but the coder may not touch tests — the plan must be honest about this).

**Acceptance criterion**: The gate replays `test/industrial/runtests.jl` and returns verdict **PASS** (green). Additionally, the coder must perform a self-check (inline, not in a test file) verifying the invariants of `compute_debt_schedule`:
- Final balance is zero within 1e-6: `abs(last(schedule).balance) < 1e-6`
- Sum of principal equals debt amount: `sum(row.principal for row in schedule) ≈ capex * fin.debt_pct`
- Schedule length equals `debt_tenor_years`
- Years are 1..n in order
- For zero interest: each principal entry equals `debt_amount / n` (straight-line)

The existing tests on `FinancingStructure` already check `equity_pct + debt_pct + grant_pct ≈ 1.0` (line 172), and the zero-interest debt service test (lines 190–197) already validates the annuity formula. The new functions re-use the same annuity formula, so gate green on the existing suite plus the coder's self-check is sufficient.

### 5. Risks and what NOT to touch

- **Do NOT modify** `FinancingStructure` definition (lines 403–410), `default_financing` (lines 417–426), or `compute_debt_service` (lines 433–446).
- **Do NOT modify** any test file. The existing `test_capex_model.jl` "exports and types" testset lists every exported name individually — the four new names will NOT appear there unless a test is edited, which this plan forbids. The gate still compiles and runs because those four names being exported doesn't break existing tests; they just aren't explicitly checked by `@test isdefined`. That is acceptable: the gate passes, and the coder's self-check covers the new functions.
- **Risk**: `NamedTuple` type annotations in the return type may cause compilation issues if not handled carefully. Using the concrete `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int,Float64,Float64,Float64,Float64}}` type parameter avoids this. The coder should verify this compiles.
- **Risk**: The `≈` default tolerance. The spec says "within 1e-6" for the sum check in `validate_financing`. Use `isapprox(..., atol=1e-6)` explicitly rather than relying on the default `≈`.
- **Risk**: Floating-point drift in the schedule — the final balance may not be exactly zero due to accumulation over many years. The annuity formula guarantees it mathematically, but the coder's self-check with `1e-6` tolerance should catch any issue.
