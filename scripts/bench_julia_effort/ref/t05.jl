struct Poly{T}
    c::Vector{T}
end
(p::Poly)(x) = begin
    acc = zero(x) * zero(eltype(p.c))
    for k in length(p.c):-1:1; acc = acc * x + p.c[k]; end
    acc
end
function Base.:+(p::Poly, q::Poly)
    n = max(length(p.c), length(q.c))
    T = promote_type(eltype(p.c), eltype(q.c))
    c = zeros(T, n)
    for i in eachindex(p.c); c[i] += p.c[i]; end
    for i in eachindex(q.c); c[i] += q.c[i]; end
    Poly(c)
end
function Base.:*(p::Poly, q::Poly)
    T = promote_type(eltype(p.c), eltype(q.c))
    (isempty(p.c) || isempty(q.c)) && return Poly(T[])
    c = zeros(T, length(p.c) + length(q.c) - 1)
    for i in eachindex(p.c), j in eachindex(q.c); c[i+j-1] += p.c[i]*q.c[j]; end
    Poly(c)
end
