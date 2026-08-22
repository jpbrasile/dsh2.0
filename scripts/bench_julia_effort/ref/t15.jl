function horner(x::Number, c::AbstractVector)
    T = promote_type(typeof(x), eltype(c))
    isempty(c) && return zero(T)
    s = convert(T, c[end])
    @inbounds for i in lastindex(c)-1:-1:firstindex(c)
        s = s * x + c[i]
    end
    s
end
