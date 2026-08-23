planner: 8678 chars

Gate is VERT. The plan also asks for a 10-point self-check of invariants, but I can only run code through `julia_gate` (no direct Julia execution allowed, and I can't add test files). I'll verify the static properties that guarantee each invariant and report the rest honestly.

Self-check against the spec:

1. **Schedule length** — vector allocated with `(undef, n)` where `n = fin.debt_tenor_years` ✅ (by construction)
2. **Final balance ≈ 0** — final year clamps `principal = balance`, then `balance -= principal` → balance = 0 exactly ✅
3. **Σ principal = debt amount** — telescoping sum: `Σ principal = debt_amount - balance_final = debt_amount` (within FP drift, far below 1e-6) ✅
4. **Σ interest = total_interest_paid** — `total_interest_paid` is defined as that exact sum ✅
5. **`validate_financing(default_financing())`** — default: 0.30+0.40+0.30=1.0 ✓, all shares ≥ 0 ✓, r=0.05 ≥ 0 ✓, tenor=15 ≥ 1 ✓, irr=0.12 ≥ 0 ✓ → true ✅
6. **Negative equity (−0.1)** — caught by the `fin.equity_pct < 0.0` check → false ✅
7. **Sum ≠ 1.0 (0.2+0.3+0.3=0.8)** — `abs(0.8−1.0)=0.2 > 1e-6` → false ✅
8. **Tenor 0** — `debt_tenor_years < 1` → false ✅
9. **Negative interest (−0.01)** — `fin.debt_interest < 0.0` → false ✅
10. **Zero-interest** — `r=0` → annuity = debt/n; each `interest = balance*0 = 0`; principal constant = debt/n until the clamped final year, which equals the same constant; balance ends at 0 ✅ (structurally guaranteed by the code path)

---

## Summary

**File changed:** `src/industrial/capex_model.jl`

**Changes (all per plan):**
1. Inserted four new functions after `compute_debt_service` (between line 446 and the `# Printing Functions` section): `validate_financing`, `compute_debt_schedule`, `total_interest_paid`, `print_debt_schedule` — verbatim from the plan.
2. `export FinancingStructure` → `export FinancingStructure, validate_financing`
3. `export default_financing, compute_debt_service` → `export default_financing, compute_debt_service, compute_debt_schedule, total_interest_paid, print_debt_schedule`

**Gate verdict:** **VERT** — `test/industrial/runtests.jl` replayed, 912 ok, 0 false, 0 errors, 4.1s.

**Self-check:** All 10 invariants hold by construction (analysis above). Note: per my role I cannot run Julia directly or create test files, so these were verified by static inspection of the inserted code against the spec, not by executing inline checks. No test files were created, modified, or deleted. No failures.