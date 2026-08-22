using .Sol: gemm5!

A = [1.0 2.0; 3.0 4.0]
B = [5.0 6.0; 7.0 8.0]
P = [19.0 22.0; 43.0 50.0]

let C = fill(NaN, 2, 2)
    gemm5!(C, A, B, 1.0, 0.0)
    @assert all(isfinite, C)                     "beta nul doit ECRASER C sans le lire : le NaN a survecu"
    @assert C == P                               "beta=0, alpha=1 : produit faux"
end

let C = [1.0 1.0; 1.0 1.0]
    gemm5!(C, A, B, 2.0, 3.0)
    @assert C == 2 .* P .+ 3.0                   "alpha ne doit PAS multiplier beta*C : $(C) au lieu de $(2 .* P .+ 3.0)"
end

let C = [7.0 8.0; 9.0 10.0], D = copy(C)
    gemm5!(C, A, B, 0.0, 1.0)
    @assert C == D                               "alpha=0, beta=1 : C doit rester inchange"
end

let C = zeros(2, 2)
    @assert gemm5!(C, A, B, 1.0, 0.0) === C      "gemm5! doit rendre C lui-meme"
end

let A2 = [1.0 2.0 3.0; 4.0 5.0 6.0],
    B2 = [1.0 0.0; 0.0 1.0; 1.0 1.0],
    C2 = fill(NaN, 2, 2)
    gemm5!(C2, A2, B2, 1.0, 0.0)
    @assert C2 == A2 * B2                        "cas non carre"
end

let Ar = Rational{Int}[1//2 1//3; 1//4 1//5],
    Br = Rational{Int}[1//1 2//1; 3//1 4//1],
    Cr = zeros(Rational{Int}, 2, 2)
    gemm5!(Cr, Ar, Br, 1//1, 0//1)
    @assert eltype(Cr) == Rational{Int}          "le type d'element doit rester Rational"
    @assert Cr == Ar * Br                        "doit rester generique : BLAS ne sait pas multiplier des Rational"
end

let ok = false
    try
        gemm5!(zeros(2, 2), zeros(2, 3), zeros(2, 2), 1.0, 0.0)
    catch e
        ok = isa(e, DimensionMismatch)
    end
    @assert ok                                   "dimensions incompatibles doivent lever DimensionMismatch"
end
