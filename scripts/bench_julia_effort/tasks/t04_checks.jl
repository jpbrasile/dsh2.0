using .Sol: trapz
@assert isapprox(trapz(sin, 0.0, pi, 100000), 2.0; rtol=1e-6)        "sin sur [0,pi]"
@assert isapprox(trapz(x -> x^2, 0.0, 3.0, 200000), 9.0; rtol=1e-6)  "x^2 sur [0,3]"
@assert isapprox(trapz(x -> 1.0, 2.0, 5.0, 10), 3.0; rtol=1e-12)     "constante"
@assert isapprox(trapz(exp, 0.0, 1.0, 100000), exp(1.0)-1.0; rtol=1e-6) "exp"
# n=1 doit rester le trapeze simple, pas une erreur
@assert isapprox(trapz(x -> x, 0.0, 2.0, 1), 2.0; rtol=1e-12)        "n=1"
