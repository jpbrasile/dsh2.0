# plasma-digital-twin/test/anchors/runtests.jl
"""
Anchors module test runner — primary-source reference registry.

Run with: julia --project=. test/anchors/runtests.jl
"""

using Test

# Include the Anchors module the same way PlasmaDigitalTwin.jl does.
include(joinpath(@__DIR__, "..", "..", "src", "anchors", "Anchors.jl"))
using .Anchors

@testset "Anchors Module Tests" begin
    include("test_anchors.jl")
end
