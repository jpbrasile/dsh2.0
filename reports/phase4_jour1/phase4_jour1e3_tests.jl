# Tests for src/industrial/biorefinery_symbiosis.jl
# Covers symbiosis_economics() and estimate_biorefinery_capex().

@testset "Biorefinery Symbiosis Tests" begin

    # ── symbiosis_economics — hand-computed values at V=100 L (with deal) ──

    r_100 = symbiosis_economics(100.0; has_methanizer_deal=true)

    @test r_100.biomass_kg ≈ 0.08
    # 100.0 * 0.8 / 1000.0 = 0.08

    @test r_100.protein_kg ≈ 0.0324
    # 0.08 * 0.45 * 0.90 = 0.0324

    @test r_100.daily_profit ≈ 0.8097946666666667 atol=1e-10
    # total_revenue - total_cost computation; see plan for full derivation

    @test r_100.fertilizer_revenue ≈ 0.000032 atol=1e-12
    # 0.4 L digestate * 40.0 mg/L / 1e6 = 1.6e-5 kg_N * 2.0 €/kg = 3.2e-5 €

    # ── symbiosis_economics — cost structure with/without deal ──

    @test r_100.co2_cost == 0.0         # free under deal
    @test r_100.heat_cost == 0.0        # free under deal
    @test r_100.methanizer_savings > 0.0  # scrubbing cost avoided

    r_standalone = symbiosis_economics(100.0; has_methanizer_deal=false)

    @test r_standalone.co2_cost > 0.0               # bottled CO₂ is not free
    @test r_100.total_cost < r_standalone.total_cost # deal reduces costs

    # ── Bound check: protein fraction ──

    @test 0.0 < r_100.protein_kg / r_100.biomass_kg <= _SYM_PROTEIN_YIELD
    # protein_kg/biomass_kg = _SYM_PROTEIN_YIELD * _SYM_HARVEST_EFF = 0.405 ≤ 0.45

    # ── Monotonicity ──

    r_200 = symbiosis_economics(200.0; has_methanizer_deal=true)

    @test r_200.biomass_kg > r_100.biomass_kg
    # V appears linearly in biomass: 200*0.8/1000 = 0.16 > 100*0.8/1000 = 0.08

    @test estimate_biorefinery_capex(200.0) > estimate_biorefinery_capex(100.0)
    # All components are either constant or scale with (V/ref)^p for p>0 → increasing

    # ── Degenerate input: zero volume ──

    r_zero = symbiosis_economics(0.0; has_methanizer_deal=true)

    @test r_zero.daily_profit ≈ 0.0 atol=1e-12
    # V=0 → biomass=0 → revenue=0, cost=0 → profit=0

    @test estimate_biorefinery_capex(0.0) ≈ 110_000.0
    # (50 + 30 + 10 + 20) * 1000 = 110 k€ * 1000 = 110,000 €
    # All power-law terms (V/ref)^p → 0 for V=0, p>0; only fixed-cost terms remain.

end