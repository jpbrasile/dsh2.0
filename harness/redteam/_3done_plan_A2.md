Good. I now have a complete understanding of the file structure. Let me verify one thing: whether `NamedTuple` is used, since we need `Vector{NamedTuple}` — the function must define fields inline. I also note the print style uses `"="*` separators and `@printf` formatting, with explicit `println` returns at end-of-function.

Here is the plan:

---

## Plan: Add four financing cash-flow helpers to `capex_model.jl`

### 1. Goal

Add `validate_financing`, `compute_debt_schedule`, `total_interest_paid`, and `print_debt_schedule` next to the existing `FinancingStructure`/`compute_debt_service` block, and export them, so the module provides a complete amortization table for project-finance debt.

### 2. Files to touch

| File | What changes | Why |
|------|-------------|-----|
| `src/industrial/capex_model.jl` | Insert four new functions after `compute_debt_service` (line 446), before the `# ============================================================================ # Printing Functions` block. Add four names to the export block (lines 566–573). | This is the only source file. The new helpers extend the financing section and use the same `FinancingStructure`/`compute_debt_service` infrastructure. |

### 3. Ordered steps for the coder

**Step 1 — Insert four functions** between line 446 (`end` of `compute_debt_service`) and line 448 (`# ============================================================================ # Printing Functions`):

Add this block (exact text to paste):

```julia
"""
    validate_financing(fin::FinancingStructure) -> Bool

Validate that the financing structure is internally consistent.

Returns `true` when:
- `equity_pct + debt_pct + grant_pct ≈ 1.0` (within `1e-6`)
- All shares and rates are non-negative
- `debt_tenor_years >= 1`

Returns `false` otherwise (never throws).
"""
function validate_financing(fin::FinancingStructure)
    shares_sum = fin.equity_pct + fin.debt_pct + fin.grant_pct
    if !(abs(shares_sum - 1.0) < 1e-6)
        return false
    end
    if fin.equity_pct < 0 || fin.debt_pct < 0 || fin.grant_pct < 0
        return false
    end
    if fin.debt_interest < 0
        return false
    end
    if fin.equity_irr_target < 0
        return false
    end
    if fin.debt_tenor_years < 1
        return false
    end
    return true
end

"""
    compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

Compute year-by-year debt amortization schedule.

Returns one `NamedTuple` per year `1..debt_tenor_years` with fields:
- `year::Int`
- `payment::Float64`
- `interest::Float64`
- `principal::Float64`
- `balance::Float64`

The schedule uses the same annuity payment as `compute_debt_service`.
At zero interest rate, principal is straight-line.
The final balance is zero within `1e-6` and the sum of principal equals the debt amount.
"""
function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
    debt = capex * fin.debt_pct
    r = fin.debt_interest
    n = fin.debt_tenor_years

    # Annuity payment (same formula as compute_debt_service)
    if r > 0
        annuity = debt * r * (1 + r)^n / ((1 + r)^n - 1)
    else
        annuity = debt / n
    end

    schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance),
                                  Tuple{Int, Float64, Float64, Float64, Float64}}}(undef, n)

    balance = debt
    for y in 1:n
        interest = balance * r
        principal = annuity - interest
        # Guard against floating-point drift in the last year
        if y == n
            principal = balance
        end
        new_balance = balance - principal
        schedule[y] = (year=y, payment=annuity, interest=interest,
                        principal=principal, balance=new_balance)
        balance = new_balance
    end

    return schedule
end

"""
    total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64

Total interest paid over the life of the debt (sum of the interest column).
"""
function total_interest_paid(capex::Float64, fin::FinancingStructure)
    schedule = compute_debt_schedule(capex, fin)
    return sum(entry.interest for entry in schedule)
end

"""
    print_debt_schedule(capex::Float64, fin::FinancingStructure)

Print the debt amortization schedule as a formatted table.
"""
function print_debt_schedule(capex::Float64, fin::FinancingStructure)
    schedule = compute_debt_schedule(capex, fin)
    debt = capex * fin.debt_pct

    println("="^80)
    println("DEBT AMORTIZATION SCHEDULE")
    println("="^80)
    @printf("  Debt amount:   €%.2f M\n", debt / 1e6)
    @printf("  Interest rate: %.2f %%\n", fin.debt_interest * 100)
    @printf("  Tenor:         %d years\n", fin.debt_tenor_years)
    @printf("  Annuity:       €%.2f k/year\n", compute_debt_service(capex, fin) / 1000)
    println("-"^80)
    @printf("%6s | %12s | %12s | %12s | %12s\n",
        "Year", "Payment k€", "Interest k€", "Principal k€", "Balance k€")
    println("-"^80)

    for entry in schedule
        @printf("%6d | %12.1f | %12.1f | %12.1f | %12.1f\n",
            entry.year,
            entry.payment / 1000,
            entry.interest / 1000,
            entry.principal / 1000,
            entry.balance / 1000)
    end

    println("-"^80)
    total_int = total_interest_paid(capex, fin)
    @printf("  Total interest: €%.2f k\n", total_int / 1000)
    println("="^80)
end
```

**Step 2 — Add four names to export block** (lines 566–573).

Current exports (lines 566–573):
```julia
export ModularCAPEX, DeploymentPhase, PhaseCAPEX, CumulativeCAPEX
export FinancingStructure
export default_capex_model, optimistic_capex_model, conservative_capex_model
export default_deployment_phases
export compute_phase_capex, compute_phased_capex, compute_cumulative_capex
export default_financing, compute_debt_service
export print_phase_capex, print_phased_capex_summary
export demo_capex_model
```

Change line 571 from:
```julia
export default_financing, compute_debt_service
```
to:
```julia
export default_financing, compute_debt_service, compute_debt_schedule, total_interest_paid, print_debt_schedule
```

And add a new line after line 572:
```julia
export validate_financing
```

So that lines 570–573 become:
```julia
export compute_phase_capex, compute_phased_capex, compute_cumulative_capex
export default_financing, compute_debt_service, compute_debt_schedule, total_interest_paid, print_debt_schedule
export print_phase_capex, print_phased_capex_summary
export validate_financing
```

**Step 3 — Verify tests pass.** After editing, the coder uses `julia_gate` on `test/industrial/runtests.jl`. No new tests are created.

### 4. Targeted tests and acceptance criterion

**Test file to replay:** `test/industrial/runtests.jl` (which includes `test_capex_model.jl`).

**Acceptance criterion:** Gate verdict `PASS` on the existing `industrial` module tests. The coder must also verify a self-check (not written into a test file) that for a well-formed `FinancingStructure` by `default_financing()` and some `capex` value:

- `validate_financing(fin)` returns `true`
- The schedule has `fin.debt_tenor_years` entries
- `schedule[end].balance` is zero within `1e-6`
- `sum(e.principal for e in schedule) ≈ capex * fin.debt_pct` within `1e-6`
- `total_interest_paid(capex, fin)` equals `sum(e.interest for e in schedule)`
- For a zero-interest `FinancingStructure(0.30, 0.40, 0.30, 0.0, 15, 0.12)`, all `e.principal` values are equal (straight-line)
- `print_debt_schedule` runs without error (catch stdout)

### 5. Risks and what NOT to touch

- **Do NOT modify** `FinancingStructure`, `compute_debt_service`, or any existing function.
- **Do NOT modify** `test_capex_model.jl` or any test file.
- **Risk:** The `NamedTuple` with typed fields `NamedTuple{(:year, ...), Tuple{Int, Float64, ...}}` must compile — this is standard Julia and the existing codebase uses `NamedTuple` patterns (`docs/modules/` references confirm). If Julia 1.12 has any issue with the explicit type parameter, the fallback is `NamedTuple` without the type annotation (just `(year=y, ...)` entries), but the explicit one is preferred for dispatch stability.
- **Risk:** The last-year principal adjustment (`principal = balance` when `y == n`) is intentional to zero out floating-point drift; this does not invalidate the annuity formula.
- **Existing test at line 17** checks `isdefined(@__MODULE__, :compute_debt_service)` — the coder does not need to add entries for the new exports, since the task explicitly forbids editing tests. The gate still passes because tests only check current exports.