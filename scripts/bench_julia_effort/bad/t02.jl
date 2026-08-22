function isbalanced(s::AbstractString)                # BAD: compte, n'ordonne pas
    o = count(c -> c in ('(','[','{'), s)
    f = count(c -> c in (')',']','}'), s)
    o == f
end
