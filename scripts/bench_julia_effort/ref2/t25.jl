# Tarjan, mais avec une pile EXPLICITE d'appels : sur une chaine de 200000
# sommets la version recursive depasse la pile systeme. Chaque cadre retient
# le sommet et l'indice de l'arc suivant a explorer.
function sccs(adj::Vector{Vector{Int}})
    n = length(adj)
    indice = zeros(Int, n)
    bas = zeros(Int, n)
    sur_pile = falses(n)
    pile = Int[]
    comps = Vector{Vector{Int}}()

    cadre_v = Int[]
    cadre_e = Int[]
    horloge = 0

    for depart in 1:n
        indice[depart] != 0 && continue
        horloge += 1
        indice[depart] = horloge
        bas[depart] = horloge
        push!(pile, depart)
        sur_pile[depart] = true
        push!(cadre_v, depart)
        push!(cadre_e, 1)

        while !isempty(cadre_v)
            v = cadre_v[end]
            e = cadre_e[end]
            voisins = adj[v]
            if e <= length(voisins)
                cadre_e[end] = e + 1
                w = voisins[e]
                if indice[w] == 0
                    horloge += 1
                    indice[w] = horloge
                    bas[w] = horloge
                    push!(pile, w)
                    sur_pile[w] = true
                    push!(cadre_v, w)
                    push!(cadre_e, 1)
                elseif sur_pile[w]
                    bas[v] = min(bas[v], indice[w])
                end
            else
                if bas[v] == indice[v]
                    comp = Int[]
                    while true
                        w = pop!(pile)
                        sur_pile[w] = false
                        push!(comp, w)
                        w == v && break
                    end
                    push!(comps, comp)
                end
                pop!(cadre_v)
                pop!(cadre_e)
                if !isempty(cadre_v)
                    p = cadre_v[end]
                    bas[p] = min(bas[p], bas[v])
                end
            end
        end
    end

    return comps
end

function condensation(adj::Vector{Vector{Int}})
    comps = sccs(adj)
    n = length(adj)
    m = length(comps)

    comp = zeros(Int, n)
    for k in 1:m
        for v in comps[k]
            comp[v] = k
        end
    end

    dag = [Int[] for _ in 1:m]
    # marque[b] == a signifie "l'arc a->b a deja ete pose" : cela dedoublonne
    # sans allouer un ensemble par composante.
    marque = zeros(Int, m)
    for a in 1:m
        for v in comps[a]
            for w in adj[v]
                b = comp[w]
                if b != a && marque[b] != a
                    marque[b] = a
                    push!(dag[a], b)
                end
            end
        end
    end

    return comp, dag
end
