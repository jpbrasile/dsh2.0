# Paire emboitee de Dormand-Prince 5(4) : sept etages, dont le septieme est
# reutilise comme premier etage du pas suivant (FSAL). Les deux solutions
# d'ordre 5 et 4 partagent EXACTEMENT les memes evaluations de f ; leur
# difference est l'estimateur d'erreur locale.
function rk_adaptive(f, y0::Float64, tspan::Tuple{Float64,Float64}, tol::Float64)
    t0, tf = tspan
    ts = Float64[t0]
    ys = Float64[y0]
    total = tf - t0
    total <= 0 && return ts, ys

    t = t0
    y = y0
    h = total / 100
    hmin = total * 1e-14

    while t < tf
        clip = false
        if t + h >= tf
            h = tf - t
            clip = true
        end

        k1 = f(t, y)
        k2 = f(t + h / 5, y + h * (k1 / 5))
        k3 = f(t + 3h / 10, y + h * (3k1 / 40 + 9k2 / 40))
        k4 = f(t + 4h / 5, y + h * (44k1 / 45 - 56k2 / 15 + 32k3 / 9))
        k5 = f(t + 8h / 9, y + h * (19372k1 / 6561 - 25360k2 / 2187 + 64448k3 / 6561 - 212k4 / 729))
        k6 = f(t + h, y + h * (9017k1 / 3168 - 355k2 / 33 + 46732k3 / 5247 + 49k4 / 176 - 5103k5 / 18656))
        y5 = y + h * (35k1 / 384 + 500k3 / 1113 + 125k4 / 192 - 2187k5 / 6784 + 11k6 / 84)
        k7 = f(t + h, y5)
        y4 = y + h * (5179k1 / 57600 + 7571k3 / 16695 + 393k4 / 640 - 92097k5 / 339200 + 187k6 / 2100 + k7 / 40)

        err = abs(y5 - y4)
        # erreur PAR UNITE DE TEMPS : la somme des erreurs locales acceptees
        # reste alors de l'ordre de tol sur tout l'intervalle, et pas de
        # tol multiplie par le nombre de pas.
        seuil = tol * (h / total)

        if err <= seuil || h <= hmin
            t = clip ? tf : t + h
            y = y5
            push!(ts, t)
            push!(ys, y)
        end

        fac = err > 0 ? 0.9 * (seuil / err)^0.2 : 5.0
        fac = clamp(fac, 0.2, 5.0)
        h = max(h * fac, hmin)
    end

    return ts, ys
end
