planner: 7965 chars
VERT achieved. The plan is fully implemented.

## Summary

**Files created** (exactly two, per the contract — no source files touched):
1. `test/anchors/runtests.jl` — orchestrator modeled on `test/industrial/runtests.jl`: `include`s `src/anchors/Anchors.jl`, `using .Anchors`, wraps `test_anchors.jl` in `@testset "Anchors Module Tests"`.
2. `test/anchors/test_anchors.jl` — 15 `@test`/`@test_throws` assertions covering all four exported functions:
   - **(A)** `validate_anchors(; verbose=false)` → `length(anchors) >= 9`, `length(errors) == 0` (observed value), warnings structural check
   - **(B)** `anchor_value("choi2006.gas_production_factor").value == 2.5` and `.unit == "dimensionless"`
   - **(C)/(D)** `@test_throws ErrorException` for unknown source id and unknown value id
   - **(E)** `load_anchor("choi_2006")`: non-empty values, all finite numeric, `a.id == "choi2006"`
   - **(F)** `anchor_value("choi2006.scod_tcod_factor").value == 4.5`
   - **(G)** `haskey(anchors, "choi2006")`; every anchor has ≥1 value
   - **(H)** `quality_tier == 1`
   - **(I)** `@test_throws ErrorException load_anchor("no_such_slug_at_all")`

**Honesty rule note (observed count):** the plan flagged a risk that `validate_anchors()` might report errors (unfetched LFS PDF pointers). **Observed at runtime: 0 errors, 0 warnings — the committed registry of 10 anchors is clean.** First gate run (ROUGE) was solely due to my placeholder `length(errors) == 2`; I corrected it to the observed `0` per the plan's honesty rule (assert the actual count, not an assumption).

**Gate history:**
1. ROUGE — 1 false assertion (`length(errors) == 2`, actual 0)
2. **VERT** — 15 ok, 0 false, 0 err, 0 uncovered

**Final verdict: VERT** (the only green). No failures outstanding; no source modifications; no other files created.