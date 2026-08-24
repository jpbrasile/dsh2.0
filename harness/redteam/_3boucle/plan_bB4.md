No top-level industrial module file. The files are included directly in the test runner. Now let me look at the `print_` functions closely to understand the style I need to match:

Looking at existing code, I have everything I need. Let me now verify one detail — the existing `FinancingStructure` fields:

- `equity_pct::Float64`
- `debt_pct::Float64`
- `grant_pct::Float64`
- `debt_interest::Float64`
- `debt_tenor_years::Int`
- `equity_irr_target::Float64`

Now I have the full picture. Here is the plan.

---

## Plan

### Goal
Add four financing cash-flow helper functions (`validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule`) to `src/industrial/capex_model.jl` and export them, without touching tests.

### Files to touch

**1. `src/industrial/capex_model.jl`** — the only file to modify.

Changes:
- **After line 446** (after `compute_debt_service`'s `end` and the blank line separator): Insert the four new functions in the "Financing Model" section (lines 386–447), before the "Printing Functions" section starts at line 448.
- **After line 520** (after `print_phased_capex_summary`'s `end`): Insert `print_debt_schedule` here, inside the "Printing Functions" section (lines 448–521), after `print_phased_capex_summary` and before the "Demo Function" section.
- **Lines 566–573** (export block): Add the four new names to the existing export lines.

### Ordered steps for the coder

1. **Insert `validate_financing`** between line 446 (`return annuity` / `end`) and line 448 (`# Printing Functions`). Implementation: a single expression `return` with chained `&&` conditions — `abs(fin.equity_pct + fin.debt_pct + fin.grant_pct - 1.0) < 1e-6`, every share/rate `>= 0`, `fin.debt_tenor_years >= 1`.

2. **Insert `compute_debt_schedule`** right after `validate_financing`. Compute `debt_amount = capex * fin.debt_pct`, compute `annuity` exactly as `compute_debt_service` does (same annuity formula), then loop year `1:n` building `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}` entries. Use a running balance starting at `debt_amount`. Each year: `interest = balance * r`, `principal = annuity - interest` (or `debt_amount / n` when `r == 0`), `balance = balance - principal`. Final balance must be zero within 1e-6.

3. **Insert `total_interest_paid`** right after `compute_debt_schedule`. One-liner: `sum(entry.interest for entry in compute_debt_schedule(capex, fin))`.

4. **Insert `print_debt_schedule`** after `print_phased_capex_summary` (after line 520). Match the style of `print_phase_capex` and `print_phased_capex_summary`: `"="^N` header, column-formatted rows with `@printf`, `"-"^N` separator. Print columns: Year, Payment, Interest, Principal, Balance. Print totals row after the separator.

5. **Export the four names**: On line 571 (`export default_financing, compute_debt_service`), append `, validate_financing, compute_debt_schedule, total_interest_paid`. On line 572 (`export print_phase_capex, print_phased_capex_summary`), append `, print_debt_schedule`.

### Targeted tests the gate must replay

- **`test/industrial/runtests.jl`** — which includes `test/industrial/test_capex_model.jl` (the existing test suite). The gate runs `julia --project=. test/industrial/runtests.jl`.

### Acceptance criterion

The gate must return **VERT** (green) on the existing test file `test/industrial/test_capex_model.jl`. The coder must also perform a **self-check of the invariants in task item 2** by running the gate and then verifying in the output (or by including inline checks in the code passed through the gate — but the coder cannot create new tests). Since the coder cannot create or edit test files, the self-check consists of verifying that the code compiles, the existing tests pass, and the following invariants can be reasoned about statically from the code:

- `compute_debt_schedule` returns one entry per year 1..`debt_tenor_years`
- The final balance is zero within 1e-6
- The sum of principal equals the debt amount
- Zero interest produces straight-line principal equal to `debt_amount / n`

### Risks and what NOT to touch

- **Do NOT touch `test/industrial/test_capex_model.jl` or any other test file.** The existing tests verify `FinancingStructure` construction (lines 162–173) and `compute_debt_service` (lines 175–197). The new functions must not break these.
- **Do NOT change `compute_debt_service`** — it is the existing annuity formula and the schedule must replicate it exactly.
- **Do NOT change `FinancingStructure` fields.**
- **Do NOT change any other source file.**
- **Risk**: The existing test on line 172 checks `fin.equity_pct + fin.debt_pct + fin.grant_pct ≈ 1.0` on `default_financing()`. The new `validate_financing` returns `Bool` and is not called anywhere in existing tests, so it cannot break them. There is no collision.
- **Risk**: Julia 1.12 struct redefinition hangs — the test runner includes each source file exactly once (line 35 of `runtests.jl`), so adding functions (not structs) is safe.
- **Risk**: The `NamedTuple` type annotation in the return type `Vector{NamedTuple}` is valid Julia syntax; specify the concrete named tuple type as `NamedTuple{(:year, :payment, :interest, :principal, :balance), Tuple{Int, Float64, Float64, Float64, Float64}}` for precision.