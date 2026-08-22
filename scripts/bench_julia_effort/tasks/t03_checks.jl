using .Sol: rle_encode, rle_decode
@assert rle_encode(Int[]) == Tuple{Int,Int}[]                       "vide"
@assert rle_encode([1,1,2,3,3,3]) == [(1,2),(2,1),(3,3)]             "entiers"
@assert rle_encode(['a','a','b']) == [('a',2),('b',1)]               "chars"
@assert rle_decode(rle_encode([5,5,5,7,7,9])) == [5,5,5,7,7,9]       "aller-retour"
let v = rand(1:3, 200)
    @assert rle_decode(rle_encode(v)) == v                           "aller-retour aleatoire"
end
