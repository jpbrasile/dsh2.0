Now I have a complete picture. Let me also verify that the `industrial` module isn't in the main module file (it's not — it's a standalone include pattern), and check the existing `print_` functions more closely so I can match the style.

I've now read all the necessary files. Here is my plan.

---

## Plan: Add financing cash-flow helpers to `src/industrial/capex_model.jl`

### (1) Goal

Add four financing helper functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) next to the existing `FinancingStructure` / `compute_debt_service` block and export them, without modifying any existing code.

### (2) Files to touch — each with what changes and why

| File | Change | Why |
|------|--------|-----|
| `src/industrial/capex_model.jl` | Add four new functions between the `compute_debt_service` block (line 446) and the `# Printing Functions` section (line 448), and add the four names to the export lines (570–572). | These are the only source modifications needed. The three `print_*` functions (lines 457–519) show the existing table-printing style to replicate. |
| *No other files modified.* | | |

### (3) Ordered steps for the coder

1. **Read `src/industrial/capex_model.jl`** (done above — the coder should re-read it to have exact line numbers before editing).

2. **Insert `validate_financing`** after line 446 (after `compute_debt_service`'s `end`) and before line 448 (`# Printing Functions`):
   ```julia
   """
       validate_financing(fin::FinancingStructure) -> Bool

   Validate that a FinancingStructure is self-consistent.

   Returns true when:
   - `equity_pct + debt_pct + grant_pct == 1` within 1e-6,
   - every share and rate is non-negative,
   - `debt_tenor_years >= 1`.

   Returns false otherwise (never throws).
   """
   function validate_financing(fin::FinancingStructure)
       # Shares must sum to 1
       if abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) > 1e-6
           return false
       end
       # All non-negative
       if fin.equity_pct < 0 || fin.debt_pct < 0 || fin.grant_pct < 0 ||
          fin.debt_interest < 0 || fin.equity_irr_target < 0
           return false
       end
       # Tenor at least 1 year
       if fin.debt_tenor_years < 1
           return false
       end
       return true
   end
   ```

3. **Insert `compute_debt_schedule`** after `validate_financing`:
   ```julia
   """
       compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

   Compute full amortization schedule for the debt portion of capex.

   Returns one `NamedTuple` per year `1..debt_tenor_years` with fields:
   `(year, payment, interest, principal, balance)`.

   Uses the same annuity formula as `compute_debt_service`. At zero interest,
   principal is straight-line (equal payments). The final balance is zero within
   1e-6, and the sum of principal equals the debt amount.
   """
   function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
       debt_amount = capex * fin.debt_pct
       r = fin.debt_interest
       n = fin.debt_tenor_years

       # Annuity (same as compute_debt_service)
       if r > 0
           annuity = debt_amount * r * (1 + r)^n / ((1 + r)^n - 1)
       else
           annuity = debt_amount / n
       end

       schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance),
                                     Tuple{Int, Float64, Float64, Float64, Float64}}}(undef, n)
       balance = debt_amount

       for year in 1:n
           interest = balance * r
           principal = annuity - interest
           balance -= principal
           if year == n
               # Force final balance to zero (handles floating-point drift)
               principal += balance
               balance = 0.0
           end
           schedule[year] = (year=year, payment=annuity, interest=interest,
                             principal=principal, balance=balance)
       end

       return schedule
   end
   ```

4. **Insert `total_interest_paid`** after `compute_debt_schedule`:
   ```julia
   """
       total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64

   Sum of the interest column of the debt schedule.
   """
   function total_interest_paid(capex::Float64, fin::FinancingStructure)
       schedule = compute_debt_schedule(capex, fin)
       return sum(row.interest for row in schedule)
   end
   ```

5. **Insert `print_debt_schedule`** after `total_interest_paid`:
   ```julia
   """
       print_debt_schedule(capex::Float64, fin::FinancingStructure)

   Print a formatted amortization table.
   """
   function print_debt_schedule(capex::Float64, fin::FinancingStructure)
       schedule = compute_debt_schedule(capex, fin)
       debt_amount = capex * fin.debt_pct
       println("="^60)
       println("DEBT AMORTIZATION SCHEDULE")
       println("="^60)
       @printf("  Debt amount:   €%.2f M\n", debt_amount / 1e6)
       @printf("  Interest rate: %.2f %%\n", fin.debt_interest * 100)
       @printf("  Tenor:         %d years\n", fin.debt_tenor_years)
       println("-"^60)
       @printf("%4s | %12s | %12s | %12s | %12s\n",
               "Year", "Payment", "Interest", "Principal", "Balance")
       println("-"^60)
       for row in schedule
           @printf("%4d | €%11.1fk | €%11.1fk | €%11.1fk | €%11.1fk\n",
                   row.year,
                   row.payment / 1000,
                   row.interest / 1000,
                   row.principal / 1000,
                   row.balance / 1000)
       end
       println("-"^60)
       @printf("%4s | €%11.1fk | €%11.1fk | €%11.1fk | %12s\n",
               "SUM",
               sum(row.payment for row in schedule) / 1000,
               total_interest_paid(capex, fin) / 1000,
               sum(row.principal for row in schedule) / 1000,
               "-")
       println("="^60)
   end
   ```

6. **Add the four names to the export lines.** There are three export statements at lines 566–573; the four new names fit naturally as:
   - Line 571: append `validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` to the existing `export default_financing, compute_debt_service` line.

   Concretely, change line 571 from:
   ```julia
   export default_financing, compute_debt_service
   ```
   to:
   ```julia
   export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
   ```

   The other two export lines (567 and 568–569) are unrelated and left untouched.

### (4) Targeted tests the gate must replay and acceptance criterion

**Test file to replay:** `test/industrial/runtests.jl` — this includes `test_capex_model.jl` at line 52, which is the file that exercises every existing `FinancingStructure` and `compute_debt_service` test, plus the `@testset "exports and types"` block that checks all symbols are defined (so the new exports will be picked up by the existing `isdefined` checks... wait — the existing test at lines 5–19 only checks the OLD names. The new names won't be checked by existing `isdefined` tests, but that's fine — the coder is instructed not to modify tests. The invariants from item 2 in the task are self-checked by the coder via `julia_gate`).

**Acceptance criterion:** The gate replays `test/industrial/runtests.jl` and the verdict is **PASS** (all 912 existing industrial tests pass — the new code does not break any existing test). Additionally, the coder runs self-checks through `julia_gate` that verify:
- For a valid `FinancingStructure`, the schedule's final `.balance` is zero within 1e-6.
- The sum of `.principal` over the schedule equals `capex * debt_pct` within 1e-6.
- `validate_financing` returns `true` for a valid struct, `false` for a struct with shares summing to ≠1, a negative share, and `debt_tenor_years = 0`.
- `total_interest_paid` equals `sum(s.interest for s in schedule)`.

### (5) Risks and what NOT to touch

- **Do NOT modify** the existing `compute_debt_service` function (lines 433–446) — it is the reference annuity formula that `compute_debt_schedule` must replicate.
- **Do NOT modify** the `FinancingStructure` struct (lines 403–410) or `default_financing` (lines 417–426).
- **Do NOT modify** the test file `test/industrial/test_capex_model.jl`.
- **Do NOT modify** any other file in the repository.
- **Risk:** The existing test file at line 5–19 checks exports with `isdefined(@__MODULE__, :Name)`. Since the four new names aren't in that list, they won't be checked — but this is by design (the coder may not create or edit tests). The self-checks via `julia_gate` cover correctness.
- **Risk:** The `compute_debt_schedule` uses a concrete `NamedTuple` type parameter for the vector. This is necessary for type-stable Julia code. The existing codebase uses `Vector{NamedTuple}` in docstrings but concrete types in practice — the coder should verify the type parameter works.
- **Style note:** The existing code uses `=` for section separators (e.g., line 458: `println("="^50)`). The `print_debt_schedule` follows the same convention with `"="^60`.
