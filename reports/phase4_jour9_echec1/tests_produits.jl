# test/liquid/test_monte_carlo_physics.jl
"""
Tests for Physics UQ Monte Carlo (proxy-only, CPU, deterministic).
Covers: construction, default params, plateau override, sampling, EROEI,
proxy run, convergence check, and round-trip to dict.
"""

using Test
using Random

# Handle both standalone and runtests.jl execution
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
    @test p.description == ""

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
