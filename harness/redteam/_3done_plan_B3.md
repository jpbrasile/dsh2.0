No module-level file — the source files are included directly from runtests. Now I have the full picture. Let me also check what `print_debt_schedule` should output, by reviewing the existing `print_phase_capex` and `print_phased_capex_summary` styles more carefully for the formatting conventions used.

I now have everything I need. Here is the plan:

---

## Plan: Financing cash-flow helpers in `src/industrial/capex_model.jl`

### 1. Goal

Add four new exported functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) adjacent to the existing `FinancingStructure` and `compute_debt_service` in `capex_model.jl`, without modifying any test files.

### 2. Files to touch

| File | Change | Why |
|---|---|---|
| **`src/industrial/capex_model.jl`** | Add four new function implementations and extend the export lines | This is the only file that changes: it already contains `FinancingStructure` (line 403), `compute_debt_service` (line 433), and the export block (lines 566–573). The new functions go after `compute_debt_service` and before the `Printing Functions` block. |

**No other files change.** The test file (`test/industrial/test_capex_model.jl`) is NOT edited — the coder may not touch it.

### 3. Ordered steps for the coder

**Step 1 – Add `validate_financing` right after `compute_debt_service` (after line 446, before the `# Printing Functions` comment at line 448)**

```julia
"""
    validate_financing(fin::FinancingStructure) -> Bool

Validate that the financing structure is internally consistent.

Returns `true` when:
- `equity_pct + debt_pct + grant_pct == 1` within 1e-6,
- every share and rate is non-negative,
- `debt_tenor_years >= 1`.

Returns `false` otherwise (no exception thrown).
"""
function validate_financing(fin::FinancingStructure)::Bool
    # Sum of shares must be 1.0 within tolerance
    if !(abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) < 1e-6)
        return false
    end
    # All shares and rates must be non-negative
    if fin.equity_pct < 0 || fin.debt_pct < 0 || fin.grant_pct < 0 ||
       fin.debt_interest < 0 || fin.equity_irr_target < 0
        return false
    end
    # Tenor must be at least 1
    if fin.debt_tenor_years < 1
        return false
    end
    return true
end
```

**Step 2 – Add `compute_debt_schedule` immediately after `validate_financing`**

```julia
"""
    compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}

Compute full amortization schedule for debt-financed CAPEX.

Returns one `NamedTuple` per year (1 .. debt_tenor_years) with fields
`(year, payment, interest, principal, balance)`.  Uses the same annuity
formula as `compute_debt_service`; for zero interest the principal
amortization is straight-line.  The final balance is zero within 1e-6
and the sum of principal payments equals the debt amount.
"""
function compute_debt_schedule(capex::Float64, fin::FinancingStructure)
    debt_amount = capex * fin.debt_pct
    r = fin.debt_interest
    n = fin.debt_tenor_years

    # Annual payment (same annuity as compute_debt_service)
    if r > 0
        payment = debt_amount * r * (1 + r)^n / ((1 + r)^n - 1)
    else
        payment = debt_amount / n
    end

    schedule = Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance),Tuple{Int,Float64,Float64,Float64,Float64}}}(undef, n)
    balance = debt_amount

    for y in 1:n
        interest = balance * r
        principal = payment - interest
        # Guard against floating-point drift on final payment
        if y == n
            principal = balance
        end
        balance = balance - principal
        # Clamp tiny negative balance to zero
        if abs(balance) < 1e-12
            balance = 0.0
        end
        schedule[y] = (year=y, payment=payment, interest=interest, principal=principal, balance=balance)
    end

    return schedule
end
```

**Step 3 – Add `total_interest_paid` immediately after `compute_debt_schedule`**

```julia
"""
    total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64

Sum of the interest column of the debt amortization schedule.
"""
function total_interest_paid(capex::Float64, fin::FinancingStructure)
    schedule = compute_debt_schedule(capex, fin)
    return sum(row.interest for row in schedule)
end
```

**Step 4 – Add `print_debt_schedule` immediately after `total_interest_paid`**, using the same `@printf`/separator style as `print_phase_capex` (lines 457–471) and `print_phased_capex_summary` (lines 478–520):

```julia
"""
    print_debt_schedule(capex::Float64, fin::FinancingStructure)

Print a formatted debt amortization table.
"""
function print_debt_schedule(capex::Float64, fin::FinancingStructure)
    schedule = compute_debt_schedule(capex, fin)
    println("="^65)
    println("DEBT AMORTIZATION SCHEDULE")
    println("="^65)
    @printf("  Debt amount:   €%.2f M\n", capex * fin.debt_pct / 1e6)
    @printf("  Interest rate: %.2f %%\n", fin.debt_interest * 100)
    @printf("  Tenor:         %d years\n", fin.debt_tenor_years)
    println("-"^65)
    @printf("  %4s | %12s | %12s | %12s | %12s\n",
        "Year", "Payment", "Interest", "Principal", "Balance")
    println("-"^65)
    for row in schedule
        @printf("  %4d | %12.2f | %12.2f | %12.2f | %12.2f\n",
            row.year, row.payment, row.interest, row.principal, row.balance)
    end
    println("-"^65)
    total_interest = sum(row.interest for row in schedule)
    @printf("  Total interest: €%.2f\n", total_interest)
    println("="^65)
end
```

**Step 5 – Extend the export lines (lines 567 and 571)**

- On line 567, change `export FinancingStructure` to `export FinancingStructure, validate_financing`
- On line 571, change `export default_financing, compute_debt_service` to `export default_financing, compute_debt_service, compute_debt_schedule, total_interest_paid, print_debt_schedule`

### 4. Targeted tests and acceptance criterion

**Existing test file replayed by the gate:** `test/industrial/runtests.jl` (which includes `test/industrial/test_capex_model.jl` at line 52).

**Existing tests that the gate will execute** (from `test_capex_model.jl`):
- `exports and types` (line 3): checks `FinancingStructure` exists, checks `compute_debt_service` exists. After the coder's change, the four new names are not in this test's `isdefined` list — this is fine; the test passes because it only checks for presence, not absence, of specific names.
- `FinancingStructure` (line 162): validates the default struct's fields and that `equity_pct + debt_pct + grant_pct ≈ 1.0`.
- `compute_debt_service` (line 175): validates annuity > 0, total payments > debt, total payments < 2.5× debt.
- `compute_debt_service zero interest` (line 190): validates straight-line at zero rate.

**Acceptance criterion:** The gate (via `julia_gate` on `test/industrial/runtests.jl`) returns verdict **VERT** (green). This means every existing test in `test_capex_model.jl` passes with the new code additions.

**Self-check of invariants in (2) — to be verified by reading the code, not by a test file:** After writing the functions, the coder should visually/mentally check:
- `compute_debt_schedule` returns `n = debt_tenor_years` entries.
- The `balance` field of the last entry is zero within 1e-6 (enforced by the `y == n` branch assigning `principal = balance` directly).
- `sum(row.principal for row in schedule) ≈ capex * fin.debt_pct` within 1e-6.
- The annuity used matches `compute_debt_service(capex, fin)` for the same inputs.
- Zero-interest path yields `payment = debt_amount / n` and `interest = 0` each year.

### 5. Risks and what NOT to touch

- **Do NOT create or edit any test file.** The task explicitly forbids it.
- **Do NOT touch the `FinancingStructure` struct** (line 403–410) — it already has the fields needed. No new fields required.
- **Do NOT touch `default_financing()`** (line 417–426) — unchanged.
- **Do NOT touch `compute_debt_service`** (line 433–446) — the new `compute_debt_schedule` replicates the same annuity formula independently but does not refactor the existing function.
- **Risk: `NamedTuple` type instability.** The schedule returns a concretely-typed `Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance),Tuple{Int,Float64,Float64,Float64,Float64}}}`. This is verbose but ensures type-stable code and lets the existing tests run without recompilation issues. If the coder finds this too verbose, a simpler `Vector{@NamedTuple{year::Int, payment::Float64, interest::Float64, principal::Float64, balance::Float64}}` is acceptable but requires `using NamedTuples` or Julia ≥1.7 — safer to use the fully-spelled `NamedTuple` type.
- **Risk: the export lines test.** The existing `exports and types` testset at line 3 checks only the 18 names currently listed. The four new names will be exported but not listed in the test — this is normal; the test checks for presence of specific symbols, not completeness of exports.
- **Risk: `print_debt_schedule` uses `Printf.@printf`** which is already in scope via `using Printf` at line 18 — no new imports needed.
