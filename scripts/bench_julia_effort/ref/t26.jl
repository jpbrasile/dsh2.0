function gemm5!(C, A, B, alpha, beta)
    m, k = size(A)
    k2, n = size(B)
    (k == k2 && size(C) == (m, n)) || throw(DimensionMismatch("dimensions incompatibles"))
    T = eltype(C)
    @inbounds for j in 1:n, i in 1:m
        s = zero(T)
        for p in 1:k
            s += A[i, p] * B[p, j]
        end
        # beta nul : on ECRASE, on ne lit pas C -- sinon un NaN deja present survit
        C[i, j] = iszero(beta) ? alpha * s : alpha * s + beta * C[i, j]
    end
    C
end
