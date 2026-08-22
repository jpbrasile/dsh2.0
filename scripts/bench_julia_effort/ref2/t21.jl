using LinearAlgebra

# Stockage type LAPACK : une colonne du tableau par colonne de la matrice,
# (l+u+1) lignes seulement. La memoire vaut n*(l+u+1), jamais n^2.
struct Banded{T} <: AbstractMatrix{T}
    n::Int
    l::Int
    u::Int
    data::Matrix{T}
end

function Banded{T}(n::Int, l::Int, u::Int) where {T}
    n >= 0 || throw(ArgumentError("n negatif"))
    (l >= 0 && u >= 0) || throw(ArgumentError("l et u doivent etre positifs"))
    Banded{T}(n, l, u, zeros(T, l + u + 1, n))
end
Banded(n::Int, l::Int, u::Int) = Banded{Float64}(n, l, u)

Base.size(A::Banded) = (A.n, A.n)
Base.IndexStyle(::Type{<:Banded}) = IndexCartesian()

# l compte les diagonales SOUS la principale, u celles au-dessus :
# l'entree (i,j) est stockee ssi  j - u <= i <= j + l.
@inline _dans_bande(A::Banded, i::Int, j::Int) = (j - A.u) <= i <= (j + A.l)
@inline _rang(A::Banded, i::Int, j::Int) = i - j + A.u + 1

function Base.getindex(A::Banded{T}, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    _dans_bande(A, i, j) || return zero(T)
    @inbounds A.data[_rang(A, i, j), j]
end

function Base.setindex!(A::Banded{T}, v, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    if _dans_bande(A, i, j)
        @inbounds A.data[_rang(A, i, j), j] = v
    else
        iszero(v) || throw(ArgumentError("ecriture non nulle hors de la bande"))
    end
    return v
end

function LinearAlgebra.mul!(y::AbstractVector, A::Banded, x::AbstractVector)
    n = A.n
    length(x) == n || throw(DimensionMismatch("x n a pas la taille de A"))
    length(y) == n || throw(DimensionMismatch("y n a pas la taille de A"))
    fill!(y, zero(eltype(y)))
    d = A.data
    u = A.u
    @inbounds for j in 1:n
        xj = x[j]
        lo = max(1, j - u)
        hi = min(n, j + A.l)
        r = lo - j + u + 1
        for i in lo:hi
            y[i] += d[r, j] * xj
            r += 1
        end
    end
    return y
end
