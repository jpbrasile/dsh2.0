# BAD: persistant et CORRECT -- mais chaque version recopie tout le tableau.
# Aucun partage de structure : garder N versions coute O(N^2).
struct PVec
    v::Vector{Any}
end

PVec() = PVec(Any[])
plength(v::PVec) = length(v.v)

function pget(v::PVec, i::Int)
    (1 <= i <= length(v.v)) || throw(BoundsError(v, i))
    v.v[i]
end

ppush(v::PVec, x) = PVec(push!(copy(v.v), x))

function pset(v::PVec, i::Int, x)
    (1 <= i <= length(v.v)) || throw(BoundsError(v, i))
    w = copy(v.v)
    w[i] = x
    PVec(w)
end
