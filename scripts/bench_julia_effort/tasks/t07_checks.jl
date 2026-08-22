using .Sol: power_iteration
using LinearAlgebra, Random
Random.seed!(20260822)
for n in (5, 12, 40)
    B = randn(n, n); A = B'B + n*I          # symetrique definie positive
    lam, v = power_iteration(A, 1e-10, 100000)
    ref = maximum(eigvals(Symmetric(A)))
    @assert isapprox(lam, ref; rtol=1e-6)   "valeur propre dominante n=$n : $lam vs $ref"
    @assert isapprox(norm(v), 1.0; rtol=1e-6) "vecteur non normalise n=$n"
    @assert norm(A*v - lam*v) / norm(A*v) < 1e-5 "residu n=$n"
end
