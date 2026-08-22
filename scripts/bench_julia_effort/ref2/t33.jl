const _SIGNE = 0x8000000000000000

# Motif binaire -> cle non signee dont l'ordre naturel EST celui de isless.
#  - flottant positif : le motif croit deja avec la valeur, il suffit de
#    basculer le bit de signe pour le placer au-dessus des negatifs ;
#  - flottant negatif : exposant et mantisse courent A L'ENVERS par rapport a
#    la valeur, donc il faut inverser TOUT le motif. Ne basculer que le bit
#    de signe laisserait les negatifs tries a l'envers.
# -0.0 donne alors 0x7fff... et +0.0 donne 0x8000..., donc -0.0 passe bien
# avant +0.0, comme l'exige isless.
@inline _cle(x::Float64) = (u = reinterpret(UInt64, x); (u & _SIGNE) != 0 ? ~u : u | _SIGNE)
@inline _decle(k::UInt64) = reinterpret(Float64, (k & _SIGNE) != 0 ? xor(k, _SIGNE) : ~k)

function fsort!(v::Vector{Float64})
    n = length(v)
    n <= 1 && return v

    # Les NaN ne sont PAS ordonnes par le motif : un NaN de signe negatif a le
    # bit de signe a 1 et retomberait tout au debut. On les met de cote, on
    # trie le reste, ils reviennent a la fin.
    j = 0
    for i in 1:n
        if !isnan(v[i])
            j += 1
            v[j], v[i] = v[i], v[j]
        end
    end
    m = j
    m <= 1 && return v

    src = Vector{UInt64}(undef, m)
    dst = Vector{UInt64}(undef, m)
    @inbounds for i in 1:m
        src[i] = _cle(v[i])
    end

    cnt = Vector{Int}(undef, 256)
    for p in 0:7
        dec = 8 * p
        fill!(cnt, 0)
        @inbounds for i in 1:m
            cnt[Int((src[i] >> dec) & 0xff)+1] += 1
        end
        tot = 0
        @inbounds for d in 1:256
            c = cnt[d]
            cnt[d] = tot
            tot += c
        end
        @inbounds for i in 1:m
            d = Int((src[i] >> dec) & 0xff) + 1
            cnt[d] += 1
            dst[cnt[d]] = src[i]
        end
        src, dst = dst, src
    end

    @inbounds for i in 1:m
        v[i] = _decle(src[i])
    end
    return v
end
