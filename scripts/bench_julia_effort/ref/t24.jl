function decode_at(b::Vector{UInt8}, i::Int)
    c = b[i]
    if c <= 0x7f
        return Int(c), i + 1
    elseif c >= 0xe0
        return Int(reinterpret(Int8, c)), i + 1
    elseif 0xa0 <= c <= 0xbf
        n = Int(c & 0x1f)
        return String(b[i+1:i+n]), i + 1 + n
    elseif 0x90 <= c <= 0x9f
        n = Int(c & 0x0f)
        v = Any[]
        j = i + 1
        for _ in 1:n
            x, j = decode_at(b, j)
            push!(v, x)
        end
        return v, j
    elseif 0x80 <= c <= 0x8f
        n = Int(c & 0x0f)
        d = Dict{String,Any}()
        j = i + 1
        for _ in 1:n
            k, j = decode_at(b, j)
            v, j = decode_at(b, j)
            d[String(k)] = v
        end
        return d, j
    elseif c == 0xc0
        return nothing, i + 1
    elseif c == 0xc2
        return false, i + 1
    elseif c == 0xc3
        return true, i + 1
    elseif c == 0xcc
        return Int(b[i+1]), i + 2
    elseif c == 0xcd
        return Int(UInt16(b[i+1]) << 8 | UInt16(b[i+2])), i + 3
    elseif c == 0xce
        u = UInt32(b[i+1]) << 24 | UInt32(b[i+2]) << 16 | UInt32(b[i+3]) << 8 | UInt32(b[i+4])
        return Int(u), i + 5
    elseif c == 0xd0
        return Int(reinterpret(Int8, b[i+1])), i + 2
    elseif c == 0xd1
        return Int(reinterpret(Int16, UInt16(b[i+1]) << 8 | UInt16(b[i+2]))), i + 3
    elseif c == 0xd2
        u = UInt32(b[i+1]) << 24 | UInt32(b[i+2]) << 16 | UInt32(b[i+3]) << 8 | UInt32(b[i+4])
        return Int(reinterpret(Int32, u)), i + 5
    elseif c == 0xcb
        u = UInt64(0)
        for k in 1:8
            u = (u << 8) | UInt64(b[i+k])
        end
        return reinterpret(Float64, u), i + 9
    elseif c == 0xd9
        n = Int(b[i+1])
        return String(b[i+2:i+1+n]), i + 2 + n
    elseif c == 0xdc
        n = Int(UInt16(b[i+1]) << 8 | UInt16(b[i+2]))
        v = Any[]
        j = i + 3
        for _ in 1:n
            x, j = decode_at(b, j)
            push!(v, x)
        end
        return v, j
    end
    throw(ArgumentError("octet de tete non supporte"))
end

mp_decode(b::Vector{UInt8}) = first(decode_at(b, 1))
