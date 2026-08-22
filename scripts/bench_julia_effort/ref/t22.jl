# Paire encastree de Bogacki-Shampine 3(2), quatre etages, FSAL.
function rk_adaptive(f, y0::Float64, tspan::Tuple{Float64,Float64}, tol::Float64)
    t0, tf = tspan
    ts = [t0]
    ys = [y0]
    t = t0
    y = y0
    h = (tf - t0) / 100
    k1 = f(t, y)
    while t < tf
        h = min(h, tf - t)
        k2 = f(t + h / 2, y + h * k1 / 2)
        k3 = f(t + 3h / 4, y + 3h * k2 / 4)
        y3 = y + h * (2 * k1 + 3 * k2 + 4 * k3) / 9
        k4 = f(t + h, y3)
        y2 = y + h * (7 * k1 / 24 + k2 / 4 + k3 / 3 + k4 / 8)
        err = abs(y3 - y2)
        seuil = tol * (1 + abs(y))
        if err <= seuil || h <= 1e-14 * max(1.0, abs(t))
            t += h
            y = y3
            k1 = k4                       # FSAL
            push!(ts, t)
            push!(ys, y)
        end
        fac = err == 0 ? 5.0 : 0.9 * (seuil / err)^(1 / 3)
        h *= clamp(fac, 0.2, 5.0)
    end
    ts[end] = tf
    (ts, ys)
end
