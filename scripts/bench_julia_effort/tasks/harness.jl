# Verificateur commun. ARGS[1] = solution.jl (ecrite par le LLM), ARGS[2] = checks.
# La solution est chargee DANS un module frais : une solution qui redefinit une
# fonction de Base ne doit pas contaminer le verificateur.
# Le verdict tient sur UNE ligne : un showerror multi-ligne avait fait lire
# "in expression starting at ..." comme verdict, et le bras known-BAD avait
# repondu 0/10 alors qu'il attrapait tout.
module Sol end
une_ligne(s) = replace(replace(s, '\r' => ' '), '\n' => " | ")
try
    Base.include(Sol, abspath(ARGS[1]))
catch e
    println("VERDICT FAIL charge: ", une_ligne(sprint(showerror, e)))
    exit(1)
end
try
    Base.include(Main, abspath(ARGS[2]))
    println("VERDICT PASS")
    exit(0)
catch e
    println("VERDICT FAIL check: ", une_ligne(sprint(showerror, e)))
    exit(1)
end
