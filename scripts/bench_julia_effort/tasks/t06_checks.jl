using .Sol: topk
@assert sort(topk([5,1,9,3,7], 3)) == [5,7,9]        "cas simple"
@assert topk([1,2,3], 0) == Int[]                     "k=0"
@assert sort(topk([2,2,2,1], 3)) == [2,2,2]           "egalites"
@assert sort(topk([4,4,1], 5)) == [1,4,4]             "k > longueur"
let v = rand(1:10^6, 5000), k = 37
    @assert sort(topk(v,k)) == sort(v)[end-k+1:end]   "aleatoire"
end
