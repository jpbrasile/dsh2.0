using .Sol: dotp
x = rand(10_000); y = rand(10_000)
@assert isapprox(dotp(x, y), sum(x .* y); rtol=1e-10)   "valeur"
@assert dotp(Float64[], Float64[]) == 0.0               "vide"
let a = Float32[1,2,3], b = Float32[4,5,6]
    @assert isapprox(dotp(a, b), 32.0f0; rtol=1e-6)     "Float32"
end
dotp(x, y)                                              # rechauffe la compilation
alloc = @allocated dotp(x, y)
@assert alloc == 0                                      "dotp alloue $alloc octets, il en faut 0"
