using .Sol: evaluate

@assert evaluate("1+2*3") == 7.0                 "priorite de * sur +"
@assert evaluate("2*3^2") == 18.0                "priorite de ^ sur *"
@assert evaluate("2^3^2") == 512.0               "^ doit associer a DROITE : $(evaluate("2^3^2")) au lieu de 512"
@assert evaluate("-2^2") == -4.0                 "l'unaire - lie MOINS fort que ^ : $(evaluate("-2^2")) au lieu de -4"
@assert evaluate("2-3-4") == -5.0                "- associe a gauche : $(evaluate("2-3-4")) au lieu de -5"
@assert evaluate("8/4/2") == 1.0                 "/ associe a gauche : $(evaluate("8/4/2")) au lieu de 1"
@assert evaluate("(1+2)*(3+4)") == 21.0          "parentheses"
@assert evaluate("10/4") == 2.5                  "division reelle, pas entiere"
@assert evaluate("2*-3") == -6.0                 "unaire juste apres un binaire"
@assert evaluate("-(3+4)") == -7.0               "unaire devant une parenthese"
@assert evaluate("  1 +2 ") == 3.0               "espaces"
@assert evaluate("3.5*2") == 7.0                 "litteral decimal"

for mauvais in ("1+", "(1+2", "1 2", "*3", "1+)", "1+2)", "2 @ 3")
    ok = false
    try
        evaluate(mauvais)
    catch
        ok = true
    end
    @assert ok                                   "l'entree malformee \"$(mauvais)\" doit lever"
end
