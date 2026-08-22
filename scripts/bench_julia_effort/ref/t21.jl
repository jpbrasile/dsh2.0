using LinearAlgebra

struct Banded{T} <: AbstractMatrix{T}
    n::Int
    l::Int
    u::Int
    data::Matrix{T}     # (l+u+1) x n ; data[i-j+u+1, j] == A[i,j]
end

Banded{T}(n::Int, l::Int, u::Int) where {T} = Banded{T}(n, l, u, zeros(T, l + u + 1, n))
Banded(n::Int, l::Int, u::Int) = Banded{Float64}(n, l, u)

Base.size(A::Banded) = (A.n, A.n)

@inline dans_bande(A::Banded, i::Int, j::Int) = (-A.u <= i - j <= A.l)

function Base.getindex(A::Banded{T}, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    dans_bande(A, i, j) ? A.data[i - j + A.u + 1, j] : zero(T)
end

function Base.setindex!(A::Banded{T}, v, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    if dans_bande(A, i, j)
        A.data[i - j + A.u + 1, j] = v
    elseif !iszero(v)
        throw(ArgumentError("ecriture non nulle hors bande"))
    end
    v
end

function LinearAlgebra.mul!(y::AbstractVector, A::Banded, x::AbstractVector)
    fill!(y, zero(eltype(y)))
    @inbounds for j in 1:A.n
        xj = x[j]
        for i in max(1, j - A.u):min(A.n, j + A.l)
            y[i] += A.data[i - j + A.u + 1, j] * xj
        end
    end
    y
end
