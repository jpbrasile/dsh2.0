using .Sol: Welford, update!, variance

let w = Welford()
    for x in (1.0, 2.0, 3.0, 4.0); update!(w, x); end
    @assert isapprox(variance(w), 5/3; rtol=1e-12)  "variance simple"
end

let w = Welford()
    @assert variance(w) == 0.0                      "aucune valeur"
    update!(w, 3.0)
    @assert variance(w) == 0.0                      "une seule valeur"
end

let w = Welford()
    for x in (1e8, 1e8 + 1.0, 1e8 + 2.0); update!(w, x); end
    v = variance(w)
    @assert isapprox(v, 1.0; rtol=1e-9)             "annulation catastrophique : variance = $v au lieu de 1.0"
end

@assert !any(t -> t <: AbstractArray, fieldtypes(Welford))  "Welford stocke les valeurs"
