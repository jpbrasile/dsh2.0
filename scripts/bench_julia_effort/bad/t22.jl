# BAD: RK4 a pas FIXE. Precis, mais le pas ne s'adapte jamais -- sur un
# probleme a pic il gaspille partout et rate le pic.
function rk_adaptive(f, y0::Float64, tspan::Tuple{Float64,Float64}, tol::Float64)
    t0, tf = tspan
    n = 20000
    h = (tf - t0) / n
    ts = Vector{Float64}(undef, n + 1)
    ys = Vector{Float64}(undef, n + 1)
    ts[1] = t0
    ys[1] = y0
    t = t0
    y = y0
    for i in 1:n
        k1 = f(t, y)
        k2 = f(t + h / 2, y + h * k1 / 2)
        k3 = f(t + h / 2, y + h * k2 / 2)
        k4 = f(t + h, y + h * k3)
        y += h * (k1 + 2k2 + 2k3 + k4) / 6
        t += h
        ts[i + 1] = t
        ys[i + 1] = y
    end
    ts[end] = tf
    (ts, ys)
end
