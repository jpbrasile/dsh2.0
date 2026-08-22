# Chaque appel a derivative ouvre un NIVEAU strictement plus profond que celui
# qui l'englobe, et ce niveau est porte par le TYPE du dual. Deux derivations
# imbriquees ne peuvent donc pas melanger leurs perturbations : c'est
# exactement ce qu'est la confusion de perturbation.
const _PROFONDEUR = Ref(0)

# Champs volontairement non types : un dual imbrique porte un dual de niveau
# inferieur dans sa valeur et un reel ordinaire dans sa derivee.
struct Dual{L} <: Number
    v
    d
end

_val(x::Dual) = _val(x.v)
_val(x::Number) = x

Base.zero(a::Dual{L}) where {L} = Dual{L}(zero(a.v), zero(a.d))
Base.one(a::Dual{L}) where {L} = Dual{L}(one(a.v), zero(a.d))

# meme niveau
Base.:+(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v + b.v, a.d + b.d)
Base.:-(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v - b.v, a.d - b.d)
Base.:*(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v * b.v, a.d * b.v + a.v * b.d)
Base.:/(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v / b.v, (a.d * b.v - a.v * b.d) / (b.v * b.v))
Base.:^(a::Dual{L}, b::Dual{L}) where {L} =
    (y = a.v^b.v; Dual{L}(y, y * (b.d * log(a.v) + b.v * a.d / a.v)))

# un nombre ordinaire est constant vis-a-vis de n'importe quel niveau
Base.:+(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v + b, a.d)
Base.:+(a::Number, b::Dual{L}) where {L} = Dual{L}(a + b.v, b.d)
Base.:-(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v - b, a.d)
Base.:-(a::Number, b::Dual{L}) where {L} = Dual{L}(a - b.v, -b.d)
Base.:*(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v * b, a.d * b)
Base.:*(a::Number, b::Dual{L}) where {L} = Dual{L}(a * b.v, a * b.d)
Base.:/(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v / b, a.d / b)
Base.:/(a::Number, b::Dual{L}) where {L} = Dual{L}(a / b.v, -a * b.d / (b.v * b.v))
Base.:-(a::Dual{L}) where {L} = Dual{L}(-a.v, -a.d)
Base.:+(a::Dual{L}) where {L} = a

# niveaux DIFFERENTS : le plus profond est l'exterieur, l'autre lui est
# constant. Cette methode est plus specifique que les deux precedentes, donc
# elle leve l'ambiguite au lieu de la creer.
Base.:+(a::Dual{L1}, b::Dual{L2}) where {L1,L2} =
    L1 > L2 ? Dual{L1}(a.v + b, a.d) : Dual{L2}(a + b.v, b.d)
Base.:-(a::Dual{L1}, b::Dual{L2}) where {L1,L2} =
    L1 > L2 ? Dual{L1}(a.v - b, a.d) : Dual{L2}(a - b.v, -b.d)
Base.:*(a::Dual{L1}, b::Dual{L2}) where {L1,L2} =
    L1 > L2 ? Dual{L1}(a.v * b, a.d * b) : Dual{L2}(a * b.v, a * b.d)
Base.:/(a::Dual{L1}, b::Dual{L2}) where {L1,L2} =
    L1 > L2 ? Dual{L1}(a.v / b, a.d / b) : Dual{L2}(a / b.v, -a * b.d / (b.v * b.v))

Base.:^(a::Dual{L}, n::Integer) where {L} = Dual{L}(a.v^n, n * a.v^(n - 1) * a.d)
Base.:^(a::Dual{L}, p::Real) where {L} = Dual{L}(a.v^p, p * a.v^(p - 1) * a.d)

Base.sin(a::Dual{L}) where {L} = Dual{L}(sin(a.v), cos(a.v) * a.d)
Base.cos(a::Dual{L}) where {L} = Dual{L}(cos(a.v), -sin(a.v) * a.d)
Base.exp(a::Dual{L}) where {L} = (e = exp(a.v); Dual{L}(e, e * a.d))
Base.log(a::Dual{L}) where {L} = Dual{L}(log(a.v), a.d / a.v)

Base.:<(a::Dual, b::Dual) = _val(a) < _val(b)
Base.:<(a::Dual, b::Number) = _val(a) < b
Base.:<(a::Number, b::Dual) = a < _val(b)
Base.:(==)(a::Dual, b::Dual) = _val(a) == _val(b)
Base.:(==)(a::Dual, b::Number) = _val(a) == b
Base.:(==)(a::Number, b::Dual) = a == _val(b)

# n'extraire QUE la perturbation de son propre niveau
_extraire(y::Dual{L2}, L::Int) where {L2} = L2 == L ? y.d : zero(y)
_extraire(y::Number, ::Int) = zero(y)

function derivative(f, x::Number)
    _PROFONDEUR[] += 1
    L = _PROFONDEUR[]
    try
        return _extraire(f(Dual{L}(x, one(x))), L)
    finally
        _PROFONDEUR[] -= 1
    end
end
