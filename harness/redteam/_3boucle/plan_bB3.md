No pre-existing usage of these names anywhere. Now I have everything I need to write the plan.

---

## Plan

### (1) Goal

Add four financing cash-flow helper functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to `src/industrial/capex_model.jl`, inserted after `compute_debt_service` (line 446) and before the "Printing Functions" block (line 448), and export all four on the existing export lines — without touching any test files.

### (2) Files to touch

**`src/industrial/capex_model.jl`** — the only file modified; two insertion sites:

- **After line 446** (after the `end` of `compute_debt_service`, before the `# Printing Functions` separator): insert the four new functions plus a `# Financing Cash-Flow Helpers` section header.
- **Lines 566–573** (the export block): add the four names to the existing `export` lists. Specifically:
  - A new `export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` line (separate from existing lines, following the established style of one semantic group per export line).

### (3) Ordered steps for the coder

1. **Read `src/industrial/capex_model.jl`** to confirm current line numbers (they may have shifted; the file is currently 573 lines).

2. **Insert new block after `compute_debt_service`'s closing `end` (currently line 446).** The block to insert (between the existing `# Printing Functions` divider and the end of `compute_debt_service`):

```julia
# ============================================================================
# Financing Cash-Flow Helpers
# ============================================================================

"""
    validate_financing(fin::FinancingStructure) -> Bool

Validate financing structure: equity + debt + grant == 1.0 within 1e-6,
every share and rate non-negative, and debt_tenor_years >= 1.
Returns `false` (never throws) on invalid input.
"""
function validate_financing(fin::FinancingStructure)
    # Sum-to-one check
    if abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) > 1e-6
        return false
    end
    # Non-negative shares and rate
    if fin.equity_pct < 0 || fin.debt_pct < 0 || fin.grant_pct < 0 ||
       fin.debt_interest < 0 || fin.equity_irr_target < 0
        return false
    end
    # Valid tenor
    if fin.debt_tenor_years < 1
        return false
    end
    return true
end

"""
    compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

Compute year-by-year amortization schedule. Returns one NamedTuple per year 1..debt_tenor_years
with fields `(year::Int, payment::Float64, interest::Float64, principal::Float64, balance::Float64)`.

Uses the same annuity formula as `compute_debt_service`. Zero interest produces
straight-line principal. Final balance is zero within 1e-6 and the sum of principal
equals the debt amount.
"""
function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
    debt_amount = capex * fin.debt_pct
    r = fin.debt_interest
    n = fin.debt_tenor_years

    # Annuity (same formula as compute_debt_service)
    if r > 0
        annuity = debt_amount * r * (1 + r)^n / ((1 + r)^n - 1)
    else
        annuity = debt_amount / n
    end

    schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}}(undef, n)
    balance = debt_amount
    for year in 1:n
        interest = balance * r
        principal = annuity - interest
        # Guard against floating drift on final payment
        if principal > balance + 1e-12
            principal = balance
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
    return sum(s.interest for s in schedule)
end

"""
    print_debt_schedule(capex::Float64, fin::FinancingStructure)

Print an amortization table in the style of other print_* functions in this file.
"""
function print_debt_schedule(capex::Float64, fin::FinancingStructure)
    schedule = compute_debt_schedule(capex, fin)
    debt_amount = capex * fin.debt_pct
    println("="^68)
    println("DEBT AMORTIZATION SCHEDULE")
    println("="^68)
    @printf("  Total CAPEX:       €%.2f M\n", capex / 1e6)
    @printf("  Debt amount (%.0f%%):  €%.2f M\n", fin.debt_pct * 100, debt_amount / 1e6)
    @printf("  Interest rate:     %.2f%%\n", fin.debt_interest * 100)
    @printf("  Tenor:             %d years\n", fin.debt_tenor_years)
    println("-"^68)
    @printf("%-6s | %12s | %12s | %12s | %12s\n",
        "Year", "Payment €M", "Interest €M", "Principal €M", "Balance €M")
    println("-"^68)
    for s in schedule
        @printf("%-6d | %12.3f | %12.3f | %12.3f | %12.3f\n",
            s.year, s.payment / 1e6, s.interest / 1e6, s.principal / 1e6, s.balance / 1e6)
    end
    println("-"^68)
    @printf("%-6s | %12.3f | %12.3f | %12.3f | %12s\n",
        "TOTAL", sum(s.payment for s in schedule) / 1e6,
        sum(s.interest for s in schedule) / 1e6,
        sum(s.principal for s in schedule) / 1e6, "-")
    println("="^68)
end
```

3. **Update the export block.** After the existing `export default_financing, compute_debt_service` line (currently line 571), add a new line:

```julia
export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
```

Alternatively, since `validate_financing` and `compute_debt_schedule` are semantically financing-related, they could be placed on the same export line as `default_financing, compute_debt_service` by extending it — but the file convention is one semantic group per `export` line, and these are new names, so a dedicated `export` line is cleaner.

### (4) Targeted tests and acceptance criterion

**Existing test file the gate replays:** `test/industrial/test_capex_model.jl` (included by `test/industrial/runtests.jl` at line 52).

The acceptance criterion is that `julia_gate` on `test/industrial/runtests.jl` yields **VERT**. The existing tests must continue to pass. The existing test at line 18 checks `isdefined(@__MODULE__, :compute_debt_service)` — the four new names will automatically be similarly available (but no new `isdefined` tests are needed since the task says the coder must not create or edit tests).

Additionally, the coder must **self-check** the invariants of `compute_debt_schedule` by reasoning over the code (not by running Julia): (a) final balance is zero to within 1e-6 (the loop subtracts principal each year and the last year's guard `if principal > balance` ensures the last principal payment cleans up the balance), and (b) the sum of the principal column equals the debt amount (each year's principal reduces the balance from the initial debt amount to zero, so by telescoping the sum of principal = debt_amount). The coder should verify these hold by code inspection since they cannot run Julia directly.

### (5) Risks and what NOT to touch

- **Do NOT touch `test/industrial/test_capex_model.jl` or any other test file.** The coder is explicitly forbidden from creating or editing tests.
- **Do NOT modify any existing function**, including `compute_debt_service`, `FinancingStructure`, or any existing export line — only add new lines.
- **The coder must not run `julia` directly** — only through the `julia_gate` tool, which replays the existing test suite.
- **Risk: the `NamedTuple` type annotation** in the `Vector{…}` is verbose and Julia-version-sensitive. The explicit `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}` annotation ensures type stability but is fragile to Julia version changes. The fallback is to drop the type parameter and use `Vector{Any}(undef, n)` or construct via `push!` — the coder should prefer the explicit type, but if the gate raises a parsing error, simplify to constructing the vector with `push!` and an untyped `[]`.
- **Risk: `NamedTuple` field `balance` on final entry may go slightly negative** due to floating-point drift (the balance after the last principal subtraction could be `-1e-16`). The `max(balance, 0.0)` guard handles this. The coder should verify the invariants both with and without this guard.
- **The `print_debt_schedule` function** uses `@printf` from `Printf` which is already imported at line 18 — no new import needed.