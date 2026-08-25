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

@testset "Ar Jet Chemistry 3D" begin

    @testset "Configuration constants" begin
        # Default config: Float32, T_gas=300, p_atm=101325, eta_O=2.0, X_H2O=0.01
        config = default_ar_jet_chemistry_config()

        @test config.k_Ar_O2 ≈ 2.1f-16 rtol=1e-6      # Velazco 1978
        @test config.k_Ar_N2 ≈ 6.9f-17 rtol=1e-6      # Velazco 1978
        @test config.k_Ar_H2O ≈ 1.5f-16 rtol=1e-6     # Herron 1999
        @test config.k_excimer == 1.1e-44              # Float64, Bogaerts 2002
        @test config.tau_Ar2 ≈ 3.0f-6 rtol=1e-6       # Kogelschatz 2003
        @test config.sigma_O2_VUV ≈ 1.17f-21 rtol=1e-6 # Watanabe 1953
        @test config.k_O3_form == 6.0e-46              # Float64, Kossyi 1992
        @test config.eta_O ≈ 2.0f0 rtol=1e-6           # Klages 2023 anchor
        @test config.X_H2O ≈ 0.01f0 rtol=1e-6
        @test config.N_gas ≈ 2.4463134f25 rtol=1e-6    # p/k_B/T
        @test config.k_O_O3 ≈ 8.3355556f-21 rtol=1e-6  # 8e-18*exp(-2060/300)

        # Float64 fields must stay Float64 (underflow guards)
        @test typeof(config.k_excimer) == Float64
        @test typeof(config.k_O3_form) == Float64
    end

    @testset "Derived rates" begin
        config = default_ar_jet_chemistry_config()

        k_exc_eff = Float32(config.k_excimer * Float64(config.N_gas)^2)
        inv_tau = Float32(1) / config.tau_Ar2

        @test k_exc_eff ≈ 6.582894f6 rtol=1e-6     # K_EXCIMER × N_gas² [1/s]
        @test inv_tau ≈ 333333.3125f0 rtol=1e-6    # exact Float32 of 1/3e-6
        @test typeof(k_exc_eff) == Float32
    end

    @testset "State allocation and reset" begin
        state = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)

        @test state.dims == (2,2,2)
        @test size(state.n_ArS) == (2,2,2)
        @test all(state.n_ArS .== 0)
        @test all(state.n_Ar2S .== 0)
        @test all(state.Q_VUV .== 0)
        @test all(state.S_O_penning .== 0)
        @test all(state.S_O_VUV .== 0)
        @test all(state.S_OH .== 0)

        # Dirty two fields, then reset
        state.n_ArS[1,1,1] = 1f18
        state.n_Ar2S[2,2,2] = 5f15
        reset_ar_jet_chemistry_state!(state)
        @test all(state.n_ArS .== 0)
        @test all(state.n_Ar2S .== 0)
    end

    @testset "Single-cell step" begin
        # (2,2,2) grid, uniform X_Ar = 0.9 (10% ambient air), dt = 1e-7.
        # Measured anchors at rtol 1e-6.
        config = default_ar_jet_chemistry_config()
        state = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
        state.n_ArS .= 1f18
        state.n_Ar2S .= 0f0
        X_Ar = fill(0.9f0, 2, 2, 2)

        step_ar_jet_chemistry!(state, config, X_Ar, 1e-7)

        @test state.n_ArS[1,1,1] ≈ 1.6063565f7 rtol=1e-6
        @test state.n_Ar2S[1,1,1] ≈ 2.0761417f16 rtol=1e-6
        @test state.Q_VUV[1,1,1] ≈ 6.9204716f21 rtol=1e-6
        @test state.S_O_penning[1,1,1] ≈ 8.6811294f24 rtol=1e-6
        # S_O_VUV is NOT written by step_ar_jet_chemistry! (VUV deposition is
        # done separately by vuv_radial_redistribute!) — EXACT zero.
        @test state.S_O_VUV[1,1,1] == 0
        @test state.S_OH[1,1,1] ≈ 1.4763826f23 rtol=1e-6

        # Direction: quenching (k_loss ≈ 1e10 /s at 10% ambient air) drains
        # the Ar* pool from 1e18; excimer builds up from zero; all sources >= 0.
        @test state.n_ArS[1,1,1] < 1f18
        @test state.n_Ar2S[1,1,1] > 0
        @test state.S_O_penning[1,1,1] >= 0
        @test state.S_OH[1,1,1] >= 0
        @test state.Q_VUV[1,1,1] >= 0

        @testset "Positivity after step" begin
            @test all(state.n_ArS .>= 0)
            @test all(state.n_Ar2S .>= 0)
            @test all(state.Q_VUV .>= 0)
            @test all(state.S_O_penning .>= 0)
            @test all(state.S_O_VUV .>= 0)
            @test all(state.S_OH .>= 0)
        end

        @testset "Diagnostics" begin
            diag = ar_jet_chemistry_diagnostics(state)
            @test diag isa NamedTuple
            @test haskey(diag, :ArS_peak)
            @test haskey(diag, :Ar2S_peak)
            @test haskey(diag, :Q_VUV_total)
            @test haskey(diag, :S_O_penning_total)
            @test haskey(diag, :S_O_VUV_total)
            @test haskey(diag, :S_OH_total)
            @test length(keys(diag)) == 6
            @test diag.ArS_peak == maximum(Array(state.n_ArS))
            @test diag.Q_VUV_total == sum(Array(state.Q_VUV))
        end
    end

    @testset "H₂O sensitivity" begin
        # Kernel mechanism (ar_jet_chemistry_3d.jl lines 238+273):
        #   n_H2O  = x_air * X_H2O * N_gas
        #   S_OH   = k_H2O * n_ArS_avg * n_H2O
        # so S_OH is linear in X_H2O. n_ArS_avg also depends on k_loss, which
        # itself contains the k_H2O × n_H2O term, so the ratio is not exactly
        # 2:1 — but the direction is unambiguous.
        config_1 = default_ar_jet_chemistry_config()                      # X_H2O = 0.01
        config_2 = default_ar_jet_chemistry_config(X_H2O=0.02)            # X_H2O = 0.02

        X_Ar = fill(0.9f0, 2, 2, 2)

        state_1 = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
        state_1.n_ArS .= 1f18
        step_ar_jet_chemistry!(state_1, config_1, X_Ar, 1e-7)
        S_OH_1pct = state_1.S_OH[1,1,1]

        state_2 = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
        state_2.n_ArS .= 1f18
        step_ar_jet_chemistry!(state_2, config_2, X_Ar, 1e-7)
        S_OH_2pct = state_2.S_OH[1,1,1]

        @test S_OH_1pct > 0
        @test S_OH_2pct > S_OH_1pct
    end

    @testset "Pure air cell (X_Ar = 0)" begin
        # Cell (1,1,1) is pure air; excimer channel ∝ X_Ar² = 0 → OFF.
        config = default_ar_jet_chemistry_config()
        state = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
        state.n_ArS .= 1f18
        X_Ar = fill(0.9f0, 2, 2, 2)
        X_Ar[1,1,1] = 0f0

        step_ar_jet_chemistry!(state, config, X_Ar, 1e-7)

        @test state.n_Ar2S[1,1,1] == 0
        @test state.Q_VUV[1,1,1] == 0
        @test state.n_ArS[1,1,1] < 1f18            # still quenched by Penning
        @test state.S_O_penning[1,1,1] > 0         # Penning O₂/N₂ active
    end

    @testset "VUV radial redistribution" begin
        # Docstring: redistribute VUV photons radially at each z-plane via
        # Beer-Lambert absorption (τ = ∫ σ_O₂ × n_O₂ dr); absorbed VUV →
        # 2 O atoms per photon, written into state.S_O_VUV.
        dims = (5, 5, 2)
        config = default_ar_jet_chemistry_config()
        state = create_ar_jet_chemistry_state(dims; use_gpu=false)
        state.Q_VUV[3,3,1] = 1f20    # single central peak

        X_Ar = fill(0.99f0, dims...)
        # 20 mm wide grid, 0.25 mm radial bin
        L = 0.020f0
        # Vector{Float64} exige par la signature (un range ne dispatch pas) --
        # correction main post-run, defaut modele mineur note au triage J12
        x_centers = collect(Float64, range(-L/2, L/2, length=5))
        y_centers = collect(Float64, range(-L/2, L/2, length=5))
        dr = 0.00025

        vuv_radial_redistribute!(state, config, X_Ar, x_centers, y_centers, dr)

        @test all(state.S_O_VUV .>= 0)
        @test any(state.S_O_VUV .> 0)          # VUV deposition produced O source
        @test sum(state.Q_VUV) >= 0            # sanity
        @test state.Q_VUV[3,3,1] == 1f20       # Q_VUV is input, not overwritten
    end

    @testset "Determinism" begin
        config = default_ar_jet_chemistry_config()
        X_Ar = fill(0.9f0, 2, 2, 2)

        state1 = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
        state1.n_ArS .= 1f18
        state2 = create_ar_jet_chemistry_state((2,2,2); use_gpu=false)
        state2.n_ArS .= 1f18

        step_ar_jet_chemistry!(state1, config, X_Ar, 1e-7)
        step_ar_jet_chemistry!(state2, config, X_Ar, 1e-7)

        @test all(state1.n_ArS .== state2.n_ArS)
        @test all(state1.n_Ar2S .== state2.n_Ar2S)
        @test all(state1.S_O_penning .== state2.S_O_penning)
    end

end

println("\nAr Jet Chemistry 3D tests complete!")