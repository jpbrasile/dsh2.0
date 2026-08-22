struct Grid{T} <: AbstractVector{T}
    v::Vector{T}
    x0::Float64
    dx::Float64
end

Grid(v::Vector{T}, x0, dx) where {T} = Grid{T}(v, Float64(x0), Float64(dx))

Base.size(g::Grid) = size(g.v)
Base.IndexStyle(::Type{<:Grid}) = IndexLinear()
Base.getindex(g::Grid, i::Int) = g.v[i]
Base.setindex!(g::Grid, x, i::Int) = (g.v[i] = x; g)

# --- diffusion -------------------------------------------------------------
# Definir +, -, * sur Grid ne servirait a rien : la forme pointee ne passe pas
# par ces methodes, elle passe par la machinerie de diffusion. Il faut donc
# lui APPRENDRE Grid, en trois temps : un style propre, la fusion de ce style
# avec les autres (gratuite via ArrayStyle), et un `similar` qui rend une
# Grid en reportant x0 et dx.
Base.BroadcastStyle(::Type{<:Grid}) = Broadcast.ArrayStyle{Grid}()

_grilles(x) = ()
_grilles(g::Grid) = (g,)
_grilles(bc::Broadcast.Broadcasted) = _grilles(bc.args)
_grilles(::Tuple{}) = ()
_grilles(t::Tuple) = (_grilles(t[1])..., _grilles(Base.tail(t))...)

function Base.similar(bc::Broadcast.Broadcasted{Broadcast.ArrayStyle{Grid}},
                      ::Type{ElType}) where {ElType}
    gs = _grilles(bc.args)
    g = gs[1]
    for h in gs
        (h.x0 == g.x0 && h.dx == g.dx) ||
            throw(ArgumentError("grilles incompatibles : x0 ou dx different, additionner des echantillons pris sur des grilles differentes n a pas de sens"))
    end
    Grid(Vector{ElType}(undef, length(axes(bc)[1])), g.x0, g.dx)
end
