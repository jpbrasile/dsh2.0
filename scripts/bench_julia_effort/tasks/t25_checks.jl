using .Sol: sccs, condensation

tri(cs) = sort([sort(c) for c in cs])

adj = [[2], [3], [1, 4], [5], [4, 6], Int[]]
@assert tri(sccs(adj)) == [[1, 2, 3], [4, 5], [6]]   "composantes fausses : $(tri(sccs(adj)))"

@assert tri(sccs([[2, 3], [4], [4], Int[]])) == [[1], [2], [3], [4]]  "un DAG n'a que des singletons"
@assert tri(sccs([[2], [3], [1]])) == [[1, 2, 3]]    "cycle simple"
@assert tri(sccs([Int[], Int[]])) == [[1], [2]]      "graphe sans arc"

@assert sort(vcat(sccs(adj)...)) == collect(1:6)     "les composantes ne partitionnent pas les sommets"

let (comp, d) = condensation(adj)
    @assert length(comp) == 6                        "comp doit couvrir tous les sommets"
    @assert length(d) == length(sccs(adj))           "dag doit avoir un noeud par composante"
    for (a, vs) in enumerate(d)
        @assert !(a in vs)                           "auto-boucle sur la composante $(a) : les arcs internes ne sont pas filtres"
        @assert length(vs) == length(unique(vs))     "arc duplique depuis la composante $(a)"
    end
    m = length(d)
    deg = fill(0, m)
    for vs in d, b in vs
        deg[b] += 1
    end
    f = [i for i in 1:m if deg[i] == 0]
    vus = 0
    while !isempty(f)
        a = pop!(f)
        vus += 1
        for b in d[a]
            deg[b] -= 1
            deg[b] == 0 && push!(f, b)
        end
    end
    @assert vus == m                                 "la condensation contient un cycle : ce n'est pas un DAG"
end

let n = 200000, chaine = [i < n ? [i + 1] : Int[] for i in 1:n]
    @assert length(sccs(chaine)) == n                "chaine de $(n) sommets : $(length(sccs(chaine))) composantes au lieu de $(n)"
end

let n = 200000, grand = [[i % n + 1] for i in 1:n]
    @assert length(sccs(grand)) == 1                 "grand cycle : une seule composante attendue"
end
