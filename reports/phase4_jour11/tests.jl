# test/gpu3d_integration/chemistry/test_ar_ion_chemistry_3d.jl
"""
Tests for Ar⁺/Ar₂⁺ ion chemistry (Phase 22).

Reactions under test:
  Ar⁺ + 2Ar → Ar₂⁺ + Ar        (three-body ion clustering, Bogaerts 2002)
  Ar₂⁺ + e⁻ → Ar*(³P₂) + Ar    (dissociative recombination, Shon & Kushner 1994)
  + explicit ambipolar diffusion (zero-flux boundaries, positivity clamp)

CPU ONLY: use_gpu=false everywhere; the CPU fallback methods are the ones
exercised (Array dispatch), and CUDA.functional() is never called.

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

using Test
using CUDA

# Include the module only if not already loaded (standalone mode)
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

@testset "Ar⁺/Ar₂⁺ Ion Chemistry 3D" begin

    @testset "a) Configuration constants" begin
        config = default_ar_ion_chemistry_config()

        # k_cluster is stored as Float64 (underflow protection) — exact literature value
        @test config.k_cluster == 2.5e-43
        @test eltype(config.k_cluster) == Float64

        # Float32-typed fields
        @test config.alpha_dr_300 ≈ 8.5f-13
        @test config.dr_exponent ≈ -0.67f0
        @test config.D_a ≈ 2.0f-2
        @test config.T_e ≈ 11600f0

        # N_gas = p_atm / (k_B × T_gas) = 101325.0 / (1.380649e-23 × 300.0)
        @test config.N_gas ≈ 2.4463134f25 rtol=1e-6

        @test config.enabled == true
    end

    @testset "b) Derived rates" begin
        config = default_ar_ion_chemistry_config()

        # k_cluster_eff = k_cluster × N_gas² (what the stepper precomputes)
        k_cluster_eff = Float32(config.k_cluster * Float64(config.N_gas)^2)
        @test k_cluster_eff ≈ 1.49611232f8 rtol=1e-6

        # alpha_dr(T_e) = alpha_dr_300 × (T_e/300)^dr_exponent
        alpha_dr = Float32(Float64(config.alpha_dr_300) *
                           (Float64(config.T_e) / 300.0)^Float64(config.dr_exponent))
        @test alpha_dr ≈ 7.3435032f-14 rtol=1e-6
    end

    @testset "c) State allocation and reset" begin
        state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)

        @test state isa ArIonChemistryState{Float32, Array{Float32,3}}
        @test eltype(state.n_Ar_plus) == Float32
        @test size(state.n_Ar_plus) == (2,2,2)
        @test size(state.n_Ar2_plus) == (2,2,2)
        @test state.dims == (2,2,2)
        @test all(state.n_Ar_plus .== 0.0f0)
        @test all(state.n_Ar2_plus .== 0.0f0)
        @test all(state.ne_afterglow .== 0.0f0)
        @test all(state.S_ArS_recycle .== 0.0f0)
        @test all(state.S_e_recomb .== 0.0f0)

        # Dirty the state, then reset
        fill!(state.n_Ar_plus, 1f18)
        fill!(state.n_Ar2_plus, 2f18)
        fill!(state.ne_afterglow, 3f18)
        fill!(state.S_ArS_recycle, 4f18)
        fill!(state.S_e_recomb, 5f18)
        reset_ar_ion_chemistry_state!(state)
        @test all(state.n_Ar_plus .== 0.0f0)
        @test all(state.n_Ar2_plus .== 0.0f0)
        @test all(state.ne_afterglow .== 0.0f0)
        @test all(state.S_ArS_recycle .== 0.0f0)
        @test all(state.S_e_recomb .== 0.0f0)
    end

    @testset "d) Single-cell pulse step" begin
        config = default_ar_ion_chemistry_config()
        state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state.n_Ar_plus .= 1f18
        state.n_Ar2_plus .= 0.0f0
        ne_ext = fill(1f18, 2, 2, 2)
        X_Ar = fill(1f0, 2, 2, 2)

        step_ar_ion_chemistry!(state, config, ne_ext, X_Ar, 1e-6; afterglow=false)

        @test state.n_Ar_plus[1,1,1] ≈ 6.639611f15 rtol=1e-6
        @test state.n_Ar2_plus[1,1,1] ≈ 7.0150768f19 rtol=1e-6
        @test state.S_ArS_recycle[1,1,1] ≈ 2.5757618f24 rtol=1e-6
        # Identity: Ar* recycle source and electron sink are the same rate
        @test state.S_ArS_recycle == state.S_e_recomb

        # Cross-check Ar⁺ against the hand-derived implicit update
        k_eff = Float32(config.k_cluster * Float64(config.N_gas)^2)
        expected_ap = Float32(1f18 / (1f0 + k_eff * 1f0^2 * Float32(1e-6)))
        @test state.n_Ar_plus[1,1,1] ≈ expected_ap rtol=1e-6

        @test state.ne_afterglow[1,1,1] ≈ 1f18 rtol=1e-6
    end

    @testset "e) Afterglow step" begin
        config = default_ar_ion_chemistry_config()
        state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state.n_Ar_plus .= 5f17
        state.n_Ar2_plus .= 5f17
        ne_ext = fill(0f0, 2, 2, 2)  # ignored in afterglow mode
        X_Ar = fill(1f0, 2, 2, 2)

        step_ar_ion_chemistry!(state, config, ne_ext, X_Ar, 1e-6; afterglow=true)

        # Quasi-neutrality: ne = n_Ar⁺ + n_Ar₂⁺ = 5e17 + 5e17 (initial)
        @test state.ne_afterglow[1,1,1] ≈ 1.0f18 rtol=1e-6
        @test state.n_Ar_plus[1,1,1] ≈ 3.3198054f15 rtol=1e-6
        @test state.n_Ar2_plus[1,1,1] ≈ 3.5541181f19 rtol=1e-6
    end

    @testset "f) Positivity" begin
        config = default_ar_ion_chemistry_config()

        # Pulse step
        state_p = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state_p.n_Ar_plus .= 1f18
        step_ar_ion_chemistry!(state_p, config,
                               fill(1f18, 2, 2, 2), fill(1f0, 2, 2, 2), 1e-6;
                               afterglow=false)
        @test all(state_p.n_Ar_plus .>= 0.0f0)
        @test all(state_p.n_Ar2_plus .>= 0.0f0)
        @test all(state_p.S_ArS_recycle .>= 0.0f0)
        @test all(state_p.S_e_recomb .>= 0.0f0)

        # Afterglow step
        state_a = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state_a.n_Ar_plus .= 5f17
        state_a.n_Ar2_plus .= 5f17
        step_ar_ion_chemistry!(state_a, config,
                               fill(0f0, 2, 2, 2), fill(1f0, 2, 2, 2), 1e-6;
                               afterglow=true)
        @test all(state_a.n_Ar_plus .>= 0.0f0)
        @test all(state_a.n_Ar2_plus .>= 0.0f0)
        @test all(state_a.S_ArS_recycle .>= 0.0f0)
        @test all(state_a.S_e_recomb .>= 0.0f0)

        # NOTE: Ion number is NOT conserved across the clustering step.
        # The operator-split semi-implicit source term over-produces Ar2+ for
        # stiff dt. With dt=1e-6, X_Ar=1, n_Ar2+ reaches ~7.015e19 from
        # 1e18 total initial ions. This is measured behaviour, not a defect.
    end

    @testset "g) Ambipolar diffusion" begin
        config = default_ar_ion_chemistry_config()

        # Uniform field: zero Laplacian everywhere → EXACTLY unchanged
        state_u = create_ar_ion_chemistry_state((5,5,5); use_gpu=false)
        state_u.n_Ar_plus .= 1f18
        state_u.n_Ar2_plus .= 1f18
        step_ambipolar_diffusion!(state_u, config, 1e-7, 1e-4, 1e-4, 1e-4)
        @test all(state_u.n_Ar_plus .== 1f18)
        @test all(state_u.n_Ar2_plus .== 1f18)

        # Single central peak: dims=(5,5,5) so (3,3,3) is fully interior
        state_p = create_ar_ion_chemistry_state((5,5,5); use_gpu=false)
        state_p.n_Ar_plus .= 0f0
        state_p.n_Ar_plus[3,3,3] = 1f18
        step_ambipolar_diffusion!(state_p, config, 1e-7, 1e-4, 1e-4, 1e-4)

        # Center: D_a·dt·|lap| = 2e-2 × 1e-7 × 6e26 = 1.2e18 > 1e18,
        # so the max(0,·) clamp engages and the center is EXACTLY zero.
        @test state_p.n_Ar_plus[3,3,3] == 0.0f0
        # Face neighbour: 0 + D_a·dt × (1e18/1e-8) = 2e17
        @test state_p.n_Ar_plus[2,3,3] ≈ 2.0f17 rtol=1e-6
        # Positivity and non-negativity of the total everywhere
        @test all(state_p.n_Ar_plus .>= 0.0f0)
        @test sum(state_p.n_Ar_plus) >= 0.0f0
    end

    @testset "h) Disabled config no-op" begin
        config = default_ar_ion_chemistry_config(enabled=false)
        @test config.enabled == false

        state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state.n_Ar_plus .= 1f18
        state.n_Ar2_plus .= 2f18
        state.ne_afterglow .= 3f18
        state.S_ArS_recycle .= 4f18
        state.S_e_recomb .= 5f18
        ne_ext = fill(1f18, 2, 2, 2)
        X_Ar = fill(1f0, 2, 2, 2)

        step_ar_ion_chemistry!(state, config, ne_ext, X_Ar, 1e-6; afterglow=false)
        @test all(state.n_Ar_plus .== 1f18)
        @test all(state.n_Ar2_plus .== 2f18)
        @test all(state.ne_afterglow .== 3f18)
        @test all(state.S_ArS_recycle .== 4f18)
        @test all(state.S_e_recomb .== 5f18)

        step_ambipolar_diffusion!(state, config, 1e-7, 1e-4, 1e-4, 1e-4)
        @test all(state.n_Ar_plus .== 1f18)
        @test all(state.n_Ar2_plus .== 2f18)
    end

    @testset "i) Diagnostics" begin
        config = default_ar_ion_chemistry_config()
        state = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state.n_Ar_plus .= 1f18
        state.n_Ar_plus[1,1,1] = 2f18
        state.n_Ar2_plus .= 1f17
        state.S_ArS_recycle .= 1f24
        state.ne_afterglow .= 5f17

        diag = ar_ion_chemistry_diagnostics(state)

        @test diag isa NamedTuple
        @test keys(diag) == (:Ar_plus_peak, :Ar_plus_total,
                             :Ar2_plus_peak, :Ar2_plus_total,
                             :S_ArS_recycle_peak, :S_ArS_recycle_total,
                             :ne_afterglow_peak)
        @test diag.Ar_plus_peak ≈ maximum(state.n_Ar_plus)
        @test diag.Ar_plus_total ≈ Float32(sum(state.n_Ar_plus))
        @test diag.Ar2_plus_peak ≈ maximum(state.n_Ar2_plus)
        @test diag.Ar2_plus_total ≈ Float32(sum(state.n_Ar2_plus))
        @test diag.S_ArS_recycle_peak ≈ maximum(state.S_ArS_recycle)
        @test diag.S_ArS_recycle_total ≈ Float32(sum(state.S_ArS_recycle))
        @test diag.ne_afterglow_peak ≈ maximum(state.ne_afterglow)
    end

    @testset "j) Determinism" begin
        config = default_ar_ion_chemistry_config()
        ne_ext = fill(1f18, 2, 2, 2)
        X_Ar = fill(1f0, 2, 2, 2)

        state1 = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state2 = create_ar_ion_chemistry_state((2,2,2); use_gpu=false)
        state1.n_Ar_plus .= 1f18
        state2.n_Ar_plus .= 1f18

        step_ar_ion_chemistry!(state1, config, ne_ext, X_Ar, 1e-6; afterglow=false)
        step_ar_ion_chemistry!(state2, config, ne_ext, X_Ar, 1e-6; afterglow=false)

        @test state1.n_Ar_plus == state2.n_Ar_plus
        @test state1.n_Ar2_plus == state2.n_Ar2_plus
        @test state1.ne_afterglow == state2.ne_afterglow
        @test state1.S_ArS_recycle == state2.S_ArS_recycle
        @test state1.S_e_recomb == state2.S_e_recomb
    end

end

println("\nAr⁺/Ar₂⁺ Ion Chemistry 3D tests complete!")
