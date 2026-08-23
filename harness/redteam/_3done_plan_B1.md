Good. Now I have a complete picture of the file. Let me now check one more thing — the `print_*` function style: they use `println` and `@printf`. The `print_debt_schedule` should follow the same pattern with a table format.

Now I have everything I need to produce the plan. Let me analyze the task carefully:

1. **`validate_financing(fin::FinancingStructure) -> Bool`** — returns false (not an exception) on invalid inputs. Checks: shares sum to 1 within 1e-6, all shares ≥ 0, interest ≥ 0, `debt_tenor_years >= 1`.

2. **`compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}`** — one entry per year 1..debt_tenor_years, fields (year, payment, interest, principal, balance), using the same annuity formula as `compute_debt_service`. Final balance zero within 1e-6, sum of principal equals debt amount. Zero interest → straight-line principal.

3. **`total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64`** — sum of interest column.

4. **`print_debt_schedule(capex::Float64, fin::FinancingStructure)`** — a printed table in the style of the other print functions.

5. Export the four names.

The invariants from (2) are: final balance ≈ 0, sum of principal ≈ debt amount.

Let me think through the annuity schedule computation:

The `compute_debt_service` already computes the constant annual payment `A = P * r * (1+r)^n / ((1+r)^n - 1)`. The schedule is a standard amortization table:
- `payment` = constant annuity (same every year) = `compute_debt_service(capex, fin)`
- `interest_t` = `balance_{t-1} * r`
- `principal_t` = `payment - interest_t`
- `balance_t` = `balance_{t-1} - principal_t`
- `balance_0` = `capex * fin.debt_pct`

For zero interest: `payment = debt/n`, `interest_t = 0`, `principal_t = payment`, `balance_t = `balance_{t-1} - payment`.

The `NamedTuple` needs field names. Julia allows `(year=1, payment=100.0, interest=5.0, principal=95.0, balance=905.0)` but the return type of `compute_debt_schedule` is declared as `Vector{NamedTuple}`. The generic `NamedTuple` in Julia requires the compiler to specialize on the exact shape — but since the shape is known (5 named fields of specific types), this works fine.

Now let me plan precisely:

---

Here is the plan:

## Goal

Add four financing cash-flow helpers (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to `src/industrial/capex_model.jl` alongside the existing `FinancingStructure` and `compute_debt_service`, and export them.

## Files to touch

### `src/industrial/capex_model.jl` (the only file changed)

1. **Insert `validate_financing`** — right after `compute_debt_service` (line 446) and before the `# Printing Functions` section (line 448). A pure validation function: `return` a `Bool`, never throw.

2. **Insert `compute_debt_schedule`** — after `validate_financing`. Builds an amortization table as `Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int64, Float64, Float64, Float64, Float64}}}`. Reuses the annuity from `compute_debt_service`. Zero-interest branch: straight-line principal. For each year t=1..n: compute interest on the previous balance, principal = payment - interest, new balance = old balance - principal. Final balance must be within 1e-6 of zero (invariant 1), sum of all principal values must equal the debt amount within 1e-6 (invariant 2).

3. **Insert `total_interest_paid`** — after `compute_debt_schedule`. Simply `sum(entry.interest for entry in compute_debt_schedule(capex, fin))`.

4. **Insert `print_debt_schedule`** — after `total_interest_paid`, before the existing `# Printing Functions` section. Follow the style of `print_phased_capex_summary`: a header banner with `=` characters, column headers, separator line with `-`, one row per year with `@printf`, a closing separator, and a total line. Format: year as `%4d`, currency amounts in millions (€) with `%10.2f` or similar.

5. **Append to export lines** (lines 566–573): add `validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`.

### `test/industrial/test_capex_model.jl` — NOT modified (coder is forbidden from editing tests)

## Ordered steps for the coder

1. **Read** `src/industrial/capex_model.jl` to ensure you have the current content.

2. **Insert `validate_financing`** between line 446 (`end` of `compute_debt_service`) and line 448 (`# Printing Functions`). The function:
   - Takes `fin::FinancingStructure`.
   - Returns `false` if `abs(equity_pct + debt_pct + grant_pct - 1.0) > 1e-6`.
   - Returns `false` if any of `equity_pct`, `debt_pct`, `grant_pct`, `debt_interest` is negative.
   - Returns `false` if `debt_tenor_years < 1`.
   - Returns `true` otherwise.

3. **Insert `compute_debt_schedule`** after `validate_financing`. The function:
   - Takes `capex::Float64, fin::FinancingStructure`.
   - Uses exactly the same annuity formula as `compute_debt_service` (copy its logic: debt amount = capex * debt_pct, r = interest rate, n = tenor, annuity formula).
   - Initializes `balance = debt_amount`, `schedule = Vector{NamedTuple}()`.
   - For year `t` in `1:n`: compute `interest = balance * r`, `principal = annuity - interest`, then `balance -= principal`. Push `(; year=t, payment=annuity, interest, principal, balance)`.
   - After the loop, `balance` must be ≈ 0 within 1e-6 (an implicit invariant — no explicit check needed, but the code should be numerically sound so this holds).
   - Return the schedule.

4. **Insert `total_interest_paid`** after `compute_debt_schedule`. Call `compute_debt_schedule` and sum the `interest` field.

5. **Insert `print_debt_schedule`** after `total_interest_paid`. Style: use `=` banner line, column header lines, `-` separator, one `@printf` per row, then a total line. Example:
   ```
   ============================================================
   DEBT REPAYMENT SCHEDULE
   ============================================================
   Year |    Payment |   Interest |  Principal |    Balance
   ------------------------------------------------------------
      1 |   €0.39 M  |    €0.20 M |    €0.19 M |   €3.81 M
   ...
   ------------------------------------------------------------
   Total interest paid: €X.XX M
   ============================================================
   ```

6. **Edit the export block** (lines 566–573). On line 571 (the `default_financing, compute_debt_service` line), append the four new names. Or add a new export line. Simplest: change line 571 from `export default_financing, compute_debt_service` to `export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`.

7. **Call `julia_gate` on `test/industrial/runtests.jl`** — the gate replays `test_capex_model.jl` (included at line 52) among other industrial tests. Acceptance criterion: **VERT**.

## Targeted tests

- **`test/industrial/runtests.jl`** — this is the single gate invocation. It includes `test/industrial/test_capex_model.jl` at line 52, which has existing tests for `FinancingStructure` (line 162) and `compute_debt_service` (line 175, 190). The existing tests cover:
  - `FinancingStructure` struct construction and field values (lines 162–173)
  - `compute_debt_service` with interest (lines 175–188)
  - `compute_debt_service` with zero interest (lines 190–197)

  The existing test at line 172 already checks `fin.equity_pct + fin.debt_pct + fin.grant_pct ≈ 1.0` — so the `validate_financing` logic is already implicitly exercised.

  The gate should also include a self-check for the two invariants in point 2: the coder should verify (by inspecting the code they write, since the gate runs existing tests only) that the final balance after the schedule loop is zero within 1e-6 and that the sum of principal equals the debt amount.

## Acceptance criterion

Gate verdict **VERT** on `test/industrial/runtests.jl`. The existing test file `test_capex_model.jl` does **not** have explicit tests for the four new functions, but the gate will catch:
- Any syntax error or type error in the inserted code, since Julia compiles the whole file.
- The existing exports test (line 9 checking `isdefined` on `FinancingStructure`, `default_financing`, `compute_debt_service`) does **not** check the new names — but the code is included and executed, so compilation errors would fail the gate.

The coder should also manually verify the two invariants of `compute_debt_schedule` since the existing tests don't cover them: that `balance` after the loop is 0 within 1e-6, and `sum(principal) ≈ debt_amount`.

## Risks and what NOT to touch

- **Do NOT modify** `test/industrial/test_capex_model.jl` or any other test file.
- **Do NOT modify** the `FinancingStructure` struct, `compute_debt_service`, or any existing function.
- **Do NOT change** the signature of `compute_debt_service` — the new `compute_debt_schedule` should independently replicate its annuity logic (or call it internally), not alter it.
- **Floating-point risk**: The final balance might not hit exactly zero due to roundoff. The code should be written so that the last period absorbs the residual (i.e., principal on the last payment = remaining balance), ensuring the invariant holds. The simplest approach: after the loop for years 1..n-1, set year n's `principal = remaining_balance` and `interest = payment - principal`, then `balance = 0.0`. This guarantees the invariant.
- **NamedTuple typing**: Julia's `NamedTuple` in `Vector{NamedTuple}` is an abstract type; the concrete type is `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int64, Float64, ...}}`. This is fine. Do not try to use parametric `NamedTuple` types — just construct them with `(; year=t, payment=annuity, interest, principal, balance)` syntax.
- **Zero-interest edge case**: When `r == 0`, `interest` is 0 for every year, `principal = payment = debt/n`, and the schedule is straight-line. The annuity formula's `r > 0` branch in `compute_debt_service` already handles this. Replicate the same branching.
