# Deux points decident de la justesse :
#  1. LE JEU DE BASES. Les douze premiers nombres premiers sont demontres
#     suffisants pour tout n < 3.317e24, donc a fortiori sur tout 2^63. Un jeu
#     court (2,3,5,7) passe tous les petits tests puis declare premier
#     3215031751 = 151*751*28351, pseudo-premier fort a ces quatre bases.
#  2. LA MULTIPLICATION MODULAIRE. Elever au carre un residu proche de 2^62
#     deborde UInt64 en silence. On passe donc par UInt128, largeur ou le
#     produit de deux entiers de 64 bits ne peut pas deborder.
const _BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)

@inline _mulmod(a::UInt64, b::UInt64, m::UInt64) =
    UInt64((UInt128(a) * UInt128(b)) % UInt128(m))

function _powmod(a::UInt64, e::UInt64, m::UInt64)
    r = UInt64(1)
    b = a % m
    while e > 0
        if (e & 0x1) == 0x1
            r = _mulmod(r, b, m)
        end
        b = _mulmod(b, b, m)
        e >>= 1
    end
    return r
end

function isprime64(n::Integer)
    n < 2 && return false
    for p in _BASES
        n == p && return true
        n % p == 0 && return false
    end

    m = UInt64(n)
    d = m - UInt64(1)
    r = 0
    while (d & 0x1) == 0x0
        d >>= 1
        r += 1
    end

    for a in _BASES
        x = _powmod(UInt64(a), d, m)
        (x == UInt64(1) || x == m - UInt64(1)) && continue
        temoin = true
        for _ in 1:(r - 1)
            x = _mulmod(x, x, m)
            if x == m - UInt64(1)
                temoin = false
                break
            end
        end
        temoin && return false
    end
    return true
end
