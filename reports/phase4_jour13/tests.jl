# test/gpu3d_integration/test_ozone_3d.jl
"""
Tests for O/O₃ chemistry tracking.

Tests:
1. OzoneConfig3D creation
2. OzoneState3D allocation
3. O atom source from dissociation
4. O₃ formation (O + O₂ + M → O₃ + M)
5. O₃ destruction (O + O₃ → 2O₂)
6. Wall losses
7. Steady-state behavior
8. Integration with detachment
"""

using Test
using CUDA
using Statistics: mean

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

@testset "O₃ Chemistry 3D" begin

    @testset "Configuration" begin
        # Default config for air at 1 atm
        config = default_ozone_config()

        @test config.enabled == true
        @test config.T_gas ≈ 300.0f0

        # Check O₂ density at 1 atm, 300 K, 21%
        @test config.n_O2 > 5e24
        @test config.n_O2 < 6e24

        # Check total gas density (n_M)
        @test config.n_M > 2e25
        @test config.n_M < 3e25

        # Check rate coefficients (order of magnitude)
        # k_O3_form ≈ 6e-46 m⁶/s at 300 K
        @test config.k_O3_form > 1e-47
        @test config.k_O3_form < 1e-44

        # k_O_O3 ≈ 8e-18 × exp(-2060/300) ≈ 8e-21 m³/s at 300 K
        @test config.k_O_O3 > 1e-22
        @test config.k_O_O3 < 1e-19

        # Custom config at higher temperature
        config2 = default_ozone_config(
            T_gas = 500.0,
            wall_loss_O = 200.0,
            wall_loss_O3 = 20.0
        )
        # O₃ formation slower at higher T (T⁻² dependence)
        @test config2.k_O3_form < config.k_O3_form
        # O + O₃ faster at higher T (Arrhenius)
        @test config2.k_O_O3 > config.k_O_O3

        @info "Config test" k_O3_form=config.k_O3_form k_O_O3=config.k_O_O3
    end

    @testset "State Allocation" begin
        # Create state with typical DBD volume
        volume = 1e-6  # 1 cm³
        state = create_ozone_state(volume = volume, particle_weight = 1e6)

        @test state.n_O[] == 0.0
        @test state.n_O3[] == 0.0
        @test state.n_dissoc[] == 0
        @test state.last_update_step[] == 0
        @test state.volume ≈ volume
        @test state.particle_weight ≈ 1e6

        # Reset
        state.n_O[] = 1e18
        state.n_O3[] = 1e17
        reset_ozone_state!(state)
        @test state.n_O[] == 0.0
        @test state.n_O3[] == 0.0
    end

    @testset "O Atom Source - Dissociation" begin
        # Test that dissociation increases O density
        volume = 1e-6  # 1 cm³
        weight = 1e6
        state = create_ozone_state(volume = volume, particle_weight = weight)
        config = default_ozone_config(update_interval = 1)

        dt = 1e-9  # 1 ns
        step = 1

        # Apply 100 dissociation events (each creates 2 O atoms)
        n_dissoc = 100

        dn_O, dn_O3 = update_ozone_populations!(
            state, config, dt, step;
            n_dissoc = n_dissoc
        )

        # Expected: dn_O ≈ (n_dissoc × 2 × weight) / volume = (100 × 2 × 1e6) / 1e-6 = 2e14 m⁻³
        # (minus small losses)
        @test state.n_O[] > 0
        @test state.n_O[] > 1e13  # Should be significant

        @info "Dissociation test" n_dissoc n_O=state.n_O[] dn_O
    end

    @testset "O₃ Formation" begin
        # Test that O atoms convert to O₃
        volume = 1e-6
        weight = 1e6
        state = create_ozone_state(volume = volume, particle_weight = weight)
        config = default_ozone_config(
            update_interval = 1,
            wall_loss_O = 10.0,    # Low wall loss
            wall_loss_O3 = 1.0     # Very low O₃ wall loss
        )

        dt = 1e-7  # 100 ns (longer for chemistry)
        step = 1

        # Create initial O population via dissociation
        update_ozone_populations!(
            state, config, dt, step;
            n_dissoc = 1000  # Large dissociation source
        )

        n_O_initial = state.n_O[]
        @test n_O_initial > 0

        # Let O₃ form over many steps (no more dissociation)
        for i in 2:1000
            update_ozone_populations!(
                state, config, dt, i;
                n_dissoc = 0
            )
        end

        # O should decrease (consumed by O₃ formation + wall loss)
        @test state.n_O[] < n_O_initial

        # O₃ should have formed
        @test state.n_O3[] > 0

        @info "O₃ formation test" n_O_initial n_O_final=state.n_O[] n_O3=state.n_O3[]
    end

    @testset "O₃ Destruction" begin
        # Test O + O₃ → 2O₂ destruction pathway
        # Set O₂ = 0 to disable formation and isolate destruction
        volume = 1e-6
        weight = 1e6
        state = create_ozone_state(volume = volume, particle_weight = weight)

        # High temperature for faster O + O₃ reaction, zero O₂ to disable formation
        config = default_ozone_config(
            update_interval = 1,
            T_gas = 500.0,          # Higher T = faster O + O₃
            O2_fraction = 0.0,      # No O₂ → no O₃ formation
            wall_loss_O = 1.0,      # Low wall loss
            wall_loss_O3 = 0.1      # Very low O₃ wall loss
        )

        dt = 1e-6  # 1 μs

        # Set initial populations manually
        state.n_O[] = 1e20    # High O density
        state.n_O3[] = 1e19   # Some O₃ present

        n_O3_initial = state.n_O3[]

        # Let destruction proceed (no source, no formation)
        for i in 1:100
            update_ozone_populations!(
                state, config, dt, i;
                n_dissoc = 0
            )
        end

        # O₃ should decrease due to O + O₃ → 2O₂
        @test state.n_O3[] < n_O3_initial

        @info "O₃ destruction test" initial=n_O3_initial final=state.n_O3[] ratio=state.n_O3[]/n_O3_initial
    end

    @testset "Wall Losses" begin
        # Test that wall loss depletes O and O₃
        # Disable O₃ formation by setting O₂ = 0 to isolate wall loss
        volume = 1e-6
        state = create_ozone_state(volume = volume)

        # High wall loss rates, no O₂ to prevent O₃ formation
        config = default_ozone_config(
            update_interval = 1,
            O2_fraction = 0.0,      # No O₂ → no O₃ formation
            wall_loss_O = 1000.0,   # Fast O wall loss
            wall_loss_O3 = 100.0    # Fast O₃ wall loss
        )

        dt = 1e-5  # 10 μs

        # Set initial populations (O will decay without forming O₃)
        state.n_O[] = 1e18
        state.n_O3[] = 1e17

        n_O_initial = state.n_O[]
        n_O3_initial = state.n_O3[]

        # Let wall loss proceed (1000 steps × 10μs = 10ms total)
        # Expected decay: exp(-k×t)
        # O: exp(-1000 × 0.01) ≈ 4.5e-5
        # O₃: exp(-100 × 0.01) ≈ 0.37
        for i in 1:1000
            update_ozone_populations!(
                state, config, dt, i;
                n_dissoc = 0
            )
        end

        # Both should decay significantly
        @test state.n_O[] < n_O_initial * 0.01  # Should be ~4.5e-5
        @test state.n_O3[] < n_O3_initial * 0.5  # Should be ~0.37

        @info "Wall loss test" O_ratio=state.n_O[]/n_O_initial O3_ratio=state.n_O3[]/n_O3_initial
    end

    @testset "Steady State" begin
        # Test approach to steady state with continuous dissociation
        volume = 1e-6
        weight = 1e6
        state = create_ozone_state(volume = volume, particle_weight = weight)
        config = default_ozone_config(
            update_interval = 1,
            wall_loss_O = 100.0,
            wall_loss_O3 = 10.0
        )

        dt = 1e-7  # 100 ns
        n_dissoc_per_step = 50  # Continuous dissociation

        # Run to approach steady state
        n_steps = 2000
        n_O3_history = Float64[]

        for step in 1:n_steps
            update_ozone_populations!(
                state, config, dt, step;
                n_dissoc = n_dissoc_per_step
            )
            push!(n_O3_history, state.n_O3[])
        end

        # Should approach steady state (changes become small)
        final_100 = n_O3_history[end-99:end]
        variation = (maximum(final_100) - minimum(final_100)) / mean(final_100)

        @test state.n_O[] > 0
        @test state.n_O3[] > 0
        @test variation < 0.2  # Less than 20% variation in final 100 steps

        @info "Steady state" final_n_O=state.n_O[] final_n_O3=state.n_O3[] variation_percent=variation*100
    end

    @testset "Disabled Ozone Chemistry" begin
        volume = 1e-6
        state = create_ozone_state(volume = volume)

        # Disabled config (k_O3_form is Float64 to avoid underflow)
        config = OzoneConfig3D{Float32}(
            false,  # DISABLED
            1e-46, 1f-20, 100f0, 10f0,
            5f24, 2.5f25, 300f0, Int32(1)
        )

        dn_O, dn_O3 = update_ozone_populations!(
            state, config, 1e-9, 1;
            n_dissoc = 1000
        )

        @test dn_O == 0.0
        @test dn_O3 == 0.0
        @test state.n_O[] == 0.0
        @test state.n_O3[] == 0.0
    end

    @testset "Update Interval Accumulation" begin
        # Test that dissociation events are accumulated over update interval
        volume = 1e-6
        weight = 1e6
        state = create_ozone_state(volume = volume, particle_weight = weight)
        config = default_ozone_config(update_interval = 10)  # Update every 10 steps

        dt = 1e-9

        # Apply dissociation over 10 steps
        for step in 1:9
            dn_O, dn_O3 = update_ozone_populations!(
                state, config, dt, step;
                n_dissoc = 10
            )
            # Should not update yet
            @test dn_O == 0.0
            @test dn_O3 == 0.0
            @test state.n_O[] == 0.0
        end

        # Accumulated counts
        @test state.n_dissoc[] == 90  # 9 × 10

        # Step 10 triggers update
        dn_O, dn_O3 = update_ozone_populations!(
            state, config, dt, 10;
            n_dissoc = 10
        )

        @test state.n_O[] > 0  # Now updated with all 100 dissociations
        @test state.n_dissoc[] == 0  # Reset after update

        @info "Accumulation test" final_n_O=state.n_O[]
    end

    @testset "Ozone Fractions" begin
        volume = 1e-6
        state = create_ozone_state(volume = volume)
        config = default_ozone_config()

        # Set some densities
        state.n_O[] = 1e20   # 10²⁰ m⁻³
        state.n_O3[] = 1e18  # 10¹⁸ m⁻³

        fractions = get_ozone_fractions(state, config.n_O2)

        # At 1 atm, n_O2 ≈ 5e24, so fractions should be ~10⁻⁴ to 10⁻⁶
        @test fractions.f_O > 0
        @test fractions.f_O < 1e-3
        @test fractions.f_O3 > 0
        @test fractions.f_O3 < fractions.f_O  # O₃ is less abundant

        densities = get_ozone_densities(state)
        @test densities.n_O ≈ 1e20
        @test densities.n_O3 ≈ 1e18

        @info "Ozone fractions" f_O=fractions.f_O f_O3=fractions.f_O3
    end

    @testset "Integration with Detachment" begin
        # Test that ozone state updates detachment config
        volume = 1e-6
        ozone_state = create_ozone_state(volume = volume)

        # Set O atom density
        ozone_state.n_O[] = 1e19  # 10¹⁹ m⁻³

        # Create base detachment config (with n_O = 0 by default)
        det_config = default_detachment_config()
        @test det_config.n_O ≈ 0.0  # Default is zero

        # Create updated config with O from ozone tracking
        det_config_new = create_detachment_config_with_ozone(det_config, ozone_state)

        # Should have the O density
        @test det_config_new.n_O ≈ Float32(1e19)
        @test det_config_new.n_O2 ≈ det_config.n_O2  # Other fields unchanged

        @info "Detachment integration" n_O_old=det_config.n_O n_O_new=det_config_new.n_O
    end

    @testset "Ozone Yield Estimate" begin
        volume = 1e-6
        state = create_ozone_state(volume = volume)
        config = default_ozone_config()

        # Set realistic O density for ozone generator
        state.n_O[] = 1e21  # High O density

        # Estimate yield at 1 W/cm³ = 1e6 W/m³
        power_density = 1e6  # W/m³

        yield = estimate_ozone_yield(state, config, power_density)

        # Typical ozone generator: 50-200 g/kWh
        # This is a rough estimate, mainly testing the function works
        @test yield >= 0
        @test isfinite(yield)

        @info "Ozone yield" n_O=state.n_O[] yield_g_kWh=yield
    end

    @testset "First-principles G-value (ozone_yield_g_per_kwh)" begin
        # (a) Constants are anchored
        @test OZONE_F_N2A_BRANCH == 1.2
        @test OZONE_G_FACTOR_G_PER_KWH ≈ 1.7909876587e3 rtol=1e-6
        @test OZONE_G_FACTOR_G_PER_KWH == 48.0 * 3.6e6 / (6.022e23 * 1.602176634e-19)

        # Shared inputs for nominal / sensitivity calls
        k_d       = 1.0e8
        k_att     = 5.0e6
        k_n2_elec = 2.0e7
        v_d       = 1.0e5
        E_N_Td    = 200.0
        n_gas     = 2.4463134e25

        # (b) Nominal call through the default kwarg
        r = ozone_yield_g_per_kwh(k_d, k_att, k_n2_elec, v_d, E_N_Td, n_gas)
        @test r.R_O3      ≈ 2.29e8            rtol=1e-6
        @test r.G_g_kWh   ≈ 8.3827397962e-1   rtol=1e-6
        @test r.eV_per_O3 ≈ 2.1365182533e3    rtol=1e-6
        @test r.eta_dissoc≈ 1.2263351049e-3   rtol=1e-6

        # (c) Default-equals-explicit identity
        r_explicit = ozone_yield_g_per_kwh(k_d, k_att, k_n2_elec, v_d, E_N_Td, n_gas;
                                           f_n2a_branch = 1.2)
        @test r_explicit.R_O3       == r.R_O3
        @test r_explicit.G_g_kWh    == r.G_g_kWh
        @test r_explicit.eV_per_O3  == r.eV_per_O3
        @test r_explicit.eta_dissoc == r.eta_dissoc

        # (d) Sensitivity direction: f_n2a_branch = 1.3 changes the output
        r_13 = ozone_yield_g_per_kwh(k_d, k_att, k_n2_elec, v_d, E_N_Td, n_gas;
                                     f_n2a_branch = 1.3)
        @test r_13.R_O3    ≈ 2.31e8            rtol=1e-6
        @test r_13.G_g_kWh ≈ 8.4559514974e-1   rtol=1e-6
        @test r_13.R_O3    > r.R_O3
        @test r_13.G_g_kWh > r.G_g_kWh

        # (e) Degenerate guards — exact equality
        degen1 = ozone_yield_g_per_kwh(1e-9, 0.0, 0.0, 1.0e5, 200.0, n_gas)
        @test degen1.G_g_kWh   == 0.0
        @test degen1.eV_per_O3 == Inf
        @test degen1.eta_dissoc == 0.0
        @test degen1.R_O3      == 0.0

        degen2 = ozone_yield_g_per_kwh(k_d, k_att, k_n2_elec, 0.5, E_N_Td, n_gas)
        @test degen2.G_g_kWh   == 0.0
        @test degen2.eV_per_O3 == Inf
        @test degen2.eta_dissoc == 0.0
        @test degen2.R_O3      == 0.0

        @info "G-value test" G_default=r.G_g_kWh G_13=r_13.G_g_kWh
    end

end

println("\nO₃ Chemistry 3D tests complete!")
