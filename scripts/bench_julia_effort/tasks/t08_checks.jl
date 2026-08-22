using .Sol: thomas
using LinearAlgebra, Random
Random.seed!(20260822)
for n in (4, 25, 300)
    a = randn(n-1); c = randn(n-1)
    b = [3.0 + abs(randn()) + (i > 1 ? abs(a[i-1]) : 0.0) + (i < n ? abs(c[i]) : 0.0) for i in 1:n]
    d = randn(n)
    M = Tridiagonal(a, b, c)
    x = thomas(copy(a), copy(b), copy(c), copy(d))
    @assert length(x) == n                     "longueur n=$n"
    @assert norm(M*x - d) / norm(d) < 1e-8     "residu n=$n"
end
