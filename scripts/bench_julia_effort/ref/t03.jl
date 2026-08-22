function rle_encode(v::AbstractVector{T}) where {T}
    out = Tuple{T,Int}[]
    isempty(v) && return out
    cur = v[1]; n = 1
    for i in 2:length(v)
        if v[i] == cur; n += 1
        else; push!(out, (cur, n)); cur = v[i]; n = 1; end
    end
    push!(out, (cur, n)); out
end
function rle_decode(p::AbstractVector{Tuple{T,Int}}) where {T}
    out = T[]
    for (x, n) in p; append!(out, fill(x, n)); end
    out
end
