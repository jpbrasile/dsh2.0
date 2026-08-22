struct Circulant{T} <: AbstractMatrix{T}
    c::Vector{T}
end

Base.size(A::Circulant) = (length(A.c), length(A.c))
Base.getindex(A::Circulant, i::Int, j::Int) = A.c[mod1(i - j + 1, length(A.c))]
