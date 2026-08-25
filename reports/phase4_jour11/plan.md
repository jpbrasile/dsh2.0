Now I have all three files. Let me analyze them carefully to produce the plan.

Key observations from the source:

1. **Source module** (`ar_ion_chemistry_3d.jl`): Uses `using CUDA` at top. Exports nothing explicitly — the module is included into `GPU3DIntegration.jl`. The state struct fields are exactly: `n_Ar_plus`, `n_Ar2_plus`, `ne_afterglow`, `S_ArS_recycle`, `S_e_recomb`, `dims`. The kernel and stepping functions are all internal (not exported from the module file). The CPU fallback for `step_ar_ion_chemistry!` dispatches on `Array` (not `CuArray`), so `use_gpu=false` gives us `Array` types and hits the CPU path.

2. **Test convention** (`test_ozone_3d.jl`): The include-if-not-defined guard uses `@__MODULE__` and `@isdefined`, then includes `../../../src/gpu3d_integration/GPU3DIntegration.jl`. This is the pattern to follow.

3. **runtests.jl**: The chemistry includes are on lines 34-37 and 44. The new include should go near the other `chemistry/test_*` lines — between line 37 (`test_nox_ozone_coupling.jl`) and line 44 (`test_air_plasma_chemistry.jl`) would be consistent with alphabetical ordering, but since the file is `test_ar_ion_chemistry_3d.jl`, it goes before `test_ion_conversion_3d.jl` (line 35) alphabetically. Actually, looking more carefully: the chemistry includes are at lines 34-37 and line 44, with the comment block between. The correct insertion point is after line 37 (`test_nox_ozone_coupling.jl`) to keep all chemistry tests contiguous, or alphabetically between lines 34 and 35. I'll put it alphabetically: between `test_air_plasma_chemistry.jl` (line 44) and the gap above. Actually, it should go — looking at the order: `test_ozone_3d.jl`, `test_ion_conversion_3d.jl`, `test_nox_chemistry_3d.jl`, then after the comment gap, `test_nox_ozone_coupling.jl`, `test_air_plasma_chemistry.jl`. Alphabetically, `test_ar_ion_chemistry_3d.jl` comes before `test_ion_conversion_3d.jl`, so it should be inserted between line 34 and line 35.

Now let me trace through the contract's numerical anchors:

**Contract (a)**: `k_cluster == 2.5e-43` — matches line 35. `alpha_dr_300 ≈ 8.5e-13f0` — line 38 has `8.5e-13` as Float64, config stores it as `T(ALPHA_DR_300)` which would be `Float32(8.5e-13)`. `dr_exponent ≈ -0.67f0` — line 39. `D_a ≈ 2.0e-2f0` — line 42. `T_e ≈ 11600f0` — default is 11600.0, `N_gas ≈ 2.4463134e25` — computed as `101325.0 / (1.380649e-23 * 300.0)` = `101325.0 / 4.141947e-21` = `2.4463134e25`. Correct.

**Contract (b)**: `Float32(k_cluster * Float64(N_gas)^2)` — `k_cluster_eff = T(config.k_cluster * Float64(config.N_gas)^2)` at line 282/317. `2.5e-43 * (2.4463134e25)^2` = `2.5e-43 * 5.984448e50` = `1.496112e8`. As Float32: `1.49611232e8`. The alpha_dr: `Float32(8.5e-13 * (11600/300)^(-0.67))`. `11600/300 = 38.666...`. `38.666^(-0.67) = exp(-0.67 * ln(38.666)) = exp(-0.67 * 3.65488) = exp(-2.44877) = 0.086394...`. `8.5e-13 * 0.086394 = 7.34349e-14`. Float32: `≈ 7.3435032e-14`.

**Contract (c)**: `create_ar_ion_chemistry_state((2,2,2); use_gpu=false)` returns Arrays of zeros, dims stored. `reset_ar_ion_chemistry_state!` zeroes — line 129-136.

**Contract (d)**: Single-cell pulse step. The CPU fallback at lines 305-344 is what executes. With `n_Ar_plus .= 1f18, n_Ar2_plus .= 0, ne_ext = fill(1f18,...), X_Ar = fill(1f0,...), dt = 1e-6, afterglow=false`:
- `k_cluster_eff ≈ 1.49611232e8` (Float32)
- `xar = 1.0f0`
- `k_loss_Ap = k_cluster_eff * 1.0 * 1.0 = 1.49611232e8`
- `n_Ap_new = 1f18 / (1 + 1.49611232e8 * 1e-6) = 1f18 / (1 + 149.611) = 1f18 / 150.611 ≈ 6.639611e15`
- `S_cluster = k_loss_Ap * (1f18 + 6.639611e15) * 0.5 = 1.49611232e8 * 1.00332e18 * 0.5 ≈ 7.503e25` — wait, that seems too high. Let me recalculate more carefully.

Actually: `k_loss_Ap * (n_Ap + n_Ap_new) * 0.5 = 1.49611232e8 * (1e18 + 6.6396e15) * 0.5`. Since `1e18` dominates, `≈ 1.49611232e8 * 1e18 * 0.5 = 7.48056e25`. But the contract says `S_ArS_recycle ≈ 2.5757618e24`. That's an order of magnitude difference — let me re-trace.

Wait, `S_cluster` is the source term for Ar₂⁺ from clustering. Then `n_A2p_new = (n_A2p + S_cluster * dt) / (1 + k_loss_A2p * dt)`. With `n_A2p = 0`, `S_cluster ≈ 7.48e25`, `dt = 1e-6`, `alpha_dr ≈ 7.3435e-14`, `n_e = 1f18`:
- `k_loss_A2p = 7.3435e-14 * 1e18 = 7.3435e4`
- `n_A2p_new = (0 + 7.48e25 * 1e-6) / (1 + 7.3435e4 * 1e-6) = 7.48e19 / (1 + 7.3435e-2) = 7.48e19 / 1.073435 ≈ 6.97e19`

Hmm, contract says `n_Ar2_plus ≈ 7.0150768e19`. Close but let me be more precise with Float32.

Actually, I need to trace this more carefully with Float32 rounding. But I have the source — the coder will run this and measure. The contract says to assert at `rtol 1e-6`. The coder should compute these from the actual state after the step.

And `S_ArS_recycle`: `alpha_dr * n_e * n_A2p_avg = 7.3435e-14 * 1e18 * 3.5075e19 ≈ 2.5758e24` — yes, that matches the contract!

And the identity: `S_ArS_recycle == S_e_recomb` — from lines 210-211: `S_ArS_recycle[ix,iy,iz] = max(T(0), S_recycle)` and `S_e_recomb[ix,iy,iz] = max(T(0), S_recomb)` where `S_recomb = S_recycle` (line 205), so yes, they are identical. On CPU fallback (line 339-340) same pattern: `S_recycle = ...` and `S_e_recomb` gets same value.

The implicit-update cross-check: `n_Ap_new = n / (1 + k_eff * X_Ar^2 * dt)`. So `n_Ar_plus` after step should equal `1f18 / (1 + 1.49611232e8 * 1.0^2 * 1e-6)` ≈ `6.639611e15`.

**Contract (e)**: Afterglow step. `n_Ar_plus .= 5f17, n_Ar2_plus .= 5f17, ne_ext ignored, dt=1e-6, afterglow=true`:
- `ne = max(0, 5e17 + 5e17) = 1e18`
- `n_Ap_new = 5e17 / (1 + 1.49611232e8 * 1e-6) = 5e17 / 150.611 ≈ 3.3198e15`
- Compute `S_cluster` and `n_A2p_new` — the contract anchors say `n_Ar_plus ≈ 3.3198054e15, n_Ar2_plus ≈ 3.5541181e19`.

**Contract (g)**: Ambipolar diffusion. `dx=dy=dz=1e-4`, uniform field — zero Laplacian, unchanged. Single peak on `(3,3,3)` with dims `(3,3,3)` — need to check: kernel uses `n_out[ix,iy,iz] = max(T(0), n_c + D_a * dt * lap)`. For a peak at center surrounded by zeros, `lap = (0 - 2*1e18 + 0)/1e-8 + ... = -6e18 / 1e-8 = -6e26`. With `D_a = 2e-2, dt = 1e-7`: `n_c + D_a * dt * lap = 1e18 + 2e-2 * 1e-7 * (-6e26) = 1e18 - 1.2e18 = -2e17`. Since `max(0, ...)`: result is 0. That's the contract's claim of "center after ≈ 0 EXACTLY". Face neighbor: a cell at (2,3,3) has `n_c=0, n_xp=1e18, n_xm=0` (Neumann at boundary: `ix > 1 ? n[ix-1,...] : n_c` = 0), so `lap = (1e18 - 2*0 + 0)/1e-8 = 1e26`. `0 + 2e-2 * 1e-7 * 1e26 = 2e17`. Contract says `≈ 2.0e17` at rtol 1e-6.

Now for the test file structure. The include path from `test/gpu3d_integration/chemistry/test_ar_ion_chemistry_3d.jl` to the module: same as `test_ozone_3d.jl` → `../../../src/gpu3d_integration/GPU3DIntegration.jl`.

One thing I need to verify: the `step_ambipolar_diffusion!` CPU fallback at line 388 doesn't use `inv_dx2`/`inv_dy2`/`inv_dz2` — it computes `dx^2` directly (line 410). So the call signature for CPU is `step_ambipolar_diffusion!(state, config, dt, dx, dy, dz)` — same as GPU. Good.

Also: `ar_ion_chemistry_diagnostics` converts to `Array` (line 431-434) — this is safe on CPU since the arrays are already `Array`. The output is a NamedTuple with exactly 7 keys as listed in contract (i).

Now let me verify: the module `ar_ion_chemistry_3d.jl` is included by `GPU3DIntegration.jl`. The functions `default_ar_ion_chemistry_config`, `create_ar_ion_chemistry_state`, `reset_ar_ion_chemistry_state!`, `step_ar_ion_chemistry!`, `step_ambipolar_diffusion!`, `ar_ion_chemistry_diagnostics` are all brought into `GPU3DIntegration` scope. The test file `using .GPU3DIntegration` makes them available.

Risk: the source has `using CUDA` on line 28. But the test will `using CUDA` too — that's fine. The CPU fallback doesn't call CUDA functions. When `use_gpu=false`, `CUDA.functional()` is not called in `create_ar_ion_chemistry_state` (line 115), so it returns `Array`.

Now the plan:

---

## IMPLEMENTATION PLAN

### READING ORDER (coder reads these 3 files first, in this order):
1. `src/gpu3d_integration/ar_ion_chemistry_3d.jl` — the module under test
2. `test/gpu3d_integration/chemistry/test_ozone_3d.jl` — convention model
3. `test/gpu3d_integration/runtests.jl` — where the include goes

### FILE 1: `test/gpu3d_integration/chemistry/test_ar_ion_chemistry_3d.jl` (NEW)

**Header docstring** (copy pattern from test_ozone_3d.jl lines 1-14):
```
# test/gpu3d_integration/chemistry/test_ar_ion_chemistry_3d.jl
"""
Tests for Ar⁺/Ar₂⁺ ion chemistry (Phase 22).

Tests:
1. Configuration — literature constants verification
2. Derived rates — precomputed effective rates
3. State allocation and reset
4. Single-cell pulse step with anchor values
5. Afterglow step with quasi-neutrality
6. Positivity after all steps
7. Ambipolar diffusion
8. Disabled config no-op
9. Diagnostics NamedTuple
10. Determinism — identical runs from identical state
"""
```

**Include guard** (exact copy from test_ozone_3d.jl lines 21-30):
```
using Test
using CUDA

if !isdefined(@__MODULE__, :GPU3DIntegration)
    if !@isdefined(GPU3DIntegration)
        include("../../../src/gpu3d_integration/GPU3DIntegration.jl")
        using .GPU3DIntegration
    end
end
```

**@testset structure** — one outer `@testset "Ar⁺/Ar₂⁺ Ion Chemistry 3D"` containing these inner `@testset` blocks:

#### @testset "a) Configuration constants"
- `config = default_ar_ion_chemistry_config()` (returns Float32 config by default)
- `@test config.k_cluster == 2.5e-43` (Float64 stored in struct)
- `@test config.alpha_dr_300 ≈ 8.5e-13f0`
- `@test config.dr_exponent ≈ -0.67f0`
- `@test config.D_a ≈ 2.0e-2f0`
- `@test config.T_e ≈ 11600f0`
- `@test config.N_gas ≈ 2.4463134e25f0 rtol=1e-6`
- `@test config.enabled == true`

#### @testset "b) Derived rates"
- `config = default_ar_ion_chemistry_config()`
- Compute `k_cluster_eff = Float32(config.k_cluster * Float64(config.N_gas)^2)` — this matches what `step_ar_ion_chemistry!` computes internally
- `@test k_cluster_eff ≈ 1.49611232f8 rtol=1e-6`
- Compute `alpha_dr = Float32(Float64(config.alpha_dr_300) * (Float64(config.T_e)/300.0)^Float64(config.dr_exponent))`
- `@test alpha_dr ≈ 7.3435032f-14 rtol=1e-6`

#### @testset "c) State allocation and reset"
- `state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)`
- `@test eltype(state.n_Ar_plus) == Float32`
- `@test size(state.n_Ar_plus) == (2,2,2)`
- `@test state.dims == (2,2,2)`
- `@test all(state.n_Ar_plus .== 0.0f0)`
- `@test all(state.n_Ar2_plus .== 0.0f0)`
- `@test all(state.ne_afterglow .== 0.0f0)`
- `@test all(state.S_ArS_recycle .== 0.0f0)`
- `@test all(state.S_e_recomb .== 0.0f0)`
- Dirty the state: `fill!(state.n_Ar_plus, 1f18)`, then `reset_ar_ion_chemistry_state!(state)`
- `@test all(state.n_Ar_plus .== 0.0f0)` (and all other fields are zero)

#### @testset "d) Single-cell pulse step"
- `config = default_ar_ion_chemistry_config()`
- `state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)`
- `state.n_Ar_plus .= 1f18`
- `state.n_Ar2_plus .= 0.0f0`
- `ne_ext = fill(1f18, 2, 2, 2)`
- `X_Ar = fill(1f0, 2, 2, 2)`
- `step_ar_ion_chemistry!(state, config, ne_ext, X_Ar, 1e-6; afterglow=false)`
- `@test state.n_Ar_plus[1,1,1] ≈ 6.639611f15 rtol=1e-6`
- `@test state.n_Ar2_plus[1,1,1] ≈ 7.0150768f19 rtol=1e-6`
- `@test state.S_ArS_recycle[1,1,1] ≈ 2.5757618f24 rtol=1e-6`
- `@test state.S_ArS_recycle[1,1,1] == state.S_e_recomb[1,1,1]` (exact equality)
- Cross-check the implicit update: compute `k_eff = Float32(config.k_cluster * Float64(config.N_gas)^2)`, then `expected = Float32(1f18 / (1 + k_eff * 1f0^2 * 1e-6))` and `@test state.n_Ar_plus[1,1,1] ≈ expected rtol=1e-6`

#### @testset "e) Afterglow step"
- `config = default_ar_ion_chemistry_config()`
- `state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)`
- `state.n_Ar_plus .= 5f17`
- `state.n_Ar2_plus .= 5f17`
- `ne_ext = fill(0f0, 2, 2, 2)` (ignored in afterglow, but must be same type)
- `X_Ar = fill(1f0, 2, 2, 2)`
- `step_ar_ion_chemistry!(state, config, ne_ext, X_Ar, 1e-6; afterglow=true)`
- `@test state.ne_afterglow[1,1,1] ≈ 1.0f18 rtol=1e-6` (quasi-neutrality: 5e17+5e17)
- `@test state.n_Ar_plus[1,1,1] ≈ 3.3198054f15 rtol=1e-6`
- `@test state.n_Ar2_plus[1,1,1] ≈ 3.5541181f19 rtol=1e-6`

#### @testset "f) Positivity"
- After the pulse step in (d), `@test all(state.n_Ar_plus .>= 0)` and `@test all(state.n_Ar2_plus .>= 0)` and `@test all(state.S_ArS_recycle .>= 0)` and `@test all(state.S_e_recomb .>= 0)`
- After the afterglow step in (e), same four positivity checks
- **DO NOT** assert ion-number conservation. Add a comment:
  ```
  # NOTE: Ion number is NOT conserved across the clustering step.
  # The operator-split semi-implicit source term over-produces Ar2+ for
  # stiff dt. With dt=1e-6, X_Ar=1, n_Ar2+ reaches ~7.015e19 from
  # 1e18 total initial ions. This is measured behaviour, not a defect.
  ```

#### @testset "g) Ambipolar diffusion"
- `config = default_ar_ion_chemistry_config()`
- `state = create_ar_ion_chemistry_state((3,3,3); use_gpu=false)`
- **Uniform field test**: `state.n_Ar_plus .= 1f18; state.n_Ar2_plus .= 1f18`
- `step_ambipolar_diffusion!(state, config, 1e-7, 1e-4, 1e-4, 1e-4)`
- `@test all(state.n_Ar_plus .== 1f18)` (zero Laplacian, exact equality)
- `@test all(state.n_Ar2_plus .== 1f18)`
- **Single peak test**: reset state, `state.n_Ar_plus .= 0f0; state.n_Ar_plus[3,3,3] = 1f18`
- `step_ambipolar_diffusion!(state, config, 1e-7, 1e-4, 1e-4, 1e-4)`
- `@test state.n_Ar_plus[3,3,3] == 0.0f0` (exact — the max(0,·) clamp engages)
- `@test state.n_Ar_plus[2,3,3] ≈ 2.0f17 rtol=1e-6`
- `@test all(state.n_Ar_plus .>= 0)` (no negative densities)

#### @testset "h) Disabled config"
- `config_disabled = default_ar_ion_chemistry_config(enabled=false)`
- `state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)`
- `state.n_Ar_plus .= 1f18`
- `ne_ext = fill(1f18, 2, 2, 2)`
- `X_Ar = fill(1f0, 2, 2, 2)`
- `step_ar_ion_chemistry!(state, config_disabled, ne_ext, X_Ar, 1e-6; afterglow=false)`
- `@test all(state.n_Ar_plus .== 1f18)` (strict no-op)
- `@test all(state.n_Ar2_plus .== 0.0f0)`
- Same test for `step_ambipolar_diffusion!` with disabled config → arrays unchanged

#### @testset "i) Diagnostics"
- `config = default_ar_ion_chemistry_config()`
- `state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)`
- `state.n_Ar_plus .= [1f18 0f0; 0f0 0f0][:,:,1]` or simpler: set a known pattern
- Actually simpler: just use the state from the pulse test (d) — the arrays already have values
- `diag = ar_ion_chemistry_diagnostics(state)`
- `@test diag isa NamedTuple`
- `@test keys(diag) == (:Ar_plus_peak, :Ar_plus_total, :Ar2_plus_peak, :Ar2_plus_total, :S_ArS_recycle_peak, :S_ArS_recycle_total, :ne_afterglow_peak)`
- `@test diag.Ar_plus_peak ≈ Float32(maximum(state.n_Ar_plus))`
- `@test diag.Ar_plus_total ≈ Float32(sum(state.n_Ar_plus))`
- `@test diag.Ar2_plus_peak ≈ Float32(maximum(state.n_Ar2_plus))`
- `@test diag.Ar2_plus_total ≈ Float32(sum(state.n_Ar2_plus))`
- `@test diag.S_ArS_recycle_peak ≈ Float32(maximum(state.S_ArS_recycle))`
- `@test diag.S_ArS_recycle_total ≈ Float32(sum(state.S_ArS_recycle))`
- `@test diag.ne_afterglow_peak ≈ Float32(maximum(state.ne_afterglow))`

#### @testset "j) Determinism"
- Create two identical `state1`, `state2` from the same initial conditions
- Run the pulse step on both
- `@test state1.n_Ar_plus == state2.n_Ar_plus` (all arrays equal)
- `@test state1.n_Ar2_plus == state2.n_Ar2_plus`
- `@test state1.S_ArS_recycle == state2.S_ArS_recycle`

**Closing line** (copy pattern from test_ozone_3d.jl line 401):
```
println("\nAr⁺/Ar₂⁺ Ion Chemistry 3D tests complete!")
```

### FILE 2: `test/gpu3d_integration/runtests.jl` (ONE EXACT INCLUDE ADDED)

**Insert location**: After line 34 (`include("chemistry/test_ozone_3d.jl")`) and before line 35 (`include("chemistry/test_ion_conversion_3d.jl")`), to maintain alphabetical order of chemistry test files.

**Exact line to insert** (as line 35, shifting everything else down):
```
    include("chemistry/test_ar_ion_chemistry_3d.jl")
```

### RISK LIST (coder must verify by reading source before writing):

1. **Field names in state struct**: The contract references `state.n_Ar_plus`, `state.n_Ar2_plus`, `state.ne_afterglow`, `state.S_ArS_recycle`, `state.S_e_recomb`, `state.dims`. Verify these are the actual field names by reading lines 98-105 of the source. CONFIRMED from source: yes, these are the exact field names.

2. **`S_e_recomb` exposed**: The contract asserts `S_ArS_recycle == S_e_recomb`. Verify that `state.S_e_recomb` is a public field. CONFIRMED: line 103, field `S_e_recomb::A`.

3. **`ne_ext`/`X_Ar` API**: The contract says `ne_ext = fill(1f18,...)`. The stepping function takes `ne_ext::A` and `X_Ar_3d::A` where `A` is the array type (line 271-272 for GPU, line 308-309 for CPU). So they must be the same array type as the state arrays. With `use_gpu=false`, that's `Array{Float32,3}`. CONFIRMED.

4. **`step_ambipolar_diffusion!` signature**: The contract calls with `(state, config, dt, dx, dy, dz)`. Verify the CPU fallback signature at lines 388-392 — it takes exactly these arguments. CONFIRMED.

5. **Include guard mechanism**: The `test_ozone_3d.jl` guard checks `@__MODULE__` and `@isdefined(GPU3DIntegration)`. The same pattern works for any chemistry test file included from `runtests.jl`. Since `runtests.jl` does `using .GPU3DIntegration` on line 18 BEFORE any test includes, `GPU3DIntegration` will already be defined when included through `runtests.jl`. The guard must correctly skip the re-include. CONFIRMED from test_ozone_3d.jl pattern.

6. **Float32 vs Float64 in test comparisons**: The state arrays are `Array{Float32,3}` (default `T=Float32`). The config stores `k_cluster` as `Float64` (line 55) and `k_cluster_eff` is computed as `T(config.k_cluster * Float64(config.N_gas)^2)` where `T=Float32`. The diagnostics return `Float32` values (through `Array()` conversion, then `maximum`/`sum`). The contract anchor values like `6.639611f15` use `f` suffix for Float32. CONFIRMED.

7. **`ne_afterglow` in afterglow mode**: In the kernel (line 175-178) and CPU fallback (line 325-326), `ne_afterglow[ix,iy,iz]` is always set to `max(T(0), n_Ap + n_A2p)` regardless of `afterglow` flag. But `n_e` (used for DR) selects differently. So `ne_afterglow` reflects quasi-neutrality in both modes, but is only USED as `n_e` in afterglow mode. CONFIRMED from source.

8. **`afterglow` kwarg type**: The GPU method takes `afterglow::Bool` (line 274), the CPU method takes `afterglow::Bool` (line 311). CONFIRMED.

9. **Diffusion kernel on (3,3,3) grid — boundary handling**: The kernel at lines 240-246 uses Neumann BC (copy center to ghost). For a `(3,3,3)` grid, cells at edges have fewer neighbors. The single-peak test places the peak at `[3,3,3]` (the corner). Corner neighbor `n_xp = ix < nx ? n[ix+1,...] : n_c` — since `ix=3, nx=3`, `3 < 3` is false, so `n_xp = n_c = 1f18`. So at the corner, `lap = (1e18 - 2*1e18 + 0)/1e-8 + (1e18 - 2*1e18 + 0)/1e-8 + (1e18 - 2*1e18 + 0)/1e-8 = -1e26 * 3 = -3e26`. Then `n_c + D_a * dt * lap = 1e18 + 2e-2 * 1e-7 * (-3e26) = 1e18 - 6e17 = 4e17`. That is > 0, so the clamp doesn't engage. The contract says "exactly 0" at center — but with this math it should be 4e17. Let me re-check...

   Actually wait: the contract says "single central peak on (3,3,3)". For `dims=(3,3,3)`, the center is `[2,2,2]`. The contract says `[3,3,3]` is the peak. With dims (3,3,3), [3,3,3] is a corner, not the center. But the contract specifies "single central peak on (3,3,3)" — this might mean dims are large enough that (3,3,3) is interior, or it means a (5,5,5) or larger grid. Let me re-read the contract...

   The contract says: "single central peak on (3,3,3) decreases: center after ≈ 0 EXACTLY". For this to work with the corner arithmetic above producing 4e17 ≠ 0, the grid must be larger than (3,3,3). If dims are (5,5,5) and the peak is at (3,3,3), then all 6 neighbors are interior and zero. Then `lap = (0 - 2*1e18 + 0)*3 / 1e-8 = -6e26`. `n_c + D_a*dt*lap = 1e18 + 2e-2*1e-7*(-6e26) = 1e18 - 1.2e18 = -2e17`. `max(0, -2e17) = 0`. EXACTLY.

   So the coder must use `dims=(5,5,5)` or larger to have the peak at `[3,3,3]` be fully interior. I should specify `dims=(5,5,5)` for the peak test, peak at `[3,3,3]`. **RISK: the contract says "(3,3,3)" for the peak coordinate but the grid dims must be larger for the peak to be interior.** The coder must use `create_ar_ion_chemistry_state((5,5,5); use_gpu=false)` for the peak diffusion test, placing the peak at `[3,3,3]` (which is the center of a 5×5×5 grid).

   For the face neighbor: with peak at `[3,3,3]`, the neighbor at `[2,3,3]` has `n_c=0, n_xp=1e18, n_xm=0, n_yp=0, n_ym=0, n_zp=0, n_zm=0` (all interior). `lap = (1e18 - 0 + 0)/1e-8 = 1e26`. `0 + 2e-2*1e-7*1e26 = 2e17`. CONFIRMED.

### DEFINITION OF DONE FOR THE CODER

1. Write `test/gpu3d_integration/chemistry/test_ar_ion_chemistry_3d.jl` with all content described above (≥ 40 `@test` macros expected).
2. Insert the single `include("chemistry/test_ar_ion_chemistry_3d.jl")` line into `test/gpu3d_integration/runtests.jl` between lines 34 and 35.
3. Call the julia_gate tool EXACTLY ONCE on `test/gpu3d_integration/runtests.jl` (or the test file). The gate verdicts are:
   - **VERT**: all tests pass within budget — SUCCESS.
   - **ORANGE with zero failures**: budget timeout (expected for this module due to CUDA replay) — ACCEPTABLE, stop here.
   - **ROUGE**: real test failures — read the failure output, fix the test file, retry once more, then stop regardless.
4. Write `DONE.md` reporting the gate verdict and the total number of `@test` macros (count them).
5. **Never** run Julia from the shell — only use the julia_gate tool for testing.