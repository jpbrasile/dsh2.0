using .Sol: isprime64

@assert !isprime64(0) && !isprime64(1) && !isprime64(-7)  "0, 1 et les negatifs ne sont pas premiers"
@assert isprime64(2) && isprime64(3) && isprime64(5)      "les premiers de base"
@assert !isprime64(4) && !isprime64(9) && !isprime64(1)   "les carres ne sont pas premiers"

let petits = [n for n in 2:2000 if isprime64(n)],
    crible = [n for n in 2:2000 if all(n % d != 0 for d in 2:isqrt(n))]
    @assert petits == crible                              "desaccord avec un crible sur [2, 2000] : $(length(petits)) contre $(length(crible))"
end

# nombres de Carmichael : composes, mais pseudo-premiers de Fermat pour presque
# toute base -- un test de Fermat les rate tous
@assert !isprime64(561) && !isprime64(1105) && !isprime64(1729) && !isprime64(2465)  "un nombre de Carmichael est COMPOSE (test de Fermat au lieu de Miller-Rabin ?)"

@assert !isprime64(2047)                                  "2047 = 23*89 est pseudo-premier fort en base 2"
@assert !isprime64(1373653)                               "1373653 est pseudo-premier fort en bases 2 et 3"
@assert !isprime64(25326001)                              "25326001 est pseudo-premier fort en bases 2, 3 et 5"

let n = 3215031751
    @assert !isprime64(n)                                 "jeu de temoins tronque : $(n) = 151*751*28351 est pseudo-premier fort en bases 2, 3, 5 ET 7"
end

@assert isprime64(1000000007)                             "1000000007 est premier"
@assert isprime64(999999999989)                           "999999999989 est premier"
@assert isprime64(2305843009213693951)                    "2^61-1 est premier -- et la multiplication modulaire y deborde si elle est faite sur 64 bits"
@assert !isprime64(4611686014132420609)                   "(2^31-1)^2 est compose -- meme piege de debordement"
@assert !isprime64(2305843009213693949)                   "2^61-3 est compose"
