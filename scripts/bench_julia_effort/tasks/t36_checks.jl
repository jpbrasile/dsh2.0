using .Sol: PVec, plength, ppush, pget, pset

let v = PVec()
    @assert plength(v) == 0                      "le vecteur vide a une longueur nulle"
    for k in 1:1000
        v = ppush(v, k)
    end
    @assert plength(v) == 1000                   "longueur apres 1000 ajouts"
    @assert pget(v, 1) == 1 && pget(v, 33) == 33 && pget(v, 1000) == 1000  "lecture : franchissement de noeud rate"
    @assert all(pget(v, k) == k for k in 1:1000) "lecture sur les 1000"
end

# persistance : l'ancienne version ne bouge pas
let a = PVec()
    for k in 1:100
        a = ppush(a, k)
    end
    b = ppush(a, 999)
    c = pset(a, 50, -1)
    @assert plength(a) == 100 && plength(b) == 101 "ppush ne doit pas modifier la version d'origine"
    @assert pget(a, 50) == 50                      "pset a modifie la version d'origine"
    @assert pget(c, 50) == -1                      "pset n'a pas pris effet sur la nouvelle version"
    @assert pget(c, 51) == 51                      "pset a touche un voisin"
    @assert plength(c) == 100                      "pset ne change pas la longueur"
end

let v = PVec()
    for k in 1:10
        v = ppush(v, k)
    end
    for mauvais in (0, 11, -1)
        ok = false
        try
            pget(v, mauvais)
        catch e
            ok = isa(e, BoundsError)
        end
        @assert ok                               "pget($(mauvais)) doit lever BoundsError"
    end
end

# profondeur : plusieurs niveaux d'arbre
let v = PVec()
    for k in 1:100000
        v = ppush(v, k)
    end
    @assert plength(v) == 100000                 "100000 elements"
    @assert all(pget(v, k) == k for k in (1, 32, 33, 1024, 1025, 32768, 99999, 100000))  "lecture en profondeur"
end

# LE test : garder toutes les versions doit coder le PARTAGE, pas la copie
let versions = Vector{Any}(undef, 10000), v = PVec()
    for k in 1:10000
        v = ppush(v, k)
        versions[k] = v
    end
    taille = Base.summarysize(versions)
    @assert taille < 80_000_000                  "aucun partage de structure : 10000 versions pesent $(round(taille/1e6, digits=1)) Mo ; la recopie en couterait ~400, le partage quelques dizaines"
    @assert pget(versions[1], 1) == 1            "la premiere version doit rester lisible"
    @assert plength(versions[5000]) == 5000      "chaque version garde sa propre longueur"
end
