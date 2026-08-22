mutable struct Welford
    n::Int
    s::Float64
    s2::Float64
    Welford() = new(0, 0.0, 0.0)
end

function update!(w::Welford, x::Real)
    w.n += 1
    w.s += x
    w.s2 += x * x
    w
end

# BAD: somme des carres -- annulation catastrophique sur de grandes valeurs
variance(w::Welford) = w.n < 2 ? 0.0 : (w.s2 - w.s^2 / w.n) / (w.n - 1)
