planner: 7557 chars
VERT. Final state of the implementation is as specified. Summary:

**File changed:** `src/industrial/capex_model.jl` (only file)
- Inserted `validate_financing` (line 455), `compute_debt_schedule` (line 474), `total_interest_paid` (line 506), `print_debt_schedule` (line 515) in the Financing Model section, between `compute_debt_service` and the Printing Functions block.
- `compute_debt_schedule` delegates the level annuity to `compute_debt_service` (no duplicated annuity logic), iterates `1..debt_tenor_years` with explicit `(year, payment, interest, principal, balance)` NamedTuples in that key order, and closes the final year by setting `principal = balance` when `r > 0`; `r == 0` falls through the straight-line `payment - interest = debt/n` branch, which zeros out exactly after `n` years.
- Added `export validate_financing, compute_debt_schedule, total_interest_paid, print_debt_schedule` directly after the `default_financing, compute_debt_service` export line.
- No test files touched; no new `using`/`import`; `print_debt_schedule` follows the file's `"="`/`"-"` rule and `@printf` style.

**Final gate verdict:** **VERT** — `test/industrial/runtests.jl` (replaying the full industrial suite incl. `test_capex_model.jl`): 912 ok, 0 false, 0 errors, 0 uncovered. (First attempt was ROUGE on invalid `-> T` return-type syntax in the three signatures; corrected to `::T` annotations in the same round.)

**Mandatory self-check disclosure:** the existing test corpus does **not** cover the four new functions (the replayed `test_capex_model.jl` checks only `FinancingStructure`, `default_financing`, `compute_debt_service`, and the old export list). The gate passing only proves no regression, not the new code. I verified the implementation line-by-line against the spec's invariant logic (final-row balance closure ⇒ `sum(principal) == debt` exactly; `debt/n` per year at `r = 0`; payment column identical to `compute_debt_service` by construction), but I have no mechanism in this environment to execute the invariants as a runnable check without adding a test file, which is forbidden — flagging this gap explicitly for the orchestrator.