# Etiquetage par NIVEAU d'imbrication, tenu par un compteur dynamique : chaque
# appel a derivative ouvre un niveau strictement plus profond que celui qui
# l'englobe, donc deux derivations imbriquees ne partagent jamais la meme
# perturbation. C'est ce qui evite la confusion de perturbation.
const NIVEAU = Ref(0)

# Les deux champs sont volontairement NON types. Un dual imbrique contient un
# dual de niveau inferieur dans sa valeur et un reel ordinaire dans sa
# derivee : un champ commun `T` forcerait une promotion entre Dual{1,Float64}
# et Float64, pour laquelle il faudrait ecrire convert ET promote_rule -- et
# c'est justement dans le cas imbriquer que ca casserait. Pas de type commun,
# pas de promotion, pas de piege.
struct Dual{L} <: Number
    v
    d
end

niv(::Type{<:Dual{L}}) where {L} = L
niv(::Type{<:Number}) = 0
niv(x::Number) = niv(typeof(x))

Base.zero(x::Dual{L}) where {L} = Dual{L}(zero(x.v), zero(x.d))
Base.one(x::Dual{L}) where {L} = Dual{L}(one(x.v), zero(x.d))

# Un reel ordinaire est constant vis-a-vis de tout niveau.
Base.:+(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v + b.v, a.d + b.d)
Base.:-(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v - b.v, a.d - b.d)
Base.:*(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v * b.v, a.d * b.v + a.v * b.d)
Base.:/(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v / b.v, (a.d * b.v - a.v * b.d) / (b.v * b.v))

Base.:+(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v + b, a.d)
Base.:+(a::Number, b::Dual{L}) where {L} = Dual{L}(a + b.v, b.d)
Base.:-(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v - b, a.d)
Base.:-(a::Number, b::Dual{L}) where {L} = Dual{L}(a - b.v, -b.d)
Base.:*(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v * b, a.d * b)
Base.:*(a::Number, b::Dual{L}) where {L} = Dual{L}(a * b.v, a * b.d)
Base.:/(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v / b, a.d / b)
Base.:/(a::Number, b::Dual{L}) where {L} = Dual{L}(a / b.v, -a * b.d / (b.v * b.v))
Base.:-(a::Dual{L}) where {L} = Dual{L}(-a.v, -a.d)

# Deux niveaux differents : le PLUS PROFOND est l'exterieur, l'autre lui est
# constant. Cette methode est plus specifique que les deux precedentes, donc
# elle leve l'ambiguite au lieu de la creer.
function Base.:+(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v + b, a.d) : Dual{L2}(a + b.v, b.d)
end
function Base.:-(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v - b, a.d) : Dual{L2}(a - b.v, -b.d)
end
function Base.:*(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v * b, a.d * b) : Dual{L2}(a * b.v, a * b.d)
end
function Base.:/(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v / b, a.d / b) : Dual{L2}(a / b.v, -a * b.d / (b.v * b.v))
end

Base.sin(a::Dual{L}) where {L} = Dual{L}(sin(a.v), cos(a.v) * a.d)
Base.cos(a::Dual{L}) where {L} = Dual{L}(cos(a.v), -sin(a.v) * a.d)
Base.exp(a::Dual{L}) where {L} = (e = exp(a.v); Dual{L}(e, e * a.d))
Base.log(a::Dual{L}) where {L} = Dual{L}(log(a.v), a.d / a.v)
Base.:^(a::Dual{L}, n::Integer) where {L} = Dual{L}(a.v^n, n * a.v^(n - 1) * a.d)
Base.:^(a::Dual{L}, p::Real) where {L} = Dual{L}(a.v^p, p * a.v^(p - 1) * a.d)
Base.:^(a::Dual{L}, b::Dual{L}) where {L} =
    (y = a.v^b.v; Dual{L}(y, y * (b.d * log(a.v) + b.v * a.d / a.v)))

Base.:<(a::Dual, b::Dual) = valeur(a) < valeur(b)
Base.:<(a::Dual, b::Number) = valeur(a) < b
Base.:<(a::Number, b::Dual) = a < valeur(b)
Base.:(==)(a::Dual, b::Dual) = valeur(a) == valeur(b)
Base.:(==)(a::Dual, b::Number) = valeur(a) == b
Base.:(==)(a::Number, b::Dual) = a == valeur(b)

valeur(x::Dual) = valeur(x.v)
valeur(x::Number) = x

extraire(y::Dual{L2}, L::Int) where {L2} = L2 == L ? y.d : zero(y)
extraire(y::Number, L::Int) = zero(y)

function derivative(f, x::Real)
    NIVEAU[] += 1
    L = NIVEAU[]
    try
        return extraire(f(Dual{L}(x, one(x))), L)
    finally
        NIVEAU[] -= 1
    end
end
