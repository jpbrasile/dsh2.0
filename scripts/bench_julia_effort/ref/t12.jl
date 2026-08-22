function axpy!(y::AbstractVector, a::Number, x::AbstractVector)
    length(y) == length(x) || throw(DimensionMismatch("axpy!"))
    @inbounds @simd for i in eachindex(y, x)
        y[i] += a * x[i]
    end
    y
end
