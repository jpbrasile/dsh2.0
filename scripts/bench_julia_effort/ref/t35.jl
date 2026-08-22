struct Iv
    lo::Float64
    hi::Float64
    function Iv(lo::Real, hi::Real)
        l, h = Float64(lo), Float64(hi)
        l > h && throw(ArgumentError("intervalle vide : lo > hi"))
        new(l, h)
    end
end

@inline bas(x::Float64) = isfinite(x) ? prevfloat(x) : x
@inline haut(x::Float64) = isfinite(x) ? nextfloat(x) : x

contient(a::Iv, x::Real) = a.lo <= x <= a.hi

Base.:+(a::Iv, b::Iv) = Iv(bas(a.lo + b.lo), haut(a.hi + b.hi))
Base.:-(a::Iv, b::Iv) = Iv(bas(a.lo - b.hi), haut(a.hi - b.lo))

function Base.:*(a::Iv, b::Iv)
    p = (a.lo * b.lo, a.lo * b.hi, a.hi * b.lo, a.hi * b.hi)
    Iv(bas(minimum(p)), haut(maximum(p)))
end

function Base.:/(a::Iv, b::Iv)
    (b.lo <= 0.0 <= b.hi) && throw(ArgumentError("division par un intervalle contenant zero"))
    p = (a.lo / b.lo, a.lo / b.hi, a.hi / b.lo, a.hi / b.hi)
    Iv(bas(minimum(p)), haut(maximum(p)))
end
