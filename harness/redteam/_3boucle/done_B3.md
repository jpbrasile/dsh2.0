planner: 8647 chars
**VERT** — done in one round.

## Summary

**Files changed:** `src/industrial/capex_model.jl` (only file touched)

1. **New block inserted after `compute_debt_service`** (old line 446, before the `# Printing Functions` divider): a `# Financing Cash-Flow Helpers` section with the four functions exactly per the plan — `validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule` (now lines 448–552).
2. **Export added** on a new dedicated line after `export default_financing, compute_debt_service` (line 678), following the one-semantic-group-per-line convention. No existing function or export line was modified; no test files were touched. `@printf` needed no new import (`Printf` already imported at line 18).

**Invariant self-check (by inspection, per plan §4):**
- Final balance zero within 1e-6: annuity identity gives `b_n = 0` in exact arithmetic; floating-point drift is ~1e-17 absolute at 10 M € scale. The `principal > balance + 1e-12` guard plus the `max(balance, 0.0)` clamp handle the residual. Holds with and without the guard.
- Σ principal = debt_amount: telescoping `Σ principal = b_0 − b_n = debt_amount`; the guard only fires in the final year, forcing `principal = balance`, which is exactly the telescoping requirement.

**Gate verdict: VERT** — `test\industrial\runtests.jl` replayed in 4.3 s: 912 ok, 0 fail, 0 error, 0 files uncovered. All existing tests still pass; no failures.