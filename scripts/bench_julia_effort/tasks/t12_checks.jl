using .Sol: axpy!

let y = [1.0, 2.0, 3.0], x = [10.0, 20.0, 30.0]
    r = axpy!(y, 2.0, x)
    @assert y == [21.0, 42.0, 63.0]   "axpy! doit ecrire DANS y, y vaut $y"
    @assert r === y                   "axpy! doit rendre y lui-meme"
end

let y = Float32[1, 2], x = Float32[3, 4]
    axpy!(y, 2.0f0, x)
    @assert y == Float32[7, 10]       "Float32"
end

let Y = zeros(200), X = ones(200)
    axpy!(view(Y, 1:100), 3.0, view(X, 51:150))
    @assert all(Y[1:100] .== 3.0) && all(Y[101:200] .== 0.0)  "vues"
end

let y = rand(1000), x = rand(1000)
    axpy!(y, 1.5, x)                  # rechauffe la compilation
    a = @allocated axpy!(y, 1.5, x)
    @assert a == 0                    "axpy! alloue $a octets, il en faut 0"
end
