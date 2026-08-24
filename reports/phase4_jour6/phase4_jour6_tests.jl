# test/liquid/test_waveform_library.jl
"""
Tests for the Li et al. (2024) IFSET 94, 103649 PEF waveform library.
Reference: Li et al. (2024) IFSET 94, 103649 — "Electroporation of Chlorella
vulgaris with laboratory devices capable of generating arbitrary waveform
pulses". Covers the 9 waveform closure functions, the WaveformSpec struct,
create_li_waveform dispatch, and create_all_li_waveforms.
"""

using Test

# Handle both standalone and runtests.jl execution
if !@isdefined(Liquid)
    push!(LOAD_PATH, joinpath(@__DIR__, "..", ".."))
    include(joinpath(@__DIR__, "..", "..", "src", "liquid", "Liquid.jl"))
    using .Liquid
end

@testset "Li et al. 2024 Waveform Library" begin

    # ------------------------------------------------------------------
    # li_waveform_specs(): the 9-entry specification table
    # ------------------------------------------------------------------
    specs = li_waveform_specs()
    @test length(specs) == 9
    @test all(s -> s isa WaveformSpec, specs)
    @test all(s -> s.V_peak == 7000.0, specs)
    @test all(s -> s.E_peak == 17.5, specs)
    @test count(s -> s.is_bipolar, specs) == 2

    # ------------------------------------------------------------------
    # WaveformSpec: hand-constructed spec with an unknown label must throw
    # ------------------------------------------------------------------
    bad_spec = WaveformSpec("Bogus", :bogus, 1000.0, 1.0, 1e-6, 0.1, false, 0.0, 0.0, 0.0)
    @test_throws ErrorException create_li_waveform(bad_spec)

    # ------------------------------------------------------------------
    # make_rectangle_waveform
    # ------------------------------------------------------------------
    V = make_rectangle_waveform(7000.0, 7.72e-6)
    @test V(0.0) == 7000.0
    @test V(-1e-6) == 0.0
    @test V(8e-6) == 0.0

    # ------------------------------------------------------------------
    # make_halfsine_waveform
    # ------------------------------------------------------------------
    V = make_halfsine_waveform(7000.0, 12.13e-6)
    @test V(0.0) == 0.0
    @test V(12.13e-6 / 2) ≈ 7000.0 rtol=1e-12
    @test V(20e-6) == 0.0

    # ------------------------------------------------------------------
    # make_expdecay_waveform: τ = t_pulse/3 → V(t_pulse) = V_peak*exp(-3)
    # ------------------------------------------------------------------
    V = make_expdecay_waveform(7000.0, 9.64e-6)
    @test V(0.0) == 7000.0
    @test V(-1e-6) == 0.0
    @test V(9.64e-6) ≈ 7000.0 * exp(-3.0) rtol=1e-12

    # ------------------------------------------------------------------
    # make_exprise_waveform
    # ------------------------------------------------------------------
    V = make_exprise_waveform(7000.0, 9.64e-6)
    @test V(0.0) == 0.0
    @test V(9.64e-6) ≈ 7000.0 * (1.0 - exp(-3.0)) rtol=1e-12

    # ------------------------------------------------------------------
    # make_twostep_waveform
    # ------------------------------------------------------------------
    V = make_twostep_waveform(7000.0, 8.36e-6)
    @test V(0.0) == 7000.0
    @test V(8.36e-6 / 2 + 1e-9) == 3500.0

    # ------------------------------------------------------------------
    # make_triangle_waveform
    # ------------------------------------------------------------------
    V = make_triangle_waveform(7000.0, 15.44e-6)
    @test V(0.0) == 0.0
    @test V(15.44e-6 / 2) ≈ 7000.0 rtol=1e-12

    # ------------------------------------------------------------------
    # make_oscrect_waveform (sin(0)=0 → base rectangle value at t=0)
    # ------------------------------------------------------------------
    V = make_oscrect_waveform(7000.0, 7.72e-6)
    @test V(0.0) == 7000.0

    # ------------------------------------------------------------------
    # make_bipolar_rect_waveform
    # ------------------------------------------------------------------
    V = make_bipolar_rect_waveform(7000.0, 15.44e-6)
    @test V(0.0) == 7000.0
    @test V(15.44e-6 / 2 + 1e-9) == -7000.0

    # ------------------------------------------------------------------
    # make_bipolar_sine_waveform (sin(2π·(t_pulse/4)/t_pulse) = sin(π/2) = 1)
    # ------------------------------------------------------------------
    V = make_bipolar_sine_waveform(7000.0, 24.28e-6)
    @test V(0.0) == 0.0
    @test V(24.28e-6 / 4) ≈ 7000.0 rtol=1e-12

    # ------------------------------------------------------------------
    # create_li_waveform: dispatch over all 9 specs
    # ------------------------------------------------------------------
    for spec in li_waveform_specs()
        Vf = create_li_waveform(spec)
        @test Vf(0.0) isa Number
    end

    # ------------------------------------------------------------------
    # create_all_li_waveforms
    # ------------------------------------------------------------------
    all_wfs = create_all_li_waveforms()
    @test length(all_wfs) == 9
    @test all(p -> p isa Tuple{WaveformSpec, Function}, all_wfs)

end