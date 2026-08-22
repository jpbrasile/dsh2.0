using .Sol: Banded
using LinearAlgebra

A = Banded(6, 1, 2)
@assert size(A) == (6, 6)                       "size"
@assert A isa AbstractMatrix                    "Banded doit se sous-typer AbstractMatrix"

A[3, 3] = 5.0
A[3, 2] = 1.0      # une sous-diagonale : i-j = 1 <= l
A[3, 5] = 2.0      # deux sur-diagonales : i-j = -2 >= -u
@assert A[3, 3] == 5.0                          "diagonale"
@assert A[3, 2] == 1.0                          "sous-diagonale : l et u sont peut-etre echanges"
@assert A[3, 5] == 2.0                          "sur-diagonale : l et u sont peut-etre echanges"
@assert A[5, 3] == 0.0                          "i-j = 2 > l : hors bande, doit lire zero"
@assert A[1, 6] == 0.0                          "hors bande doit lire zero, pas lever"

let ok = false
    try
        A[5, 3] = 1.0
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                  "ecrire non-nul hors bande doit lever ArgumentError"
end
A[5, 3] = 0.0                                   # autorise, ne fait rien

@assert Base.summarysize(Banded(400, 1, 1)) < 400 * 400 * 8 / 4  "stockage dense : la memoire suit n^2"

B = Banded(50, 2, 3)
for j in 1:50, i in max(1, j - 3):min(50, j + 2)
    B[i, j] = sin(i * j)
end
D = Matrix(B)
x = [cos(k) for k in 1:50]
y = zeros(50)
mul!(y, B, x)
@assert maximum(abs.(y .- D * x)) < 1e-10       "mul! : produit faux"

mul!(y, B, x)                                    # rechauffe
let al = @allocated mul!(y, B, x)
    @assert al == 0                             "mul! alloue $(al) octets, il en faut 0"
end

@assert sum(B) ≈ sum(D)                         "sum via l'interface AbstractArray"
