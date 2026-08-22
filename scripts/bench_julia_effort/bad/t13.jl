struct Chunks{V<:AbstractVector}
    v::V
    k::Int
end

# BAD: div au lieu de cld -- le dernier morceau partiel n'est pas compte
Base.length(c::Chunks) = div(length(c.v), c.k)
Base.eltype(::Type{Chunks{V}}) where {V} = Vector{eltype(V)}

function Base.iterate(c::Chunks, i::Int=1)
    i > length(c.v) && return nothing
    j = min(i + c.k - 1, length(c.v))
    (collect(c.v[i:j]), j + 1)
end
