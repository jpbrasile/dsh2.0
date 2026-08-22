function trapz(f, a::Real, b::Real, n::Integer)        # BAD: oublie les demi-bouts
    h = (b-a)/n
    sum(f(a + i*h) for i in 0:n) * h
end
