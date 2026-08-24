Good. Now I have all the context I need. Let me lay out the plan.

---

## Plan

### 1. Goal
Add four financing cash-flow helper functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to `src/industrial/capex_model.jl`, placed after `compute_debt_service` (line 446) and before the "Printing Functions" section (line 448), and export all four names on the existing export lines.

### 2. Files to touch

| File | What changes | Why |
|---|---|---|
| `src/industrial/capex_model.jl` | Insert 4 new functions between `compute_debt_service` (ends line 446) and the `# Printing Functions` divider (line 448). Add 4 names to the export block (lines 566–573). | This is where `FinancingStructure` is defined and where sister functions `compute_debt_service` and the print helpers live. |
| *(no test file changes — the plan specifies no new tests; the gate replays existing `test/industrial/runtests.jl` which includes `test_capex_model.jl`)* | N/A | N/A |

### 3. Ordered steps for the coder

1. **Read `src/industrial/capex_model.jl`** to have current content with line numbers.
2. **Insert the four new functions** immediately after line 446 (the `end` of `compute_debt_service`) and before line 448 (`# ============================================================================ # Printing Functions`). Leave the `# Financing Model` section divider (line 446–447 area) as-is; the new functions are part of that section. Add a brief comment separator like `# --- Debt schedule helpers` before the new code.
3. **Implement `validate_financing`**: return `true` when:
   - `abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) < 1e-6`
   - `fin.equity_pct >= 0`, `fin.debt_pct >= 0`, `fin.grant_pct >= 0`, `fin.debt_interest >= 0`, `fin.equity_irr_target >= 0`
   - `fin.debt_tenor_years >= 1`
   - Return `false` otherwise (no exception).  
   Signature: `validate_financing(fin::FinancingStructure) -> Bool`
4. **Implement `compute_debt_schedule`**: return a `Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int64, Float64, Float64, Float64, Float64}}}` with one entry per year `1..fin.debt_tenor_years`.  
   - `debt_amount = capex * fin.debt_pct`
   - Annuity `A` = same computation as `compute_debt_service` (lines 439–443): `r > 0 ? debt_amount * r * (1+r)^n / ((1+r)^n - 1) : debt_amount / n`
   - `balance_prev = debt_amount`; for each year `y`:
     - `interest = balance_prev * r`
     - `principal = A - interest` (when `r > 0`), else `principal = debt_amount / n` (straight-line)
     - `balance = balance_prev - principal`
     - Push `(year=y, payment=A, interest=interest, principal=principal, balance=balance)`; set `balance_prev = balance`
   - The final `balance` must be `0.0` within `1e-6` and `sum(principal_i) ≈ debt_amount` within `1e-6` (these are mathematical invariants of the annuity formula, not runtime checks — the coder should verify them when testing via the gate).
5. **Implement `total_interest_paid`**: compute the schedule and return `sum(s.interest for s in schedule)`. Signature: `total_interest_paid(capex::Float64, fin::FinancingStructure) -> Float64`.
6. **Implement `print_debt_schedule`**: print a table in the style of `print_phase_capex` (lines 457–471) and `print_phased_capex_summary` (lines 478–520). Use `=` for header separators, `-` for sub-lines, `@printf` for alignment. Columns: Year, Payment, Interest, Principal, Balance (all in EUR, formatted with `%.2f`). Print a total footer line with sums.
7. **Add the four names to the export block** (lines 566–573). The existing exports are grouped: add `validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` after `compute_debt_service` on line 571 (or on its own new export line, following the file's style of one export per logical group). The cleanest approach: add a new `export` line after the `default_financing, compute_debt_service` line (571), e.g. `export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule`.

### 4. Targeted tests and acceptance criterion

- **Gate replays**: `test/industrial/runtests.jl` (which includes `test/industrial/test_capex_model.jl`).
- **Acceptance criterion**: The gate verdict is **PASS** on the full `test/industrial/runtests.jl` suite.  
- Additionally, the coder must self-check (via the gate's test run) these invariants in `compute_debt_schedule`:
  - `sum(entry.principal for entry in schedule) ≈ capex * fin.debt_pct` within `1e-6`
  - `schedule[end].balance ≈ 0.0` within `1e-6`
  - Each `entry.principal + entry.interest ≈ entry.payment` within `1e-6` (except potentially the last row due to rounding, though the annuity formula guarantees it)
  - The output type is `Vector{NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int64, Float64, Float64, Float64, Float64}}}` (strongly typed NamedTuples as specified)

No new test file is to be created. The existing tests on `FinancingStructure`, `default_financing`, and `compute_debt_service` (lines 162–197 of the test file) remain unchanged and naturally exercise the same `FinancingStructure` values that the new functions consume.

### 5. Risks and what NOT to touch

- **Do NOT touch** any existing function, struct, or export: `FinancingStructure`, `compute_debt_service`, `default_financing`, the `ModularCAPEX` struct or its factories, the `PhaseCAPEX` logic, the demo, or the printing functions above line 448.
- **Do NOT touch** `test/industrial/test_capex_model.jl` or any test file.
- **Risk**: The `NamedTuple` return type specified uses a very specific tuple type annotation. If the coder constructs NamedTuples with `(; year=y, …)` syntax, Julia will infer the correct concrete type automatically as long as all values are consistently `Int64`/`Float64`. The coder should verify the return type at a REPL or via the gate's `@test` assertions on type stability.
- **Risk**: Floating-point rounding on the final balance. The annuity formula is exact in principle; the final balance should be zero within `1e-6` for reasonable capex values (up to ~1e12). This is a mathematical property of the amortization formula, not a runtime clamp.
- **Risk**: `print_debt_schedule` uses `@printf` which requires `using Printf` — already present at line 18 of the source file.
- **Risk**: The new export line must be placed so that `demo_capex_model` (exported on line 573) can optionally call the new helpers without a separate `using` — the export ensures visibility to downstream code.