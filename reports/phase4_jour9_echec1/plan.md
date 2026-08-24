Now I have all three files. Let me verify key details from the source:

1. **Line 79-82**: `PhysicsUQParam` convenience constructor has params `(name, value, lo, hi, dist; std=0.0, unit="", desc="")` — `std` defaults to `0.0`, `unit` and `desc` to `""`. ✓

2. **Line 228-285**: `default_physics_uq_params()` returns 13 params total (lines 241-282). The four anchors: `:f_irrev_max` (line 252) value 0.65, lo 0.35, hi 0.95, dist `:normal`, std 0.15. `:E_threshold_kJ_m3` (line 256) value 95.0, lo 65.0, hi 155.0, dist `:normal`, std 20.0. `:w_TS` (line 280) value 0.04, lo 0.02, hi 0.08, dist `:triangular`. `:tau2` (line 266) value 150.0, lo 50.0, hi 400.0, dist `:lognormal`, std 0.3. ✓

3. **Line 294-308**: `plateau_physics_uq_params()` overrides exactly three: `:V_peak_kV`, `:V_plateau_V`, `:n_pulses` where lo == hi == value. `:t_peak_us` is NOT overridden, so it keeps `[5, 50]`. ✓

4. **Line 319-348**: `_sample_physics_param` — `:fixed` returns `param.value` directly (line 321). ✓

5. **Line 355-357**: `_sample_all_params` returns `Dict(p.name => _sample_physics_param(p) for p in uq.params)` — one entry per param. ✓

6. **Line 373-378**: `_calculate_eroei` — EROEI anchor computation. Let me verify by tracing the code. The function signature is `_calculate_eroei(ΔBMP_pct, E_kWh_m3, w_TS, BMP_control)`. With args `(10.0, 1.0, 0.05, 250.0)`:
   - `VS_kg_per_m3 = 1020.0 * 0.05 * 0.75 = 38.25`
   - `add_CH4_mL = (10.0 / 100.0) * 250.0 * 38.25 * 1000 = 0.1 * 250.0 * 38.25 * 1000`
   - `0.1 * 250.0 = 25.0`, `25.0 * 38.25 = 956.25`, `956.25 * 1000 = 956250.0`
   - Wait, that doesn't match the stated 956250. Let me recheck: `0.1 * 250.0 * 38.25 * 1000 = 956250`. Yes.
   - `E_gain_kJ = 956250.0 * 0.0358 = 34233.75`
   - `E_input_kJ = 1.0 * 3600 = 3600.0`
   - `EROEI = 34233.75 / 3600.0 = 9.509375` ✓

7. **Line 561-690**: `run_physics_monte_carlo_proxy` has keywords `n_samples` (default 10000), `seed` (42), `verbose` (true), `convergence_threshold` (0.02), `BMP_control` (250.0). ✓

8. **Line 795-809**: `physics_uq_convergence_check` returns NamedTuple with keys `converged`, `n`, `eroei_rse`, `dbmp_rse`, `f_irrev_rse`. ✓

9. **Line 906-959**: `physics_uq_to_dict` returns Dict with keys "metadata", "f_irrev", "E_kWh_m3", "dT_max_K", "CH4_yield", "CH4_increase_pct", "EROEI", "probabilities", "sensitivity", "distributions". Wait — the task says six top-level keys plus "distributions" and "probabilities" and "sensitivity". But actually the metadata "n_total" maps to `r.n_total` (line 912). ✓

Now about the dual-load guard pattern in `test_waveform_library.jl` (lines 13-17):

```julia
if !@isdefined(Liquid)
    push!(LOAD_PATH, joinpath(@__DIR__, "..", ".."))
    include(joinpath(@__DIR__, "..", "..", "src", "liquid", "Liquid.jl"))
    using .Liquid
end
```

This is the standalone-capable header. The new test file should replicate this pattern exactly.

Now let me also note: the task says the include line goes in `test/liquid/runtests.jl` immediately after line 120 (`include("test_waveform_library.jl")`). Looking at line 120-121, the include is at line 120, and line 121 is blank. The new include goes at line 121 (or we insert a comment + include after line 120).

Now let me also note from runtests.jl: `CUDA_AVAILABLE` is defined (line 16), but the task says new tests must NOT depend on CUDA. That's fine — we won't reference it.

The new test file must use `Liquid._calculate_eroei` and `Liquid._sample_physics_param` etc. because the private functions are not exported — but since the file is included directly into `module Liquid`, the private functions are accessible as `Liquid._calculate_eroei` once `using .Liquid` is in effect. But wait, `_calculate_eroei` has no `_` in its definition that would make it private in Julia... actually the underscore is just a naming convention; the function is just defined at module scope. Since `monte_carlo_physics.jl` is included directly into `module Liquid` (per the task), these functions are `Liquid._calculate_eroei` etc.

Let me now produce the plan.

---

## PLAN

### 1. Goal

Create `test/liquid/test_monte_carlo_physics.jl` with ≥15 CPU-only, deterministic `@test` assertions covering physics UQ Monte Carlo (construction, defaults, plateau, sampling, EROEI, proxy run, convergence, round-trip), and add one include line to `test/liquid/runtests.jl` after line 120.

### 2. Files to Touch

| File | Change | Why |
|------|--------|-----|
| `test/liquid/runtests.jl` | Insert one comment line + one `include("test_monte_carlo_physics.jl")` line right after line 120 | Wire the new test into the liquid suite at the correct position |
| `test/liquid/test_monte_carlo_physics.jl` | Create new file (~140 lines) | The test suite itself; nothing else created |

No `src/` file is touched.

### 3. Ordered Steps for the Coder

#### Step A: Insert include line in `test/liquid/runtests.jl`

After line 120 (`    include("test_waveform_library.jl")`), insert:

```
    # Monte Carlo Physics UQ (proxy-only, CPU, deterministic)
    include("test_monte_carlo_physics.jl")
```

Use the `edit` tool: old_string is `include("test_waveform_library.jl")\n`, new_string adds the two new lines. Exact match: the include at line 120 appears exactly once, so no ambiguity.

#### Step B: Create `test/liquid/test_monte_carlo_physics.jl`

Use `write` tool to create the file from scratch. Structure:

1. **Header** (lines 1-8): docstring + `using Test`
2. **Standalone guard** (lines 10-14): copy-paste pattern from `test_waveform_library.jl` lines 13-17 exactly:
   ```julia
   if !@isdefined(Liquid)
       push!(LOAD_PATH, joinpath(@__DIR__, "..", ".."))
       include(joinpath(@__DIR__, "..", "..", "src", "liquid", "Liquid.jl"))
       using .Liquid
   end
   ```
3. **Single `@testset "Physics UQ Monte Carlo" begin ... end`** containing these test blocks:

   **Test 1 (Construction):** 
   ```julia
   p = PhysicsUQParam(:test, 1.0, 0.0, 2.0, :normal)
   @test p.std == 0.0
   @test p.unit == ""
   @test p.desc == ""
   @test p.distribution == :normal
   ```

   **Test 2 (Defaults):**
   ```julia
   d = default_physics_uq_params()
   @test length(d.params) == 13
   f_irrev = d.params[5]   # or find by name
   ```
   Actually, since `PhysicsUQParams.params` is a `Vector{PhysicsUQParam}`, we should find by name. Use:
   ```julia
   d = default_physics_uq_params()
   @test length(d.params) == 13
   # Find by name
   f_idx = findfirst(p -> p.name == :f_irrev_max, d.params)
   p = d.params[f_idx]
   @test p.value ≈ 0.65
   @test p.lo ≈ 0.35
   @test p.hi ≈ 0.95
   @test p.distribution == :normal
   @test p.std ≈ 0.15
   # E_threshold
   e_idx = findfirst(p -> p.name == :E_threshold_kJ_m3, d.params)
   p2 = d.params[e_idx]
   @test p2.value ≈ 95.0
   @test p2.lo ≈ 65.0
   @test p2.hi ≈ 155.0
   @test p2.distribution == :normal
   @test p2.std ≈ 20.0
   # w_TS
   w_idx = findfirst(p -> p.name == :w_TS, d.params)
   p3 = d.params[w_idx]
   @test p3.value ≈ 0.04
   @test p3.distribution == :triangular
   # tau2
   t_idx = findfirst(p -> p.name == :tau2, d.params)
   p4 = d.params[t_idx]
   @test p4.value ≈ 150.0
   @test p4.distribution == :lognormal
   @test p4.std ≈ 0.3
   # Config defaults
   @test d.geometry_type == :parallel
   @test d.gap_m == 0.025
   @test d.L_m == 0.050
   @test d.nr == 48
   @test d.nz == 24
   ```

   **Test 3 (Plateau):**
   ```julia
   q = plateau_physics_uq_params()
   # Three overridden params have lo == hi
   for name in [:V_peak_kV, :V_plateau_V, :n_pulses]
       idx = findfirst(p -> p.name == name, q.params)
       @test q.params[idx].lo == q.params[idx].hi
   end
   # t_peak_us still spans [5, 50]
   tp_idx = findfirst(p -> p.name == :t_peak_us, q.params)
   @test q.params[tp_idx].lo ≈ 5.0
   @test q.params[tp_idx].hi ≈ 50.0
   ```

   **Test 4 (Sampling):**
   ```julia
   Random.seed!(12345)
   # :fixed returns value exactly
   p_fixed = PhysicsUQParam(:f, 7.0, 1.0, 10.0, :fixed)
   @test Liquid._sample_physics_param(p_fixed) == 7.0
   # :normal clamped
   p_norm = PhysicsUQParam(:n, 5.0, 0.0, 10.0, :normal; std=2.0)
   for _ in 1:200
       v = Liquid._sample_physics_param(p_norm)
       @test 0.0 <= v <= 10.0
   end
   # :triangular in bounds (note: w_TS has lo 0.02, hi 0.08, value 0.04)
   p_tri = PhysicsUQParam(:t, 0.04, 0.02, 0.08, :triangular)
   for _ in 1:200
       v = Liquid._sample_physics_param(p_tri)
       @test 0.02 <= v <= 0.08
   end
   # :lognormal clamped
   p_ln = PhysicsUQParam(:ln, 150.0, 50.0, 400.0, :lognormal; std=0.3)
   for _ in 1:200
       v = Liquid._sample_physics_param(p_ln)
       @test 50.0 <= v <= 400.0
   end
   # _sample_all_params returns one entry per param
   uq = default_physics_uq_params()
   Random.seed!(42)
   d1 = Liquid._sample_all_params(uq)
   @test length(d1) == 13
   @test all(k -> haskey(d1, k), [p.name for p in uq.params])
   # Reproducibility
   Random.seed!(42)
   d2 = Liquid._sample_all_params(uq)
   @test d1 == d2
   ```

   Note on the 200-draw for :triangular with lo=0.02, hi=0.08, mode=0.04: the triangular inverse CDF stays within [lo, hi] by construction. But I need to be careful — the task says `triangular` uses `_sample_physics_param` which uses the inverse CDF. Let me re-read lines 327-339. Yes: `lo + sqrt(u * (hi - lo) * (mode - lo))` and `hi - sqrt((1 - u) * (hi - lo) * (hi - mode))` — both are clamped between lo and hi. The 200 draws test is a statistical check that no sample falls outside bounds. This is fine.

   However, wait: the task says 200 draws of `:normal`, `:lognormal` and `:triangular` all fall inside [lo, hi]. Since `:normal` and `:lognormal` use `clamp()`, they can return exactly lo or hi — and they can also return values at the boundary. The test only checks that values are within the inclusive range, which is fine.

   **Test 5 (EROEI):**
   ```julia
   @test Liquid._calculate_eroei(10.0, 1.0, 0.05, 250.0) ≈ 9.509375 atol=1e-12
   @test Liquid._calculate_eroei(0.0, 1.0, 0.05, 250.0) == 0.0
   ```

   **Test 6 (Proxy run):**
   ```julia
   Random.seed!(42)
   r = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
   @test r isa PhysicsUQResults
   @test r.n_total == 300
   @test 0 <= r.n_feasible <= 300
   @test length(r.EROEI_distribution) == r.n_feasible
   @test r.f_irrev_p5 <= r.f_irrev_p50 <= r.f_irrev_p95
   # Reproducibility
   Random.seed!(42)
   r2 = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
   @test r.f_irrev_mean == r2.f_irrev_mean
   ```

   **Test 7 (Convergence check):**
   ```julia
   cc = physics_uq_convergence_check(r)
   @test cc isa NamedTuple
   @test haskey(cc, :converged)
   @test haskey(cc, :n)
   @test haskey(cc, :eroei_rse)
   @test haskey(cc, :dbmp_rse)
   @test haskey(cc, :f_irrev_rse)
   @test cc.eroei_rse >= 0.0
   @test cc.dbmp_rse >= 0.0
   @test cc.f_irrev_rse >= 0.0
   ```

   **Test 8 (Round-trip):**
   ```julia
   dct = physics_uq_to_dict(r)
   @test haskey(dct, "metadata")
   @test haskey(dct, "f_irrev")
   @test haskey(dct, "E_kWh_m3")
   @test haskey(dct, "dT_max_K")
   @test haskey(dct, "CH4_yield")
   @test haskey(dct, "CH4_increase_pct")
   @test dct["metadata"]["n_total"] == 300
   ```

Wait — the task says "six top-level keys and metadata 'n_total' == 300". The six keys from the task are `f_irrev`, `E_kWh_m3`, `dT_max_K`, `CH4_yield`, `CH4_increase_pct`, and `metadata`. But looking at `physics_uq_to_dict` output (lines 907-959), it also has `EROEI`, `probabilities`, `sensitivity`, `distributions`. The task says "six top-level keys" — I'll check for the six specified.

Actually, re-reading the task: "physics_uq_to_dict(r) has the six top-level keys and metadata 'n_total' == 300". The six top-level keys listed in the facts above are the six output stat blocks: `f_irrev`, `E_kWh_m3`, `dT_max_K`, `CH4_yield`, `CH4_increase_pct`, and `metadata` or `EROEI`. Let me count: the task facts say the dict has keys "metadata" (containing "seed", "n_total", ...), "f_irrev", "E_kWh_m3", "dT_max_K", "CH4_yield", "CH4_increase_pct", each stats sub-dict... That's 6. But actually looking at the source, there are more keys. The task says "the six top-level keys" — I'll just test for the six specifically mentioned: "metadata", "f_irrev", "E_kWh_m3", "dT_max_K", "CH4_yield", "CH4_increase_pct". Plus "n_total" == 300.

Now let me count the assertions to ensure ≥15. Let me tally:

Test 1: 4 assertions
Test 2: 4 (f_irrev value, lo, hi, dist) + 1 (std) + 4 (E_threshold) + 2 (w_TS) + 3 (tau2) + 6 (config defaults) = 20? That's too many. Let me be more precise.

Actually, let me just ensure at least 15 `@test` lines total across all tests. Let me structure more carefully.

Let me also verify: `_sample_physics_param` for `:triangular` with lo=0.02, hi=0.08, value=0.04. The inverse CDF: `f_c = (0.04 - 0.02) / (0.08 - 0.02) = 0.02/0.06 = 1/3`. If `u < 1/3`: `lo + sqrt(u * (hi-lo) * (mode-lo))`. If `u >= 1/3`: `hi - sqrt((1-u)*(hi-lo)*(hi-mode))`. Both stay in [0.02, 0.08]. Good.

One concern: the `_sample_physics_param` for `:triangular` has `mode = clamp(mode, lo + 1e-10, hi - 1e-10)` (line 332). For our test params with lo=0.02, hi=0.08, mode=0.04: `lo + 1e-10 = 0.0200000001`, which is > 0.04, so `clamp(0.04, 0.0200000001, 0.0799999999) = 0.04`. OK, no modification.

Now, let me finalize the plan. The test file content will be:

```julia
# test/liquid/test_monte_carlo_physics.jl
"""
Tests for Physics UQ Monte Carlo (proxy-only, CPU, deterministic).
Covers: construction, default params, plateau override, sampling, EROEI,
proxy run, convergence check, and round-trip to dict.
"""

using Test
using Random
using Statistics

# Standalone guard: load Liquid module if not already loaded via runtests.jl
if !@isdefined(Liquid)
    push!(LOAD_PATH, joinpath(@__DIR__, "..", ".."))
    include(joinpath(@__DIR__, "..", "..", "src", "liquid", "Liquid.jl"))
    using .Liquid
end

@testset "Physics UQ Monte Carlo" begin

    # ── 1. Construction: convenience constructor defaults ──
    p = PhysicsUQParam(:test, 1.0, 0.0, 2.0, :normal)
    @test p.std == 0.0
    @test p.unit == ""
    @test p.desc == ""

    # ── 2. Defaults ──
    d = default_physics_uq_params()
    @test length(d.params) == 13
    # Anchors
    f_idx = findfirst(p -> p.name == :f_irrev_max, d.params)
    @test d.params[f_idx].value ≈ 0.65
    @test d.params[f_idx].lo ≈ 0.35
    @test d.params[f_idx].hi ≈ 0.95
    @test d.params[f_idx].distribution == :normal
    e_idx = findfirst(p -> p.name == :E_threshold_kJ_m3, d.params)
    @test d.params[e_idx].value ≈ 95.0
    @test d.params[e_idx].lo ≈ 65.0
    @test d.params[e_idx].hi ≈ 155.0
    @test d.params[e_idx].distribution == :normal
    w_idx = findfirst(p -> p.name == :w_TS, d.params)
    @test d.params[w_idx].value ≈ 0.04
    @test d.params[w_idx].distribution == :triangular
    t_idx = findfirst(p -> p.name == :tau2, d.params)
    @test d.params[t_idx].value ≈ 150.0
    @test d.params[t_idx].distribution == :lognormal
    @test d.params[t_idx].std ≈ 0.3
    # Config defaults
    @test d.geometry_type == :parallel
    @test d.gap_m == 0.025
    @test d.L_m == 0.050
    @test d.nr == 48
    @test d.nz == 24

    # ── 3. Plateau: three pulse params locked ──
    q = plateau_physics_uq_params()
    for name in [:V_peak_kV, :V_plateau_V, :n_pulses]
        idx = findfirst(p -> p.name == name, q.params)
        @test q.params[idx].lo == q.params[idx].hi
    end
    tp_idx = findfirst(p -> p.name == :t_peak_us, q.params)
    @test q.params[tp_idx].lo ≈ 5.0
    @test q.params[tp_idx].hi ≈ 50.0

    # ── 4. Sampling ──
    Random.seed!(12345)
    # :fixed returns value exactly
    p_fixed = PhysicsUQParam(:f, 7.0, 1.0, 10.0, :fixed)
    @test Liquid._sample_physics_param(p_fixed) == 7.0
    # :normal clamped within [lo, hi]
    p_norm = PhysicsUQParam(:n, 5.0, 0.0, 10.0, :normal; std=2.0)
    for _ in 1:200
        v = Liquid._sample_physics_param(p_norm)
        @test 0.0 <= v <= 10.0
    end
    # :triangular within [lo, hi]
    p_tri = PhysicsUQParam(:t, 0.04, 0.02, 0.08, :triangular)
    for _ in 1:200
        v = Liquid._sample_physics_param(p_tri)
        @test 0.02 <= v <= 0.08
    end
    # :lognormal clamped within [lo, hi]
    p_ln = PhysicsUQParam(:ln, 150.0, 50.0, 400.0, :lognormal; std=0.3)
    for _ in 1:200
        v = Liquid._sample_physics_param(p_ln)
        @test 50.0 <= v <= 400.0
    end
    # _sample_all_params: one entry per param, reproducible
    uq = default_physics_uq_params()
    Random.seed!(42)
    d1 = Liquid._sample_all_params(uq)
    @test length(d1) == 13
    @test all(k -> haskey(d1, k), [p.name for p in uq.params])
    Random.seed!(42)
    d2 = Liquid._sample_all_params(uq)
    @test d1 == d2

    # ── 5. EROEI ──
    @test Liquid._calculate_eroei(10.0, 1.0, 0.05, 250.0) ≈ 9.509375 atol=1e-12
    @test Liquid._calculate_eroei(0.0, 1.0, 0.05, 250.0) == 0.0

    # ── 6. Proxy run ──
    Random.seed!(42)
    r = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
    @test r isa PhysicsUQResults
    @test r.n_total == 300
    @test 0 <= r.n_feasible <= 300
    @test length(r.EROEI_distribution) == r.n_feasible
    @test r.f_irrev_p5 <= r.f_irrev_p50 <= r.f_irrev_p95
    # Reproducibility
    Random.seed!(42)
    r2 = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
    @test r.f_irrev_mean == r2.f_irrev_mean

    # ── 7. Convergence check ──
    cc = physics_uq_convergence_check(r)
    @test haskey(cc, :converged)
    @test haskey(cc, :n)
    @test haskey(cc, :eroei_rse)
    @test haskey(cc, :dbmp_rse)
    @test haskey(cc, :f_irrev_rse)
    @test cc.eroei_rse >= 0.0
    @test cc.dbmp_rse >= 0.0
    @test cc.f_irrev_rse >= 0.0

    # ── 8. Round-trip to dict ──
    dct = physics_uq_to_dict(r)
    @test haskey(dct, "metadata")
    @test haskey(dct, "f_irrev")
    @test haskey(dct, "E_kWh_m3")
    @test haskey(dct, "dT_max_K")
    @test haskey(dct, "CH4_yield")
    @test haskey(dct, "CH4_increase_pct")
    @test dct["metadata"]["n_total"] == 300

end
```

Let me count `@test` lines. I count them:

Test 1: 3
Test 2: 18
Test 3: 5
Test 4: 7 (but the for-loops produce many more — the 3×200 draws are 600 @test invocations, but they're in loops. Let me count "test lines" as lines with @test on them): let me count properly just the `@test` lines:

Test 1: lines with @test = 3
Test 2: 18
Test 3: 5
Test 4: 7 (`==`, `<=`, `<=`, `<=`, `==`, `==`, `==`) — but wait, the loops produce many more. Let me count unique `@test` lines:
- `@test Liquid._sample_physics_param(p_fixed) == 7.0` → 1
- `@test 0.0 <= v <= 10.0` inside loop → 1 but executed 200 times
- `@test 0.02 <= v <= 0.08` inside loop → 1 but executed 200 times  
- `@test 50.0 <= v <= 400.0` inside loop → 1 but executed 200 times
- `@test length(d1) == 13` → 1
- `@test all(...)` → 1
- `@test d1 == d2` → 1

Test 5: 2
Test 6: 6 (`isa`, `==`, `<=`, `==`, `<=`, `==`)
Test 7: 8 (5 haskey + 3 >=)
Test 8: 7 (6 haskey + 1 ==)

Total unique `@test` lines: 3+18+5+7+2+6+8+7 = 56. Well above 15. ✓

Now, about the `using Random` and `using Statistics` — we need `Random.seed!` and the test file uses `findfirst` (from Base). Actually `findfirst` is in Base, no import needed. `Random` we import for `Random.seed!`. `Statistics` we don't actually use directly (we use `run_physics_monte_carlo_proxy` which uses it internally).

Actually wait — should I import Random? The task says pattern the file after `test_waveform_library.jl`. That file only uses `using Test`. For `Random.seed!`, we can either do `using Random` or use `Random.seed!` fully qualified. Looking at the source code itself (line 403, 569), the module uses `using Random`. Since we have `using .Liquid`, `Random` is available through the module. But in the test file we call `Random.seed!` directly — we should import it. I'll add `using Random` to be safe.

Let me finalize and write the plan.

---

## FINAL PLAN

### Goal
Add a CPU-only, deterministic test suite for `src/liquid/monte_carlo_physics.jl` with ≥15 `@test` assertions, wired into `test/liquid/runtests.jl` immediately after the waveform library include at line 120.

### Files to touch
1. **`test/liquid/runtests.jl`** — insert one comment + one include line after line 120
2. **`test/liquid/test_monte_carlo_physics.jl`** — create new file (~125 lines)

Nothing else created or modified.

### Ordered steps

**Step 1:** Edit `test/liquid/runtests.jl` — use the `edit` tool with `old_string` exactly matching line 120 (`    include("test_waveform_library.jl")`) followed by the newline. `new_string` appends the comment `    # Monte Carlo Physics UQ (proxy-only, CPU, deterministic)` and the include `    include("test_monte_carlo_physics.jl")` on the next line. This old_string is unique (appears only at line 120).

**Step 2:** Create `test/liquid/test_monte_carlo_physics.jl` using `write` tool. Content as designed above: standalone-capable header matching `test_waveform_library.jl` pattern (dual-load guard, `using Test`, `using Random`), single `@testset "Physics UQ Monte Carlo"` with 8 sub-sections covering construction (3 tests), defaults (18 tests), plateau (5 tests), sampling (7 tests), EROEI (2 tests), proxy run (6 tests), convergence (8 tests), round-trip (7 tests). All CPU-only, all deterministic (seeded), `verbose=false`, `n_samples=300`.

**Step 3:** Run `julia_gate` on the workspace (or on `test/liquid/runtests.jl`). Report the gate's printed verdict line verbatim.

### Targeted tests and acceptance criterion

- **Gate target:** `test/liquid/runtests.jl` (or the full workspace — the gate will discover the new test through the include).
- **Acceptance criterion:** VERT (green) verdict. If ROUGE: report honestly, do NOT weaken assertions. If any assertion fails for a reason other than test logic (e.g., the source code's actual behavior differs from the documented expectation), keep the assertion and add a `# FAILS against src as of 2026-08-24:` comment with the measured value.

### Risks and what NOT to touch

- **Risk:** The proxy model's internal behavior at `n_samples=300, seed=42` could produce edge cases (e.g., `n_feasible == 0` making `f_irrev_p5` NaN). The `safe_mean`/`pctl` helpers handle empty arrays by returning 0.0, so `r.f_irrev_p5 <= r.f_irrev_p50 <= r.f_irrev_p95` should still hold (0.0 <= 0.0 <= 0.0). So this should be safe.
- **Risk:** The `@test r.f_irrev_mean == r2.f_irrev_mean` reproducibility test depends on the proxy model being fully deterministic given `Random.seed!`. The source calls `Random.seed!(seed)` at line 569, so two runs with the same seed should be byte-identical. This should work.
- **Do NOT touch:** `src/liquid/monte_carlo_physics.jl` (read-only), any other source file, any existing test file, `test/liquid/runtests.jl` beyond the single insert after line 120.
- **Do NOT call:** `run_physics_monte_carlo` (GPU path) — tests are proxy-only.
- **Do NOT depend on:** CUDA or `CUDA_AVAILABLE` flag.
- **Self-check after coder finishes:** verify that only `test/liquid/test_monte_carlo_physics.jl` was created, only one line was added to `test/liquid/runtests.jl` (the include + its comment), and no other files were modified anywhere.