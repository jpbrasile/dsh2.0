Now I have all three files. Let me analyze the structure carefully and produce the plan.

---

## Plan: Write `test/liquid/test_waveform_library.jl` + one include line in `test/liquid/runtests.jl`

### (1) Goal

Add a standalone-runnable, dual-load-guarded test file covering all 13 exports from `waveform_library.jl` with ≥15 `@test` assertions, and wire it into the Liquid test suite via one new `include` line.

### (2) Files to touch

**A) `test/liquid/test_waveform_library.jl` — NEW FILE**

Structure (mirrors `test_cap_viability.jl` exactly in its guard pattern):

1. **Module docstring** (lines 1–8): Reference Li et al. 2024 IFSET 94, 103649; state that this tests the 9 waveform closure functions, the spec struct, `create_li_waveform`, and `create_all_li_waveforms`.

2. **`using Test`** (line 10).

3. **Dual-load guard** (lines 12–17): verbatim copy of the guard from `test_cap_viability.jl` lines 13–17:
   ```julia
   # Handle both standalone and runtests.jl execution
   if !@isdefined(Liquid)
       push!(LOAD_PATH, joinpath(@__DIR__, "..", ".."))
       include(joinpath(@__DIR__, "..", "..", "src", "liquid", "Liquid.jl"))
       using .Liquid
   end
   ```

4. **One `@testset` block** containing tests for all 13 exported names. Specific tests:

   **`li_waveform_specs()`** (vector of `WaveformSpec`):
   - `@test length(li_waveform_specs()) == 9`
   - Loop over all 9 specs: `@test spec.V_peak == 7000.0` (from source line 133: `V = 7000.0`)
   - Loop over all 9 specs: `@test spec.E_field == 17.5` or `spec.E_peak == 17.5` (from source lines 137-148, all entries pass `17.5` as E_peak)
   - Count unipolar vs bipolar: `count(s -> s.is_bipolar, li_waveform_specs()) == 2` (source: 7 unipolar + 2 bipolar)

   **`WaveformSpec`** (construct and inspect):
   - Construct a hand-built `WaveformSpec` with a bogus label, test that `create_li_waveform(hand_spec)` throws `ErrorException`:
     ```julia
     bad_spec = WaveformSpec("Bogus", :bogus, 1000.0, 1.0, 1e-6, 0.1, false, 0.0, 0.0, 0.0)
     @test_throws ErrorException create_li_waveform(bad_spec)
     ```

   **`make_rectangle_waveform`** (closure V(t)):
   - `V = make_rectangle_waveform(7000.0, 7.72e-6)`
   - `@test V(0.0) == 7000.0` (anchor: rectangle gives V(0) == V_peak)
   - `@test V(-1e-6) == 0.0` (zero outside [0, t_pulse])
   - `@test V(8e-6) == 0.0` (zero after t_pulse)

   **`make_halfsine_waveform`**:
   - `V = make_halfsine_waveform(7000.0, 12.13e-6)`
   - `@test V(0.0) == 0.0` (sin(0) = 0)
   - `@test V(12.13e-6 / 2) ≈ 7000.0 rtol=1e-12` (peak at t_pulse/2)
   - `@test V(20e-6) == 0.0` (outside)

   **`make_expdecay_waveform`**:
   - `V = make_expdecay_waveform(7000.0, 9.64e-6)`
   - `@test V(9.64e-6) ≈ 7000.0 * exp(-3.0) rtol=1e-12` (anchor: V(t_pulse) == V_peak * exp(-3))
   - `@test V(0.0) == 7000.0`
   - `@test V(-1e-6) == 0.0`

   **`make_exprise_waveform`**:
   - `V = make_exprise_waveform(7000.0, 9.64e-6)`
   - `@test V(0.0) == 0.0`  (1 - exp(0) = 0)
   - `@test V(9.64e-6) ≈ 7000.0 * (1.0 - exp(-3.0)) rtol=1e-12`

   **`make_twostep_waveform`**:
   - `V = make_twostep_waveform(7000.0, 8.36e-6)`
   - `@test V(0.0) == 7000.0`
   - `@test V(8.36e-6 / 2 + 1e-9) == 3500.0` (second half at V_peak/2)

   **`make_triangle_waveform`**:
   - `V = make_triangle_waveform(7000.0, 15.44e-6)`
   - `@test V(0.0) == 0.0`
   - `@test V(15.44e-6 / 2) ≈ 7000.0 rtol=1e-12`

   **`make_oscrect_waveform`**:
   - `V = make_oscrect_waveform(7000.0, 7.72e-6)`
   - `@test V(0.0) == 7000.0` (sin(0)=0, so base rectangle value)

   **`make_bipolar_rect_waveform`**:
   - `V = make_bipolar_rect_waveform(7000.0, 15.44e-6)`
   - `@test V(0.0) == 7000.0`
   - `@test V(15.44e-6 / 2 + 1e-9) == -7000.0`

   **`make_bipolar_sine_waveform`**:
   - `V = make_bipolar_sine_waveform(7000.0, 24.28e-6)`
   - `@test V(0.0) == 0.0`
   - `@test V(24.28e-6 / 4) ≈ 7000.0 rtol=1e-12` (sin(π/2) = 1 at t_pulse/4)

   **`create_li_waveform`** (dispatched creation):
   - Loop through all 9 `li_waveform_specs()`, call `create_li_waveform(spec)`, verify the returned object is callable: `@test V_callable(0.0) isa Number`
   - Plus the error-path test on bogus label already covered above.

   **`create_all_li_waveforms`**:
   - `all_wfs = create_all_li_waveforms()`
   - `@test length(all_wfs) == 9`
   - `@test all(p -> p isa Tuple{WaveformSpec, Function}, all_wfs)`

   This yields well over 15 `@test` assertions (counting each `@test` macro call, not each loop-body assertion). The exact count: 1 (length==9) + 9 (V_peak) + 9 (E_peak) + 1 (bipolar count) + 1 (bogus error) + 3 (rectangle) + 3 (halfsine) + 3 (expdecay) + 2 (exprise) + 2 (twostep) + 2 (triangle) + 1 (oscrect) + 2 (birect) + 2 (bisine) + 9 (create_li_waveform dispatch loop) + 2 (create_all_li_waveforms) = ~52 `@test` calls, all inside a single `@testset`.

**B) `test/liquid/runtests.jl` — ONE-LINE EDIT**

Insert one line after line 117:
```julia
    # CAP/PAW Weibull/Mafart survival utility (non-validation; fitted params)
    include("test_cap_viability.jl")

    # Li et al. 2024 IFSET 94 — nine PEF waveform library
    include("test_waveform_library.jl")
```
That is the **only** change to `runtests.jl`. Nothing else is added, removed, or reordered.

### (3) Ordered steps for the coder

1. **Create `test/liquid/test_waveform_library.jl`** with the structure above. Every numerical reference value comes from `waveform_library.jl` itself (read from the specs table at lines 137-148 or the `V = 7000.0` at line 133) or from closed-form math (`exp(-3.0)`, `sin(π/2)=1`, `sin(2π·(t_pulse/4)/t_pulse)=sin(π/2)=1`). No invented numbers.

2. **Edit `test/liquid/runtests.jl`** — insert exactly one `include("test_waveform_library.jl")` line after line 117 (after the `test_cap_viability.jl` include). Use `edit` with old_string covering lines 116–118 (the blank line between them) to ensure the old_string is unique.

3. **Run `julia_gate`** on the module — it will run `test/liquid/runtests.jl` and the new file will be included. If the gate reports ORANGE (timeout/heavy suite budget), run the new test file standalone and paste its `Test Summary` line showing all tests passing.

4. **Verify**: no file other than `DONE.md`, `test/liquid/test_waveform_library.jl`, and the one-line edit to `test/liquid/runtests.jl` was created or modified.

### (4) Targeted tests and acceptance criterion

- **Gate target**: `test/liquid/runtests.jl` (the whole Liquid suite). The new test file gets pulled in via the new `include` line.
- **Standalone fallback**: `julia --project=. test/liquid/test_waveform_library.jl` — must show all `@test` assertions passing.
- **Acceptance**: The gate verdict (VERBATIM) must be GREEN for the new tests, or if the gate reports ORANGE due to budget on the full 3894-test suite, the standalone run's `Test Summary` line must show all tests passing. Any ROUGE or failed `@test` is a failure.

### (5) Risks and what NOT to touch

- **Do NOT modify `src/liquid/waveform_library.jl`** or any other source file.
- **Do NOT modify anything in `test/liquid/runtests.jl` beyond the ONE new `include` line** — do not reorder existing includes, change comments, or alter any other line.
- **Do NOT use `using CUDA`** or any GPU path in the new test file. The test file is CPU-only.
- **Risk: `E_field` vs `E_peak` field confusion** — the task's anchors say `E_field == 17.5`. The `WaveformSpec` struct has a field `E_peak::Float64` (line 115), not `E_field`. The specs table passes `17.5` as the 4th positional argument which maps to `E_peak`. The test should assert `spec.E_peak == 17.5`, not `spec.E_field`. Do NOT use `.E_field` as a field accessor — it does not exist on `WaveformSpec`.
- **Risk: `create_all_li_waveforms` return type** — returns `Vector{Tuple{WaveformSpec, Function}}` (line 379). On Julia 1.12+, the `Tuple{WaveformSpec, Function}` type assertion `p isa Tuple{WaveformSpec, Function}` may need to use `typeof(p) <: Tuple` approach or just check `p[2] isa Function`. If `isa Tuple{WaveformSpec, Function}` fails, fall back to structural checks.
- **Risk: the `τ = t_pulse/3` in expdecay** — the closure at lines 196-205 uses `τ = t_pulse / 3.0`, so `V(t_pulse) = V_peak * exp(-t_pulse / (t_pulse/3)) = V_peak * exp(-3)`. This is exactly what the anchor says. Test with the actual `t_pulse` from the spec table (9.64e-6 for expdecay).
- **No file other than the two above** (new test file, one-line runtests.jl edit) and `DONE.md` may be created or modified.