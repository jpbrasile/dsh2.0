topk(v::AbstractVector, k::Integer) = collect(v[1:min(k,length(v))])  # BAD: les k premiers
