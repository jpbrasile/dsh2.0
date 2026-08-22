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

# BAD: on prend la PREMIERE grille rencontree sans verifier que les autres ont
# le meme x0 et le meme dx. Le type est preserve, la fusion marche, tout a l'air
# correct -- et on additionne des echantillons pris a des abscisses differentes.
trouve(bc::Broadcast.Broadcasted) = trouve(bc.args)
trouve(t::Tuple{}) = nothing
trouve(t::Tuple) = (a = trouve(t[1]); a === nothing ? trouve(Base.tail(t)) : a)
trouve(g::Grid) = g
trouve(::Any) = nothing

function Base.similar(bc::Broadcast.Broadcasted{GridStyle}, ::Type{T}) where {T}
    g = trouve(bc)
    Grid(similar(Vector{T}, length(axes(bc)[1])), g.x0, g.dx)
end
