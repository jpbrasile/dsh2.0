using .Sol: Chunks

@assert collect(Chunks(1:7, 3)) == [[1,2,3],[4,5,6],[7]]  "decoupage"
@assert length(Chunks(1:7, 3)) == 3                       "length : $(length(Chunks(1:7,3))) au lieu de 3"
@assert length(Chunks(1:10, 4)) == length(collect(Chunks(1:10, 4)))  "length ne suit pas collect"

let n = 0
    for _ in Chunks(1:10, 4); n += 1; end
    @assert n == 3                                        "boucle for"
end

@assert collect(Chunks([5, 6], 5)) == [[5, 6]]            "k plus grand que le vecteur"
@assert eltype(Chunks(1:7, 3)) <: AbstractVector          "eltype"
