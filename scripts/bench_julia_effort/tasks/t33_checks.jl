using .Sol: fsort!

meme(a, b) = length(a) == length(b) && all(isequal(a[i], b[i]) for i in eachindex(a))

let v = [3.0, -1.0, 2.5, -7.25, 0.0, 10.0, -3.5]
    @assert meme(fsort!(copy(v)), sort(v))       "les negatifs sortent a l'envers : $(fsort!(copy(v)))"
end

let v = [0.0, -0.0, 0.0, -0.0]
    @assert meme(fsort!(copy(v)), sort(v))       "-0.0 doit preceder +0.0 (isless(-0.0, 0.0) est vrai)"
end

let v = [1.0, Inf, -Inf, 0.0, -0.0, 5e-324, -5e-324, 2.2250738585072014e-308]
    @assert meme(fsort!(copy(v)), sort(v))       "infinis et sous-normaux"
end

let v = [1.0, NaN, -1.0, NaN, 0.0]
    r = fsort!(copy(v))
    @assert meme(r[1:3], [-1.0, 0.0, 1.0])       "partie non-NaN mal triee : $(r[1:3])"
    @assert all(isnan, r[4:5])                   "les NaN doivent finir a la fin, apres +Inf"
end

let v = [-1.0, NaN, -Inf, Inf]
    r = fsort!(copy(v))
    @assert isequal(r[1], -Inf) && isequal(r[2], -1.0) && isequal(r[3], Inf) && isnan(r[4])  "NaN apres +Inf"
end

let v = fill(4.0, 100)
    @assert meme(fsort!(copy(v)), v)             "tableau constant"
end

@assert meme(fsort!(Float64[]), Float64[])       "tableau vide"
@assert meme(fsort!([2.0]), [2.0])               "tableau a un element"

let v = [(-1.0)^i * (i^3 / 7.0) for i in 1:200000]
    @assert meme(fsort!(copy(v)), sort(v))       "200000 valeurs des deux signes"
end

let v = fsort!([3.0, 1.0, 2.0])
    @assert v == [1.0, 2.0, 3.0]                 "fsort! doit trier EN PLACE et rendre le tableau"
end
