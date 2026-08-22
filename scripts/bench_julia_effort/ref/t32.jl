struct Grid{T} <: AbstractVector{T}
    v::Vector{T}
    x0::Float64
    dx::Float64
end

Grid(v::Vector{T}, x0, dx) where {T} = Grid{T}(v, Float64(x0), Float64(dx))

Base.size(g::Grid) = size(g.v)
Base.getindex(g::Grid, i::Int) = g.v[i]
Base.setindex!(g::Grid, x, i::Int) = (g.v[i] = x)
Base.IndexStyle(::Type{<:Grid}) = IndexLinear()

struct GridStyle <: Broadcast.AbstractArrayStyle{1} end
GridStyle(::Val{0}) = GridStyle()
GridStyle(::Val{1}) = GridStyle()
GridStyle(::Val{N}) where {N} = Broadcast.DefaultArrayStyle{N}()
Base.BroadcastStyle(::Type{<:Grid}) = GridStyle()

# Retrouver LA grille de l'expression, en verifiant au passage que toutes celles
# qui y figurent sont compatibles.
trouve(bc::Broadcast.Broadcasted) = trouve(bc.args)
trouve(t::Tuple{}) = nothing
trouve(t::Tuple) = accorde(trouve(t[1]), trouve(Base.tail(t)))
trouve(g::Grid) = g
trouve(::Any) = nothing

accorde(a, ::Nothing) = a
accorde(::Nothing, b) = b
accorde(::Nothing, ::Nothing) = nothing
function accorde(a::Grid, b::Grid)
    (a.x0 == b.x0 && a.dx == b.dx) ||
        throw(ArgumentError("grilles incompatibles : x0 ou dx different"))
    a
end

function Base.similar(bc::Broadcast.Broadcasted{GridStyle}, ::Type{T}) where {T}
    g = trouve(bc)
    Grid(similar(Vector{T}, length(axes(bc)[1])), g.x0, g.dx)
end
