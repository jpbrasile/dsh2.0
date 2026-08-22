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
        # BAD: pas de cas particulier pour beta nul. C est LU quand meme, donc
        # 0 * NaN = NaN et le resultat est empoisonne par ce qui trainait dans C.
        C[i, j] = alpha * s + beta * C[i, j]
    end
    C
end
