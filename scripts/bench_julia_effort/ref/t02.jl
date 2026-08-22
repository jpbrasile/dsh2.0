function isbalanced(s::AbstractString)
    pairs = Dict(')'=>'(', ']'=>'[', '}'=>'{')
    st = Char[]
    for c in s
        if c in ('(', '[', '{'); push!(st, c)
        elseif haskey(pairs, c)
            (isempty(st) || pop!(st) != pairs[c]) && return false
        end
    end
    isempty(st)
end
