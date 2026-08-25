I now have all the evidence I need. Let me produce the plan.

---

# Plan: Hardening test_ozone_3d.jl with `ozone_yield_g_per_kwh` coverage

## 1. Goal

Append one new `@testset` block to `test/gpu3d_integration/chemistry/test_ozone_3d.jl` that exercises `ozone_yield_g_per_kwh` end-to-end — including degenerate guards, nominal defaults, the `OZONE_F_N2A_BRANCH`-sensitive output, and the G-factor constant identity — so that a mutation of `OZONE_F_N2A_BRANCH` from 1.2 to 1.3 produces a test failure.

---

## 2. Verified facts

### 2.1 Constants (source: `src/gpu3d_integration/ozone_3d.jl`)

**`OZONE_G_FACTOR_G_PER_KWH`** — lines 473-474:

```julia
const OZONE_G_FACTOR_G_PER_KWH =
    OZONE_M_O3_G_PER_MOL * 3.6e6 / (OZONE_N_AVOGADRO * OZONE_E_CHARGE)
```

With `OZONE_M_O3_G_PER_MOL = 48.0` (line 470), `OZONE_N_AVOGADRO = 6.022e23` (line 471), `OZONE_E_CHARGE = 1.602176634e-19` (line 472).

Contract check: `48.0 * 3.6e6 / (6.022e23 * 1.602176634e-19)` — matches the TEST CONTRACT's item (a) exactly.

**`OZONE_F_N2A_BRANCH`** — line 478:

```julia
const OZONE_F_N2A_BRANCH = 1.2
```

Contract check: `== 1.2` exactly. Matches contract (a).

**Exports**: Lines 544:

```julia
export ozone_yield_g_per_kwh, OZONE_G_FACTOR_G_PER_KWH, OZONE_F_N2A_BRANCH
```

All three are exported from the top-level module that `test_ozone_3d.jl` imports.

### 2.2 Function signature (source: `src/gpu3d_integration/ozone_3d.jl`, lines 508-513)

```julia
function ozone_yield_g_per_kwh(
    k_d::Real, k_att::Real, k_n2_elec::Real,
    v_d::Real, E_N_Td::Real, n_gas::Real;
    eps_thresh_eV::Real = 6.0,
    f_n2a_branch::Real = OZONE_F_N2A_BRANCH,
)
```

**Positional parameters** (6, in order): `k_d`, `k_att`, `k_n2_elec`, `v_d`, `E_N_Td`, `n_gas`.

**Keyword parameters**: `eps_thresh_eV` (default `6.0`), `f_n2a_branch` (defaults to `OZONE_F_N2A_BRANCH`, which is `1.2`).

### 2.3 R_O3 formula (source: line 517)

```julia
R_O3 = 2.0 * Float64(k_d) + Float64(k_att) + Float64(f_n2a_branch) * Float64(k_n2_elec)
```

Contract check: **Matches exactly** — `2*k_d + k_att + f_n2a_branch * k_n2_elec`. ✓

### 2.4 Return value: NamedTuple (source: line 530)

```julia
return (G_g_kWh = G_g_kWh, eV_per_O3 = eV_per_O3, eta_dissoc = eta_dissoc, R_O3 = R_O3)
```

**Field names** (in order): `G_g_kWh`, `eV_per_O3`, `eta_dissoc`, `R_O3`.

### 2.5 Degenerate guards (source: lines 520-522)

```julia
if R_O3 < 1e-3 || Float64(v_d) < 1.0
    return (G_g_kWh = 0.0, eV_per_O3 = Inf, eta_dissoc = 0.0, R_O3 = 0.0)
end
```

Contract check:

- Guard 1: `R_O3 < 1e-3` — the contract's "e" first case: `ozone_yield_g_per_kwh(1e-9, 0.0, 0.0, 1.0e5, 200.0, 2.4463134e25)` → `R_O3 = 2*1e-9 + 0 + 1.2*0 = 2e-9 < 1e-3` → triggers. Expected return: `(G_g_kWh=0.0, eV_per_O3=Inf, eta_dissoc=0.0, R_O3=0.0)`. ✓

- Guard 2: `v_d < 1.0` — the contract's "e" second case: `ozone_yield_g_per_kwh(1.0e8, 5.0e6, 2.0e7, 0.5, 200.0, 2.4463134e25)` → `v_d = 0.5 < 1.0` → triggers even though `R_O3` is large. Expected return: same degenerate tuple. ✓

**Both guards match contract item (e) exactly.**

> **Note on degenerate-guard `R_O3` field**: The guard returns `R_O3 = 0.0`, NOT the computed `R_O3` that fell below the threshold. This is explicit in the source (line 521). Tests must use `==` for `R_O3 == 0.0` in degenerate cases, not compute the sub-threshold `R_O3`.

### 2.6 Test file structure (source: `test/gpu3d_integration/chemistry/test_ozone_3d.jl`)

**Import/include block** (lines 16-30):

```julia
using Test
using CUDA
using Statistics: mean

if !isdefined(@__MODULE__, :GPU3DIntegration)
    if !@isdefined(GPU3DIntegration)
        include("../../../src/gpu3d_integration/GPU3DIntegration.jl")
        using .GPU3DIntegration
    end
end
```

After this block, `.GPU3DIntegration` is the module alias. All exported symbols — `ozone_yield_g_per_kwh`, `OZONE_G_FACTOR_G_PER_KWH`, `OZONE_F_N2A_BRANCH` — are brought into scope by `using .GPU3DIntegration`. They are therefore **directly in scope** from the test file — no module qualification needed (though it would also work).

**Top-level testset**: `@testset "O₃ Chemistry 3D" begin` at line 32, closing `end` at **line 399**.

**Last existing `@testset`**: `"Ozone Yield Estimate"` at lines 378-397. Its closing `end` is on **line 397**. The blank line 398 and the top-level `end` on line 399 follow.

**Insertion point**: between line 397 (close of last inner testset) and line 399 (close of top-level testset). The new block goes after line 397, before line 399.

**Style conventions**:
- Testset names: `"Descriptive Title"` — Pascal-ish descriptive phrases (e.g. `"Configuration"`, `"Wall Losses"`, `"Ozone Yield Estimate"`).
- Indentation: 4 spaces for nesting inside the top-level `begin`…`end`.
- Assertion style: uses `@test x ≈ y` (no explicit `rtol` in existing tests — they use default; exceptions use `@test x == true` / `@test x == 0.0`). Uses `@info` blocks after each testset.
- No comment header above testsets — just `@testset "Name" begin`.

---

## 3. Insertion point

| Item | Line |
|---|---|
| Last line of last existing inner `@testset` (`"Ozone Yield Estimate"`) | 397 |
| Top-level testset closing `end` | 399 |
| **Insertion point** | After line 397, before line 399 |

---

## 4. New testset (exact code)

The testset name follows the file's convention: descriptive, naming what it exercises. The constant `OZONE_F_N2A_BRANCH` and `OZONE_G_FACTOR_G_PER_KWH` are directly in scope via `using .GPU3DIntegration`. The function `ozone_yield_g_per_kwh` is also directly in scope.

```julia
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
```

**Test count**: 23 `@test` macros (well above the ≥12 minimum).

**Assertion granularity by contract item**:

| Contract item | What is tested | Test count |
|---|---|---|
| (a) Constants | `== 1.2`, `≈ 1.7909876587e3`, identity expression | 3 |
| (b) Nominal default | 4 fields × `≈ rtol=1e-6` | 4 |
| (c) Default==explicit | 4 fields × `==` | 4 |
| (d) Sensitivity + direction | 2 `≈` anchors + 2 strict `>` | 4 |
| (e) Degenerate guard 1 | 4 fields × `==` | 4 |
| (e) Degenerate guard 2 | 4 fields × `==` | 4 |
| **Total** | | **23** |

---

## 5. Risks for the implementing agent

1. **Float64 bit-identity of the G-factor expression**: The expression `48.0 * 3.6e6 / (6.022e23 * 1.602176634e-19)` must be written in the test EXACTLY as it is in the source (lines 473-474) so that the compiled `const` and the inline expression produce bit-identical `Float64`s. Any reordering of the multiplication/division could introduce a ULP difference that breaks `==`.

2. **`Inf` equality in degenerate `eV_per_O3`**: `== Inf` works correctly in Julia (`Inf == Inf` is `true`), but some test runners or floating-point modes can be fragile here. The source returns `Inf` explicitly (line 521), so `==` is the correct assertion.

3. **Floating-point exactness of `R_O3 == 0.0` in degenerate cases**: The guard returns `R_O3 = 0.0` (not the computed tiny value). The tests use `== 0.0`, which is correct.

4. **Scoping**: The constants and function ARE directly in scope via `using .GPU3DIntegration` (line 28). No qualification needed. If the runner's environment somehow does not trigger the `include` path, the test file would fail to find the symbols — but that's an environment issue, not a code issue.

5. **Testset ordering**: The new testset must be placed INSIDE the top-level `@testset "O₃ Chemistry 3D" begin`…`end` block (before line 399's `end`). If placed after line 399, it would be outside the testset and might not be collected by the runner.

---

## 6. Gate protocol

After writing the file exactly as specified:

1. Call the **julia_gate** tool EXACTLY ONCE with `files = ["test/gpu3d_integration/chemistry/test_ozone_3d.jl"]`.

2. **ORANGE with zero failures** is the expected outcome (budget timeout) — quote the verdict VERBATIM and do NOT call the gate again.

3. **ROUGE** (real test failures) → fix the test file once, then ONE final gate call. Never more than two gate calls total.