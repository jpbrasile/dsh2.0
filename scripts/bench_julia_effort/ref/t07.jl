using LinearAlgebra
function power_iteration(A::AbstractMatrix, tol::Real, maxiter::Integer=10000)
    n = size(A, 1)
    v = ones(eltype(A) === Int ? Float64 : float(eltype(A)), n) ./ sqrt(n)
    lam = zero(eltype(v))
    for _ in 1:maxiter
        w = A * v
        nw = norm(w)
        nw == 0 && break
        vnew = w ./ nw
        lamnew = dot(vnew, A * vnew)
        if abs(lamnew - lam) <= tol * max(1, abs(lamnew)); v = vnew; lam = lamnew; break; end
        v = vnew; lam = lamnew
    end
    (lam, v)
end
