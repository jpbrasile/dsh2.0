Good — `FinancingStructure` and `compute_debt_service` are only used within `capex_model.jl` itself. Now I have everything I need to produce the plan.

---

## Plan

### (1) Goal

Add four financing cash-flow helper functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to `src/industrial/capex_model.jl`, placed immediately after the existing `compute_debt_service` (after line 446), and export them alongside the existing export lines.

### (2) Files to touch

**`src/industrial/capex_model.jl`** — the only file to modify:
- **Insert new functions** after line 446 (the `end` of `compute_debt_service`) and before line 448 (`# Printing Functions` section header). The functions reuse the annuity logic from `compute_debt_service` (lines 438–443).
- **Extend exports** on lines 567–573: add `validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` to the appropriate export lines.

### (3) Ordered steps for the coder

#### Step A — Insert `validate_financing` (after line 446)

```julia
"""
    validate_financing(fin::FinancingStructure) -> Bool

Return `true` when the financing structure is valid:
- `equity_pct + debt_pct + grant_pct == 1` within 1e-6
- Every share (`equity_pct`, `debt_pct`, `grant_pct`) is non-negative
- `debt_interest` is non-negative
- `debt_tenor_years >= 1`
Returns `false` otherwise (never throws).
"""
function validate_financing(fin::FinancingStructure)
    shares_sum = fin.equity_pct + fin.debt_pct + fin.grant_pct
    if abs(shares_sum - 1.0) > 1e-6
        return false
    end
    if fin.equity_pct < 0.0 || fin.debt_pct < 0.0 || fin.grant_pct < 0.0
        return false
    end
    if fin.debt_interest < 0.0
        return false
    end
    if fin.debt_tenor_years < 1
        return false
    end
    return true
end
```

#### Step B — Insert `compute_debt_schedule` (after `validate_financing`)

The schedule is a `Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int,Float64,Float64,Float64,Float64}}}`.

Algorithm:
1. `debt_amount = capex * fin.debt_pct`
2. Compute annual annuity `A` using the same formula as `compute_debt_service`:
   - If `r > 0`: `A = debt_amount * r * (1+r)^n / ((1+r)^n - 1)`
   - Else: `A = debt_amount / n`
3. `balance = debt_amount`; for `y = 1:n`:
   - `interest = balance * r`
   - `principal = A - interest`
   - On the final year (`y == n`), set `principal = balance` and `payment = interest + principal` (to force balance to zero despite floating-point drift)
   - `balance -= principal`
   - Push `(year=y, payment=A (or adjusted on final year), interest=interest, principal=principal, balance=balance)`
4. After loop: assert `abs(balance) < 1e-6` and `abs(sum(p.principal for p in schedule) - debt_amount) < 1e-6` (internal invariant checks; use `@assert` so they fire in tests).

The return type annotation `-> Vector{...}` is fine, but Julia will infer the concrete type from the NamedTuple construction.

#### Step C — Insert `total_interest_paid` (after `compute_debt_schedule`)

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

#### Step D — Insert `print_debt_schedule` (after `total_interest_paid`)

Style: follow the patterns in `print_phase_capex` (lines 457–471) and `print_phased_capex_summary` (lines 478–520). Use `=` characters for framing, `@printf` for numbers, with the same EUR M formatting for money columns.

Table columns: Year, Payment, Interest, Principal, Balance. All in EUR M, right-aligned.

Include a summary line: total interest paid. Keep it consistent with the existing print style (no emoji, clean ASCII borders).

#### Step E — Extend exports

- Line 567: add `validate_financing` to the same export line as `FinancingStructure` (it's a related symbol). Current line 566–567:
  ```julia
  export ModularCAPEX, DeploymentPhase, PhaseCAPEX, CumulativeCAPEX
  export FinancingStructure
  ```
  Change line 567 to:
  ```julia
  export FinancingStructure, validate_financing
  ```

- Line 571: current reads `export default_financing, compute_debt_service`. Change to:
  ```julia
  export default_financing, compute_debt_service, compute_debt_schedule, total_interest_paid
  ```

- Add a new export line after line 573 (`export demo_capex_model`):
  ```julia
  export print_debt_schedule
  ```
  (keeping `print_*` functions grouped separately as they are now — `print_phase_capex` and `print_phased_capex_summary` are on line 572).

### (4) Targeted tests and acceptance criterion

**Test file:** `test/industrial/test_capex_model.jl` — this is the existing test file included by `test/industrial/runtests.jl` on line 52. The coder must NOT edit this file. The gate replays it as-is.

**Acceptance criterion:** The coder runs the gate via its `julia_gate` tool on `test/industrial/runtests.jl` (which includes `test_capex_model.jl`), and the verdict must be **VERT** (all existing tests pass — no regressions). Additionally, the coder runs a self-check (a small inline `@testset` block executed within the gate run or as a one-shot `julia_gate` invocation) that verifies the two internal invariants of `compute_debt_schedule`:

1. Final balance is zero within `1e-6`
2. Sum of principal equals debt amount within `1e-6`

These invariant checks can be exercised by calling `compute_debt_schedule` with the existing `default_financing()` and a representative `capex`, then asserting the invariants hold. Since the test file won't be edited, the coder should run these as an ad-hoc validation (either via the gate tool or by noting them in the gate's self-check output).

Existing tests that must still pass (from `test_capex_model.jl`):
- `exports and types` (lines 3–19) — verifies `FinancingStructure`, `default_financing`, `compute_debt_service` are exported
- `FinancingStructure` (lines 162–173) — verifies field values and share sum
- `compute_debt_service` (lines 175–188) — verifies positive annuity, total payments > debt
- `compute_debt_service zero interest` (lines 190–197) — verifies straight-line at zero interest

**Note:** The existing `exports and types` testset checks `isdefined` on specific names but does NOT list the four new function names — this is expected since tests aren't being edited. The gate still passes because the new names simply aren't tested for `isdefined` (they won't cause failures).

### (5) Risks and what NOT to touch

- **Do NOT edit** `test/industrial/test_capex_model.jl` or any other test file.
- **Do NOT edit** `test/industrial/runtests.jl`.
- **Do NOT modify** the existing `compute_debt_service` function (lines 433–446) — the new functions call it internally? No, the new functions replicate the annuity formula inline rather than calling `compute_debt_service`. This is deliberate: `compute_debt_schedule` needs the annuity value AND the per-year breakdown, and calling `compute_debt_service` would require recomputing the same formula. The duplication is minimal (3 lines) and keeps each function self-contained.
- **Risk: floating-point drift on final principal.** The task requires final balance = 0 within 1e-6. With standard annuity amortization, the final balance may have a small floating-point residual. The plan handles this: on the last year (`y == n`), set `principal = balance` explicitly rather than `A - interest`, so the final balance is pinned to exactly zero.
- **Risk: the `@assert` statements inside `compute_debt_schedule`** could fail in production if `-O0` is not used. In Julia, `@assert` is removed under `-O1`/`-O2`. This is acceptable — they are development-time invariant checks; the function logic ensures correctness regardless.
- **Do NOT touch** any other file in `src/industrial/` or elsewhere.