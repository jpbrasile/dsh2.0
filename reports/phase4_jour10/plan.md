Now I have all three files. Let me verify a few key facts before writing the plan:

1. The header pattern from `test_monte_carlo_physics.jl`: lines 1-18 show the standalone-capable header with `using Test`, `@isdefined(Liquid)` guard, `LOAD_PATH` manipulation, and `using .Liquid`.

2. The include insertion point: line 123 in `runtests.jl` is `include("test_monte_carlo_physics.jl")`. The new line goes after it (line 124).

3. Source verification:
   - `OscillationEnhancedConfig` constructor at line 75: defaults `κ_osc=1e-7, r_p_crit=1.5e-9, enabled=true`, stores `Float64`.
   - `OD_EPState` constructor at line 254: sets `N=N_init, r_p=r_p_init, Γ_line=1.0, C_in=1.0, t=0.0, max_r_p=r_p_init, n_total_steps=0`.
   - `default_OD_ep_params()` at line 306: `α=1.0e9, β=1.0, V_ep=0.258, N_0=1.5e15, N_eq=1.0e10, q=2.46`; `N_0_override` at line 346; `max(1.0, wall_factor)` at line 355.
   - Derived values: `A_m = 4π*r_cell²` (line 342), `V_cell = 4/3*π*r_cell³` (line 343), `Am_over_Vcell = A_m/V_cell` (line 353), `τ_m` (line 336), `a_p` (line 340).
   - `OD_EPResult` at lines 575-593.
   - `run_0d_ep_simulation` at line 595.
   - `RE_predicted = (1.0 - C_in_final)*100.0` at line 626.
   - `run_all_li_waveforms` at line 642: `f_osc` defaults to `params.f_goertzel` (line 646).
   - `compute_validation_metrics` at line 672.
   - No-op fields: lines 290, 295, 297, 298 — `osc_enhance`, `k_fat`, `k_goertzel`, `f_goertzel` are all documented no-ops.

4. Key check: `Γ_min` at line 357 is `clamp(Γ_min, 0.01, 1.0)` — it IS still used. The no-ops are: `osc_enhance` (stored but never read in `step_0d_ep!`), `k_fat`, `k_goertzel`, `f_goertzel`. But `f_goertzel` IS read at line 646 as the default for `f_osc` in `run_all_li_waveforms`. However, for the single-run test with `run_0d_ep_simulation`, none of those deprecated kwargs are read — only `step_0d_ep!` is called there, which doesn't touch them.

5. The `li_waveform_specs()` and `create_li_waveform` — I need to confirm these are available from the waveform library. Since I cannot read additional files, but the task states "Waveforms come from the already-tested waveform library", and the test file `test_waveform_library.jl` exists and is included in runtests, these should be available via `Liquid.`.

6. The `WaveformSpec` type and `create_all_li_waveforms` are used in the source — they come from the waveform library.

Now let me write the plan. The test file needs:
- The standalone header pattern from `test_monte_carlo_physics.jl`
- `@testset` structure
- `Liquid.` qualification for private helpers (though in this case most calls are to exported functions)
- All 7 test groups as specified

Let me now compute the derived values to verify the measured values:

- `r_cell = 8.0e-6`
- `A_m = 4π * (8.0e-6)^2 = 4π * 6.4e-11 = 8.04247719318987e-10` ✓
- `V_cell = (4/3)*π * (8.0e-6)^3 = (4/3)*π * 5.12e-16 = 2.144660584850632e-15` ✓
- `Am_over_Vcell = A_m / V_cell = 8.04247719318987e-10 / 2.144660584850632e-15 = 375,000.0` ✓ (= 3/r_cell)
- `C_m = ε_mem_rel * EPS0_EP2 / d_mem = 1.4 * 8.8541878128e-12 / 10.0e-9 = 1.239586293792e-3`
- `τ_m = r_cell * C_m * (1/σ_i + 1/(2*σ_e)) = 8.0e-6 * 1.239586293792e-3 * (1/0.3 + 1/(2*0.012))` = `8.0e-6 * 1.239586293792e-3 * (3.33333... + 41.6666...)` = `8.0e-6 * 1.239586293792e-3 * 45.0` = `4.4625106576511995e-7` ✓
- `a_p = EPS0_EP2 * (80.0 - 2.0) / (2.0 * d_mem) = 8.8541878128e-12 * 78.0 / (2.0 * 10.0e-9) = 8.8541878128e-12 * 78.0 / 2.0e-8 = 0.03453133246992` ✓

All checks out. Now I need to check one important thing: the task says `f_goertzel` "IS still read as a default for `f_osc` in run_all_li_waveforms -- test the no-op claim ONLY through `run_0d_ep_simulation` with a fixed waveform_func." This is exactly the plan — test no-op with `run_0d_ep_simulation`, not `run_all_li_waveforms`.

Now let me produce the plan.

---

## PLAN

**Goal**: Add a single deterministic CPU-only test file `test/liquid/test_oscillation_enhanced_ep.jl` for the `oscillation_enhanced_ep.jl` module, and wire it into `test/liquid/runtests.jl` with one include line.

**Files to touch**:

### 1. `test/liquid/test_oscillation_enhanced_ep.jl` (CREATE, ~115 lines)

New file. Structure mirrors `test_monte_carlo_physics.jl` exactly: standalone-capable header (lines 1-18 pattern), `@testset "Oscillation-Enhanced Electroporation" begin ... end` wrapping all tests, `Liquid.` qualification on any private helpers.

Seven test groups with at least 15 `@test` assertions total:

1. **Config defaults** (~3 assertions): `Liquid.OscillationEnhancedConfig()` → `κ_osc ≈ 1e-7`, `r_p_crit ≈ 1.5e-9`, `enabled == true`.

2. **State defaults** (~6 assertions): `Liquid.OD_EPState()` → `N == 1e10`, `r_p == 0.5e-9`, `Γ_line == 1.0`, `C_in == 1.0`, `t == 0.0`, `max_r_p == 0.5e-9`, `n_total_steps == 0`. (7 assertions; exact equality.)

3. **Params: Krassowska anchors + derived values** (~11 assertions):
   - `p = Liquid.default_OD_ep_params()`: `V_ep == 0.258`, `N_0 == 1.5e15`, `q == 2.46`, `N_eq == 1.0e10`, `α == 1.0e9`.
   - `p2 = Liquid.default_OD_ep_params(N_0_override=2.0e15)`: `N_0 == 2.0e15`.
   - `p3 = Liquid.default_OD_ep_params(wall_factor=0.5)`: `wall_factor == 1.0` (floored).
   - Derived: `A_m ≈ 8.04247719318987e-10 rtol=1e-10`, `V_cell ≈ 2.144660584850632e-15 rtol=1e-10`, `Am_over_Vcell ≈ 375000.0 rtol=1e-10`, `τ_m ≈ 4.4625106576511995e-7 rtol=1e-10`, `a_p ≈ 0.03453133246992 rtol=1e-10`. (10 assertions.)

4. **Single run on spec 1: structure + invariants** (~9 assertions):
   - `specs = Liquid.li_waveform_specs()`; `wf = Liquid.create_li_waveform(specs[1])`; `params = Liquid.default_OD_ep_params()`.
   - `r = Liquid.run_0d_ep_simulation(wf, specs[1], params)`.
   - `r isa Liquid.OD_EPResult`, `waveform_label == specs[1].label`, `0.0 <= RE_predicted <= 100.0`, `RE_predicted ≈ (1 - C_in_final)*100`, `r_p_max >= 0.5e-9`, `Vm_max > 0`, `0.0 <= f_large_pore <= 1.0`, `0.0 <= C_in_final <= 1.0`.
   - Determinism: `r2 = Liquid.run_0d_ep_simulation(wf, specs[1], params)` → `RE_predicted == r2.RE_predicted` and `r_p_max == r2.r_p_max`.

5. **No-op claim** (~2 assertions):
   - `p_noop = Liquid.default_OD_ep_params(osc_enhance=5.0, k_fat=1.0, k_goertzel=1.0)`.
   - `r_noop = Liquid.run_0d_ep_simulation(wf, specs[1], p_noop)`.
   - `RE_predicted == r.RE_predicted` and `r_p_max == r.r_p_max` (from the default run above).

6. **Batch: run_all_li_waveforms** (~3 assertions):
   - `results = Liquid.run_all_li_waveforms(params)`.
   - `length(results) == 9`.
   - `[res.waveform_label for res in results] == [s.label for s in specs]`.
   - `all(res -> 0.0 <= res.RE_predicted <= 100.0, results)`.

7. **Validation metrics: structure only** (~5 assertions):
   - `metrics = Liquid.compute_validation_metrics(results, specs)`.
   - NamedTuple with keys `:rmse, :r_squared, :rank_correct, :rank_total, :rank_accuracy`.
   - `rank_total == 36`.
   - `0 <= rank_correct <= rank_total`.
   - `rank_accuracy == rank_correct / rank_total` (exact, both Ints→Float64).
   - `rmse >= 0`.

Why: The module has 3894 existing tests but none for this 798-line file, which carries the core 0D electroporation engine with oscillation enhancement, energy landscape, Renkin transport, and batch waveform simulation — all deterministic, all CPU-only, all fast.

### 2. `test/liquid/runtests.jl` (EDIT, 1 insertion)

After line 123 (`include("test_monte_carlo_physics.jl")`), insert:
```
    # 0D Electroporation with oscillation enhancement (oscillation_enhanced_ep.jl)
    include("test_oscillation_enhanced_ep.jl")
```

Line 124 becomes the blank line, the new lines are at 125-126, and the old line 124 (`# Advanced Solvers...`) shifts down.

Why: Follows the convention established for every other test file in the runner — a one-line comment above the include; placed after `test_monte_carlo_physics.jl` as specified.

**Ordered steps for the coder**:

1. Create `test/liquid/test_oscillation_enhanced_ep.jl` with the standalone-capable header (copied from `test_monte_carlo_physics.jl` lines 1-18, adjusting the docstring and using the same `@isdefined(Liquid)` guard, `LOAD_PATH`, `include`, `using .Liquid` pattern), then the `@testset` with all 7 groups as detailed above.
2. Edit `test/liquid/runtests.jl`: insert the two new lines after line 123 (after the `include("test_monte_carlo_physics.jl")` line).
3. Call `julia_gate` ONCE on the workspace. Expect ORANGE (CUDA suite budget exceeded — documented expected behavior). If ROUGE or explicit failures, report honestly.

**Targeted tests the gate must replay**: The gate will run `test/liquid/runtests.jl` (the entire liquid suite) because the changes are under `test/liquid/`. The new test file will be exercised as part of that replay.

**Acceptance criterion**: 
- `test/liquid/test_oscillation_enhanced_ep.jl` exists with the content described above.
- `test/liquid/runtests.jl` has exactly the two new lines inserted after line 123.
- No other file created or modified (except `DONE.md`).
- `julia_gate` invoked exactly once; its verdict quoted verbatim in the final message.
- ORANGE with no failures listed = ACCEPTED (expected budget timeout on CUDA suite).
- ROUGE or explicit test failure = reported honestly in DONE.md.

**Risks and what NOT to touch**:

- **DO NOT touch `src/` at all.** The source module is untouchable.
- **DO NOT use `run_0d_ep_batch_gpu` or `run_all_li_waveforms_gpu`** — GPU variants are never called.
- **DO NOT assert model-vs-experiment agreement** (RMSE, R², rank correctness) — only assert structure and invariants on `compute_validation_metrics`.
- **DO NOT test `compute_RE_physical`** — it is exported but not defined in this file.
- **The no-op test MUST use `run_0d_ep_simulation`, NOT `run_all_li_waveforms`**, because `run_all_li_waveforms` DOES read `f_goertzel` (line 646: `f_osc = params.f_goertzel`) as the default for `f_osc`, so changing `f_goertzel` would affect the waveform creation, not the no-op claim.
- **Risk of `li_waveform_specs()` returning a type that needs qualification**: the test uses `Liquid.li_waveform_specs()` and `Liquid.create_li_waveform()` — both are part of the waveform library, already tested and included in the Liquid module. If they are not exported from `Liquid`, the test will fail at load time with `UndefVarError`. In that case, the coder should investigate via the `Liquid.` qualification first; if that fails, the private-path qualification would be `Liquid.WaveformLib.li_waveform_specs` or similar. However, since `oscillation_enhanced_ep.jl` itself calls `li_waveform_specs()` and `create_li_waveform()` unqualified (it's included directly into `module Liquid`), these must be available as `Liquid.li_waveform_specs()` and `Liquid.create_li_waveform()`.
- **Honesty rule**: If any assertion fails against the real source, annotate it with `# FAILS against src as of 2026-08-24:` plus the measured value, and report the failure in the final message. Do not weaken, delete, or tune numbers.