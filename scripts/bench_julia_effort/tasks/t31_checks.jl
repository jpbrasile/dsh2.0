using .Sol: derivative

@assert derivative(x -> x^2, 3.0) ≈ 6.0                  "derivee de x^2"
@assert derivative(sin, 0.0) ≈ 1.0                       "derivee de sin en 0"
@assert derivative(x -> exp(2x), 0.0) ≈ 2.0              "regle de composition"
@assert derivative(x -> log(x), 2.0) ≈ 0.5               "derivee de log"
@assert derivative(x -> 1 / x, 2.0) ≈ -0.25              "derivee de 1/x"
@assert derivative(x -> x < 0 ? -x : x, 2.0) ≈ 1.0       "le dual doit se comparer, pour que f puisse brancher"

# derivee seconde par imbrication
@assert derivative(x -> derivative(sin, x), 1.0) ≈ -sin(1.0)  "derivee seconde de sin : $(derivative(x -> derivative(sin, x), 1.0)) au lieu de $(-sin(1.0))"
@assert derivative(x -> derivative(y -> y^3, x), 2.0) ≈ 12.0  "derivee seconde de y^3 en 2"

# LE test : confusion de perturbation
let r = derivative(x -> x * derivative(y -> x + y, 1.0), 1.0)
    @assert r ≈ 1.0                                      "confusion de perturbation : $(r) au lieu de 1.0 -- la derivation interne ramasse la perturbation externe"
end

let r = derivative(x -> derivative(y -> x * y, 2.0), 3.0)
    @assert r ≈ 1.0                                      "confusion de perturbation (produit) : $(r) au lieu de 1.0"
end

# une fonction constante en x a bien une derivee nulle
@assert derivative(x -> 7.0, 3.0) ≈ 0.0                  "derivee d'une constante"
