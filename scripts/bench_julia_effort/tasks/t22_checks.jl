using .Sol: rk_adaptive

# 1. exactitude sur une primitive connue
let (ts, ys) = rk_adaptive((t, y) -> cos(t), 0.0, (0.0, 10.0), 1e-9)
    @assert length(ts) == length(ys)             "ts et ys de longueurs differentes"
    @assert ts[1] == 0.0                         "ts[1] doit valoir exactement le debut"
    @assert ts[end] == 10.0                      "ts[end] doit valoir EXACTEMENT la fin : $(ts[end])"
    @assert all(diff(ts) .> 0)                   "ts doit etre strictement croissant"
    @assert abs(ys[end] - sin(10.0)) < 1e-6      "y(10) = $(ys[end]) au lieu de $(sin(10.0))"
end

# 2. exactitude sur une decroissance exponentielle
let (ts, ys) = rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-9)
    @assert abs(ys[end] - exp(-5.0)) / exp(-5.0) < 1e-5  "y(5) = $(ys[end]) au lieu de $(exp(-5.0))"
end

# 3. LE point : le pas doit VRAIMENT s'adapter. Pic etroit en t = 2.
let (ts, _) = rk_adaptive((t, y) -> 1 / ((t - 2)^2 + 1e-3), 0.0, (0.0, 4.0), 1e-8)
    d = diff(ts)
    r = maximum(d) / minimum(d)
    @assert r > 10                               "pas non adaptatif : rapport max/min des pas = $(r), il faut > 10"
end

# 4. et il ne doit pas y arriver en prenant 20000 pas partout
let (ts, _) = rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-6)
    @assert length(ts) < 5000                    "$(length(ts)) pas pour une exponentielle a tol 1e-6 : le pas ne grandit pas"
end

# 5. une tolerance plus lache doit couter moins de pas
let n1 = length(first(rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-10))),
    n2 = length(first(rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-4)))
    @assert n2 < n1                              "tol 1e-4 coute $(n2) pas et tol 1e-10 en coute $(n1) : la tolerance n'agit pas"
end
