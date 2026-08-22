using LinearAlgebra
function power_iteration(A::AbstractMatrix, tol::Real, maxiter::Integer=10000)
    n = size(A,1); v = ones(Float64,n)                 # BAD: jamais normalise
    lam = 0.0
    for _ in 1:200; w = A*v; lam = norm(w)/norm(v); v = w; end
    (lam, v)
end
