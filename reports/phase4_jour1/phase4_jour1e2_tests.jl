# Tests for src/industrial/biorefinery_symbiosis.jl
#
# symbiosis_economics: Algae–PEF–Plasma daily economics with methanizer barter.
# estimate_biorefinery_capex: power-law scaled CAPEX from a 10 m³ reference.
#
# Every expected value below is derived BY HAND from the module's own public
# constants (no re-running of the source to pin numbers):
#   growth 0.8 g/L/day, CO2 1.8 kg/kg, heat 2.0 kWh/m³/day, PEF 80 kJ/kg,
#   protein yield 0.45, harvest 0.90, plasma 300 W, NO3 40 mg-N/L,
#   digestate 5 L/kg, protein 25 €/kg, elec 0.12 €/kWh, CO2 200 €/t,
#   heat 0.05 €/kWh, fert-N 2 €/kg-N.

@testset "Biorefinery Symbiosis Tests" begin

    @testset "symbiosis_economics — hand-computed values at V=100 L (with deal)" begin
        # V = 100.0 L, has_methanizer_deal = true
        r = symbiosis_economics(100.0)

        # A1: daily_biomass = V * 0.8 / 1000 = 100 * 0.8 / 1000 = 0.08 kg/day
        @test r.biomass_kg ≈ 0.08 atol=1e-12

        # A2: daily_protein = 0.08 * 0.45 * 0.90 = 0.0324 kg/day
        @test r.protein_kg ≈ 0.0324 atol=1e-12

        # A3: co2_needed = 0.08 * 1.8 = 0.144 kg/day
        @test r.co2_needed_kg ≈ 0.144 atol=1e-12

        # A4: heat_needed = 100/1000 * 2.0 = 0.2 kWh/day
        @test r.heat_needed_kwh ≈ 0.2 atol=1e-12

        # A5: protein_revenue = 0.0324 * 25.0 = 0.81 €/day
        @test r.protein_revenue ≈ 0.81 atol=1e-12

        # A6: co2_savings = (0.144/1000) * 200.0 = 0.0288 €/day
        @test r.co2_savings ≈ 0.0288 atol=1e-12

        # A7: heat_savings = 0.2 * 0.05 = 0.01 €/day
        @test r.heat_savings ≈ 0.01 atol=1e-12

        # A8: full hand chain for daily_profit at V=100 with deal:
        #   digestate   = 0.08 * 5.0                          = 0.4 L
        #   no3_kg_n    = 0.4 * 40.0 / 1e6                    = 1.6e-5 kg
        #   fert_rev    = 1.6e-5 * 2.0                        = 3.2e-5 €
        #   total_rev   = 0.81 + 3.2e-5                       = 0.810032 €
        #   pef_kwh     = 0.08 * 80.0 / 3600.0                = 1.7777...e-3
        #   plasma_h    = 0.4/50.0 * (5.0/60.0)               = 6.6666...e-4 h
        #   plasma_kwh  = 0.3 * 6.6666...e-4                  = 2.0e-4
        #   total_elec  = 1.7777...e-3 + 2.0e-4               = 1.9777...e-3 kWh
        #   elec_cost   = 1.9777...e-3 * 0.12                 = 2.3733...e-4 €
        #   daily_profit = 0.810032 - 2.3733...e-4            = 0.80979466...
        @test r.daily_profit ≈ 0.0324*25.0 + (0.4*40.0/1e6)*2.0 - (0.08*80.0/3600.0 + (0.4/50.0*(5.0/60.0))*0.3)*0.12 atol=1e-12
        @test r.daily_profit ≈ 0.8097946666666667 atol=1e-8
        @test r.annual_profit ≈ r.daily_profit * 300.0 atol=1e-10
    end

    @testset "symbiosis_economics — hand values at reference volume V=10_000 L" begin
        # V = 10_000.0 L:
        #   daily_biomass = 10_000 * 0.8 / 1000 = 8.0 kg/day
        #   daily_protein = 8.0 * 0.45 * 0.90   = 3.24 kg/day
        #   co2_needed    = 8.0 * 1.8           = 14.4 kg/day
        r_ref = symbiosis_economics(10_000.0)
        @test r_ref.biomass_kg ≈ 8.0 atol=1e-12
        @test r_ref.protein_kg ≈ 3.24 atol=1e-12
        @test r_ref.co2_needed_kg ≈ 14.4 atol=1e-12
    end

    @testset "monotonicity in culture volume" begin
        r_small = symbiosis_economics(100.0)
        r_big   = symbiosis_economics(10_000.0)
        # biomass = V * const: strictly increasing in V
        @test r_big.biomass_kg > r_small.biomass_kg
        # CAPEX = sum of (const + const*(V/ref)^α with α>0): non-decreasing,
        # and the strictly growing power terms make 10_000 L strictly > 100 L
        capex_small = estimate_biorefinery_capex(100.0)
        capex_big   = estimate_biorefinery_capex(10_000.0)
        @test capex_big > capex_small
    end

    @testset "bounds and ratio invariants" begin
        r = symbiosis_economics(100.0)
        # protein_kg = biomass_kg * 0.45 * 0.90 ⇒ ratio exactly 0.405,
        # strictly below the raw extraction yield 0.45
        @test 0.0 < r.protein_kg / r.biomass_kg <= 0.45
        @test r.protein_kg / r.biomass_kg ≈ 0.45 * 0.90 atol=1e-12
        # co2_needed_kg = biomass_kg * 1.8 ⇒ ratio exactly the constant
        @test r.co2_needed_kg / r.biomass_kg ≈ 1.8 atol=1e-12
    end

    @testset "degenerate input — zero volume" begin
        r0 = symbiosis_economics(0.0)
        # 0.0 * const is exactly 0.0 in IEEE 754: use ==, not ≈
        @test r0.biomass_kg == 0.0
        @test r0.protein_kg == 0.0
        @test r0.total_revenue == 0.0
        @test r0.total_cost == 0.0
        @test r0.daily_profit == 0.0
        @test r0 isa NamedTuple
        # fixed-cost CAPEX components survive zero volume:
        # PEF 50 + HV 30 + plasma 10 + control 20 = 110 k€ (tanks and
        # installation scale to 0^α = 0)
        @test estimate_biorefinery_capex(0.0) ≈ 110_000.0 atol=1e-6
    end

    @testset "estimate_biorefinery_capex — hand-computed component sums" begin
        # At the reference volume V = ref = 10_000 L, (V/ref)^α = 1.0 for all α,
        # so every term hits its full coefficient exactly:
        #   tanks 15.0 | PEF 50.0+10.0 | HV 30.0+5.0 | plasma 10.0
        #   control 20.0+5.0 | installation 25.0  →  170.0 k€ = 170_000 €
        @test estimate_biorefinery_capex(10_000.0) ≈ 170_000.0 atol=1e-8
        # At V = 100 L (V/ref = 0.01 = 10^-2), each power term is exact in log10:
        #   tanks  15 * 10^-1.4        ≈ 0.59716
        #   PEF    50 + 10*10^-1.0     = 51.0
        #   HV     30 + 5*10^-0.6      ≈ 31.25594
        #   plasma 10.0
        #   ctrl   20 + 5*10^-0.6      ≈ 21.25594
        #   instal 25 * 10^-1.2        ≈ 1.57739
        #   sum  ≈ 115.68644 k€ → ≈ 115_686.44 €
        # The expected value is the hand-derivation itself (same closed form),
        # pinned to 1e-4 € so it tracks the math, not a rounded transcription.
        @test estimate_biorefinery_capex(100.0) ≈
            (15.0*0.01^0.70 + 50.0 + 10.0*0.01^0.50 + 30.0 + 5.0*0.01^0.30 +
             10.0 + 20.0 + 5.0*0.01^0.30 + 25.0*0.01^0.60) * 1000.0 atol=1e-4
    end

    @testset "with-deal vs standalone — barter changes sign of CO2/heat terms" begin
        r_deal       = symbiosis_economics(100.0)
        r_standalone = symbiosis_economics(100.0; has_methanizer_deal=false)

        # with deal: CO2 and heat are bartered (free), no purchase cost
        @test r_deal.co2_cost == 0.0
        @test r_deal.heat_cost == 0.0
        @test r_deal.co2_savings > 0.0
        @test r_deal.heat_savings > 0.0
        @test r_deal.methanizer_savings > 0.0

        # standalone: CO2 and heat are purchased at market price
        #   co2_cost = 0.000144 t * 200 €/t = 0.0288 €
        #   heat_cost = 0.2 kWh * 0.05 €/kWh = 0.01 €
        @test r_standalone.co2_cost > 0.0
        @test r_standalone.co2_cost ≈ 0.0288 atol=1e-12
        @test r_standalone.heat_cost > 0.0
        @test r_standalone.heat_cost ≈ 0.01 atol=1e-12
        @test r_standalone.co2_savings == 0.0
        @test r_standalone.heat_savings == 0.0
        @test r_standalone.methanizer_savings == 0.0
        # paying for CO2 + heat strictly reduces profit (electricity identical)
        @test r_standalone.daily_profit < r_deal.daily_profit
    end
end
