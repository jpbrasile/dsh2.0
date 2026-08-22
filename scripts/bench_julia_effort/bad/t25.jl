function sccs(adj::Vector{Vector{Int}})
    n = length(adj)
    index = fill(0, n)
    bas = fill(0, n)
    surpile = falses(n)
    pile = Int[]
    res = Vector{Vector{Int}}()
    cpt = 0
    appels = Tuple{Int,Int}[]
    for r in 1:n
        index[r] != 0 && continue
        cpt += 1
        index[r] = cpt
        bas[r] = cpt
        push!(pile, r)
        surpile[r] = true
        empty!(appels)
        push!(appels, (r, 1))
        while !isempty(appels)
            v, k = appels[end]
            if k <= length(adj[v])
                appels[end] = (v, k + 1)
                w = adj[v][k]
                if index[w] == 0
                    cpt += 1
                    index[w] = cpt
                    bas[w] = cpt
                    push!(pile, w)
                    surpile[w] = true
                    push!(appels, (w, 1))
                elseif surpile[w]
                    bas[v] = min(bas[v], index[w])
                end
            else
                pop!(appels)
                if !isempty(appels)
                    p = appels[end][1]
                    bas[p] = min(bas[p], bas[v])
                end
                if bas[v] == index[v]
                    comp = Int[]
                    while true
                        w = pop!(pile)
                        surpile[w] = false
                        push!(comp, w)
                        w == v && break
                    end
                    push!(res, comp)
                end
            end
        end
    end
    res
end

function condensation(adj::Vector{Vector{Int}})
    cs = sccs(adj)
    n = length(adj)
    comp = fill(0, n)
    for (ci, c) in enumerate(cs), v in c
        comp[v] = ci
    end
    ens = [Set{Int}() for _ in 1:length(cs)]
    # BAD: les arcs INTERNES a une composante ne sont pas filtres. La
    # condensation gagne une auto-boucle par composante non triviale -- et
    # cesse d'etre un DAG, ce qui est toute sa raison d'etre.
    for v in 1:n, w in adj[v]
        push!(ens[comp[v]], comp[w])
    end
    (comp, [sort!(collect(s)) for s in ens])
end
