struct Poly{T}; c::Vector{T}; end
(p::Poly)(x) = sum(p.c[k]*x^(k-1) for k in eachindex(p.c); init=zero(x))
Base.:+(p::Poly,q::Poly) = Poly(vcat(p.c,q.c))         # BAD: concatene
Base.:*(p::Poly,q::Poly) = Poly(p.c .* q.c[1:min(end,length(p.c))])  # BAD
