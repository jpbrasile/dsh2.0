# Les deux clauses du contrat a cinq arguments :
#  - alpha ne multiplie QUE le produit A*B, jamais le terme beta*C ;
#  - beta nul veut dire "C n'est pas lu", pas "C est multiplie par zero".
#    La difference se voit des que C contient NaN ou Inf : 0*NaN vaut NaN,
#    alors que le contrat exige un resultat fini.
function gemm5!(C, A, B, alpha, beta)
    mA = size(A, 1)
    kA = size(A, 2)
    kB = size(B, 1)
    nB = size(B, 2)

    kA == kB || throw(DimensionMismatch("dimensions internes de A et B incompatibles"))
    size(C, 1) == mA || throw(DimensionMismatch("C n a pas le nombre de lignes de A"))
    size(C, 2) == nB || throw(DimensionMismatch("C n a pas le nombre de colonnes de B"))

    zero_produit = zero(eltype(A)) * zero(eltype(B))
    beta_nul = iszero(beta)

    @inbounds for j in 1:nB
        for i in 1:mA
            s = zero_produit
            for p in 1:kA
                s += A[i, p] * B[p, j]
            end
            t = alpha * s
            C[i, j] = beta_nul ? t : t + beta * C[i, j]
        end
    end

    return C
end
