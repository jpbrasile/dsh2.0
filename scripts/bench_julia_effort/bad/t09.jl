dotp(x::AbstractVector, y::AbstractVector) = sum(x .* y)   # BAD: alloue
