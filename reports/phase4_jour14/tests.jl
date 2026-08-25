#!/usr/bin/env julia
"""
Test adaptive subcycling state machine for multi-timescale plasma simulations.

Run standalone: julia --project=. test/gpu3d_integration/test_adaptive_subcycle.jl
Run with suite: julia --project=. test/gpu3d_integration/runtests.jl
"""

# Only load modules if running standalone (not from runtests.jl)
if !@isdefined(GPU3DIntegration)
    using Test
    include(joinpath(@__DIR__, "..", "..", "..", "src", "PlasmaDigitalTwin.jl"))
    using .PlasmaDigitalTwin.GPU3DIntegration
end

using Test

println("=" ^ 60)
println("Testing Adaptive Subcycling Framework")
println("=" ^ 60)

@testset "PropagationMode enum" begin
    println("\n--- PropagationMode enum ---")

    # Test all modes exist
    @test BUILDUP isa PropagationMode
    @test PROPAGATION isa PropagationMode
    @test CHEMISTRY isa PropagationMode
    @test STEADY_STATE isa PropagationMode

    # Test mode symbols
    @test mode_symbol(BUILDUP) == "🟢"
    @test mode_symbol(PROPAGATION) == "🔴"
    @test mode_symbol(CHEMISTRY) == "🟡"
    @test mode_symbol(STEADY_STATE) == "⚪"

    # Test mode names
    @test mode_name(BUILDUP) == "BUILDUP"
    @test mode_name(PROPAGATION) == "PROPAGATION"
    @test mode_name(CHEMISTRY) == "CHEMISTRY"
    @test mode_name(STEADY_STATE) == "STEADY_STATE"

    println("✓ All modes and symbols correct")
end

@testset "AdaptiveSubcycleConfig" begin
    println("\n--- AdaptiveSubcycleConfig ---")

    # Test default config
    config = create_adaptive_config()
    @test config.modes == [BUILDUP, PROPAGATION, CHEMISTRY]
    @test config.subcycle_factors[BUILDUP] == 10
    @test config.subcycle_factors[PROPAGATION] == 100
    @test config.subcycle_factors[CHEMISTRY] == 20
    @test config.min_steps_per_mode == 5000
    println("  Default config: modes=$(length(config.modes)), z_target=$(config.z_target)m")

    # Test jet config
    jet_config = create_jet_config(z_tube_exit = 0.038)
    @test jet_config.z_target == Float32(0.038)
    println("  Jet config: z_target=$(jet_config.z_target)m")

    # Test streamer config
    streamer_config = create_streamer_config(z_gap = 0.01)
    @test streamer_config.z_target == Float32(0.01)
    println("  Streamer config: z_target=$(streamer_config.z_target)m")

    # Test custom config
    custom_config = create_adaptive_config(
        modes = [BUILDUP, STEADY_STATE],
        z_target = 0.05,
        min_steps_per_mode = 1000
    )
    @test length(custom_config.modes) == 2
    @test custom_config.modes[1] == BUILDUP
    @test custom_config.modes[2] == STEADY_STATE
    @test custom_config.min_steps_per_mode == 1000
    println("  Custom config: $(length(custom_config.modes)) modes")

    println("✓ All config tests passed")
end

@testset "AdaptiveSubcycleState" begin
    println("\n--- AdaptiveSubcycleState ---")

    config = create_adaptive_config()
    state = create_adaptive_state(config)

    # Test initial state
    @test current_mode(state) == BUILDUP
    @test state.mode_index == 1
    @test state.steps_total == 0
    @test state.steps_in_mode == 0
    @test state.mode_transitions == 0
    @test isempty(state.z_history)
    @test isempty(state.v_history)

    println("  Initial mode: $(mode_name(current_mode(state)))")
    println("  Subcycle factor: $(get_subcycle_factor(state, config))")

    @test get_subcycle_factor(state, config) == 10  # BUILDUP default

    println("✓ Initial state correct")
end

@testset "should_update_chemistry!" begin
    println("\n--- should_update_chemistry! ---")

    config = create_adaptive_config()
    state = create_adaptive_state(config)

    # In BUILDUP mode, subcycle = 10
    # Should NOT update for first 9 steps
    for i in 1:9
        result = should_update_chemistry!(state, config)
        @test result == false
    end
    @test state.steps_total == 9
    @test state.steps_since_update == 9

    # Step 10 should trigger update
    result = should_update_chemistry!(state, config)
    @test result == true
    @test state.steps_total == 10
    @test state.steps_since_update == 0  # Reset after update

    # Next 9 steps should not trigger
    for i in 1:9
        result = should_update_chemistry!(state, config)
        @test result == false
    end

    # Step 20 should trigger
    result = should_update_chemistry!(state, config)
    @test result == true
    @test state.steps_total == 20

    println("  Steps total: $(state.steps_total)")
    println("  Updates triggered at: 10, 20 (every $(get_subcycle_factor(state, config)) steps)")
    println("✓ Chemistry update timing correct")
end

@testset "get_effective_dt" begin
    println("\n--- get_effective_dt ---")

    config = create_adaptive_config()
    state = create_adaptive_state(config)

    dt_pic = Float32(1e-13)  # 100 fs

    # BUILDUP mode: subcycle = 10
    dt_eff = get_effective_dt(state, config, dt_pic)
    @test dt_eff ≈ 10 * dt_pic
    println("  BUILDUP: dt_eff = $(dt_eff*1e12) ps ($(Int(dt_eff/dt_pic))× dt_pic)")

    # Manually set to PROPAGATION mode
    state.mode = PROPAGATION
    state.mode_index = 2
    dt_eff = get_effective_dt(state, config, dt_pic)
    @test dt_eff ≈ 100 * dt_pic
    println("  PROPAGATION: dt_eff = $(dt_eff*1e12) ps ($(Int(dt_eff/dt_pic))× dt_pic)")

    # CHEMISTRY mode
    state.mode = CHEMISTRY
    state.mode_index = 3
    dt_eff = get_effective_dt(state, config, dt_pic)
    @test dt_eff ≈ 20 * dt_pic
    println("  CHEMISTRY: dt_eff = $(dt_eff*1e12) ps ($(Int(dt_eff/dt_pic))× dt_pic)")

    println("✓ Effective dt calculation correct")
end

@testset "update_mode! - velocity-based transition" begin
    println("\n--- update_mode! (velocity-based) ---")

    config = create_jet_config(
        z_tube_exit = 0.03,
        v_threshold = 1e4,  # 10 km/s
        min_steps_per_mode = 100  # Lower for testing
    )
    state = create_adaptive_state(config)

    dt = 1e-10  # 100 ps per "macro step"

    # Simulate wave propagation at 50 km/s
    v_wave = 5e4  # 50 km/s
    z = 0.010  # Start at 10 mm
    t = 0.0

    println("  Simulating wave at v = $(v_wave/1e3) km/s...")

    # Run through BUILDUP phase
    transitions = 0
    for step in 1:500
        # Advance position
        z += v_wave * dt
        t += dt

        # Simulate chemistry update every 10 steps
        if step % 10 == 0
            for _ in 1:10
                should_update_chemistry!(state, config)
            end

            changed, new_mode = update_mode!(state, config, z, t)
            if changed
                transitions += 1
                println("  Step $step: Transition to $(mode_name(new_mode)) at z=$(round(z*1e3, digits=2))mm")
            end
        end
    end

    @test transitions >= 1  # Should have at least one transition
    @test current_mode(state) != BUILDUP  # Should have left BUILDUP

    # Check velocity tracking
    @test !isempty(state.v_history)
    v_avg = get_wave_velocity(state)
    println("  Measured wave velocity: $(round(v_avg/1e3, digits=1)) km/s")
    @test v_avg > 0  # Should have positive velocity

    println("✓ Velocity-based transition works")
end

@testset "update_mode! - position-based transition" begin
    println("\n--- update_mode! (position-based) ---")

    config = create_jet_config(
        z_tube_exit = 0.03,  # 30 mm
        z_chemistry_fraction = 0.8,  # Trigger at 24 mm
        min_steps_per_mode = 10  # Lower for testing
    )
    state = create_adaptive_state(config)

    # Force into PROPAGATION mode
    state.mode = PROPAGATION
    state.mode_index = 2
    state.steps_in_mode = 100

    # Add some velocity history
    for _ in 1:20
        push!(state.v_history, 5e4)
        push!(state.z_history, 0.020)
        push!(state.t_history, 1e-9)
    end

    println("  Testing position threshold at 80% of $(config.z_target*1e3)mm = $(0.8*config.z_target*1e3)mm")

    # Below threshold - no transition
    changed, _ = update_mode!(state, config, 0.020, 2e-9)  # 20 mm
    @test changed == false
    @test current_mode(state) == PROPAGATION
    println("  z = 20mm: No transition (below threshold)")

    # Above threshold - should transition
    changed, new_mode = update_mode!(state, config, 0.025, 3e-9)  # 25 mm > 24 mm threshold
    @test changed == true
    @test new_mode == CHEMISTRY
    println("  z = 25mm: Transition to $(mode_name(new_mode))")

    println("✓ Position-based transition works")
end

@testset "get_state_summary" begin
    println("\n--- get_state_summary ---")

    config = create_jet_config(z_tube_exit = 0.03)
    state = create_adaptive_state(config)

    # Add some history
    push!(state.z_history, Float32(0.015))
    push!(state.t_history, Float32(1e-9))
    push!(state.v_history, Float32(5e4))
    state.steps_total = 1000
    state.mode_transitions = 1

    summary = get_state_summary(state, config)

    @test summary.mode == BUILDUP
    @test summary.mode_symbol == "🟢"
    @test summary.subcycle_factor == 10
    @test summary.z_front ≈ 0.015
    @test summary.z_target == Float32(0.03)
    @test summary.z_progress ≈ 0.5
    @test summary.steps_total == 1000

    println("  Summary: $(summary.mode_symbol) $(summary.mode_name)")
    println("    z = $(summary.z_front*1e3)mm / $(summary.z_target*1e3)mm ($(round(summary.z_progress*100))%)")
    println("    v = $(round(summary.v_wave/1e3, digits=1)) km/s")
    println("    subcycle = $(summary.subcycle_factor)")

    println("✓ State summary correct")
end

@testset "Full simulation scenario" begin
    println("\n--- Full Simulation Scenario ---")
    println("  Simulating plasma jet from z=10mm to z=30mm tube exit")

    config = create_jet_config(
        z_tube_exit = 0.030,  # 30 mm
        v_threshold = 3e4,    # 30 km/s to consider established
        z_chemistry_fraction = 0.85,
        min_steps_per_mode = 50
    )
    state = create_adaptive_state(config)

    dt_pic = 1e-13  # 100 fs
    t = 0.0
    z = 0.010  # Start at 10 mm

    # Simulate wave velocity typical of plasma jets (~50-100 km/s)
    n_steps = 0
    chemistry_updates = 0
    mode_history = [current_mode(state)]

    while t < 300e-9 && z < 0.035  # 300 ns max or past tube exit
        n_steps += 1
        t += dt_pic

        # Wave velocity typical of plasma jets (~50 km/s, increases slightly)
        v_wave = 5e4 + (z - 0.010) * 1e6  # Starts at 50 km/s, accelerates
        z += v_wave * dt_pic

        # Check chemistry update
        if should_update_chemistry!(state, config)
            chemistry_updates += 1
            dt_eff = get_effective_dt(state, config, Float32(dt_pic))

            # Update mode
            changed, new_mode = update_mode!(state, config, z, t)
            if changed
                push!(mode_history, new_mode)
                println("  t=$(round(t*1e9, digits=1))ns, z=$(round(z*1e3, digits=1))mm: → $(mode_name(new_mode))")
            end
        end
    end

    println("\n  Results:")
    println("    PIC steps: $n_steps")
    println("    Chemistry updates: $chemistry_updates")
    println("    Mode transitions: $(length(mode_history)-1)")
    println("    Final mode: $(mode_name(current_mode(state)))")
    println("    Final z: $(round(z*1e3, digits=1))mm")
    println("    Final t: $(round(t*1e9, digits=1))ns")

    # Check we went through expected progression
    @test n_steps > 0
    @test chemistry_updates > 0
    @test length(mode_history) >= 2  # At least one transition

    # Should have reached CHEMISTRY mode if wave reached 85% of tube exit
    if z > 0.85 * 0.030
        @test CHEMISTRY in mode_history
        println("    ✓ Reached CHEMISTRY mode as expected")
    end

    println("✓ Full scenario completed successfully")
end

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
