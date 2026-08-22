using .Sol: Iv, contient

@assert contient(Iv(1.0, 2.0), 1.5)              "contient"
@assert !contient(Iv(1.0, 2.0), 2.5)             "contient : hors bornes"

let ok = false
    try
        Iv(2.0, 1.0)
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "lo > hi doit lever ArgumentError"
end

# arrondi vers l'exterieur : le resultat exact n'est PAS representable
let s = Iv(0.1, 0.1) + Iv(0.2, 0.2)
    @assert s.lo < 0.1 + 0.2 < s.hi              "les bornes ne sont pas elargies vers l'exterieur : [$(s.lo), $(s.hi)]"
end

# le piege du produit : quatre coins, pas deux
let p = Iv(-2.0, 3.0) * Iv(-5.0, 7.0)
    @assert p.lo <= -15.0                        "produit sur deux coins au lieu de quatre : lo = $(p.lo), il faut <= -15"
    @assert p.hi >= 21.0                         "produit sur deux coins au lieu de quatre : hi = $(p.hi), il faut >= 21"
end

let p = Iv(-3.0, -1.0) * Iv(-4.0, -2.0)
    @assert p.lo <= 2.0 && p.hi >= 12.0          "produit de deux intervalles negatifs : [$(p.lo), $(p.hi)], il faut contenir [2, 12]"
end

let p = Iv(-1.0, 1.0) * Iv(-1.0, 1.0)
    @assert p.lo <= -1.0 && p.hi >= 1.0          "produit de deux intervalles a cheval sur zero"
end

# confinement, teste sur des points reels des intervalles
let a = Iv(-2.0, 3.0), b = Iv(-5.0, 7.0)
    s, d, p = a + b, a - b, a * b
    for i in 0:40, j in 0:40
        x = a.lo + (a.hi - a.lo) * i / 40
        y = b.lo + (b.hi - b.lo) * j / 40
        @assert contient(s, x + y)               "x+y = $(x+y) sort de la somme"
        @assert contient(d, x - y)               "x-y = $(x-y) sort de la difference"
        @assert contient(p, x * y)               "x*y = $(x*y) sort du produit [$(p.lo), $(p.hi)]"
    end
end

# la dependance : a - a contient zero et n'est PAS reduit a zero
let d = Iv(1.0, 2.0) - Iv(1.0, 2.0)
    @assert contient(d, 0.0)                     "a - a doit contenir zero"
    @assert d.lo <= -1.0 && d.hi >= 1.0          "a - a vaut [-1, 1] : les deux occurrences sont independantes"
end

let ok = false
    try
        Iv(1.0, 2.0) / Iv(-1.0, 1.0)
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "diviser par un intervalle contenant zero doit lever"
end

let q = Iv(1.0, 2.0) / Iv(2.0, 4.0)
    @assert q.lo <= 0.25 && q.hi >= 1.0          "quotient : [$(q.lo), $(q.hi)] doit contenir [0.25, 1]"
end
