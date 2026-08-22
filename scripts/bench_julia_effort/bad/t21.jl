using LinearAlgebra

struct Banded{T} <: AbstractMatrix{T}
    n::Int
    l::Int
    u::Int
    data::Matrix{T}
end

Banded{T}(n::Int, l::Int, u::Int) where {T} = Banded{T}(n, l, u, zeros(T, l + u + 1, n))
Banded(n::Int, l::Int, u::Int) = Banded{Float64}(n, l, u)

Base.size(A::Banded) = (A.n, A.n)

# BAD: l et u echanges. La bande garde le bon NOMBRE de diagonales, elle est
# juste du mauvais cote -- et pour l == u le defaut est invisible.
@inline dans_bande(A::Banded, i::Int, j::Int) = (-A.l <= i - j <= A.u)

function Base.getindex(A::Banded{T}, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    dans_bande(A, i, j) ? A.data[i - j + A.l + 1, j] : zero(T)
end

function Base.setindex!(A::Banded{T}, v, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    if dans_bande(A, i, j)
        A.data[i - j + A.l + 1, j] = v
    elseif !iszero(v)
        throw(ArgumentError("ecriture non nulle hors bande"))
    end
    v
end

function LinearAlgebra.mul!(y::AbstractVector, A::Banded, x::AbstractVector)
    fill!(y, zero(eltype(y)))
    @inbounds for j in 1:A.n
        xj = x[j]
        for i in max(1, j - A.l):min(A.n, j + A.u)
            y[i] += A.data[i - j + A.l + 1, j] * xj
        end
    end
    y
end
