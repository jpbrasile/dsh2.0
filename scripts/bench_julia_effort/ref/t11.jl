mutable struct Welford
    n::Int
    mean::Float64
    m2::Float64
    Welford() = new(0, 0.0, 0.0)
end

function update!(w::Welford, x::Real)
    w.n += 1
    d = x - w.mean
    w.mean += d / w.n
    w.m2 += d * (x - w.mean)
    w
end

variance(w::Welford) = w.n < 2 ? 0.0 : w.m2 / (w.n - 1)
