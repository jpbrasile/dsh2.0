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

    # ------------------------------------------------------------------
    # 1. Construction — PhysicsUQParam convenience constructor defaults
    # ------------------------------------------------------------------
    p = PhysicsUQParam(:test, 1.0, 0.0, 2.0, :fixed)
    @test p.std == 0.0
    @test p.unit == ""
    @test p.description == ""

    # ------------------------------------------------------------------
    # 2. Defaults — default_physics_uq_params()
    # ------------------------------------------------------------------
    dp = default_physics_uq_params()
    @test length(dp.params) == 13
    dp_by_name(name) = dp.params[findfirst(q -> q.name == name, dp.params)]

    # f_irrev_max anchor
    f = dp_by_name(:f_irrev_max)
    @test f.value == 0.65
    @test f.lo == 0.35
    @test f.hi == 0.95
    @test f.distribution == :normal
    @test f.std == 0.15

    # E_threshold_kJ_m3 anchor
    e = dp_by_name(:E_threshold_kJ_m3)
    @test e.value == 95.0
    @test e.lo == 65.0
    @test e.hi == 155.0
    @test e.distribution == :normal
    @test e.std == 20.0

    # w_TS anchor
    w = dp_by_name(:w_TS)
    @test w.value == 0.04
    @test w.lo == 0.02
    @test w.hi == 0.08
    @test w.distribution == :triangular

    # tau2 anchor
    t2 = dp_by_name(:tau2)
    @test t2.value == 150.0
    @test t2.lo == 50.0
    @test t2.hi == 400.0
    @test t2.distribution == :lognormal
    @test t2.std == 0.3

    # Config defaults
    @test dp.geometry_type == :parallel
    @test dp.gap_m == 0.025
    @test dp.L_m == 0.050
    @test dp.nr == 48
    @test dp.nz == 24
    @test dp.T_initial == 293.15
    @test dp.use_pavlin == true
    @test dp.use_ion_transport == true
    @test dp.C_ion_initial == 150.0

    # ------------------------------------------------------------------
    # 3. Plateau — plateau_physics_uq_params() overrides pulse params
    # ------------------------------------------------------------------
    pp = plateau_physics_uq_params()
    pp_by_name(name) = pp.params[findfirst(q -> q.name == name, pp.params)]
    for name in (:V_peak_kV, :V_plateau_V, :n_pulses)
        @test pp_by_name(name).lo == pp_by_name(name).hi
    end
    @test pp_by_name(:t_peak_us).lo == 5.0
    @test pp_by_name(:t_peak_us).hi == 50.0

    # ------------------------------------------------------------------
    # 4. Sampling
    # ------------------------------------------------------------------
    # :fixed returns value exactly
    @test Liquid._sample_physics_param(dp.params[1]) == 6.0

    # Draw bounds within [lo, hi] for each stochastic distribution
    Random.seed!(12345)
    for _ in 1:200
        s = Liquid._sample_physics_param(f)  # :normal
        @test f.lo <= s <= f.hi
    end
    Random.seed!(12345)
    for _ in 1:200
        s = Liquid._sample_physics_param(t2)  # :lognormal
        @test t2.lo <= s <= t2.hi
    end
    Random.seed!(12345)
    for _ in 1:200
        s = Liquid._sample_physics_param(w)  # :triangular
        @test w.lo <= s <= w.hi
    end

    # _sample_all_params: Dict of 13 Float64, reproducible under same seed
    Random.seed!(42)
    d1 = Liquid._sample_all_params(dp)
    @test length(d1) == 13
    @test all(v -> v isa Float64, values(d1))
    Random.seed!(42)
    d2 = Liquid._sample_all_params(dp)
    @test d1 == d2

    # ------------------------------------------------------------------
    # 5. EROEI — hand-computed anchor: (10% * 250 * 38.25 kg/m3 VS * 1000
    # mL) * 0.0358 kJ/mL / 3600 kJ = 34233.75/3600 = 9.509375
    # ------------------------------------------------------------------
    @test Liquid._calculate_eroei(10.0, 1.0, 0.05, 250.0) ≈ 9.509375 atol=1e-12
    @test Liquid._calculate_eroei(10.0, 0.0, 0.05, 250.0) == 0.0

    # ------------------------------------------------------------------
    # 6. Proxy-based Monte Carlo (CPU-only, never touches the GPU path)
    # ------------------------------------------------------------------
    Random.seed!(42)
    r = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
    @test r isa PhysicsUQResults
    @test r.n_total == 300
    @test 0 <= r.n_feasible <= 300
    @test length(r.EROEI_distribution) == r.n_feasible
    @test r.f_irrev_p5 <= r.f_irrev_p50 <= r.f_irrev_p95
    Random.seed!(42)
    r2 = run_physics_monte_carlo_proxy(; n_samples=300, verbose=false)
    @test r2.f_irrev_mean == r.f_irrev_mean

    # ------------------------------------------------------------------
    # 7. Convergence check
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 8. Round-trip export — physics_uq_to_dict
    # ------------------------------------------------------------------
    d = physics_uq_to_dict(r)
    @test haskey(d, "metadata")
    @test haskey(d, "f_irrev")
    @test haskey(d, "E_kWh_m3")
    @test haskey(d, "dT_max_K")
    @test haskey(d, "CH4_yield")
    @test haskey(d, "CH4_increase_pct")
    @test d["metadata"]["n_total"] == 300

end
