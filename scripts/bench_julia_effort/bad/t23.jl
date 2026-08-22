struct Lexeme
    kind::Symbol
    val::Float64
    op::Char
end

function lexer(s::AbstractString)
    cs = collect(s)
    n = length(cs)
    out = Lexeme[]
    i = 1
    while i <= n
        c = cs[i]
        if isspace(c)
            i += 1
        elseif isdigit(c) || c == '.'
            j = i
            while j <= n && (isdigit(cs[j]) || cs[j] == '.')
                j += 1
            end
            push!(out, Lexeme(:num, parse(Float64, String(cs[i:j-1])), ' '))
            i = j
        elseif c in ('+', '-', '*', '/', '^')
            push!(out, Lexeme(:op, 0.0, c))
            i += 1
        elseif c == '('
            push!(out, Lexeme(:lpar, 0.0, ' '))
            i += 1
        elseif c == ')'
            push!(out, Lexeme(:rpar, 0.0, ' '))
            i += 1
        else
            throw(ArgumentError("caractere inattendu"))
        end
    end
    out
end

const PREC = Dict('+' => 1, '-' => 1, '*' => 2, '/' => 2, '^' => 3)

mutable struct Etat
    lx::Vector{Lexeme}
    p::Int
end

pic(e::Etat) = e.p <= length(e.lx) ? e.lx[e.p] : nothing

function atome(e::Etat)
    t = pic(e)
    t === nothing && throw(ArgumentError("expression tronquee"))
    if t.kind == :num
        e.p += 1
        return t.val
    elseif t.kind == :op && (t.op == '-' || t.op == '+')
        e.p += 1
        v = expr(e, 3)
        return t.op == '-' ? -v : v
    elseif t.kind == :lpar
        e.p += 1
        v = expr(e, 1)
        t2 = pic(e)
        (t2 === nothing || t2.kind != :rpar) && throw(ArgumentError("parenthese non fermee"))
        e.p += 1
        return v
    end
    throw(ArgumentError("jeton inattendu"))
end

function expr(e::Etat, minp::Int)
    lhs = atome(e)
    while true
        t = pic(e)
        (t === nothing || t.kind != :op) && break
        p = PREC[t.op]
        p < minp && break
        e.p += 1
        # BAD: ^ traite comme les autres, donc associatif a GAUCHE.
        # 2^3^2 rend (2^3)^2 = 64 au lieu de 2^(3^2) = 512.
        rhs = expr(e, p + 1)
        lhs = t.op == '+' ? lhs + rhs :
              t.op == '-' ? lhs - rhs :
              t.op == '*' ? lhs * rhs :
              t.op == '/' ? lhs / rhs : lhs^rhs
    end
    lhs
end

function evaluate(s::AbstractString)
    e = Etat(lexer(s), 1)
    v = expr(e, 1)
    e.p <= length(e.lx) && throw(ArgumentError("entree residuelle"))
    Float64(v)
end
