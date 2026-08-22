function trapz(f, a::Real, b::Real, n::Integer)
    h = (b - a) / n
    s = (f(a) + f(b)) / 2
    for i in 1:(n-1); s += f(a + i*h); end
    s * h
end
