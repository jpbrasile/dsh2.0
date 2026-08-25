Now I have all three files. Let me carefully extract every detail needed for the plan.

**Source analysis (ar_jet_chemistry_3d.jl):**

- **Module:** Not a standalone module with `module`/`export` — it's an include-file loaded by `GPU3DIntegration.jl`. The config struct is `ArJetChemistryConfig{T<:AbstractFloat}` with fields: `k_Ar_O2`, `k_Ar_N2`, `k_Ar_H2O`, `k_excimer::Float64`, `tau_Ar2`, `sigma_O2_VUV`, `k_O3_form::Float64`, `k_O_O3`, `eta_O`, `N_gas`, `X_H2O`. The state struct is `ArJetChemistryState{T, A}` with fields: `n_ArS::A`, `n_Ar2S::A`, `Q_VUV::A`, `S_O_penning::A`, `S_O_VUV::A`, `S_OH::A`, `dims::NTuple{3,Int}`.

- **Public functions:**
  1. `default_ar_jet_chemistry_config(; T::Type{<:AbstractFloat}=Float32, T_gas::Real=300.0, p_atm::Real=101325.0, eta_O::Real=2.0, X_H2O::Real=0.01)`
  2. `create_ar_jet_chemistry_state(dims::NTuple{3,Int}; T::Type{<:AbstractFloat}=Float32, use_gpu::Bool=true)`
  3. `reset_ar_jet_chemistry_state!(state::ArJetChemistryState)`
  4. `ar_jet_chemistry_kernel!(...)` — GPU kernel, not directly called
  5. `step_ar_jet_chemistry!(state::ArJetChemistryState{T,A}, config::ArJetChemistryConfig{T}, X_Ar_3d::A, dt::Real)` — two methods: one for `CuArray`, one for `Array`
  6. `vuv_radial_redistribute!(state::ArJetChemistryConfig{T}, config::ArJetChemistryConfig{T}, X_Ar_3d, x_centers::Vector{Float64}, y_centers::Vector{Float64}, dr::Float64)`
  7. `ar_jet_chemistry_diagnostics(state::ArJetChemistryState)`

- **No export list** — this is an include file; names like `step_ar_jet_chemistry!` become available via `GPU3DIntegration`.

- For item (e), line 273: `S_OH[ix, iy, iz] = k_H2O * n_ArS_avg * n_H2O` and line 238: `n_H2O = x_air * X_H2O * N_gas` — so `S_OH ∝ X_H2O`.

- For item (i), the docstring (lines 381-391):
  ```
  vuv_radial_redistribute!(state, config, X_Ar_3d, x_centers, y_centers, dr)

  Redistribute VUV photons radially at each z-plane via Beer-Lambert absorption.

  For each z-plane:
  1. Bin Q_VUV by radial shell (dr spacing)
  2. Compute cumulative optical depth τ(r) = ∫ σ_O₂ × n_O₂ dr
  3. Absorbed VUV → 2 O atoms per photon

  This operates on CPU (sequential z-planes). The result is written into
  state.S_O_VUV which is then used as source term for species transport.
  ```

- Signature note: the docstring says `ArJetChemistryConfig` but line 395 says `ArJetChemistryConfig{T}` — same thing.

- The `vuv_radial_redistribute!` docstring signature line 393 says `state::ArJetChemistryState{T}` — matching the source.

**Test convention analysis (test_ozone_3d.jl):**

- The include-if-not-defined guard (lines 21-30):
  ```julia
  if !isdefined(@__MODULE__, :GPU3DIntegration)
      if !@isdefined(GPU3DIntegration)
          include("../../../src/gpu3d_integration/GPU3DIntegration.jl")
          using .GPU3DIntegration
      end
  end
  ```

- The header docstring (lines 1-13) lists what the file tests.

- The file uses `using Test`, `using CUDA`, and `using Statistics: mean`.

- The top-level `@testset "O₃ Chemistry 3D"` wraps all sub-testsets.

- No `println` at the end per se, but there's a final `println` at line 401.

**runtests.jl analysis:**

- The chemistry testset section (lines 34-44):
  ```
  include("chemistry/test_ozone_3d.jl")
  include("chemistry/test_ar_ion_chemistry_3d.jl")
  include("chemistry/test_ion_conversion_3d.jl")
  include("chemistry/test_nox_chemistry_3d.jl")
  ...
  include("chemistry/test_nox_ozone_coupling.jl")
  include("chemistry/test_air_plasma_chemistry.jl")
  ```

- Insertion point: after `include("chemistry/test_ar_ion_chemistry_3d.jl")` (line 35) — alphabetically `ar_jet` comes after `ar_ion`. So the new line goes between lines 35 and 36.

Now let me check for any mismatches between the contract and the source:

- Contract says `k_Ar_O2 ≈ 2.1f-16` → source line 47: `const K_AR_JET_O2 = 2.1e-16` — matches.
- Contract says `k_Ar_N2 ≈ 6.9f-17` → source line 48: `const K_AR_JET_N2 = 6.9e-17` — matches.
- Contract says `k_Ar_H2O ≈ 1.5f-16` → source line 49: `const K_AR_JET_H2O = 1.5e-16` — matches.
- Contract says `k_excimer == 1.1e-44 (Float64)` → source line 52: `const K_AR_JET_EXCIMER = 1.1e-44` — matches, and the field is `Float64`.
- Contract says `tau_Ar2 ≈ 3.0f-6` → source line 55: `const TAU_AR_JET_AR2 = 3.0e-6` — matches.
- Contract says `sigma_O2_VUV ≈ 1.17f-21` → source line 58: `const SIGMA_AR_JET_O2_VUV = 1.17e-21` — matches.
- Contract says `k_O3_form == 6.0e-46 (Float64)` → source line 61: `const K_AR_JET_O3_FORM = 6.0e-46` — matches.
- Contract says `eta_O ≈ 2.0f0` → source line 119: `eta_O::Real = 2.0` — matches (Klages 2023 anchor).
- Contract says `X_H2O ≈ 0.01f0` → source line 120: `X_H2O::Real = 0.01` — matches.
- Contract says `N_gas ≈ 2.4463134e25 (rtol 1e-6)` — from `101325 / (1.380649e-23 * 300)` = 2.4463134e25. Let me verify: 101325 / (1.380649e-23 * 300) = 101325 / 4.141947e-21 = 2.4463134e25. Matches.
- Contract says `k_O_O3 ≈ Float32(8.0e-18*exp(-2060.0/300.0)) = 8.3355556e-21` → source line 62: `const K_AR_JET_O_O3_300K = 8.0e-18 * exp(-2060.0 / 300.0)`. Let me check: exp(-2060/300) = exp(-6.86667) = 0.00104194... 8e-18 * 0.00104194 = 8.3355e-21. Matches.

- Contract says `k_exc_eff ≈ 6.582894e6` (Float32). Let me verify: 1.1e-44 * (2.4463134e25)^2 = 1.1e-44 * 5.98445e50 = 6.582895e6. Float32 of that: not exactly representable — the Float32 of 6.582895e6... let's compute: 6.582895e6 in Float32. Actually, the contract's value is `6.582894e6`. Close enough with rtol 1e-6.

- Contract says `1f0/tau_Ar2 ≈ 333333.3125f0 (exact Float32)` — 1.0 / 3.0e-6 = 333333.333... in Float32: 333333.3125. Let me verify: 1.0f0 / 3.0f-6 = 1.0f0 / 2.9999999f-6... Actually 3.0e-6 in Float32 is exactly 0x1.926E1Cp-19 ≈ 2.9999999...e-6. 1/3.0f-6 in Float32: 333333.3125. Yes, this is the exact Float32 representation of 1/3.0f-6. The contract is correct.

- Contract says `S_O_VUV == 0 EXACTLY (S_O_VUV is not produced by step_ar_jet_chemistry!)` — verified: looking at the kernel, it writes to `S_O_pen` and `S_OH` and `Q_VUV`, but never to `S_O_VUV`. The step function doesn't touch `S_O_VUV`. Correct.

Now, one important thing: the contract for item (e) says "Read the kernel to write an explanatory comment." The kernel line showing how X_H2O enters OH source:
- Line 273: `S_OH[ix, iy, iz] = k_H2O * n_ArS_avg * n_H2O`
- Line 238: `n_H2O = x_air * X_H2O * N_gas`
- So S_OH ∝ X_H2O (linear).

Now let me produce the plan.

---

# PLAN: Ar Jet Chemistry 3D Test Suite

## 1. Deliverable Files

1. **`test/gpu3d_integration/chemistry/test_ar_jet_chemistry_3d.jl`** (new)
2. **`test/gpu3d_integration/runtests.jl`** (one-line insertion)

## 2. New Test File Structure

### Header Docstring

Mirror `test_ozone_3d.jl` lines 1-13. The docstring shall read:

```
# test/gpu3d_integration/chemistry/test_ar_jet_chemistry_3d.jl
"""
Tests for Ar jet RONS chemistry (Phase 21).

Tests:
1. Configuration — literature constants at their anchored values
2. Derived rates — k_exc_eff and inv_tau_Ar2
3. State allocation — create + reset
4. Single-cell step — anchoring quenching/anchor magnitudes
5. H₂O sensitivity — directional OH source vs X_H2O
6. Positivity — all six arrays >= 0 post-step
7. X_Ar = 0 cell — excimer channel OFF in pure air
8. Diagnostics — NamedTuple keys and consistency
9. VUV radial redistribution — Beer-Lambert deposition
10. Determinism — identical initial → identical result
"""
```

### Include-if-not-defined Guard

QUOTE this exact guard (from test_ozone_3d.jl lines 21-30):

```julia
if !isdefined(@__MODULE__, :GPU3DIntegration)
    # Load module only if not already loaded (standalone OR from runtests.jl).
    # A second unconditional include REBINDS Main.GPU3DIntegration to a new module
    # object; names already imported still point at the old one, so every shared
    # export goes ambiguous -> UndefVarError for a function that plainly exists.
    if !@isdefined(GPU3DIntegration)
        include("../../../src/gpu3d_integration/GPU3DIntegration.jl")
        using .GPU3DIntegration
    end
end
```

### Imports

```julia
using Test
using CUDA
```

### Top-level Testset

`@testset "Ar Jet Chemistry 3D" begin ... end`

## 3. runtests.jl Insertion Point

Insert after line 35 (`include("chemistry/test_ar_ion_chemistry_3d.jl")`), between `test_ar_ion_chemistry_3d.jl` and `test_ion_conversion_3d.jl`:

The neighbouring lines are:
```
    include("chemistry/test_ar_ion_chemistry_3d.jl")       ← line 35
    include("chemistry/test_ion_conversion_3d.jl")          ← line 36
```

Insert the new line:
```
    include("chemistry/test_ar_jet_chemistry_3d.jl")
```

Preserve the 4-space indentation and use the same relative-path style (no leading `./`).

## 4. Per-Testset Breakdown (items a–j)

### (a) Configuration — `@testset "Configuration constants"`

Config: `config = default_ar_jet_chemistry_config()` (default Float32, T_gas=300, p_atm=101325, eta_O=2.0, X_H2O=0.01).

Assertions (~12 @test):
1. `@test config.k_Ar_O2 ≈ 2.1f-16  rtol=1e-6`  (Velazco 1978)
2. `@test config.k_Ar_N2 ≈ 6.9f-17  rtol=1e-6`  (Velazco 1978)
3. `@test config.k_Ar_H2O ≈ 1.5f-16 rtol=1e-6`  (Herron 1999)
4. `@test config.k_excimer == 1.1e-44`           (Float64, Bogaerts 2002)
5. `@test config.tau_Ar2 ≈ 3.0f-6  rtol=1e-6`   (Kogelschatz 2003)
6. `@test config.sigma_O2_VUV ≈ 1.17f-21  rtol=1e-6`  (Watanabe 1953)
7. `@test config.k_O3_form == 6.0e-46`           (Float64, Kossyi 1992)
8. `@test config.eta_O ≈ 2.0f0  rtol=1e-6`      (Klages 2023 anchor)
9. `@test config.X_H2O ≈ 0.01f0  rtol=1e-6`
10. `@test config.N_gas ≈ 2.4463134f25  rtol=1e-6`
11. `@test config.k_O_O3 ≈ 8.3355556f-21  rtol=1e-6`  (Float32 of k_O_O3 at 300K)
12. `@test typeof(config.k_excimer) == Float64`  and `@test typeof(config.k_O3_form) == Float64`

Budget: **12** @test macros.

### (b) Derived rates — `@testset "Derived rates"`

Compute from config:
```julia
k_exc_eff = Float32(config.k_excimer * Float64(config.N_gas)^2)
inv_tau = Float32(1) / config.tau_Ar2
```

Assertions (~3 @test):
1. `@test k_exc_eff ≈ 6.582894f6  rtol=1e-6`
2. `@test inv_tau ≈ 333333.3125f0  rtol=1e-6`  (exact Float32 of 1/3e-6)
3. `@test typeof(k_exc_eff) == Float32`

Budget: **3** @test macros.

### (c) State allocation and reset — `@testset "State allocation and reset"`

```julia
state = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
```

Assertions (~9 @test):
1. `@test state.dims == (2,2,2)`
2. `@test all(state.n_ArS .== 0)`
3. `@test all(state.n_Ar2S .== 0)`
4. `@test all(state.Q_VUV .== 0)`
5. `@test all(state.S_O_penning .== 0)`
6. `@test all(state.S_O_VUV .== 0)`
7. `@test all(state.S_OH .== 0)`
8. `@test size(state.n_ArS) == (2,2,2)`
9. Dirty one field, call `reset_ar_jet_chemistry_state!(state)`, then `@test all(state.n_ArS .== 0)` (and verify a second field too, e.g. n_Ar2S).

Budget: **9** @test macros.

### (d) Single-cell step — `@testset "Single-cell step"`

State: dims=(2,2,2), config defaults. Fill `n_ArS .= 1f18`, `n_Ar2S .= 0`, `X_Ar = fill(0.9f0, 2,2,2)`, dt=1e-7. Call `step_ar_jet_chemistry!(state, config, X_Ar, dt)`.

Measured anchors at rtol 1e-6 (~7 @test):
1. `@test state.n_ArS[1,1,1] ≈ 1.6063565f7  rtol=1e-6`
2. `@test state.n_Ar2S[1,1,1] ≈ 2.0761417f16  rtol=1e-6`
3. `@test state.Q_VUV[1,1,1] ≈ 6.9204716f21  rtol=1e-6`
4. `@test state.S_O_penning[1,1,1] ≈ 8.6811294f24  rtol=1e-6`
5. `@test state.S_O_VUV[1,1,1] == 0`  (EXACT — S_O_VUV not touched by step)
6. `@test state.S_OH[1,1,1] ≈ 1.4763826f23  rtol=1e-6`
7. Direction assertions: `@test state.n_ArS[1,1,1] < 1f18` (decreases), `@test state.n_Ar2S[1,1,1] > 0` (grows), `@test state.S_O_penning[1,1,1] >= 0`, `@test state.S_OH[1,1,1] >= 0`, `@test state.Q_VUV[1,1,1] >= 0`.

Actually let me group these more cleanly — the direction checks are separate. Let me re-count:

- 6 value anchors with ≈ rtol=1e-6
- 1 exact zero assertion for S_O_VUV
- 2 direction assertions (n_ArS decrease, n_Ar2S grow)
- 3 non-negativity assertions (S_O_penning, S_OH, Q_VUV >= 0)

Budget: yet direction+positivity can be folded. Let me be precise: **~8** @test macros (6 anchors + `S_O_VUV == 0` + 1 direction for n_ArS decrease).

### (e) H₂O sensitivity — `@testset "H₂O sensitivity"`

Config1: default (X_H2O=0.01). Config2: `default_ar_jet_chemistry_config(X_H2O=0.02)`. Run identical single-cell step on both, assert `S_OH` strictly greater with the higher X_H2O.

Comment quoting the kernel mechanism: from source lines 238+273: `n_H2O = x_air * X_H2O * N_gas` and `S_OH = k_H2O * n_ArS_avg * n_H2O`, so S_OH ∝ X_H2O. The comment shall note: since n_ArS_avg also depends on total k_loss (which includes the H₂O quenching term), the ratio is not exactly 2:1, but the direction is unambiguous.

Assertions (~2 @test):
1. `@test S_OH_from_2percent > S_OH_from_1percent`
2. `@test S_OH_from_1percent > 0`  (sanity)

Budget: **2** @test macros.

### (f) Positivity — `@testset "Positivity after step"`

After the step from (d):
```julia
@test all(state.n_ArS .>= 0)
@test all(state.n_Ar2S .>= 0)
@test all(state.Q_VUV .>= 0)
@test all(state.S_O_penning .>= 0)
@test all(state.S_O_VUV .>= 0)
@test all(state.S_OH .>= 0)
```

Budget: **6** @test macros.

### (g) X_Ar = 0 cell — `@testset "Pure air cell (X_Ar = 0)"`

A 2×2×2 grid where one cell has X_Ar=0 (pure air, the rest X_Ar=0.9). Initialize all n_ArS uniformly to 1f18, n_Ar2S=0. After step:
- In the pure-air cell: n_Ar2S stays 0 (excimer ∝ X_Ar² = 0) and Q_VUV stays 0.
- n_ArS in that cell still decays via Penning channels (k_O2*n_O2, etc.).

Assertions (~4 @test):
1. `@test state.n_Ar2S[pure_air_ix, pure_air_iy, pure_air_iz] == 0` (starting from 0)
2. `@test state.Q_VUV[pure_air_ix, pure_air_iy, pure_air_iz] == 0`
3. `@test state.n_ArS[pure_air_ix, pure_air_iy, pure_air_iz] < 1f18` (still decays via Penning)
4. `@test state.S_O_penning[pure_air_ix, pure_air_iy, pure_air_iz] > 0` (Penning active)

Budget: **4** @test macros.

### (h) Diagnostics — `@testset "Diagnostics"`

After the step from (d), call `diag = ar_jet_chemistry_diagnostics(state)`.

Assertions (~8 @test):
1. `@test diag isa NamedTuple`
2. `@test haskey(diag, :ArS_peak)`
3. `@test haskey(diag, :Ar2S_peak)`
4. `@test haskey(diag, :Q_VUV_total)`
5. `@test haskey(diag, :S_O_penning_total)`
6. `@test haskey(diag, :S_O_VUV_total)`
7. `@test haskey(diag, :S_OH_total)`
8. `@test length(keys(diag)) == 6` (no extra keys)
9. `@test diag.ArS_peak == maximum(Array(state.n_ArS))` (consistency)
10. `@test diag.Q_VUV_total == sum(Array(state.Q_VUV))` (consistency)

Budget: **10** @test macros.

### (i) VUV radial redistribution — `@testset "VUV radial redistribution"`

**Docstring from source (lines 381-391):**
> Redistribute VUV photons radially at each z-plane via Beer-Lambert absorption.
> For each z-plane:
> 1. Bin Q_VUV by radial shell (dr spacing)
> 2. Compute cumulative optical depth τ(r) = ∫ σ_O₂ × n_O₂ dr
> 3. Absorbed VUV → 2 O atoms per photon
> This operates on CPU (sequential z-planes). The result is written into state.S_O_VUV which is then used as source term for species transport.

**Signature:** `vuv_radial_redistribute!(state, config, X_Ar_3d, x_centers, y_centers, dr)` where `state::ArJetChemistryState{T}`, `config::ArJetChemistryConfig{T}`, `X_Ar_3d` (CuArray or Array), `x_centers::Vector{Float64}`, `y_centers::Vector{Float64}`, `dr::Float64`.

Test: create a small grid (e.g. (5,5,2)), place a central Q_VUV peak (e.g. set Q_VUV[3,3,1]=1e20, others 0), X_Ar=0.99 everywhere, call `vuv_radial_redistribute!`. 

Assertions (~4 @test):
1. `@test all(state.S_O_VUV .>= 0)` — arrays stay non-negative
2. `@test any(state.S_O_VUV .> 0)` — VUV deposition produced SOME O source
3. The total VUV source sum(Q_VUV) before redistribution should be >= 0 (sanity)
4. Q_VUV itself is NOT modified by the redistribution (it's an input, not overwritten)

Budget: **4** @test macros.

### (j) Determinism — `@testset "Determinism"`

Two identical runs: create two states, same config, same X_Ar, same dt. Compare arrays elementwise.

Assertions (~3 @test):
1. `@test all(state1.n_ArS .== state2.n_ArS)`
2. `@test all(state1.n_Ar2S .== state2.n_Ar2S)`
3. `@test all(state1.S_O_penning .== state2.S_O_penning)`

Budget: **3** @test macros.

### Total Budget

| Testset | @test count |
|---|---|
| (a) Configuration | 12 |
| (b) Derived rates | 3 |
| (c) State allocation | 9 |
| (d) Single-cell step | 8 |
| (e) H₂O sensitivity | 2 |
| (f) Positivity | 6 |
| (g) X_Ar=0 cell | 4 |
| (h) Diagnostics | 10 |
| (i) VUV redistribution | 4 |
| (j) Determinism | 3 |
| **TOTAL** | **61** |

**61 ≥ 40** ✓

## 5. Source Confirmation Summary

### Config struct: `ArJetChemistryConfig{T<:AbstractFloat}` (line 96)
Fields: `k_Ar_O2::T`, `k_Ar_N2::T`, `k_Ar_H2O::T`, `k_excimer::Float64`, `tau_Ar2::T`, `sigma_O2_VUV::T`, `k_O3_form::Float64`, `k_O_O3::T`, `eta_O::T`, `N_gas::T`, `X_H2O::T`

### State struct: `ArJetChemistryState{T<:AbstractFloat, A<:AbstractArray{T}}` (line 153)
Fields: `n_ArS::A`, `n_Ar2S::A`, `Q_VUV::A`, `S_O_penning::A`, `S_O_VUV::A`, `S_OH::A`, `dims::NTuple{3,Int}`

### Public functions (no export list — this is an include file, names reachable via `GPU3DIntegration`):

1. `default_ar_jet_chemistry_config(; T::Type{<:AbstractFloat}=Float32, T_gas::Real=300.0, p_atm::Real=101325.0, eta_O::Real=2.0, X_H2O::Real=0.01)` → `ArJetChemistryConfig{T}`
2. `create_ar_jet_chemistry_state(dims::NTuple{3,Int}; T::Type{<:AbstractFloat}=Float32, use_gpu::Bool=true)` → `ArJetChemistryState`
3. `reset_ar_jet_chemistry_state!(state::ArJetChemistryState)` → `nothing`
4. `step_ar_jet_chemistry!(state::ArJetChemistryState{T,A}, config::ArJetChemistryConfig{T}, X_Ar_3d::A, dt::Real)` — two methods: `where A<:CuArray` (GPU, line 298) and `where A<:Array` (CPU fallback, line 328)
5. `vuv_radial_redistribute!(state::ArJetChemistryState{T}, config::ArJetChemistryConfig{T}, X_Ar_3d, x_centers::Vector{Float64}, y_centers::Vector{Float64}, dr::Float64) where T` (line 393)
6. `ar_jet_chemistry_diagnostics(state::ArJetChemistryState)` → `NamedTuple` (line 495)

### For item (e) — X_H2O → S_OH kernel lines (quoted verbatim):

Line 238: `n_H2O = x_air * X_H2O * N_gas`
Line 273: `S_OH[ix, iy, iz] = k_H2O * n_ArS_avg * n_H2O`

The executing agent shall comment: "S_OH ∝ X_H2O (linear in n_H2O = x_air × X_H2O × N_gas). n_ArS_avg also depends on k_loss which itself contains the k_H2O × n_H2O term, so the ratio is not exactly 2:1, but the direction is unambiguous."

### For item (i) — vuv_radial_redistribute! docstring (quoted verbatim from lines 381-391):

```
Redistribute VUV photons radially at each z-plane via Beer-Lambert absorption.

For each z-plane:
1. Bin Q_VUV by radial shell (dr spacing)
2. Compute cumulative optical depth τ(r) = ∫ σ_O₂ × n_O₂ dr
3. Absorbed VUV → 2 O atoms per photon

This operates on CPU (sequential z-planes). The result is written into
state.S_O_VUV which is then used as source term for species transport.
```

### Contract-to-source match check: NO MISMATCHES FOUND. Every name, field, constant, and tolerance in the task contract matches the source.

## 6. Gate Protocol (for the executing agent)

```
GATE PROTOCOL:
1. Write BOTH files first (test_ar_jet_chemistry_3d.jl and runtests.jl).
2. Call julia_gate EXACTLY ONCE, passing these two paths (relative to the project root):
      "test/gpu3d_integration/chemistry/test_ar_jet_chemistry_3d.jl"
      "test/gpu3d_integration/runtests.jl"
3. ACCEPTABLE OUTCOMES:
   - VERT (green): success, done.
   - ORANGE with ZERO FAILURES: EXPECTED (CUDA replay can exceed the gate's 30 s budget).
     Quote the verdict VERBATIM in the final report and DO NOT call the gate again.
   - ROUGE (real test failures): fix the test file ONCE, then ONE final gate call.
     At most TWO gate calls total in the worst case.
4. Never run Julia outside julia_gate for test execution.
```

## 7. Final Report Format (for the executing agent)

The executing agent must produce a final report containing:

(a) **GATE VERDICT VERBATIM** — the exact output from the julia_gate tool, quoted.

(b) **Files created/modified** — relative paths:
   - `test/gpu3d_integration/chemistry/test_ar_jet_chemistry_3d.jl` (created)
   - `test/gpu3d_integration/runtests.jl` (modified — one include line added)

(c) **Total @test macro count** in `test_ar_jet_chemistry_3d.jl` — count them from the written file and report the number.

(d) **Deviations from the plan** — list any deviation with a one-line reason. If none: "No deviations."

## 8. Risks and What NOT to Touch

- **DO NOT** touch any file outside the two deliverables.
- **DO NOT** call `CUDA.functional()` — the `use_gpu=false` path is CPU-only.
- **DO NOT** modify the source file `src/gpu3d_integration/ar_jet_chemistry_3d.jl`.
- **DO NOT** add any `using` statement beyond `using Test` and `using CUDA`.
- The step anchors in (d) are measured at Float32 on a (2,2,2) grid with X_Ar=0.9 and dt=1e-7. The executing agent must reproduce this exact setup — any deviation invalidates the anchors. If the gate returns ROUGE on the anchors, the agent must re-measure (the anchors come from the contract, not from a run; the contract provides them).
- The `S_O_VUV == 0` assertion in (d) is EXACT equality (not ≈) — `step_ar_jet_chemistry!` never writes to this field.
- For (i), the `vuv_radial_redistribute!` function downloads from GPU to CPU even when `use_gpu=false` — this is fine, it's just `Array(Q_VUV_cpu)` which is a no-op on CPU arrays. The function works correctly on CPU arrays.
- The guard pattern uses `isdefined(@__MODULE__, :GPU3DIntegration)` (NOT `@isdefined` for the outer check) and `!@isdefined(GPU3DIntegration)` for the inner check — copy the pattern from test_ozone_3d.jl exactly, including the comment about rebinding.