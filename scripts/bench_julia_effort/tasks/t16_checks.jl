using .Sol: Circulant

let c = [1, 2, 3], M = [1 3 2; 2 1 3; 3 2 1]
    A = Circulant(c)
    @assert A isa AbstractMatrix          "doit etre <: AbstractMatrix"
    @assert size(A) == (3, 3)             "size"
    @assert A[2, 1] == 2                  "A[2,1] vaut $(A[2,1]) au lieu de 2"
    @assert Matrix(A) == M                "matrice complete : $(Matrix(A))"
    @assert sum(A) == sum(M)              "sum par le fallback AbstractArray"
    @assert A * [1, 1, 1] == M * [1, 1, 1]  "produit matrice-vecteur"
end
