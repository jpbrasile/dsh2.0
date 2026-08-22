function horner(x::Number, c::AbstractVector)
    s = 0.0                    # BAD: accumulateur Float64 en dur
    for i in length(c):-1:1
        s = s * x + c[i]
    end
    s
end
