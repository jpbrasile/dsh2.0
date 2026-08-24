Good, I can see the test patterns used. Now let me do the derivation work.

Let me compute the expected values carefully from the source constants.

---

## Source Constants Recap (lines 22-41)

```
_SYM_GROWTH_RATE_G_L_DAY   = 0.8     # g/L/day
_SYM_CO2_PER_KG_BIOMASS    = 1.8     # kg CO₂/kg biomass
_SYM_HEAT_KWH_M3_DAY       = 2.0     # kWh/m³/day
_SYM_PEF_ENERGY_KJ_KG      = 80.0    # kJ/kg
_SYM_PROTEIN_YIELD         = 0.45    # fraction
_SYM_HARVEST_EFF           = 0.90    # fraction
_SYM_PLASMA_POWER_W        = 300.0
_SYM_NO3_PROD_MG_L         = 40.0    # mg-N/L
_SYM_DIGESTATE_L_KG        = 5.0     # L/kg
_SYM_PROTEIN_EUR_KG        = 25.0
_SYM_ELEC_EUR_KWH          = 0.12
_SYM_CO2_EUR_T             = 200.0
_SYM_HEAT_EUR_KWH          = 0.05
_SYM_FERT_N_EUR_KG         = 2.0
```

## Hand-Computed Values at V = 100 L

This is small enough to hand-check but large enough to avoid degeneracy.

**symbiosis_economics(100.0; has_methanizer_deal=true):**

- `daily_biomass_kg` = 100 × 0.8 / 1000 = **0.08 kg**
- `daily_protein_kg` = 0.08 × 0.45 × 0.90 = 0.08 × 0.405 = **0.0324 kg**
- `co2_needed_kg` = 0.08 × 1.8 = **0.144 kg**
- `co2_needed_tons` = 0.144 / 1000 = **0.000144 t**
- `heat_needed_kwh` = 100/1000 × 2.0 = **0.2 kWh**
- `pef_energy_kwh` = 0.08 × 80.0 / 3600 = 6.4/3600 = **0.0017777... kWh**
- `digestate_L` = 0.08 × 5.0 = **0.4 L**
- `plasma_hours` = 0.4/50.0 × (5.0/60.0) = 0.008 × 0.08333... = **0.0006666... h**
- `plasma_energy_kwh` = (300/1000) × 0.0006666... = 0.3 × 0.0006666... = **0.0002 kWh**

Let me recompute plasma_hours more precisely: 0.4/50.0 = 0.008; 0.008 × (5.0/60.0) = 0.008 × 0.0833333... = 0.000666666...

`plasma_energy_kwh` = 0.3 × 0.000666666... = 0.0002 kWh exactly.

- `total_elec_kwh` = 0.0017777... + 0.0002 = **0.00197777... kWh**
- `no3_kg_n` = 0.4 × 40.0 / 1e6 = 16.0/1e6 = **0.000016 kg_N** = **1.6×10⁻⁵ kg_N**
- `protein_revenue` = 0.0324 × 25.0 = **0.81 €**
- `fertilizer_revenue` = 0.000016 × 2.0 = **0.000032 €**
- `total_revenue` = 0.81 + 0.000032 = **0.810032 €**
- `electricity_cost` = 0.00197777... × 0.12 = **0.000237333... €**

With methanizer deal: `co2_cost` = 0, `heat_cost` = 0, `total_cost` = 0.000237333...

- `daily_profit` = 0.810032 - 0.000237333... = **0.809794666... €**

**estimate_biorefinery_capex(100.0):**

V=100, ref=10000, ratio = 100/10000 = 0.01

- Culture tanks: 15.0 × 0.01^0.70 = 15.0 × 0.01^0.7

0.01^0.7 = exp(0.7 × ln(0.01)) = exp(0.7 × -4.60517...) = exp(-3.22362...) ≈ 0.0398107...

Culture tanks = 15.0 × 0.0398107... ≈ 0.59716... k€

- PEF system: 50.0 + 10.0 × 0.01^0.50 = 50.0 + 10.0 × 0.1 = 50.0 + 1.0 = 51.0 k€
- HV generator: 30.0 + 5.0 × 0.01^0.30 = 30.0 + 5.0 × exp(0.3 × -4.60517...) = 30.0 + 5.0 × exp(-1.38155...) = 30.0 + 5.0 × 0.2511886... = 30.0 + 1.25594... = 31.25594... k€
- Plasma unit: 10.0 k€ (constant)
- Control: 20.0 + 5.0 × 0.01^0.30 = 20.0 + 1.25594... = 21.25594... k€
- Installation: 25.0 × 0.01^0.60 = 25.0 × exp(0.6 × -4.60517...) = 25.0 × exp(-2.76310...) = 25.0 × 0.0630957... = 1.57739... k€

Sum = 0.59716 + 51.0 + 31.25594 + 10.0 + 21.25594 + 1.57739 = 115.68644... k€

**CAPEX = 115,686.44... €** (sum × 1000)

Now, let me verify monotonicity:

**symbiosis_economics(200.0):** (double 100)

- `daily_biomass_kg` = 200 × 0.8 / 1000 = 0.16 kg (doubles)
- `daily_protein_kg` = 0.16 × 0.405 = 0.0648 kg (doubles)
- profit scales approximately linearly with volume here, so profit(200) > profit(100)

**estimate_biorefinery_capex(200.0):** ratio = 0.02

- Culture tanks: 15.0 × 0.02^0.70 = 15.0 × exp(0.7 × ln(0.02)) = 15.0 × exp(0.7 × -3.912...) = 15.0 × exp(-2.7384...) = 15.0 × 0.06470... = 0.9705... k€

So total is larger than at 100 L. Monotonicity holds.

**Zero-volume case:**

`symbiosis_economics(0.0)`:
- `daily_biomass_kg` = 0.0 × 0.8 / 1000 = 0.0
- `daily_protein_kg` = 0.0
- Everything scales to 0 → `daily_profit = 0.0`, `total_revenue = 0.0`, `total_cost = 0.0`

`estimate_biorefinery_capex(0.0)`:
- V=0, ratio=0, 0^x for x>0 is 0, so all power-law terms vanish.
- Culture tanks: 15.0 × 0 = 0
- PEF: 50.0 + 10.0 × 0 = 50.0
- HV generator: 30.0 + 5.0 × 0 = 30.0
- Plasma unit: 10.0
- Control: 20.0 + 5.0 × 0 = 20.0
- Installation: 25.0 × 0 = 0
- Sum = 0 + 50 + 30 + 10 + 20 + 0 = 110 k€ = **110,000 €**

This makes physical sense: at zero volume you still need the PEF system, HV generator, plasma unit and control hardware as fixed costs; only the culture tanks and installation scale to zero.

Now let me check near-zero: `estimate_biorefinery_capex(1e-6)` — V → 0+ gives the same floor of 110,000 €.

Let me now also verify the existing test patterns are consistent — I already have `test_algae_pef_chain.jl` as a template. And I need to check how the source is included to know the module context:

Looking at the source again: `biorefinery_symbiosis.jl` has `using Printf` and defines module-level constants and functions directly — no module wrapper. The include in runtests.jl (line 39) brings everything into the test's `@__MODULE__`. So the tests reference the functions and constants directly without a module prefix.

Now let me finalize my plan with all 12+ assertions mapped out:

---

## Plan

### Goal
Create `test/industrial/test_biorefinery_symbiosis.jl` with ≥12 numerically-grounded `@test` assertions covering `symbiosis_economics` and `estimate_biorefinery_capex`, and register it in `test/industrial/runtests.jl`.

### Files to touch

1. **`test/industrial/test_biorefinery_symbiosis.jl`** — NEW FILE: full test suite
2. **`test/industrial/runtests.jl`** — one-line insertion: `include("test_biorefinery_symbiosis.jl")` after the existing biorefinery_symbiosis source include (line 39) and before the closing `end` of the `@testset`.

### Assertion Plan (13 assertions, each with derivation)

| # | Assertion | Derivation from constants |
|---|---|---|
| **A1** | `@test r_100.biomass_kg ≈ 0.08` | `100 × 0.8 / 1000 = 0.08` (line 69: `V * _SYM_GROWTH_RATE_G_L_DAY / 1000.0`) |
| **A2** | `@test r_100.protein_kg ≈ 0.0324` | `0.08 × 0.45 × 0.90 = 0.0324` (line 70: `daily_biomass_kg * _SYM_PROTEIN_YIELD * _SYM_HARVEST_EFF`) |
| **A3** | `@test r_100.daily_profit ≈ 0.809794666...` atol=1e-6 | `total_revenue - total_cost = (0.81 + 0.000032) - (0.00023733...) = 0.809794666...` (from above derivation with methanizer deal) |
| **A4** | `@test r_100.co2_cost == 0.0` | `has_methanizer_deal=true` → line 94: `co2_cost = 0.0` |
| **A5** | `@test r_standalone.co2_cost > 0.0` | `has_methanizer_deal=false` → line 99: `co2_cost = co2_needed_tons * _SYM_CO2_EUR_T = 0.000144 × 200 = 0.0288` (exact), definitely > 0 |
| **A6** | `@test r_100.total_cost < r_standalone.total_cost` | With the deal, CO₂ and heat are free (lines 94-95); without, both have cost (lines 99-100). Electricity cost is identical in both. So `total_cost` with deal is strictly lower. |
| **A7** | `@test r_100.methanizer_savings > 0.0` | `has_methanizer_deal=true` → line 109: `co2_needed_tons * 50.0 = 0.000144 × 50 = 0.0072`, definitely > 0 |
| **A8** | `@test 0.0 < r_100.protein_kg / r_100.biomass_kg <= _SYM_PROTEIN_YIELD` | Biomass → protein via `_SYM_PROTEIN_YIELD * _SYM_HARVEST_EFF = 0.45 × 0.90 = 0.405`. So ratio = 0.405 ≤ 0.45. |
| **A9** | `@test r_200.biomass_kg > r_100.biomass_kg` | Monotonicity: `V` appears linearly in `daily_biomass_kg = V × 0.8/1000`, so `biomass_kg(200) = 0.16 > 0.08 = biomass_kg(100)`. |
| **A10** | `@test estimate_biorefinery_capex(200.0) > estimate_biorefinery_capex(100.0)` | Monotonicity: every component is either constant or scales with `(V/ref)^p` for p>0, which is increasing in V. So capex strictly increases with volume. |
| **A11** | `@test estimate_biorefinery_capex(0.0) ≈ 110_000.0` | At V=0, all (V/ref)^p terms = 0 (p>0). Remaining: PEF 50 + HV 30 + Plasma 10 + Control 20 = 110 k€, × 1000 = 110,000 €. |
| **A12** | `@test r_zero.daily_profit ≈ 0.0` | V=0 → biomass=0 → protein=0 → revenue=0, electricity cost=0, total cost=0, so daily_profit = 0.0. |
| **A13** | `@test r_100.fertilizer_revenue ≈ 0.000032` | `no3_kg_n = digestate_L × 40.0 / 1e6 = 0.4 × 40.0 / 1e6 = 1.6e-5 kg_N`, × `_SYM_FERT_N_EUR_KG = 2.0` = `3.2e-5` = 0.000032 €. |

That's 13 assertions covering:
- **(a)** Hand-computed value checks: A1, A2, A3, A11, A12, A13 (6 assertions with exact expected numbers)
- **(b)** Monotonicity: A9 (biomass), A10 (capex)
- **(c)** Bounds checks: A8 (protein fraction ≤ yield constant), A4/A5/A6/A7 (cost structure)
- **(d)** Degenerate input: A11 (capex at V=0 gives floor of 110k€), A12 (profit at V=0 is 0)

### Ordered steps for the coder

1. Read `src/industrial/biorefinery_symbiosis.jl` to confirm constants (already done; skip unless source has changed).
2. Create `test/industrial/test_biorefinery_symbiosis.jl` with the full test file content (see below for the exact file, or construct from the assertion plan).
3. Edit `test/industrial/runtests.jl`: add line `include("test_biorefinery_symbiosis.jl")` immediately before line 58 (`if HAS_CUDA`), inside the `@testset "Industrial Module Tests"` block.
4. Run `julia_gate` on the workspace. Expect VERT.
5. If ORANGE or ROUGE: read the failure output, fix the test file only (NEVER the source module), re-run gate.

### Targeted tests
- **File**: `test/industrial/runtests.jl` (this replays the new file since it's included from the `@testset` block)
- **Acceptance criterion**: `julia_gate` returns VERT verdict. Plus self-check: every assertion A1-A13 listed above is present (by grep) in `test/industrial/test_biorefinery_symbiosis.jl`.

### Risks and what NOT to touch
- **DO NOT modify** `src/industrial/biorefinery_symbiosis.jl` under any circumstance.
- **Risk: floating-point rendering of 0.000032**. The value `0.000032` may render slightly differently; use `isapprox` with appropriate `atol` rather than `==`. Already planned: A13 uses `≈`.
- **Risk: `estimate_biorefinery_capex(0.0)` may give slightly different float for 110_000**. The sum of exact floats 50.0+30.0+10.0+20.0 = 110.0, × 1000 = 110_000.0 — this is exact in Float64.
- **Risk: the `plasma_hours` computation at V=100**: `0.4/50.0 * (5.0/60.0)` — the Float64 value of `5.0/60.0 = 0.08333...` introduces a small FP error. The final `daily_profit` has a cumulative FP error. Use `atol=1e-10` on A3 (the profit is ~0.81, so relative error ~1e-9 is safe).
- **Risk: `_SYM_PROTEIN_YIELD` is accessed from the test file**. The source file is `include`d into the test's module scope, so constants are available. This is the established pattern in other industrial tests.

### Test file content

```julia
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
```

That's 14 `@test` assertions (I added `heat_cost == 0.0` as an extra one, making it 14 total — all numeric, exceeding the 12 minimum). The file is self-contained, follows the existing industrial test conventions (same `@testset` naming style, same comment style), and every assertion is anchored to specific lines and constants from the source.

The runtests.jl edit is a single `include` line inserted between `include("test_algae_pef_chain.jl")` (line 57) and `if HAS_CUDA` (line 58).