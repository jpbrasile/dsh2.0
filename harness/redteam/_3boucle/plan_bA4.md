I now have everything I need. Here is the plan.

---

# Plan: financing cash-flow helpers in `src/industrial/capex_model.jl`

## 1. Goal

Add four financing cash-flow helpers (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to `src/industrial/capex_model.jl` beside `FinancingStructure`/`compute_debt_service`, export them, and confirm the `industrial` module gate still passes via a self-check of the amortization invariants.

## 2. Files to touch

### `src/industrial/capex_model.jl` (only file changed)

All four functions go into the **"Financing Model"** section (between the `compute_debt_service` function body ending at line 446 and the `# Printing Functions` block at line 448–451), with `print_debt_schedule` following the established print style.

**New functions (concrete implementation guidance):**

1. `validate_financing(fin::FinancingStructure) -> Bool`
   - Compute `tot = fin.equity_pct + fin.debt_pct + fin.grant_pct`; return `false` unless `abs(tot - 1.0) <= 1e-6`.
   - Return `false` if any of `equity_pct`, `debt_pct`, `grant_pct`, `debt_interest`, `equity_irr_target` is negative (use `isless(x, 0.0)` or `x < 0`).
   - Return `false` unless `fin.debt_tenor_years >= 1`.
   - Otherwise return `true`. No exception anywhere (note: `debt_tenor_years` is typed `Int`, so `>= 1` is safe without NaN handling).

2. `compute_debt_schedule(capex::Float64, fin::FinancingStructure) -> Vector{NamedTuple}`
   - `debt = capex * fin.debt_pct`, `r = fin.debt_interest`, `n = fin.debt_tenor_years`.
   - Compute the annuity `payment` exactly as `compute_debt_service` does (copy its two branches: `r > 0 ⇒ debt*r*(1+r)^n / ((1+r)^n - 1)`; else `debt / n`). To guarantee consistency, consider calling `compute_debt_service(capex, fin)` for the payment.
   - Iterate `year in 1:n`, maintaining `balance` (start at `debt`). For each year:
     - `interest = balance * r`
     - `principal = payment - interest` — but clamp/handle the **last year**: to make `balance` hit exactly zero within `1e-6` and `sum(principal) == debt`, in year `n` set `principal = balance` (with `balance` the outstanding balance *before* the last payment) when `r > 0`, and recompute `payment`-column faithfully. For `r == 0`, the straight-line principal `debt/n` already zeroes out after `n` years.
     - `balance = balance - principal`.
   - Build each entry as `(year=year, payment=payment, interest=interest, principal=principal, balance=balance)` (use explicit `NamedTuple`s so the field order is deterministic as specified).
   - Note on the last-year annuity: standard level-payment amortization has a final partial payment; since `compute_debt_service` returns a single level annuity, use that same `payment` for the `payment` field of each row but drive `principal` in the final year to close out the balance. The invariant check in step 4 validates this.

3. `total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64`
   - `sum(entry.interest for entry in compute_debt_schedule(capex, fin))`.

4. `print_debt_schedule(capex::Float64, fin::FinancingStructure)` (returns `nothing`)
   - `sched = compute_debt_schedule(capex, fin)`.
   - Emit `"="^N` header, a title like `"DEBT SERVICE SCHEDULE"`, then a `@printf` header row (`"Year"`, `"Payment"`, `"Interest"`, `"Principal"`, `"Balance"`) mirroring the `%-Ns | ...\n` format used by `print_phased_capex_summary` (lines 485–499), a separator line of `"-"^N`, one `@printf` row per entry, a closing separator, and a "TOTAL" cumulative row (total payment / interest / principal). Keep it consistent with the file's `=`/`-` rule and `@printf` style. No new `using` needed — `Printf` is already imported at line 18.

**Exports (lines 566–573):**
- Line 571 currently: `export default_financing, compute_debt_service` → append, or add a new line `export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`. Keep them grouped on the financing-related export lines.

## 3. Ordered steps for the coder

1. Insert `validate_financing` after `compute_debt_service` (after line 446).
2. Insert `compute_debt_schedule` after it.
3. Insert `total_interest_paid` after that.
4. Insert `print_debt_schedule` after that (still above the `# Printing Functions` header, so the financing helpers stay contiguous).
5. Add the four names to the export block near lines 566–572.
6. Run the gate (the coder must use its `julia_gate` tool, never a shell `julia`): replay the industrial test files below.
7. Separately self-check the invariant from spec item 2 (below) — this is a manual/self-check, not a new test file.

## 4. Tests the gate replays & acceptance criterion

**Existing test files the gate must replay** (all already wired via `test/industrial/runtests.jl`, lines 50–66):
- `test/industrial/runtests.jl`
- `test/industrial/test_capex_model.jl`

Note: `test_capex_model.jl` currently checks only `FinancingStructure`, `default_financing`, `compute_debt_service`, and the export list (lines 3–19). The task forbids the coder from creating/editing tests, so the new functions are **not** individually tested by the replay; the gate still exercises the full existing `capex_model` test set (912 industrial assertions) plus the `isdefined` export checks.

**Acceptance criterion:** gate verdict **VERT** (pass) on the replay of `test/industrial/runtests.jl` (which includes `test_capex_model.jl`), **plus** a self-check (run in isolation or via the gate, not a new test file) of the spec-item-2 invariants:
- One schedule entry per year `1..debt_tenor_years`; final `balance ≈ 0` within `1e-6`.
- `sum(principal) ≈ capex * debt_pct` (the debt amount).
- For `debt_interest == 0`, `principal == debt/n` every year (straight-line).
- For a positive-rate case (e.g. `default_financing()`), the schedule's first-year payment equals `compute_debt_service(capex, fin)`.

Since the coder cannot add tests, this self-check is the only mechanism to verify the new code; flag plainly that the existing test corpus does **not** cover the new functions, so the self-check is mandatory and must be reported in the coder's final summary.

## 5. Risks and what NOT to touch

- **Do NOT modify** any test file. The gate replay list is fixed to the two `runtests.jl` files above.
- **Do NOT touch** `compute_debt_service`, `FinancingStructure`, `default_financing`, or any `print_*`/`compute_*` functions — `compute_debt_schedule` must reproduce the annuity via the same formula/branching (ideally by delegating the annuity to `compute_debt_service`), not by rewriting the annuity logic inline and risking drift.
- **Floating-point invariant risk:** the final-balance-zero and sum-of-principal-equals-debt invariants will only hold within `1e-6` if the last-year `principal` is set to the outstanding `balance` (for `r > 0`). A naive `sum(principal)` computed from `payment - interest` each year can drift off `debt` due to rounding; close out the final row exactly.
- **Field order/type risk:** return a `Vector{NamedTuple}`, not a `Vector{Dict}` or a `Tuple`, and keep the `(year, payment, interest, principal, balance)` key order so downstream dispatch and any future tests match the spec.
- **`debt_tenor_years` typed as `Int`** (line 408): guard `n >= 1` so `n = 0` or negative (invalid financing) does not divide by zero or loop zero times; but do not add type piracy or change the struct.
- **No new `using`/`import`** other than what already exists (`Printf`, `Statistics` at lines 18–19) — print helpers rely on `@printf` already in scope.