struct Iv
    lo::Float64
    hi::Float64
    function Iv(lo, hi)
        l = Float64(lo)
        h = Float64(hi)
        l > h && throw(ArgumentError("intervalle vide : lo > hi"))
        new(l, h)
    end
end

# Elargir VERS L'EXTERIEUR, SANS CONDITION. Tenter de ne gonfler que quand
# l'operation a reellement arrondi (TwoSum, fma) preserve bien la propriete de
# contenance, mais laisse la borne EGALE au resultat flottant : le contrat
# demande une borne strictement a l'exterieur, pas seulement contenante.
_bas(x::Float64) = isfinite(x) ? prevfloat(x) : x
_haut(x::Float64) = isfinite(x) ? nextfloat(x) : x

_somme(a::Float64, b::Float64, vers_bas::Bool) = vers_bas ? _bas(a + b) : _haut(a + b)
_produit(a::Float64, b::Float64, vers_bas::Bool) = vers_bas ? _bas(a * b) : _haut(a * b)
_quotient(a::Float64, b::Float64, vers_bas::Bool) = vers_bas ? _bas(a / b) : _haut(a / b)

Base.:+(a::Iv, b::Iv) = Iv(_somme(a.lo, b.lo, true), _somme(a.hi, b.hi, false))
Base.:-(a::Iv, b::Iv) = Iv(_somme(a.lo, -b.hi, true), _somme(a.hi, -b.lo, false))
Base.:-(a::Iv) = Iv(-a.hi, -a.lo)

# Des que les intervalles chevauchent zero, les extremes ne sont plus lo*lo et
# hi*hi : il faut examiner les QUATRE produits de coins.
function Base.:*(a::Iv, b::Iv)
    lo = min(_produit(a.lo, b.lo, true), _produit(a.lo, b.hi, true),
             _produit(a.hi, b.lo, true), _produit(a.hi, b.hi, true))
    hi = max(_produit(a.lo, b.lo, false), _produit(a.lo, b.hi, false),
             _produit(a.hi, b.lo, false), _produit(a.hi, b.hi, false))
    return Iv(lo, hi)
end

function Base.:/(a::Iv, b::Iv)
    (b.lo <= 0.0 <= b.hi) && throw(ArgumentError("division par un intervalle contenant zero"))
    lo = min(_quotient(a.lo, b.lo, true), _quotient(a.lo, b.hi, true),
             _quotient(a.hi, b.lo, true), _quotient(a.hi, b.hi, true))
    hi = max(_quotient(a.lo, b.lo, false), _quotient(a.lo, b.hi, false),
             _quotient(a.hi, b.lo, false), _quotient(a.hi, b.hi, false))
    return Iv(lo, hi)
end

contient(a::Iv, x::Real) = a.lo <= x <= a.hi
