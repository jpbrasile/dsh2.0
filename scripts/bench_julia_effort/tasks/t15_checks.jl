using .Sol: horner
using Test

@assert horner(2.0, [1.0, 2.0, 3.0]) == 17.0     "valeur"
@assert horner(3, [1, 0, 2]) == 19               "entiers"

let r = horner(2.0f0, Float32[1, 2, 3])
    @assert r isa Float32                        "Float32 doit rendre Float32, pas $(typeof(r))"
end

let r = horner(3, [1, 0, 2])
    @assert r isa Integer                        "entier doit rendre un entier, pas $(typeof(r))"
end

try
    @inferred horner(2.0f0, Float32[1, 2, 3])
catch e
    error("horner n'est pas de type stable : ", sprint(showerror, e))
end
