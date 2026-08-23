# Session Julia persistante de la porte de tests.
#
#   julia --project=<framework> serveur.jl --port 8077
#   (lance par porte.py avec JULIA_LOAD_PATH = <framework>;<ici>/env;@stdlib)
#
# Charge Revise puis le paquet une fois (10 s tiede, mesure 2026-08-23), puis
# attend sur 127.0.0.1:<port> des lignes JSON :
#   {"ping": true}                       -> {"pong": true, "paquet": "...", "charge_s": ..., "projet": "<dossier --project>"}
#   {"fichier": "C:/.../test_x.jl"}      -> {"fichier", "passes", "echecs", "erreurs",
#                                            "casses", "s", "etat", "sortie_fin"}
#   {"arret": true}                      -> fin du processus
# Chaque fichier est inclus dans un Module NEUF (pas d etat entre deux rejeux ;
# les tests qui font `if !@isdefined(Physics) include(...)` rechargent donc
# vraiment leurs sources). Revise.revise() est appele avant chaque rejeu pour
# que les sources du PAQUET modifiees soient prises en compte.
# etat : "ok" | "echec" (au moins un @test faux) | "erreur" (le fichier n a pas
# pu etre execute jusqu au bout) . Les comptes viennent de Test lui-meme.

using Sockets, Test, JSON

const t_depart = time()
using Revise
const PAQUET = "PlasmaDigitalTwin"
Core.eval(Main, Meta.parse("using $PAQUET"))
const CHARGE_S = round(time() - t_depart; digits = 1)

port = 8077
journaux = tempdir()
for (i, a) in enumerate(ARGS)
    a == "--port" && (global port = parse(Int, ARGS[i + 1]))
    a == "--journaux" && (global journaux = ARGS[i + 1])
end
mkpath(journaux)

compteur = 0

"""Remplace le symbole `Main` par le module `m` dans une expression lue d un fichier
de test : `Main.X` -> `m.X`, `isdefined(Main, :X)` -> `isdefined(m, :X)`.
Les QuoteNode (symboles litteraux) ne sont pas touches."""
function remplacer_main(ex, m::Module)
    ex === :Main && return m
    ex isa Expr || return ex
    return Expr(ex.head, (remplacer_main(a, m) for a in ex.args)...)
end

function comptes(ts)
    c = Test.get_test_counts(ts)
    if c isa Tuple
        p, f, e, b = c[1], c[2], c[3], c[4]
        if length(c) >= 8
            p += c[5]; f += c[6]; e += c[7]; b += c[8]
        end
        return p, f, e, b
    end
    # Julia >= 1.11 : structure TestCounts
    p = c.passes + c.cumulative_passes
    f = c.fails + c.cumulative_fails
    e = c.errors + c.cumulative_errors
    b = c.broken + c.cumulative_broken
    return p, f, e, b
end

function rejouer(fichier::String)
    global compteur += 1
    t0 = time()
    try
        Revise.revise()
    catch e
        # une erreur de Revise (fichier source invalide) est une vraie erreur : on la remonte
        return Dict("fichier" => fichier, "passes" => 0, "echecs" => 0, "erreurs" => 1,
                    "casses" => 0, "s" => round(time() - t0; digits = 1), "etat" => "erreur",
                    "sortie_fin" => "Revise: " * sprint(showerror, e))
    end
    m = Module(Symbol("Porte", compteur))
    Core.eval(m, :(using Test))
    # Le module neuf joue le role de Main : `Main.X` et `isdefined(Main, :X)` ecrits en dur
    # dans les tests (14 fichiers) doivent viser les copies incluses par le test, pas le
    # paquet charge dans le vrai Main (sinon faux ROUGE : MethodError entre deux copies
    # du meme module, vu sur electrical_model le 23/08).
    Core.eval(m, :(include(f::AbstractString) = Base.include(ex -> Main.remplacer_main(ex, $m), $m, f)))
    Core.eval(m, :(include(mapexpr::Function, f::AbstractString) = Base.include(ex -> mapexpr(Main.remplacer_main(ex, $m)), $m, f)))
    Core.eval(m, :(eval(x) = Core.eval($m, x)))
    ts = Test.DefaultTestSet("porte")
    journal = joinpath(journaux, "rejeu_$(compteur)_$(basename(dirname(fichier)))_$(basename(fichier)).log")
    etat = "ok"
    msg = ""
    Test.push_testset(ts)
    try
        redirect_stdio(stdout = journal, stderr = journal) do
            cd(dirname(fichier)) do
                Base.include(ex -> remplacer_main(ex, m), m, fichier)
            end
        end
    catch e
        etat = "erreur"
        msg = sprint(showerror, e)
        msg = length(msg) > 600 ? msg[1:600] : msg
    finally
        Test.pop_testset()
    end
    p, f, e, b = comptes(ts)
    if etat == "ok" && (f > 0 || e > 0)
        etat = "echec"
    end
    sortie = isfile(journal) ? read(journal, String) : ""
    fin = length(sortie) > 1500 ? sortie[end-1500+1:end] : sortie
    etat == "ok" && isfile(journal) && rm(journal; force = true)  # on ne garde que les journaux non verts
    return Dict("fichier" => fichier, "passes" => p, "echecs" => f, "erreurs" => e,
                "casses" => b, "s" => round(time() - t0; digits = 1), "etat" => etat,
                "journal" => (etat == "ok" ? "" : journal),
                "sortie_fin" => (etat == "ok" ? "" : msg * "\n" * fin))
end

serveur = listen(ip"127.0.0.1", port)
println("porte prete sur 127.0.0.1:$port ($PAQUET charge en $(CHARGE_S)s)")
flush(stdout)
while true
    sock = accept(serveur)
    try
        while isopen(sock)
            ligne = readline(sock)
            isempty(ligne) && break
            req = JSON.parse(ligne)
            if get(req, "arret", false)
                println(sock, JSON.json(Dict("arret" => true)))
                close(sock)
                exit(0)
            elseif get(req, "ping", false)
                # "projet" : le dossier --project reellement charge ; porte.py le compare a --repo et
                # relance si ce n est pas le meme (sinon un serveur lance sur le vrai depot
                # validerait en silence un fichier de la copie avec le Physics du vrai depot)
                println(sock, JSON.json(Dict("pong" => true, "paquet" => PAQUET, "charge_s" => CHARGE_S,
                                             "julia" => string(VERSION), "rejeux" => compteur,
                                             "projet" => replace(dirname(Base.active_project()), "\\" => "/"))))
            elseif haskey(req, "fichier")
                println(sock, JSON.json(rejouer(String(req["fichier"]))))
            else
                println(sock, JSON.json(Dict("erreur" => "requete inconnue")))
            end
            flush(sock)
        end
    catch e
        e isa EOFError || @warn "connexion" exception = e
    finally
        close(sock)
    end
end
