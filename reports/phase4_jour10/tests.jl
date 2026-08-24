# test/liquid/test_oscillation_enhanced_ep.jl
"""
Tests for Oscillation-Enhanced Electroporation (src/liquid/oscillation_enhanced_ep.jl).
Covers: OscillationEnhancedConfig defaults, OD_EPState defaults, OD_EPParams
Krassowska anchors and derived values, single-run structure/invariants and
determinism, the deprecated no-op kwargs claim, the 9-waveform batch, and the
structural shape of compute_validation_metrics.
CPU-only, deterministic — no GPU dependencies, no model-vs-experiment claims.
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

@testset "Oscillation-Enhanced Electroporation" begin

    # ------------------------------------------------------------------
    # 1. Config defaults — OscillationEnhancedConfig()
    # ------------------------------------------------------------------
    cfg = Liquid.OscillationEnhancedConfig()
    @test cfg.κ_osc ≈ 1e-7
    @test cfg.r_p_crit ≈ 1.5e-9
    @test cfg.enabled == true

    # ------------------------------------------------------------------
    # 2. State defaults — OD_EPState() (exact equality)
    # ------------------------------------------------------------------
    st = Liquid.OD_EPState()
    @test st.N == 1.0e10
    @test st.r_p == 0.5e-9
    @test st.Γ_line == 1.0
    @test st.C_in == 1.0
    @test st.t == 0.0
    @test st.max_r_p == 0.5e-9
    @test st.n_total_steps == 0

    # ------------------------------------------------------------------
    # 3. Params: Krassowska anchors, overrides, derived values
    # ------------------------------------------------------------------
    p = Liquid.default_OD_ep_params()
    @test p.V_ep == 0.258
    @test p.N_0 == 1.5e15
    @test p.q == 2.46
    @test p.N_eq == 1.0e10
    @test p.α == 1.0e9

    p2 = Liquid.default_OD_ep_params(N_0_override=2.0e15)
    @test p2.N_0 == 2.0e15

    p3 = Liquid.default_OD_ep_params(wall_factor=0.5)
    @test p3.wall_factor == 1.0  # floored at 1.0

    # Derived membrane/cell values (r_cell = 8.0e-6, d_mem = 10e-9)
    @test p.A_m ≈ 8.04247719318987e-10 rtol=1e-10
    @test p.V_cell ≈ 2.144660584850632e-15 rtol=1e-10
    @test p.Am_over_Vcell ≈ 375000.0 rtol=1e-10
    @test p.τ_m ≈ 4.4625106576511995e-7 rtol=1e-10
    @test p.a_p ≈ 0.03453133246992 rtol=1e-10

    # ------------------------------------------------------------------
    # 4. Single run on spec 1: structure + invariants + determinism
    # ------------------------------------------------------------------
    specs = Liquid.li_waveform_specs()
    wf = Liquid.create_li_waveform(specs[1])
    r = Liquid.run_0d_ep_simulation(wf, specs[1], p)

    @test r isa Liquid.OD_EPResult
    @test r.waveform_label == specs[1].label
    @test 0.0 <= r.RE_predicted <= 100.0
    @test r.RE_predicted ≈ (1.0 - r.C_in_final) * 100.0
    @test r.r_p_max >= 0.5e-9
    @test r.Vm_max > 0
    @test 0.0 <= r.f_large_pore <= 1.0
    @test 0.0 <= r.C_in_final <= 1.0

    r2 = Liquid.run_0d_ep_simulation(wf, specs[1], p)
    @test r.RE_predicted == r2.RE_predicted
    @test r.r_p_max == r2.r_p_max

    # ------------------------------------------------------------------
    # 5. No-op claim — deprecated kwargs do not change the trajectory
    #    (tested via run_0d_ep_simulation, which never reads them)
    # ------------------------------------------------------------------
    p_noop = Liquid.default_OD_ep_params(osc_enhance=5.0, k_fat=1.0, k_goertzel=1.0)
    r_noop = Liquid.run_0d_ep_simulation(wf, specs[1], p_noop)
    @test r_noop.RE_predicted == r.RE_predicted
    @test r_noop.r_p_max == r.r_p_max

    # ------------------------------------------------------------------
    # 6. Batch — run_all_li_waveforms
    # ------------------------------------------------------------------
    results = Liquid.run_all_li_waveforms(p)
    @test length(results) == 9
    @test [res.waveform_label for res in results] == [s.label for s in specs]
    @test all(res -> 0.0 <= res.RE_predicted <= 100.0, results)

    # ------------------------------------------------------------------
    # 7. Validation metrics — structure only (no model-vs-experiment claim)
    # ------------------------------------------------------------------
    metrics = Liquid.compute_validation_metrics(results, specs)
    @test hasfield(typeof(metrics), :rmse)
    @test hasfield(typeof(metrics), :r_squared)
    @test hasfield(typeof(metrics), :rank_correct)
    @test hasfield(typeof(metrics), :rank_total)
    @test hasfield(typeof(metrics), :rank_accuracy)
    @test metrics.rank_total == 36
    @test 0 <= metrics.rank_correct <= metrics.rank_total
    @test metrics.rank_accuracy == metrics.rank_correct / metrics.rank_total
    @test metrics.rmse >= 0.0
end
