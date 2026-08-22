const BITS = 5
const LARG = 1 << BITS
const MASQ = LARG - 1

struct Noeud
    fils::Vector{Any}
end

struct PVec
    n::Int
    prof::Int          # la racine couvre LARG^prof elements
    racine::Union{Noeud,Nothing}
end

PVec() = PVec(0, 1, nothing)
plength(v::PVec) = v.n

function pget(v::PVec, i::Int)
    (1 <= i <= v.n) || throw(BoundsError(v, i))
    k = i - 1
    nd = v.racine
    for niveau in (v.prof - 1):-1:1
        nd = nd.fils[((k >> (BITS * niveau)) & MASQ) + 1]
    end
    nd.fils[(k & MASQ) + 1]
end

function assoc(nd, k::Int, niveau::Int, x)
    idx = ((k >> (BITS * niveau)) & MASQ) + 1
    f = nd === nothing ? Vector{Any}(undef, 0) : copy(nd.fils)
    while length(f) < idx
        push!(f, nothing)
    end
    if niveau == 0
        f[idx] = x
    else
        f[idx] = assoc(f[idx], k, niveau - 1, x)
    end
    Noeud(f)
end

function ppush(v::PVec, x)
    if v.n == LARG^v.prof
        v = PVec(v.n, v.prof + 1, Noeud(Any[v.racine]))
    end
    PVec(v.n + 1, v.prof, assoc(v.racine, v.n, v.prof - 1, x))
end

function pset(v::PVec, i::Int, x)
    (1 <= i <= v.n) || throw(BoundsError(v, i))
    PVec(v.n, v.prof, assoc(v.racine, i - 1, v.prof - 1, x))
end
