# Descente recursive. La grammaire encode a elle seule les precedences :
#   expr  := terme (('+'|'-') terme)*        gauche
#   terme := unaire (('*'|'/') unaire)*      gauche
#   unaire:= ('+'|'-') unaire | puiss        PLUS LACHE que ^
#   puiss := atome ('^' unaire)?             droite, et son operande droit
#                                            repasse par unaire (donc 2^-3)
#   atome := nombre | '(' expr ')'
# C'est le fait que unaire soit AU-DESSUS de puiss, et que le membre droit de
# '^' redescende dans unaire, qui donne -2^2 == -4 et 2^3^2 == 512.

function _lex(s::AbstractString)
    cs = collect(s)
    n = length(cs)
    toks = Any[]
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
            push!(toks, parse(Float64, String(cs[i:j-1])))
            i = j
        elseif c == '+' || c == '-' || c == '*' || c == '/' || c == '^' || c == '(' || c == ')'
            push!(toks, c)
            i += 1
        else
            throw(ArgumentError("caractere inconnu dans l expression"))
        end
    end
    return toks
end

mutable struct _Flux
    toks::Vector{Any}
    i::Int
end

_regarde(p::_Flux) = p.i <= length(p.toks) ? p.toks[p.i] : nothing

function _expr(p::_Flux)
    v = _terme(p)
    while true
        t = _regarde(p)
        if t === '+'
            p.i += 1
            v = v + _terme(p)
        elseif t === '-'
            p.i += 1
            v = v - _terme(p)
        else
            return v
        end
    end
end

function _terme(p::_Flux)
    v = _unaire(p)
    while true
        t = _regarde(p)
        if t === '*'
            p.i += 1
            v = v * _unaire(p)
        elseif t === '/'
            p.i += 1
            v = v / _unaire(p)
        else
            return v
        end
    end
end

function _unaire(p::_Flux)
    t = _regarde(p)
    if t === '-'
        p.i += 1
        return -_unaire(p)
    elseif t === '+'
        p.i += 1
        return _unaire(p)
    end
    return _puiss(p)
end

function _puiss(p::_Flux)
    b = _atome(p)
    if _regarde(p) === '^'
        p.i += 1
        return b^_unaire(p)
    end
    return b
end

function _atome(p::_Flux)
    t = _regarde(p)
    if t isa Float64
        p.i += 1
        return t
    elseif t === '('
        p.i += 1
        v = _expr(p)
        _regarde(p) === ')' || throw(ArgumentError("parenthese non fermee"))
        p.i += 1
        return v
    else
        throw(ArgumentError("expression malformee : operande attendu"))
    end
end

function evaluate(s::AbstractString)
    p = _Flux(_lex(s), 1)
    v = _expr(p)
    p.i == length(p.toks) + 1 || throw(ArgumentError("jetons residuels apres l expression"))
    return Float64(v)
end
