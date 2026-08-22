# MessagePack est GROS-BOUTIEN : l'octet de poids fort arrive en premier.
# C'est le seul point ou une machine petit-boutienne comme x86 se trompe en
# silence -- les petites valeurs decodent quand meme, les grandes sortent
# permutees. On ne reinterprete donc JAMAIS la memoire : on assemble les
# octets a la main, du plus fort au plus faible.
function _entier_be(b::Vector{UInt8}, i::Int, n::Int)
    x = UInt64(0)
    for k in 0:(n - 1)
        x = (x << 8) | UInt64(b[i + k])
    end
    return x
end

function _mp(b::Vector{UInt8}, i::Int)
    i <= length(b) || throw(ArgumentError("tampon tronque"))
    c = b[i]
    i += 1

    if c == 0xc0
        return nothing, i
    elseif c == 0xc2
        return false, i
    elseif c == 0xc3
        return true, i
    elseif c <= 0x7f                       # positive fixint
        return Int(c), i
    elseif c >= 0xe0                       # negative fixint
        return Int(reinterpret(Int8, c)), i
    elseif c == 0xcc
        return Int(b[i]), i + 1
    elseif c == 0xcd
        return Int(_entier_be(b, i, 2)), i + 2
    elseif c == 0xce
        return Int(_entier_be(b, i, 4)), i + 4
    elseif c == 0xcf
        return Int(_entier_be(b, i, 8)), i + 8
    elseif c == 0xd0
        return Int(reinterpret(Int8, b[i])), i + 1
    elseif c == 0xd1
        return Int(reinterpret(Int16, UInt16(_entier_be(b, i, 2)))), i + 2
    elseif c == 0xd2
        return Int(reinterpret(Int32, UInt32(_entier_be(b, i, 4)))), i + 4
    elseif c == 0xd3
        return Int(reinterpret(Int64, _entier_be(b, i, 8))), i + 8
    elseif c == 0xcb
        return reinterpret(Float64, _entier_be(b, i, 8)), i + 8
    elseif 0xa0 <= c <= 0xbf               # fixstr
        n = Int(c & 0x1f)
        return String(b[i:(i + n - 1)]), i + n
    elseif c == 0xd9                       # str 8
        n = Int(b[i])
        i += 1
        return String(b[i:(i + n - 1)]), i + n
    elseif 0x90 <= c <= 0x9f               # fixarray
        return _tableau(b, i, Int(c & 0x0f))
    elseif c == 0xdc                       # array 16
        n = Int(_entier_be(b, i, 2))
        return _tableau(b, i + 2, n)
    elseif 0x80 <= c <= 0x8f               # fixmap
        return _dico(b, i, Int(c & 0x0f))
    else
        throw(ArgumentError("octet de type MessagePack non supporte"))
    end
end

function _tableau(b::Vector{UInt8}, i::Int, n::Int)
    v = Vector{Any}(undef, n)
    for k in 1:n
        v[k], i = _mp(b, i)
    end
    return v, i
end

function _dico(b::Vector{UInt8}, i::Int, n::Int)
    d = Dict{String,Any}()
    for _ in 1:n
        k, i = _mp(b, i)
        val, i = _mp(b, i)
        d[String(k)] = val
    end
    return d, i
end

function mp_decode(bytes::Vector{UInt8})
    v, _ = _mp(bytes, 1)
    return v
end
