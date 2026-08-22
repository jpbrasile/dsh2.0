using .Sol: Interval
using Random
Random.seed!(20260822)
a = Interval(1.0, 2.0); b = Interval(3.0, 5.0)
s = a + b; p = a * b
@assert s.lo <= 4.0 && s.hi >= 7.0                   "somme englobe"
@assert p.lo <= 3.0 && p.hi >= 10.0                  "produit englobe"
# le produit doit gerer les signes : [-2,1] * [-3,4] contient -8 et 6
q = Interval(-2.0, 1.0) * Interval(-3.0, 4.0)
@assert q.lo <= -8.0 && q.hi >= 6.0                  "produit signe : got [$(q.lo), $(q.hi)]"
# containment echantillonne
for _ in 1:2000
    l1, l2 = rand()*4-2, rand()*4-2; i1 = Interval(min(l1,l2), max(l1,l2))
    l3, l4 = rand()*4-2, rand()*4-2; i2 = Interval(min(l3,l4), max(l3,l4))
    x = i1.lo + rand()*(i1.hi-i1.lo); y = i2.lo + rand()*(i2.hi-i2.lo)
    ss = i1 + i2; pp = i1 * i2
    @assert ss.lo <= x+y <= ss.hi                    "somme ne contient pas"
    @assert pp.lo <= x*y <= pp.hi                    "produit ne contient pas"
end
# promotion : Interval{Int} + Interval{Float64} doit marcher
z = Interval(1, 2) + Interval(0.5, 0.5)
@assert z.lo <= 1.5 && z.hi >= 2.5                   "promotion"
