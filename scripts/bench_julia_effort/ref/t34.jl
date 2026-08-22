@inline function mulmod(a::UInt64, b::UInt64, m::UInt64)
    UInt64(mod(widemul(a, b), UInt128(m)))
end

function powmod(a::UInt64, e::UInt64, m::UInt64)
    r = UInt64(1)
    a %= m
    while e > 0
        if (e & 0x1) == 1
            r = mulmod(r, a, m)
        end
        a = mulmod(a, a, m)
        e >>= 1
    end
    r
end

# Jeu de temoins suffisant pour tout n < 3.3e24, donc a fortiori sur 64 bits.
const TEMOINS = UInt64[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]

function isprime64(n::Integer)
    n < 2 && return false
    m = UInt64(n)
    for p in TEMOINS
        m == p && return true
        m % p == 0 && return false
    end
    d = m - 1
    r = 0
    while (d & 0x1) == 0
        d >>= 1
        r += 1
    end
    for a in TEMOINS
        x = powmod(a, d, m)
        (x == 1 || x == m - 1) && continue
        compose = true
        for _ in 1:(r - 1)
            x = mulmod(x, x, m)
            if x == m - 1
                compose = false
                break
            end
        end
        compose && return false
    end
    true
end
