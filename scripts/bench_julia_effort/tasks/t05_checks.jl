using .Sol: Poly
p = Poly([1.0, 2.0, 3.0])      # 1 + 2x + 3x^2
q = Poly([0.0, 1.0])           # x
@assert p(0.0) == 1.0                       "p(0)"
@assert p(1.0) == 6.0                       "p(1)"
@assert p(2.0) == 17.0                      "p(2)"
r = p + q
@assert r(2.0) == 19.0                      "(p+q)(2)"
s = p * q
@assert isapprox(s(2.0), 34.0)              "(p*q)(2)"
@assert isapprox(s(3.0), p(3.0)*q(3.0))     "produit coherent en 3"
t = q * q
@assert isapprox(t(4.0), 16.0)              "x^2 en 4"
