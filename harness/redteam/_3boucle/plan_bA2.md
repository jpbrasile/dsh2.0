Good — no prior art. Now I have everything I need.

---

## Plan: Add Financing Cash-Flow Helpers to `src/industrial/capex_model.jl`

### 1. Goal
Add four new functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) next to `FinancingStructure` / `compute_debt_service` in the financing section, and wire them onto the existing export lines — all without breaking the existing 912 industrial tests.

### 2. Files to touch

**`src/industrial/capex_model.jl`** — the only file. Two insertion zones and one addendum:

| Zone | What changes | Why |
|---|---|---|
| After line 446 (`return annuity` of `compute_debt_service`), before the `# Printing Functions` banner | Insert `validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule` bodies and docstrings (55–65 lines). | Task 1–4: define the four helpers right next to the existing `FinancingStructure` block, reusing the same annuity formula. |
| Lines 571–572 (the `default_financing, compute_debt_service` export) | Append `, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`. | Task 5: export the four names. |

### 3. Ordered steps for the coder

1. **Read `src/industrial/capex_model.jl`** to get the exact byte content (the planner already has it; the coder must re-read before editing).

2. **After line 446** (`return annuity` — the last line of `compute_debt_service`), insert a blank line and then the following block:

   ```julia
   """
       validate_financing(fin::FinancingStructure) -> Bool

   Return `true` when `equity_pct + debt_pct + grant_pct == 1` within `1e-6`,
   every share and rate is non-negative, and `debt_tenor_years >= 1`.
   Returns `false` otherwise (no exception).
   """
   function validate_financing(fin::FinancingStructure)
       # Shares sum to 1
       abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) > 1e-6 && return false
       # Non-negative shares
       fin.equity_pct < 0.0 && return false
       fin.debt_pct < 0.0 && return false
       fin.grant_pct < 0.0 && return false
       # Non-negative rates
       fin.debt_interest < 0.0 && return false
       fin.equity_irr_target < 0.0 && return false
       # Tenor
       fin.debt_tenor_years < 1 && return false
       return true
   end

   """
       compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

   Amortisation schedule: one NamedTuple per year 1..debt_tenor_years with fields
   `(year, payment, interest, principal, balance)`. Uses the same annuity as
   `compute_debt_service`. Zero interest → straight-line principal. The final
   balance reaches zero within 1e-6 and the sum of principal equals the debt amount.
   """
   function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
       debt = capex * fin.debt_pct
       r = fin.debt_interest
       n = fin.debt_tenor_years

       if r > 0.0
           annuity = debt * r * (1.0 + r)^n / ((1.0 + r)^n - 1.0)
       else
           annuity = debt / n
       end

       schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance),Tuple{Int,Float64,Float64,Float64,Float64}}}(undef, n)
       balance = debt
       for t in 1:n
           if r > 0.0
               interest = balance * r
           else
               interest = 0.0
           end
           principal = annuity - interest
           if t == n
               # Absorb rounding: force principal to bring balance to exactly zero
               principal = balance
           end
           balance = balance - principal
           schedule[t] = (year = t, payment = annuity, interest = interest, principal = principal, balance = balance)
       end
       return schedule
   end

   """
       total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64

   Sum of the interest column of `compute_debt_schedule`.
   """
   function total_interest_paid(capex::Float64, fin::FinancingStructure)
       sched = compute_debt_schedule(capex, fin)
       return sum(e.interest for e in sched)
   end

   """
       print_debt_schedule(capex::Float64, fin::FinancingStructure)

   Print the amortisation table in the style of the other `print_*` functions.
   """
   function print_debt_schedule(capex::Float64, fin::FinancingStructure)
       sched = compute_debt_schedule(capex, fin)
       println("="^75)
       println("DEBT REPAYMENT SCHEDULE")
       println("="^75)
       @printf("%-6s | %12s | %12s | %12s | %12s\n",
           "Year", "Payment", "Interest", "Principal", "Balance")
       println("-"^75)
       for e in sched
           @printf("%6d | %12.2f | %12.2f | %12.2f | %12.2f\n",
               e.year, e.payment, e.interest, e.principal, e.balance)
       end
       total_int = sum(e.interest for e in sched)
       println("-"^75)
       @printf("Total interest paid: €%.2f\n", total_int)
       println("="^75)
   end
   ```

3. **Edit the export lines** (lines 571–572). Replace:
   ```
   export default_financing, compute_debt_service
   ```
   with:
   ```
   export default_financing, compute_debt_service
   export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
   ```

   (The four new names land on their own export line for readability, consistent with the existing style that groups related names.)

### 4. Tests and acceptance criterion

**Targeted test file (gate replays):**
- `test/industrial/test_capex_model.jl` (included via `test/industrial/runtests.jl` line 52)

**Acceptance criterion:**
The `industrial` module's gate must return **PASS** (912 tests, already green) when `test/industrial/runtests.jl` is replayed. This means:
- No existing test breaks (the existing `FinancingStructure` and `compute_debt_service` tests continue to pass).
- The four new names are exported and therefore reachable from the test environment, but — critically — the tests do *not* add new `@test` blocks for them. The coder is instructed not to create or edit tests.

**Self-check the coder should perform before calling the gate** (not in tests, but a manual verification run within the gate session or via a quick REPL snippet):

The gate runner likely wraps the test file. The coder can manually verify invariants on `compute_debt_schedule` by running (inside the gate's Julia process, before or alongside test execution) something like:

```julia
# Invariant 1: final balance ≈ 0 within 1e-6
fin = default_financing()
sched = compute_debt_schedule(10_000_000.0, fin)
@assert abs(sched[end].balance) < 1e-6

# Invariant 2: sum(principal) ≈ debt amount
debt_amt = 10_000_000.0 * fin.debt_pct
@assert abs(sum(e.principal for e in sched) - debt_amt) < 1e-6

# Invariant 3: zero-interest → straight-line
fin0 = FinancingStructure(0.3, 0.4, 0.3, 0.0, 10, 0.12)
sched0 = compute_debt_schedule(5_000_000.0, fin0)
@assert all(abs(e.interest) < 1e-12 for e in sched0)
principal_each = 5_000_000.0 * 0.4 / 10
@assert abs(sched0[1].principal - principal_each) < 1e-6

# Invariant 4: validate_financing on default
@assert validate_financing(default_financing()) == true

# Invariant 5: validate_financing catches bad sums
bad = FinancingStructure(0.5, 0.4, 0.3, 0.05, 15, 0.12)
@assert validate_financing(bad) == false
```

These are not test blocks — they are the coder's own sanity check before running the gate.

### 5. Risks and what NOT to touch

- **Do NOT touch** any existing struct definition, function body, or docstring — especially `FinancingStructure`, `compute_debt_service`, `default_financing`, or any of the printing/demo functions.
- **Do NOT touch** `test/industrial/test_capex_model.jl` or `test/industrial/runtests.jl`.
- **Risk**: The use of `NamedTuple{(:year, ...)}` in the schedule return type is concretely typed — this is deliberate and consistent with Julia 1.12's performance expectations. If the exact type parameter syntax causes issues in an older Julia, the coder may simplify to `Vector{NamedTuple}` (the outer return type annotation already says `Vector{NamedTuple}`; the inner concrete type is an implementation detail).
- **Risk**: The `print_debt_schedule` function uses `@printf` and `println` — it must be compatible with the existing `using Printf` at the top of the file (line 18), which is already in scope.
- **Risk**: `FinancingStructure` has `debt_tenor_years::Int` (line 408), so `compute_debt_schedule` must respect that type when iterating `1:n`. The plan uses `Int` arithmetic throughout.
- The `Compute_debt_schedule` interest/principal amortization follows standard level-payment (annuity) math: interest = outstanding balance × rate each period, principal = annuity − interest. For the final period, principal is forced to consume the remaining balance exactly, absorbing any floating-point drift. This matches the task spec that the final balance must be zero within 1e-6 and sum of principals equals debt amount.