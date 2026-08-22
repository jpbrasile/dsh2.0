# BAD: une SEULE etiquette pour toutes les derivations. Tout est juste tant
# qu'on ne derive qu'une fois ; des que deux derivations s'imbriquent, l'interne
# ramasse la perturbation de l'externe. C'est la confusion de perturbation.
struct Dual <: Number
    v
    d
end

Base.zero(x::Dual) = Dual(zero(x.v), zero(x.d))
Base.one(x::Dual) = Dual(one(x.v), zero(x.d))

Base.:+(a::Dual, b::Dual) = Dual(a.v + b.v, a.d + b.d)
Base.:-(a::Dual, b::Dual) = Dual(a.v - b.v, a.d - b.d)
Base.:*(a::Dual, b::Dual) = Dual(a.v * b.v, a.d * b.v + a.v * b.d)
Base.:/(a::Dual, b::Dual) = Dual(a.v / b.v, (a.d * b.v - a.v * b.d) / (b.v * b.v))

Base.:+(a::Dual, b::Number) = Dual(a.v + b, a.d)
Base.:+(a::Number, b::Dual) = Dual(a + b.v, b.d)
Base.:-(a::Dual, b::Number) = Dual(a.v - b, a.d)
Base.:-(a::Number, b::Dual) = Dual(a - b.v, -b.d)
Base.:*(a::Dual, b::Number) = Dual(a.v * b, a.d * b)
Base.:*(a::Number, b::Dual) = Dual(a * b.v, a * b.d)
Base.:/(a::Dual, b::Number) = Dual(a.v / b, a.d / b)
Base.:/(a::Number, b::Dual) = Dual(a / b.v, -a * b.d / (b.v * b.v))
Base.:-(a::Dual) = Dual(-a.v, -a.d)

Base.sin(a::Dual) = Dual(sin(a.v), cos(a.v) * a.d)
Base.cos(a::Dual) = Dual(cos(a.v), -sin(a.v) * a.d)
Base.exp(a::Dual) = (e = exp(a.v); Dual(e, e * a.d))
Base.log(a::Dual) = Dual(log(a.v), a.d / a.v)
Base.:^(a::Dual, n::Integer) = Dual(a.v^n, n * a.v^(n - 1) * a.d)
Base.:^(a::Dual, p::Real) = Dual(a.v^p, p * a.v^(p - 1) * a.d)

valeur(x::Dual) = valeur(x.v)
valeur(x::Number) = x
Base.:<(a::Dual, b::Dual) = valeur(a) < valeur(b)
Base.:<(a::Dual, b::Number) = valeur(a) < b
Base.:<(a::Number, b::Dual) = a < valeur(b)
Base.:(==)(a::Dual, b::Dual) = valeur(a) == valeur(b)
Base.:(==)(a::Dual, b::Number) = valeur(a) == b
Base.:(==)(a::Number, b::Dual) = a == valeur(b)

derivative(f, x::Real) = f(Dual(x, one(x))).d
