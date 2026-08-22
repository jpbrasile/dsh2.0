using .Sol: Grid

n = 10000
a = Grid(collect(1.0:n), 0.0, 0.5)
b = Grid(fill(2.0, n), 0.0, 0.5)

@assert a isa AbstractVector                     "Grid doit se sous-typer AbstractVector"
@assert length(a) == n && a[3] == 3.0            "interface AbstractVector"

r = a .+ 2 .* b
@assert r isa Grid                               "la diffusion doit rendre un Grid, pas un $(typeof(r))"
@assert r.x0 == 0.0 && r.dx == 0.5               "x0 et dx doivent traverser la diffusion"
@assert r[1] == 5.0 && r[n] == n + 4.0           "valeurs fausses"

@assert (a .+ 1.0) isa Grid                      "Grid + scalaire doit rester un Grid"
@assert (a .+ ones(n)) isa Grid                  "Grid + Vector doit rester un Grid"
@assert (a .> 500.0) isa Grid                    "une diffusion booleenne doit rester un Grid"

let c = Grid(fill(1.0, n), 1.0, 0.5), ok = false
    try
        a .+ c
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "x0 different : la diffusion doit lever ArgumentError, pas melanger deux grilles"
end

let c = Grid(fill(1.0, n), 0.0, 0.25), ok = false
    try
        a .+ c
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "dx different : la diffusion doit lever ArgumentError"
end

# fusion : une seule allocation de resultat, pas une chaine de temporaires
let _ = a .+ a .+ a
    al = @allocated (a .+ a .+ a)
    @assert al < 2.2 * 8 * n                     "la diffusion n'est pas fusionnee : $(al) octets pour $(8*n) attendus"
end
