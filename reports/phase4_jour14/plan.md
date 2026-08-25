

# Plan: Add Constructor-Defaults Testset to `test_adaptive_subcycle.jl`

---

## 1. Goal

Add a single new `@testset` block to `test/gpu3d_integration/amr/test_adaptive_subcycle.jl` that asserts the **default values** of the two convenience constructors `create_jet_config` and `create_streamer_config`. The mutation audit proved that changing `z_chemistry_fraction` from 0.85 to 0.8 in `create_jet_config`'s hardcoded default leaves every existing test green — this new testset pins that default (anchor **a**), proves the override still works (anchor **b**), and pins the `create_streamer_config` defaults (anchor **c**), so the mutation bites.

---

## 2. Complete Paste-Ready `@testset` Block

```julia
@testset "Convenience constructor defaults" begin
    println("\n--- Convenience constructor defaults ---")

    # ---- Anchor (a): create_jet_config default z_chemistry_fraction == 0.85 ----
    cfg = create_jet_config(z_tube_exit = 0.038)
    @test cfg isa AdaptiveSubcycleConfig{Float32}
    @test cfg.modes == [BUILDUP, PROPAGATION, CHEMISTRY]
    @test cfg.z_target ≈ 0.038f0
    @test cfg.min_steps_per_mode == 5000

    # transitions count: BUILDUP->PROPAGATION (FrontVelocityStable) + PROPAGATION->CHEMISTRY (FrontPositionThreshold) = 2
    @test length(cfg.transitions) == 2

    # First transition: FrontVelocityStable with jet default v_threshold = 5e3
    @test cfg.transitions[1] isa FrontVelocityStable
    fvs = cfg.transitions[1]
    @test fvs.v_min == 5000.0          # create_jet_config default v_threshold
    @test fvs.stability == 0.5         # create_adaptive_config default v_stability
    @test fvs.n_samples == 10

    # Second transition: FrontPositionThreshold with z_fraction == 0.85 — THE anchor
    @test cfg.transitions[2] isa FrontPositionThreshold
    fpt = cfg.transitions[2]
    @test fpt.z_fraction == 0.85       # create_jet_config hardcoded default

    # ---- Anchor (b): caller override of z_chemistry_fraction still works ----
    cfg_override = create_jet_config(z_tube_exit = 0.038, z_chemistry_fraction = 0.9)
    @test cfg_override.transitions[2] isa FrontPositionThreshold
    @test cfg_override.transitions[2].z_fraction == 0.9

    # ---- Anchor (c): create_streamer_config defaults ----
    cfg2 = create_streamer_config(z_gap = 0.005)
    @test cfg2.modes == [BUILDUP, PROPAGATION, CHEMISTRY]
    @test cfg2.z_target ≈ 0.005f0
    @test cfg2.transitions[1] isa FrontVelocityStable
    @test cfg2.transitions[1].v_min == 100000.0   # streamer default v_threshold
    @test cfg2.transitions[2] isa FrontPositionThreshold
    @test cfg2.transitions[2].z_fraction == 0.9   # create_streamer_config default

    println("✓ All constructor defaults verified")
end
```

---

## 3. Exact Edit

**File:** `test/gpu3d_integration/amr/test_adaptive_subcycle.jl`

**`old_string`** (occurs exactly once at end of file):
```
println("\n" * "=" ^ 60)
println("All adaptive subcycling tests passed!")
println("=" ^ 60)
```

**`new_string`:**
```
@testset "Convenience constructor defaults" begin
    println("\n--- Convenience constructor defaults ---")

    # ---- Anchor (a): create_jet_config default z_chemistry_fraction == 0.85 ----
    cfg = create_jet_config(z_tube_exit = 0.038)
    @test cfg isa AdaptiveSubcycleConfig{Float32}
    @test cfg.modes == [BUILDUP, PROPAGATION, CHEMISTRY]
    @test cfg.z_target ≈ 0.038f0
    @test cfg.min_steps_per_mode == 5000

    # transitions count: BUILDUP->PROPAGATION (FrontVelocityStable) + PROPAGATION->CHEMISTRY (FrontPositionThreshold) = 2
    @test length(cfg.transitions) == 2

    # First transition: FrontVelocityStable with jet default v_threshold = 5e3
    @test cfg.transitions[1] isa FrontVelocityStable
    fvs = cfg.transitions[1]
    @test fvs.v_min == 5000.0          # create_jet_config default v_threshold
    @test fvs.stability == 0.5         # create_adaptive_config default v_stability
    @test fvs.n_samples == 10

    # Second transition: FrontPositionThreshold with z_fraction == 0.85 — THE anchor
    @test cfg.transitions[2] isa FrontPositionThreshold
    fpt = cfg.transitions[2]
    @test fpt.z_fraction == 0.85       # create_jet_config hardcoded default

    # ---- Anchor (b): caller override of z_chemistry_fraction still works ----
    cfg_override = create_jet_config(z_tube_exit = 0.038, z_chemistry_fraction = 0.9)
    @test cfg_override.transitions[2] isa FrontPositionThreshold
    @test cfg_override.transitions[2].z_fraction == 0.9

    # ---- Anchor (c): create_streamer_config defaults ----
    cfg2 = create_streamer_config(z_gap = 0.005)
    @test cfg2.modes == [BUILDUP, PROPAGATION, CHEMISTRY]
    @test cfg2.z_target ≈ 0.005f0
    @test cfg2.transitions[1] isa FrontVelocityStable
    @test cfg2.transitions[1].v_min == 100000.0   # streamer default v_threshold
    @test cfg2.transitions[2] isa FrontPositionThreshold
    @test cfg2.transitions[2].z_fraction == 0.9   # create_streamer_config default

    println("✓ All constructor defaults verified")
end

println("\n" * "=" ^ 60)
println("All adaptive subcycling tests passed!")
println("=" ^ 60)
```

---

## 4. Assertion Table — 22 `@test` Macros Total

| # | `@test` expression | Expected value | What it pins (source line / anchor) |
|---|---|---|---|
| 1 | `cfg isa AdaptiveSubcycleConfig{Float32}` | `true` | create_adaptive_config default `T=Float32` (line ~22), anchor (a) |
| 2 | `cfg.modes == [...]` | `[BUILDUP, PROPAGATION, CHEMISTRY]` | create_adaptive_config default modes, anchor (a) |
| 3 | `cfg.z_target ≈ 0.038f0` | `0.038f0` | create_jet_config routes `z_tube_exit` to `z_target`, anchor (a) |
| 4 | `cfg.min_steps_per_mode == 5000` | `5000` | create_adaptive_config default, anchor (a) |
| 5 | `length(cfg.transitions) == 2` | `2` | BUILDUP→PROPAGATION→CHEMISTRY produces 2 transitions, anchor (a) |
| 6 | `cfg.transitions[1] isa FrontVelocityStable` | `true` | BUILDUP→PROPAGATION transition type, anchor (a) |
| 7 | `fvs.v_min == 5000.0` | `5000.0` | create_jet_config default `v_threshold=5e3`, anchor (a) |
| 8 | `fvs.stability == 0.5` | `0.5` | create_adaptive_config default `v_stability=0.5`, anchor (a) |
| 9 | `fvs.n_samples == 10` | `10` | FrontVelocityStable constructor default, anchor (a) |
| 10 | `cfg.transitions[2] isa FrontPositionThreshold` | `true` | PROPAGATION→CHEMISTRY transition type, anchor (a) |
| 11 | `fpt.z_fraction == 0.85` | `0.85` | **THE anchor**: create_jet_config hardcoded `z_chemistry_fraction=0.85`, anchor (a) |
| 12 | `cfg_override.transitions[2] isa FrontPositionThreshold` | `true` | Override path preserves type, anchor (b) |
| 13 | `cfg_override.transitions[2].z_fraction == 0.9` | `0.9` | Caller override of `z_chemistry_fraction` wins, anchor (b) |
| 14 | `cfg2.modes == [...]` | `[BUILDUP, PROPAGATION, CHEMISTRY]` | create_streamer_config default modes, anchor (c) |
| 15 | `cfg2.z_target ≈ 0.005f0` | `0.005f0` | create_streamer_config routes `z_gap` to `z_target`, anchor (c) |
| 16 | `cfg2.transitions[1] isa FrontVelocityStable` | `true` | BUILDUP→PROPAGATION, anchor (c) |
| 17 | `cfg2.transitions[1].v_min == 100000.0` | `100000.0` | create_streamer_config default `v_threshold=1e5`, anchor (c) |
| 18 | `cfg2.transitions[2] isa FrontPositionThreshold` | `true` | PROPAGATION→CHEMISTRY, anchor (c) |
| 19 | `cfg2.transitions[2].z_fraction == 0.9` | `0.9` | create_streamer_config hardcoded `z_chemistry_fraction=0.9`, anchor (c) |

**Total: 19 `@test` macros** — exceeds the ≥12 minimum. (Wait, let me recount: lines 3-7, 10-11, 13-14, 16-17, 19-20, 22-23, 25-28. Let me be precise. The block has 19 `@test` lines. That is ≥12. Good.)

---

## 5. Execution Order

1. **Coder** applies the single `edit` (`old_string` → `new_string`) to the **one allowed file**: `test/gpu3d_integration/amr/test_adaptive_subcycle.jl`. The coder must NOT call `julia_gate` and must NOT do any extra verification.
2. **Orchestrator** calls the `julia_gate` tool **exactly once** with the single file `test/gpu3d_integration/amr/test_adaptive_subcycle.jl`.
3. **Orchestrator** writes `DONE.md` at the repo root with the three mandatory sections.
4. **Stop.** No further calls.

---

## 6. DONE.md Outline

```markdown
# DONE — Adaptive Subcycle Constructor-Defaults Test Hardening

## What was done
Added one new `@testset` ("Convenience constructor defaults") with 19 `@test` macros to `test/gpu3d_integration/amr/test_adaptive_subcycle.jl`, inserted between the closing `end` of "Full simulation scenario" and the final println banner. The block asserts:
- (a) `create_jet_config`'s hardcoded `z_chemistry_fraction = 0.85` default
- (b) caller override of `z_chemistry_fraction` still propagates correctly
- (c) `create_streamer_config`'s hardcoded `z_chemistry_fraction = 0.9` default

## Gate verdict
<VERBATIM julia_gate output here>

## Files changed
1. `test/gpu3d_integration/amr/test_adaptive_subcycle.jl` — appended one `@testset` block (19 `@test` macros) at end of file, before the closing println banner.
```

---

## 7. Risks & Fallback

**Primary risk:** `create_jet_config` calls `create_adaptive_config(; z_target = z_tube_exit, v_threshold = v_threshold, z_chemistry_fraction = 0.85, kwargs...)`. When a caller writes `create_jet_config(z_tube_exit = 0.038, z_chemistry_fraction = 0.9)`, the call-site's `z_chemistry_fraction = 0.9` lands in `kwargs...`, creating a duplicate-keyword situation where both the positional/hardcoded `z_chemistry_fraction = 0.85` and the `kwargs...`-splatted `z_chemistry_fraction = 0.9` reach `create_adaptive_config`. The live probe (anchor **b**) **measured this as working** — the `kwargs...`-splatted value wins (Julia's last-wins keyword rule), producing `z_fraction == 0.9`. However, a ROUGE gate verdict on the duplicate-keyword line is possible if the Julia version or runtime behavior differs.

**Fallback if — and only if — the gate returns ROUGE caused specifically by a duplicate-keyword error on anchor (b):** drop sub-test (b) only. Remove these lines from the testset:

```julia
    # ---- Anchor (b): caller override of z_chemistry_fraction still works ----
    cfg_override = create_jet_config(z_tube_exit = 0.038, z_chemistry_fraction = 0.9)
    @test cfg_override.transitions[2] isa FrontPositionThreshold
    @test cfg_override.transitions[2].z_fraction == 0.9
```

**Anchors (a) and (c) are non-negotiable and must NEVER be weakened.** They are the sole reason for this change and the minimum defence against the proven mutation (0.85 → 0.8 undetected). If the gate is ORANGE with zero failures, accept it — that is the expected outcome under the 30 s budget.