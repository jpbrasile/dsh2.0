planner: 10370 chars
VERT achieved. Self-check of invariants (logical verification, no test code added):

1. **Length**: `schedule` is allocated with `n = fin.debt_tenor_years` and filled for `year in 1:n` ✓
2. **Final balance ≈ 0**: For r > 0 the annuity formula guarantees exact amortization; the `max(balance, 0.0)` clamp removes any tiny negative FP residue, so last balance is within 1e-6 of zero ✓
3. **Σ principal = debt amount**: Each principal = annuity − interest; telescoping gives Σ principal = debt_amount ✓ (zero-interest: n × annuity = debt_amount exactly) ✓
4. **Zero interest**: every principal = annuity = debt_amount / n ✓
5. **Positive interest**: payment = annuity = interest + principal, and annuity uses the identical formula as `compute_debt_service` ✓
6. **total_interest_paid** sums the interest column directly ✓
7. **validate_financing(default_financing())**: 0.30+0.40+0.30 = 1.0, all non-negative, tenor 15 ≥ 1 → `true` ✓
8. **(0.5, 0.5, 0.1, ...)**: sums to 1.1 > 1+1e-6 → `false` ✓
9. **(..., -0.01, ...)**: negative rate → `false` ✓
10. **(..., 0, ...)**: tenor 0 < 1 → `false` ✓

---

**Summary**

- **Files changed**: `src/industrial/capex_model.jl` — inserted `validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule` after `compute_debt_service` (before the Printing Functions section) and added one export line to the export block. No other files touched; no test files modified; `compute_debt_service` and `FinancingStructure` untouched.
- **Gate verdict**: **VERT** — `test/industrial/runtests.jl` replayed green (912 ok, 0 false, 0 errors, 4.2s).
- **Failures**: none.