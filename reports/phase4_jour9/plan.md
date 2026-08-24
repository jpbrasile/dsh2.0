Now I have all three files. Let me verify key facts:

1. **`src/liquid/monte_carlo_physics.jl`**: 960 lines. Let me verify:
   - Line 45-50: exports confirmed ✓
   - Line 228: `default_physics_uq_params()` ✓
   - Line 294: `plateau_physics_uq_params()` ✓
   - Line 319: `_sample_physics_param` ✓
   - Line 355: `_sample_all_params` ✓
   - Lines 369-371: constants ✓
   - Line 373: `_calculate_eroei` ✓
   - Line 561: `run_physics_monte_carlo_proxy` ✓
   - Line 795: `physics_uq_convergence_check` ✓
   - Line 906: `physics_uq_to_dict` ✓

2. **`test/liquid/test_waveform_library.jl`**: Pattern file. Let me note:
   - Lines 1-8: Docstring header
   - Line 10: `using Test`
   - Lines 13-17: Dual-load guard `if !@isdefined(Liquid)`
   - Line 19: `@testset "..." begin`
   - Symbols qualified as `Liquid.WaveformSpec` etc. — but in this file they use bare names since they're already `using .Liquid`. Looking at it: `WaveformSpec` at line 26 is bare — so within the `@testset`, names from `.Liquid` are available.

3. **`test/liquid/runtests.jl`**: 
   - Line 120: `include("test_waveform_library.jl")` — this is where we insert after
   - Lines 23-27: dual-load guard ✓
   - Line 16: `CUDA_AVAILABLE` — our tests must NOT depend on CUDA ✓

Now let me verify the EROEI hand-computed anchor. Let me trace through `_calculate_eroei`:
- `ΔBMP_pct = 10.0, E_kWh_m3 = 1.0, w_TS = 0.05, BMP_control = 250.0`
- `VS_kg_per_m3 = 1020.0 * 0.05 * 0.75 = 38.25` ✓
- `add_CH4_mL = (10.0/100.0) * 250.0 * 38.25 * 1000 = 0.1 * 250.0 * 38.25 * 1000`
  - = 25.0 * 38.25 * 1000 = 956.25 * 1000 = 956250.0 ✓
- `E_gain_kJ = 956250.0 * 0.0358 = 34233.75` ✓
- `E_input_kJ = 1.0 * 3600 = 3600.0`
- `EROEI = 34233.75 / 3600.0`
  - = 34233.75 / 3600 = 9.509375 ✓

Now let me also check: the `_calculate_eroei` function with `E_kWh_m3 = 0.0`:
- `E_input_kJ = 0.0 * 3600 = 0.0`
- `E_input_kJ > 0` → false → returns `0.0` ✓

Now let me check `physics_uq_convergence_check`. Looking at line 795-809:
- It returns a NamedTuple with keys `converged`, `n`, `eroei_rse`, `dbmp_rse`, `f_irrev_rse` ✓
- When n < 10: returns `(converged=false, n=n, eroei_rse=1.0, dbmp_rse=1.0, f_irrev_rse=1.0)` ✓

Now let me verify `PhysicsUQParam` convenience constructor. Lines 79-82:
```julia
function PhysicsUQParam(name, value, lo, hi, dist; std=0.0, unit="", desc="")
    return PhysicsUQParam(name, Float64(value), Float64(lo), Float64(hi),
                          dist, Float64(std), unit, desc)
end
```
The kwargs: `std=0.0, unit="", desc=""`. So calling with only positional args should give `std=0.0, unit="", desc=""`. ✓

Now let me carefully design the test file. I need to follow the pattern from `test_waveform_library.jl`:

Pattern:
1. File header docstring
2. `using Test`
3. Dual-load guard (standalone + runtests.jl)
4. `@testset "..." begin` ... `end`

For the test file, I need to use `Liquid.` prefix for private/unexported names. Let me check what is exported vs private:
- Exported: `PhysicsUQParam`, `PhysicsUQParams`, `default_physics_uq_params`, `plateau_physics_uq_params`, `PhysicsUQSample`, `PhysicsUQResults`, `run_physics_monte_carlo`, `run_physics_monte_carlo_proxy`, `print_physics_uq_report`, `physics_uq_to_dict`, `physics_uq_convergence_check`
- Private (need `Liquid.` prefix): `_calculate_eroei`, `_sample_physics_param`, `_sample_all_params`

Now let me construct the plan.

**Test 1: Construction** — `PhysicsUQParam` convenience constructor
```julia
p = Liquid.PhysicsUQParam(:test, 1.0, 0.0, 2.0, :fixed)
@test p.std == 0.0
@test p.unit == ""
@test p.description == ""
```

Wait, actually `PhysicsUQParam` is exported, so I can use it bare (it will be in scope via `using .Liquid`). But let me look at how the waveform test file qualifies symbols... In `test_waveform_library.jl`, `WaveformSpec` is used bare (line 26, 34), as are `li_waveform_specs`, `create_li_waveform`, etc. All are exported. So exported symbols are bare, private ones need `Liquid.` prefix.

But wait — since `monte_carlo_physics.jl` is `include`d directly into `module Liquid` at line 89 of `Liquid.jl`, all its exports become exports of `Liquid`, and its private symbols are accessible as `Liquid._calculate_eroei` etc.

Now let me plan the test file carefully:

```julia
# test/liquid/test_monte_carlo_physics.jl
"""
Tests for Monte Carlo physics UQ (src/liquid/monte_carlo_physics.jl).
Covers: types, default/plateau param sets, sampling, EROEI calculation,
proxy-based Monte Carlo, convergence check, and round-trip export.
CPU-only — no GPU dependencies.
"""

using Test
using Random
using Statistics

# Handle both standalone and runtests.jl execution
if !@isdefined(Liquid)
    push!(LOAD_PATH, joinpath(@__DIR__, "..", ".."))
    include(joinpath(@__DIR__, "..", "..", "src", "liquid", "Liquid.jl"))
    using .Liquid
end

@testset "Monte Carlo Physics UQ" begin
    # 1. Construction
    p = PhysicsUQParam(:test, 1.0, 0.0, 2.0, :fixed)
    @test p.std == 0.0
    @test p.unit == ""
    @test p.description == ""

    # 2. Defaults
    dp = default_physics_uq_params()
    @test length(dp.params) == 13
    # anchors
    f_irrev = dp.params[5]  # first material param
    @test f_irrev.name == :f_irrev_max
    @test f_irrev.value == 0.65
    @test f_irrev.lo == 0.35
    @test f_irrev.hi == 0.95
    @test f_irrev.distribution == :normal
    @test f_irrev.std == 0.15
    # ...
```

Hmm wait, I need to be careful about how to find params by index. Let me use a helper approach — find by name:

Actually, let me look at the params vector more carefully. The 13 params in order are:
1. `:V_peak_kV` (pulse, fixed)
2. `:V_plateau_V` (pulse, fixed)
3. `:n_pulses` (pulse, fixed)
4. `:t_peak_us` (pulse, fixed)
5. `:f_irrev_max` (material, normal)
6. `:E_threshold_kJ_m3` (material, normal)
7. `:sigma_base` (material, normal)
8. `:tau1` (material, lognormal)
9. `:tau2` (material, lognormal)
10. `:tau3` (material, lognormal)
11. `:CH4_yield_factor` (material, normal)
12. `:r_cell_um` (material, lognormal)
13. `:w_TS` (material, triangular)

I'll use a helper to find by name to be robust:
```julia
function find_param(params, name)
    idx = findfirst(p -> p.name == name, params)
    return params[idx]
end
```

Or simpler, just iterate. Let me write it cleanly:

```julia
# Find param helper for defaults test
p_by_name(name) = dp.params[findfirst(p -> p.name == name, dp.params)]
```

Now for the plateau test:
```julia
pp = plateau_physics_uq_params()
# The three overridden params have lo == hi
for name in (:V_peak_kV, :V_plateau_V, :n_pulses)
    p2 = pp.params[findfirst(p -> p.name == name, pp.params)]
    @test p2.lo == p2.hi
end
# t_peak_us still spans [5, 50]
t_peak = pp.params[findfirst(p -> p.name == :t_peak_us, pp.params)]
@test t_peak.lo == 5.0
@test t_peak.hi == 50.0
```

For sampling tests:
```julia
# :fixed returns value exactly
fp = dp.params[1]  # :V_peak_kV, :fixed
@test Liquid._sample_physics_param(fp) == 6.0

# bounds check
Random.seed!(12345)
fp_normal = p_by_name(:f_irrev_max)
for _ in 1:200
    s = Liquid._sample_physics_param(fp_normal)
    @test fp_normal.lo <= s <= fp_normal.hi
end
# triangular
fp_tri = p_by_name(:w_TS)
for _ in 1:200
    s = Liquid._sample_physics_param(fp_tri)
    @test fp_tri.lo <= s <= fp_tri.hi
end
# lognormal
fp_ln = p_by_name(:tau2)
for _ in 1:200
    s = Liquid._sample_physics_param(fp_ln)
    @test fp_ln.lo <= s <= fp_ln.hi
end
```

Wait, but I need to re-seed before each block for determinism. Let me track which tests need seeding.

For `_sample_all_params`:
```julia
Random.seed!(42)
d1 = Liquid._sample_all_params(dp)
@test length(d1) == 13
Random.seed!(42)
d2 = Liquid._sample_all_params(dp)
@test d1 == d2
```

For EROEI:
```julia
@test Liquid._calculate_eroei(10.0, 1.0, 0.05, 250.0) == 9.509375
@test Liquid._calculate_eroei(10.0, 0.0, 0.05, 250.0) == 0.0
```

Wait, is `==` reliable here? Let me check if Float64 arithmetic could cause issues. The computation is:
- `1020.0 * 0.05 * 0.75 = 38.25` — exact
- `0.1 * 250.0 * 38.25 * 1000 = 956250.0` — `0.1 * 250.0 = 25.0` exactly, `25.0 * 38.25 = 956.25` exactly, `956.25 * 1000 = 956250.0` exactly
- `956250.0 * 0.0358 = 34233.75` — `0.0358` is not exactly representable, but `956250.0 * 0.0358` might have a small error. Let me think...

Actually, let me compute: `0.0358` in IEEE 754: `0.0358 = 358/10000`, not exact. `956250 * 358 / 10000 = 342337500 / 10000 = 34233.75`. But in Float64, `956250.0 * 0.0358` might not be exactly `34233.75`.

Hmm, but `34233.75` IS exactly representable as Float64. And `0.0358 * 956250.0` — let me think about whether this is exact. `0.0358` in binary: the exact decimal 0.0358... let me not overthink this. The task says `atol 1e-12 or ==`. I'll use `≈` with `atol=1e-12` to be safe, plus mention the exact value in a comment. But the task says "the 9.509375 anchor exactly (atol 1e-12 or ==)". So I'll use:
```julia
@test Liquid._calculate_eroei(10.0, 1.0, 0.05, 250.0) ≈ 9.509375 atol=1e-12
```

Actually, wait. Let me think more carefully. The task says the hand-computed value is exact in Float64. Let me check: `34233.75 / 3600.0`. `34233.75` is exactly representable. `3600.0` is exactly representable. The division `34233.75 / 3600.0` in Float64... Let me compute: `34233.75 / 3600.0 = 3423375 / 360000 = 9.509375`. Is `9.509375` exactly representable in Float64? `9.509375 = 9509375 / 1000000`. Let me check: `9.509375 * 3600.0 = 34233.75`. This should be exact if `9.509375` is exactly representable. Actually, `9.509375 = 9 + 509375/1000000`. The denominator `1000000` is not a power of 2, so `9.509375` may not be exactly representable. But the product `9.509375 * 3600.0` needs to give exactly `34233.75`, and this depends on rounding. 

Let me just use `≈` with a small tolerance and a comment. I'll go with `atol=1e-12` as stated.

For the proxy run test (test 6):
```julia
Random.seed!(42)
r = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
@test r isa PhysicsUQResults
@test r.n_total == 300
@test 0 <= r.n_feasible <= 300
@test length(r.EROEI_distribution) == r.n_feasible
@test r.f_irrev_p5 <= r.f_irrev_p50 <= r.f_irrev_p95
# reproducibility
Random.seed!(42)
r2 = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
@test r2.f_irrev_mean == r.f_irrev_mean
```

Wait, do I also need to test the dual-load guard? Actually `run_physics_monte_carlo_proxy` is exported, so just call it.

For convergence check (test 7):
```julia
cc = physics_uq_convergence_check(r)
@test cc isa NamedTuple
@test haskey(cc, :converged)
@test haskey(cc, :n)
@test haskey(cc, :eroei_rse)
@test haskey(cc, :dbmp_rse)
@test haskey(cc, :f_irrev_rse)
@test cc.eroei_rse >= 0
@test cc.dbmp_rse >= 0
@test cc.f_irrev_rse >= 0
```

For round-trip (test 8):
```julia
d = physics_uq_to_dict(r)
@test haskey(d, "metadata")
@test haskey(d, "f_irrev")
@test haskey(d, "E_kWh_m3")
@test haskey(d, "dT_max_K")
@test haskey(d, "CH4_yield")
@test haskey(d, "CH4_increase_pct")
@test d["metadata"]["n_total"] == 300
```

Now let me count the assertions:
1. Construction: `p.std == 0.0`, `p.unit == ""`, `p.description == ""` → 3
2. Defaults: `length(dp.params) == 13` → 1; f_irrev_max: name, value, lo, hi, distribution, std → 6; E_threshold: I need all 4 anchors. Let me count carefully:
   - `length(dp.params) == 13`: 1
   - f_irrev_max: name, value, lo, hi, dist, std → 6
   - E_threshold_kJ_m3: value, lo, hi, dist, std → 5
   - w_TS: value, lo, hi, dist → 4
   - tau2: value, lo, hi, dist, std → 5
   - config defaults (I should test at least some): geometry_type, gap_m, L_m, nr, nz, T_initial, use_pavlin, use_ion_transport, C_ion_initial → I don't need all, but let me pick a few key ones as required: at least `dp.geometry_type == :parallel`, `dp.gap_m == 0.025`, `dp.L_m == 0.050`, `dp.nr == 48`, `dp.nz == 24`, `dp.T_initial == 293.15`, `dp.use_pavlin == true`, `dp.use_ion_transport == true`, `dp.C_ion_initial == 150.0` → but task says "config defaults as stated" — that's quite a few. Let me include all config defaults since they're one-liners each. That's 9 more. But the task says "at least 15", not a strict number.

Actually, let me re-read the task: "config defaults as stated" — I'll test all of them for thoroughness. That adds 9 assertions.

Let me re-count:
- Construction: 3
- Defaults length: 1
- f_irrev_max: 6
- E_threshold: 5
- w_TS: 4
- tau2: 5
- Config: 9
  That's already 33 for test 2 alone. But let me be more focused on what's explicitly asked.

Actually the task says the four anchors and config defaults "as stated," which means the values given in the task description. Let me just test what was listed explicitly:
- f_irrev_max: value 0.65, lo 0.35, hi 0.95, dist :normal, std 0.15
- E_threshold_kJ_m3: value 95.0, lo 65, hi 155, dist :normal, std 20.0
- w_TS: value 0.04, lo 0.02, hi 0.08, dist :triangular
- tau2: value 150.0, lo 50, hi 400, dist :lognormal, std 0.3

That's 5+5+4+5 = 19 for the anchors. Plus config = 9 more. But the task said "at least 15 @test assertions" — so I'm well over. Let me trim config to the key ones: geometry_type, gap_m, L_m, nr, nz, T_initial, use_pavlin, use_ion_transport, C_ion_initial — that's 9. But let me keep it reasonable.

OK, let me not over-optimize the counting. I should include all the required tests and let the count fall where it may. The "at least 15" is a floor.

Now, one concern: the task says `_sample_all_params` returns a `Dict{Symbol, Float64}`. Let me verify: line 355-357: `return Dict(p.name => _sample_physics_param(p) for p in uq.params)`. So it returns keys like `:f_irrev_max => Float64`. Yes.

Now the test for `_sample_all_params`:
```julia
Random.seed!(42)
d1 = Liquid._sample_all_params(dp)
@test length(d1) == 13
@test all(v -> v isa Float64, values(d1))
Random.seed!(42)
d2 = Liquid._sample_all_params(dp)
@test d1 == d2
```

Wait, that adds 3 more assertions. Good.

Let me finalize the test file plan. Let me think about what to include and verify each assertion will actually work.

One thing I need to verify: `isdefined` check. In the test file, `@isdefined(Liquid)` — this should work since `Liquid` is a module. When standalone, it's not defined so we load it. When included from `runtests.jl`, it's already defined. This is exactly the pattern from `test_waveform_library.jl`.

Now for the include in `runtests.jl`, I need to add after line 120:
```julia
    # Monte Carlo Physics UQ
    include("test_monte_carlo_physics.jl")
```

Now let me write the plan.

---

**PLAN**

## Goal
Write `test/liquid/test_monte_carlo_physics.jl` with CPU-only deterministic tests for the physics UQ Monte Carlo module, and wire it into `test/liquid/runtests.jl` after line 120.

## Files to touch

### 1. `test/liquid/test_monte_carlo_physics.jl` (NEW)
Create this file following the exact pattern of `test/liquid/test_waveform_library.jl`:
- Docstring header
- `using Test`, `using Random`, `using Statistics`
- Dual-load guard (lines 13-17 pattern)
- Single `@testset "Monte Carlo Physics UQ" begin ... end`

Tests inside @testset:

**Test 1 — Construction (3 assertions):**
- `PhysicsUQParam(:test, 1.0, 0.0, 2.0, :fixed)` — verify `std == 0.0`, `unit == ""`, `desc == ""` (the convenience constructor defaults).

**Test 2 — Defaults (~28 assertions):**
- `length(dp.params) == 13`
- Find params by name via `findfirst(p -> p.name == name, dp.params)`
- Four anchors verified:
  - `:f_irrev_max`: value 0.65, lo 0.35, hi 0.95, distribution `:normal`, std 0.15
  - `:E_threshold_kJ_m3`: value 95.0, lo 65.0, hi 155.0, distribution `:normal`, std 20.0
  - `:w_TS`: value 0.04, lo 0.02, hi 0.08, distribution `:triangular`
  - `:tau2`: value 150.0, lo 50.0, hi 400.0, distribution `:lognormal`, std 0.3
- Config defaults: `dp.geometry_type == :parallel`, `dp.gap_m == 0.025`, `dp.L_m == 0.050`, `dp.nr == 48`, `dp.nz == 24`, `dp.T_initial == 293.15`, `dp.use_pavlin == true`, `dp.use_ion_transport == true`, `dp.C_ion_initial == 150.0`

**Test 3 — Plateau (4 assertions):**
- `plateau_physics_uq_params()`: for `:V_peak_kV`, `:V_plateau_V`, `:n_pulses`, `lo == hi`
- `:t_peak_us` still has `lo == 5.0` and `hi == 50.0`

**Test 4 — Sampling (~10 assertions):**
- `_sample_physics_param` on a `:fixed` param returns `value` exactly
- With `Random.seed!(12345)`, 200 draws each of `:normal` (`:f_irrev_max`), `:lognormal` (`:tau2`), `:triangular` (`:w_TS`) all within `[lo, hi]` (3 assertions + 3 loop blocks)
- `_sample_all_params` returns Dict with 13 entries, all values `Float64`
- Reseed `Random.seed!(42)` reproduces identical Dict: `d1 == d2`

**Test 5 — EROEI (2 assertions):**
- `Liquid._calculate_eroei(10.0, 1.0, 0.05, 250.0) ≈ 9.509375 atol=1e-12`
- `Liquid._calculate_eroei(10.0, 0.0, 0.05, 250.0) == 0.0`

**Test 6 — Proxy run (~7 assertions):**
- `r = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)`
- `r isa PhysicsUQResults`, `r.n_total == 300`, `0 <= r.n_feasible <= 300`
- `length(r.EROEI_distribution) == r.n_feasible`
- `r.f_irrev_p5 <= r.f_irrev_p50 <= r.f_irrev_p95`
- Second run with same seed: `r2.f_irrev_mean == r.f_irrev_mean`

**Test 7 — Convergence check (~7 assertions):**
- `cc = physics_uq_convergence_check(r)`
- `cc isa NamedTuple` with keys `:converged`, `:n`, `:eroei_rse`, `:dbmp_rse`, `:f_irrev_rse`
- RSE values `>= 0`

**Test 8 — Round-trip (~7 assertions):**
- `d = physics_uq_to_dict(r)`
- Has keys `"metadata"`, `"f_irrev"`, `"E_kWh_m3"`, `"dT_max_K"`, `"CH4_yield"`, `"CH4_increase_pct"`
- `d["metadata"]["n_total"] == 300`

Total: well over 15 assertions.

**Honesty rule:** If any assertion fails against source, mark with `# FAILS against src as of 2026-08-24:` plus measured value.

### 2. `test/liquid/runtests.jl` (EDIT at line 120)
After line 120 (`include("test_waveform_library.jl")`), insert exactly:
```julia

    # Monte Carlo Physics UQ
    include("test_monte_carlo_physics.jl")
```
(blank line, comment, include — preserving indentation at the `include` level inside `@testset`)

## Ordered steps for the coder

1. **Read** `test/liquid/runtests.jl` to confirm line 120 content hasn't drifted (but it was just read — use the known content from this session).
2. **Create** `test/liquid/test_monte_carlo_physics.jl` with all tests as specified above.
3. **Edit** `test/liquid/runtests.jl`: insert the include line after line 120.
4. **Call `julia_gate`** ONCE on the workspace (or on `test/liquid/`). Expect ORANGE (budget timeout on CUDA suite — expected and accepted). Quote the verdict verbatim.
5. **Write `DONE.md`** with the verdict and a self-check confirming no other files were modified.

## Targeted tests for gate replay
- `test/liquid/runtests.jl` — includes the new file; the gate runs the full liquid suite.

## Acceptance criterion
- Two files changed exactly as specified (new test file, one include line added).
- Single `julia_gate` call returns ORANGE with no explicit test failures (ORANGE = budget timeout, expected for this CUDA suite).
- If ROUGE or explicit test failure: report honestly in DONE.md.

## Risks and what NOT to touch
- **NEVER call `run_physics_monte_carlo`** (GPU path) — use only `run_physics_monte_carlo_proxy`.
- **Do NOT touch `src/`** at all — the source module is untouchable.
- **Do NOT add CUDA-dependent tests** — the new tests must work without CUDA.
- Gate will return ORANGE by construction (30s budget exceeded by CUDA suite); do not retry.
- `_sample_physics_param` and `_calculate_eroei` are private — access as `Liquid._sample_physics_param` etc.
- The `_calculate_eroei` anchor `9.509375` may have a tiny Float64 rounding difference — use `≈ atol=1e-12`, not `==`. If it fails even with that tolerance, mark honestly per the honesty rule.