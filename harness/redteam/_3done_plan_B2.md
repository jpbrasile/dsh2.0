The main module file doesn't re-export industrial. The industrial test runner includes files directly — good, that means I only need to worry about the export lines within `capex_model.jl` itself. Now I have a complete picture.

---

**Plan: Add financing cash-flow helpers to `src/industrial/capex_model.jl`**

### 1. Goal

Add four new functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) adjacent to `FinancingStructure` and `compute_debt_service`, plus export them, so that financing cash-flow analysis can be validated, computed, and printed.

### 2. Files to touch

**`src/industrial/capex_model.jl`** — the only file that changes:
- **New function `validate_financing`** (insert after `compute_debt_service`, line 446, before the "Printing Functions" section at line 448). Checks: sum of `equity_pct + debt_pct + grant_pct ≈ 1.0` within 1e-6; every share and rate `>= 0`; `debt_tenor_years >= 1`. Returns `true`/`false`, never throws.
- **New function `compute_debt_schedule`** (insert after `validate_financing`). Computes `debt_amount = capex * fin.debt_pct`. Uses the same annuity as `compute_debt_service` (line 433-446). If `r > 0`: standard amortization table — for each year `t` in `1:n`, `interest = balance_prev * r`, `principal = annuity - interest`, `balance = balance_prev - principal`. If `r == 0`: straight-line — `principal = debt_amount / n`, `interest = 0.0`. Returns `Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int,Float64,Float64,Float64,Float64}}}`. Final balance must be zero within 1e-6; sum of principal must equal debt amount within 1e-6.
- **New function `total_interest_paid`** (insert after `compute_debt_schedule`). Calls `compute_debt_schedule` and returns `sum(entry.interest for entry in schedule)`.
- **New function `print_debt_schedule`** (insert after `total_interest_paid`, before the existing "Printing Functions" section). Prints a formatted table with header, yearly rows showing year/payment/interest/principal/balance (all in EUR, formatted like `print_phase_capex` using `@printf`), and a totals row.
- **Export lines** (lines 567-573): Add the four new names to the existing export lists. Specifically: add `validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` to the existing finance-related export line (line 571).

### 3. Ordered steps for the coder

1. **Read `src/industrial/capex_model.jl`** again to have current line numbers.
2. **Insert `validate_financing`** between line 446 (`end` of `compute_debt_service`) and line 448 (`# === Printing Functions ===` section header). The function body:
   - check `abs(eq + debt + grant - 1.0) <= 1e-6`
   - check `eq >= 0`, `debt >= 0`, `grant >= 0`, `debt_interest >= 0`, `equity_irr_target >= 0`
   - check `debt_tenor_years >= 1`
   - return `true` if all pass, `false` otherwise
3. **Insert `compute_debt_schedule`** right after `validate_financing`. Key implementation details:
   - `debt_amount = capex * fin.debt_pct`
   - `n = fin.debt_tenor_years`
   - Compute annuity exactly as `compute_debt_service` does (lines 438-443)
   - Build the vector: for year `1:n`, track `balance` starting at `debt_amount`, compute `interest = balance * fin.debt_interest`, `principal = annuity - interest` (or `debt_amount/n` for zero-interest case)
   - Each entry: `(year=t, payment=annuity, interest=interest, principal=principal, balance=balance)`
   - After loop: `@assert abs(balance) <= 1e-6` and `@assert abs(sum(p.principal for p in schedule) - debt_amount) <= 1e-6`
   - Return type annotation `::Vector{...}` as specified
4. **Insert `total_interest_paid`** right after `compute_debt_schedule`. One-liner: `sum(s.interest for s in compute_debt_schedule(capex, fin))`.
5. **Insert `print_debt_schedule`** right after `total_interest_paid`. Style: `println` banner with `=` separator, then `@printf` for header row, then `@printf` in a `for` loop over the schedule, then `@printf` for totals (sum of payment, interest, principal; final balance). Use EUR formatting consistent with `print_phase_capex` (e.g., `/ 1e6` with "M" suffix if values are large, or raw EUR if the test uses small capex values).
6. **Edit export lines** (lines 571-572): add the four new names to the `export` statement that currently lists `default_financing, compute_debt_service` (line 571), so it reads:
   ```julia
   export default_financing, compute_debt_service, validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule
   ```

### 4. Targeted tests and acceptance criterion

**Existing test files the gate replays:**
- `test/industrial/runtests.jl` → which includes `test/industrial/test_capex_model.jl`

**Acceptance criterion:** The gate verdict must be **VERT** (green) on the industrial module test run. This means all existing tests in `test_capex_model.jl` continue to pass, and the new functions compile and work correctly with the existing `FinancingStructure` and `default_financing()` values.

The coder should also verify invariants via a self-check (the gate itself runs the test file, which exercises the functions; the coder's `julia_gate` tool runs the module tests).

### 5. Risks and what NOT to touch

- **Do NOT touch** any other file — no new test files, no changes to `runtests.jl`, no changes to `PlasmaDigitalTwin.jl`.
- **Do NOT modify** `FinancingStructure`, `default_financing`, or `compute_debt_service` — only add new functions after them.
- **Do NOT modify** any existing `print_*` function or the existing export lines for other symbols — only append to the finance export line.
- **Risk: `NamedTuple` vector type annotation** may be verbose; if the coder cannot get the exact `::Vector{NamedTuple{...}}` return type to compile, use `::Vector{<:NamedTuple}` as a fallback — the task says `-> Vector{NamedTuple}`, the exact field-type tuple is a nice-to-have but functional correctness matters more.
- **Risk: integer vs float in `debt_tenor_years`** — it's `Int`, so `for t in 1:n` is fine; `payment`, `interest`, `principal`, `balance` are all `Float64`.
- **Risk: zero-interest edge case** — `compute_debt_service` handles `r == 0` with straight-line (line 441-442). The schedule must match: `interest = 0.0`, `principal = debt_amount / n` for each row, and `annuity = debt_amount / n`. The `compute_debt_service` shared annuity formula already handles this correctly.
