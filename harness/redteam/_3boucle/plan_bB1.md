Now I have a clear picture. Let me verify the existing `print_*` style by looking at a couple more examples to ensure consistency:

The task asks me to look at the style of `print_phase_capex` (lines 457-471) and `print_phased_capex_summary` (lines 478-520) — I already have those. The style uses `@printf`, separator lines with `"="^N`, and headers. Now let me verify the current export lines to know exactly where to add the four new names.

Now I have everything I need. Here's the plan:

---

## Plan: Add financing cash-flow helpers to `capex_model.jl`

### Goal
Add four functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) next to `FinancingStructure` / `compute_debt_service`, plus export them, with acceptance verified by re-running the existing test file through the gate.

### Files to touch

| File | Change |
|------|--------|
| `src/industrial/capex_model.jl` | Insert four new functions (between the `compute_debt_service` block, ending line 446, and the `# Printing Functions` block starting line 448). Extend the export list (lines 566-573) with the four new names. |
| `test/industrial/test_capex_model.jl` | **NO CHANGE** — the planner must not create or edit test files per the task constraint. The coder cannot either. Existing tests are the acceptance surface. |

### The four functions (implementation details)

**1. `validate_financing(fin::FinancingStructure) -> Bool`** (insert after line 446)
- Return `true` iff all hold; `false` otherwise (no `throw`).
- Checks:
  - `fin.equity_pct + fin.debt_pct + fin.grant_pct ≈ 1.0` within `1e-6` absolute tolerance
  - Every individual share (`equity_pct`, `debt_pct`, `grant_pct`) `>= 0`
  - `fin.debt_interest >= 0`
  - `fin.equity_irr_target >= 0`
  - `fin.debt_tenor_years >= 1`

**2. `compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}`** (insert after validate)
- `debt_amount = capex * fin.debt_pct`
- `r = fin.debt_interest`, `n = fin.debt_tenor_years`
- Compute the annuity payment `A` using the same formula as `compute_debt_service` (lines 439-443): `r > 0 ? debt_amount * r * (1+r)^n / ((1+r)^n - 1) : debt_amount / n`
- For year `t` in `1:n`:
  - If `r > 0`: `interest = balance * r`, `principal = A - interest`, `payment = A`
  - If `r == 0`: `interest = 0.0`, `principal = debt_amount / n`, `payment = principal`
  - `balance = previous_balance - principal`
- Return a `Vector{NamedTuple}` with entries `(year::Int, payment::Float64, interest::Float64, principal::Float64, balance::Float64)`
- Invariants: final balance ≈ 0 (within 1e-6), sum of principal ≈ debt_amount (within 1e-6)

**3. `total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64`** (insert after schedule)
- Calls `compute_debt_schedule`, sums the `interest` field.

**4. `print_debt_schedule(capex::Float64, fin::FinancingStructure)`** (insert after total_interest)
- Style: mirror `print_phase_capex` (lines 457-471): a header line with `"="^N`, column headers, then `@printf` rows for each schedule entry, a separator line, and a total line.
- Columns: Year, Payment, Interest, Principal, Balance (all in EUR, formatted to two decimals).
- Print the total interest paid at the bottom.

**Export lines** (lines 566-573): Add `validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` to the appropriate export statement. The most natural place is the last `export` line (line 571) which currently exports `default_financing, compute_debt_service` — extend it or add a new line:
- Extend line 571: `export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`

### Ordered steps for the coder

1. **Read** `src/industrial/capex_model.jl` (already provided, but re-read to verify current state before editing).
2. **Insert** the four new functions between line 446 (end of `compute_debt_service`) and line 448 (start of `# ===== Printing Functions =====`). Keep the `# ===== Printing Functions =====` block header untouched.
3. **Edit** the export line at line 571 to append the four new names: change `export default_financing, compute_debt_service` to `export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`.
4. **Self-check invariants** (static verification — the coder has no Julia execution beyond the gate):
   - The `compute_debt_schedule` amortization loop must produce final `balance ≈ 0` when `sum(principal) == debt_amount`.
   - For zero interest, each principal payment must equal `debt_amount / n`.
   - For positive interest, the annuity formula must match `compute_debt_service` exactly.
5. **Run the gate** on `test/industrial/runtests.jl` (which includes `test_capex_model.jl`). The gate recompiles from source, so the new exports are checked by the existing `@test isdefined` testset.

### Targeted test files for gate replay

- **`test/industrial/runtests.jl`** — this includes `test/industrial/test_capex_model.jl` at line 52.

### Acceptance criterion

- Gate verdict **VERT** (green) on `test/industrial/runtests.jl`.
- The existing `test_capex_model.jl` export-check block (lines 3-19) will implicitly verify the four new names are exported (though the existing `@test isdefined` list at lines 9-18 does *not* list them — it only checks existing names). The gate will still pass because all existing tests pass, and the new code has no syntax or import errors.

**Note on test coverage**: The task explicitly says the coder may NOT create or edit tests. The existing test file `test_capex_model.jl` has no tests for the new functions. The gate will pass based on the existing tests remaining green. The invariants in point 2 (final balance ≈ 0, sum of principal = debt amount) are to be self-checked by the coder statically, not via `@test` blocks.

### Risks and what NOT to touch

- **Do NOT** create or modify any test file. The task forbids it.
- **Do NOT** modify `FinancingStructure`, `compute_debt_service`, `default_financing`, or any existing function. Add only new code.
- **Do NOT** touch the existing export lines except to append the four new names.
- **Do NOT** change the `print_phase_capex` or `print_phased_capex_summary` functions.
- **Risk**: The `compute_debt_schedule` annuity formula must be character-for-character identical to `compute_debt_service` lines 439-443. Any divergence produces an inconsistent schedule.
- **Risk**: The `NamedTuple` fields must all be `Float64` except `year` which is `Int`. Julia's `@printf` in `print_debt_schedule` needs matching format strings.
- **Risk**: `NamedTuple` construction syntax: use `(year=y, payment=p, interest=i, principal=pr, balance=b)` inside the loop.