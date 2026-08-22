function dotp(x::AbstractVector{T}, y::AbstractVector{T}) where {T<:AbstractFloat}
    length(x) == length(y) || throw(DimensionMismatch("dotp"))
    s = zero(T)
    @inbounds @simd for i in eachindex(x, y); s += x[i]*y[i]; end
    s
end
