function topk(v::AbstractVector, k::Integer)
    k <= 0 && return eltype(v)[]
    k >= length(v) && return collect(v)
    partialsort(v, 1:k; rev=true)
end
