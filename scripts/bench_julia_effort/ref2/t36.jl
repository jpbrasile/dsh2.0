# Arbre a 32 branches indexe par tranches de 5 bits. Une mise a jour ne
# reconstruit QUE les noeuds du chemin racine -> feuille touche (au plus
# log32(N) noeuds de 32 pointeurs) et REUTILISE tous les autres tels quels.
# C'est le partage de structure : deux versions successives ont presque toute
# leur memoire en commun, donc N versions coutent O(N log N) et pas O(N^2).
const _BITS = 5
const _MASQUE = 31

struct PVec
    n::Int
    dec::Int                 # decalage du niveau racine ; 0 = la racine est une feuille
    racine::Vector{Any}
end

PVec() = PVec(0, 0, Any[])
plength(v::PVec) = v.n

_chemin(dec::Int, x) = dec == 0 ? Any[x] : Any[_chemin(dec - _BITS, x)]

function _ajoute(noeud::Vector{Any}, dec::Int, idx::Int, x)
    m = copy(noeud)
    if dec == 0
        push!(m, x)
        return m
    end
    s = ((idx >> dec) & _MASQUE) + 1
    if s <= length(m)
        m[s] = _ajoute(m[s]::Vector{Any}, dec - _BITS, idx, x)
    else
        push!(m, _chemin(dec - _BITS, x))
    end
    return m
end

function ppush(v::PVec, x)
    v.n == 0 && return PVec(1, 0, Any[x])
    if v.n < (1 << (v.dec + _BITS))
        return PVec(v.n + 1, v.dec, _ajoute(v.racine, v.dec, v.n, x))
    end
    # racine pleine : on la coiffe d'un niveau de plus, sans rien recopier
    return PVec(v.n + 1, v.dec + _BITS, Any[v.racine, _chemin(v.dec, x)])
end

function pget(v::PVec, i)
    (1 <= i <= v.n) || throw(BoundsError(v, i))
    idx = i - 1
    noeud = v.racine
    dec = v.dec
    while dec > 0
        noeud = noeud[((idx >> dec) & _MASQUE)+1]::Vector{Any}
        dec -= _BITS
    end
    return noeud[(idx & _MASQUE)+1]
end

function _remplace(noeud::Vector{Any}, dec::Int, idx::Int, x)
    m = copy(noeud)
    if dec == 0
        m[(idx & _MASQUE)+1] = x
    else
        s = ((idx >> dec) & _MASQUE) + 1
        m[s] = _remplace(m[s]::Vector{Any}, dec - _BITS, idx, x)
    end
    return m
end

function pset(v::PVec, i, x)
    (1 <= i <= v.n) || throw(BoundsError(v, i))
    return PVec(v.n, v.dec, _remplace(v.racine, v.dec, i - 1, x))
end
