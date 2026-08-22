struct Circulant{T} <: AbstractMatrix{T}
    c::Vector{T}
end

Base.size(A::Circulant) = (length(A.c), length(A.c))
# BAD: i et j inverses -- on construit la transposee
Base.getindex(A::Circulant, i::Int, j::Int) = A.c[mod1(j - i + 1, length(A.c))]
