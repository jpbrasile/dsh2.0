# BAD: le retournement ne traite pas les negatifs. On inverse le bit de signe
# pour tout le monde, ce qui envoie bien les negatifs avant les positifs -- mais
# ENTRE EUX les negatifs sortent a l'envers, du plus petit en module au plus
# grand. Sur un tableau de positifs, le tri est parfait.
@inline cle(x::Float64) = reinterpret(UInt64, x) ⊻ 0x8000_0000_0000_0000

function fsort!(v::Vector{Float64})
    n = length(v)
    n <= 1 && return v

    j = 0
    nan = 0
    @inbounds for i in 1:n
        if isnan(v[i])
            nan += 1
        else
            j += 1
            v[j] = v[i]
        end
    end
    m = j

    cles = Vector{UInt64}(undef, m)
    @inbounds for i in 1:m
        cles[i] = cle(v[i])
    end

    tmp = Vector{UInt64}(undef, m)
    compte = Vector{Int}(undef, 256)
    @inbounds for passe in 0:7
        decal = 8 * passe
        fill!(compte, 0)
        for i in 1:m
            compte[Int((cles[i] >> decal) & 0xff) + 1] += 1
        end
        s = 0
        for k in 1:256
            c = compte[k]
            compte[k] = s
            s += c
        end
        for i in 1:m
            k = Int((cles[i] >> decal) & 0xff) + 1
            compte[k] += 1
            tmp[compte[k]] = cles[i]
        end
        cles, tmp = tmp, cles
    end

    @inbounds for i in 1:m
        v[i] = reinterpret(Float64, cles[i] ⊻ 0x8000_0000_0000_0000)
    end
    @inbounds for i in (m + 1):n
        v[i] = NaN
    end
    v
end
