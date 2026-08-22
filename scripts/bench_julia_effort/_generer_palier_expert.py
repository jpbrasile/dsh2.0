# -*- coding: utf-8 -*-
"""Ecrit le palier EXPERT du corpus : t21..t26, enonces + verificateurs + bras
known-GOOD et known-BAD.

Ce palier repond a une demande precise : des taches assez complexes pour passer
par une PHASE DE PLANIFICATION, courues avec et sans recherche web prealable.

Il est donc construit sur DEUX axes, pas un :

  planification  chaque tache a plusieurs composants qui doivent etre decides
                 avant d'etre ecrits (un lexeur ET un analyseur ET un
                 evaluateur ; un stockage ET une interface ET un produit).

  faits externes certaines taches dependent d'un fait VERIFIABLE hors du modele
                 -- l'ordre des octets d'un format, la semantique exacte d'une
                 API, les coefficients d'un schema numerique. C'est la que la
                 recherche web peut aider. Les autres n'en dependent pas du
                 tout, et servent de TEMOIN : si le bras "avec web" les ameliore
                 elles aussi, ce n'est pas la recherche qui agit, c'est le
                 contexte supplementaire.

  tache  planification  fait externe  ce qui separe
  t21    stockage + interface + produit   non    l et u ne sont pas symetriques
  t22    schema + controle de pas         OUI    un tableau faux = precision fausse
  t23    lexeur + analyseur + evaluateur  NON    associativite de ^ et de l'unaire
  t24    dispatch sur 18 octets de tete   OUI    gros-boutiste, et le format le dit
  t25    parcours iteratif + condensation NON    200000 sommets en chaine
  t26    contrat a cinq arguments         OUI    beta=0 n'ecrit pas, il ECRASE

Deux taches SANS fait externe (t23, t25) : ce sont elles qui rendent le bras web
interpretable. Sans elles, "le web aide" serait indistinguable de "un prompt plus
long aide".

Mesure prealable qui justifie le protocole : sur 91 sessions du banc, 10 395
appels d'outils (write 6308, pwsh 2429, edit 1057, read 597, glob 4) et ZERO
appel a `web_search` ou `web_fetch`, alors que les deux outils etaient declares
au modele dans chaque run. Laisse seul, ce modele ne cherche jamais. Le bras
"avec web" doit donc etre une INSTRUCTION EXPLICITE, sinon les deux bras sont le
meme bras.

Chaque bras known-BAD porte UN defaut nomme, et c'est l'assertion qui le nomme
qui doit tomber. Un verificateur casse attrape 6/6 lui aussi ; ce qui distingue
les deux, c'est PAR QUOI chacun tombe.
"""
import io
import os

BASE = os.path.dirname(os.path.abspath(__file__))

ENTETE = ("Write a Julia solution and save it as the file `solution.jl` in the "
          "current working directory.\n\n")
REGLES = """
Rules:
- `solution.jl` must define EXACTLY the names listed above, with those exact spellings.
- Use only Julia Base and standard libraries (LinearAlgebra, Random are allowed). Do NOT add packages.
- Do not print anything at top level and do not write tests in the file.
- Write the file with your tools. When it is written, reply with the single word DONE.
"""

T = {}

# ---------------------------------------------------------------- t21 Banded
T["t21"] = dict(
    externe=False,
    enonce="""Define `struct Banded{T} <: AbstractMatrix{T}`, a square n-by-n matrix holding
only `l` sub-diagonals and `u` super-diagonals. Provide the constructors
`Banded{T}(n::Int, l::Int, u::Int)` returning an all-zero matrix and `Banded(n, l, u)`
defaulting to `T = Float64`.

The storage must NOT be a dense n-by-n array: memory must grow like `n*(l+u+1)`, not `n^2`.

Implement `Base.size`, `Base.getindex` and `Base.setindex!` so that:
- reading an entry OUTSIDE the band returns `zero(T)` -- that is not an error;
- writing a NON-ZERO value outside the band throws an `ArgumentError`;
- writing zero outside the band is allowed and does nothing.

Also implement `LinearAlgebra.mul!(y::AbstractVector, A::Banded, x::AbstractVector)`
computing `y .= A*x`. Once compiled it must allocate NOTHING, and it must touch only
the stored band -- never the full n-by-n.

Beware: `l` counts diagonals BELOW the main one and `u` counts diagonals ABOVE it.
They are not interchangeable.""",
    ref="""using LinearAlgebra

struct Banded{T} <: AbstractMatrix{T}
    n::Int
    l::Int
    u::Int
    data::Matrix{T}     # (l+u+1) x n ; data[i-j+u+1, j] == A[i,j]
end

Banded{T}(n::Int, l::Int, u::Int) where {T} = Banded{T}(n, l, u, zeros(T, l + u + 1, n))
Banded(n::Int, l::Int, u::Int) = Banded{Float64}(n, l, u)

Base.size(A::Banded) = (A.n, A.n)

@inline dans_bande(A::Banded, i::Int, j::Int) = (-A.u <= i - j <= A.l)

function Base.getindex(A::Banded{T}, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    dans_bande(A, i, j) ? A.data[i - j + A.u + 1, j] : zero(T)
end

function Base.setindex!(A::Banded{T}, v, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    if dans_bande(A, i, j)
        A.data[i - j + A.u + 1, j] = v
    elseif !iszero(v)
        throw(ArgumentError("ecriture non nulle hors bande"))
    end
    v
end

function LinearAlgebra.mul!(y::AbstractVector, A::Banded, x::AbstractVector)
    fill!(y, zero(eltype(y)))
    @inbounds for j in 1:A.n
        xj = x[j]
        for i in max(1, j - A.u):min(A.n, j + A.l)
            y[i] += A.data[i - j + A.u + 1, j] * xj
        end
    end
    y
end
""",
    bad="""using LinearAlgebra

struct Banded{T} <: AbstractMatrix{T}
    n::Int
    l::Int
    u::Int
    data::Matrix{T}
end

Banded{T}(n::Int, l::Int, u::Int) where {T} = Banded{T}(n, l, u, zeros(T, l + u + 1, n))
Banded(n::Int, l::Int, u::Int) = Banded{Float64}(n, l, u)

Base.size(A::Banded) = (A.n, A.n)

# BAD: l et u echanges. La bande garde le bon NOMBRE de diagonales, elle est
# juste du mauvais cote -- et pour l == u le defaut est invisible.
@inline dans_bande(A::Banded, i::Int, j::Int) = (-A.l <= i - j <= A.u)

function Base.getindex(A::Banded{T}, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    dans_bande(A, i, j) ? A.data[i - j + A.l + 1, j] : zero(T)
end

function Base.setindex!(A::Banded{T}, v, i::Int, j::Int) where {T}
    @boundscheck checkbounds(A, i, j)
    if dans_bande(A, i, j)
        A.data[i - j + A.l + 1, j] = v
    elseif !iszero(v)
        throw(ArgumentError("ecriture non nulle hors bande"))
    end
    v
end

function LinearAlgebra.mul!(y::AbstractVector, A::Banded, x::AbstractVector)
    fill!(y, zero(eltype(y)))
    @inbounds for j in 1:A.n
        xj = x[j]
        for i in max(1, j - A.l):min(A.n, j + A.u)
            y[i] += A.data[i - j + A.l + 1, j] * xj
        end
    end
    y
end
""",
    checks="""using .Sol: Banded
using LinearAlgebra

A = Banded(6, 1, 2)
@assert size(A) == (6, 6)                       "size"
@assert A isa AbstractMatrix                    "Banded doit se sous-typer AbstractMatrix"

A[3, 3] = 5.0
A[3, 2] = 1.0      # une sous-diagonale : i-j = 1 <= l
A[3, 5] = 2.0      # deux sur-diagonales : i-j = -2 >= -u
@assert A[3, 3] == 5.0                          "diagonale"
@assert A[3, 2] == 1.0                          "sous-diagonale : l et u sont peut-etre echanges"
@assert A[3, 5] == 2.0                          "sur-diagonale : l et u sont peut-etre echanges"
@assert A[5, 3] == 0.0                          "i-j = 2 > l : hors bande, doit lire zero"
@assert A[1, 6] == 0.0                          "hors bande doit lire zero, pas lever"

let ok = false
    try
        A[5, 3] = 1.0
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                  "ecrire non-nul hors bande doit lever ArgumentError"
end
A[5, 3] = 0.0                                   # autorise, ne fait rien

@assert Base.summarysize(Banded(400, 1, 1)) < 400 * 400 * 8 / 4  "stockage dense : la memoire suit n^2"

B = Banded(50, 2, 3)
for j in 1:50, i in max(1, j - 3):min(50, j + 2)
    B[i, j] = sin(i * j)
end
D = Matrix(B)
x = [cos(k) for k in 1:50]
y = zeros(50)
mul!(y, B, x)
@assert maximum(abs.(y .- D * x)) < 1e-10       "mul! : produit faux"

mul!(y, B, x)                                    # rechauffe
let al = @allocated mul!(y, B, x)
    @assert al == 0                             "mul! alloue $(al) octets, il en faut 0"
end

@assert sum(B) ≈ sum(D)                         "sum via l'interface AbstractArray"
""")

# ------------------------------------------------------------------- t22 ODE
T["t22"] = dict(
    externe=True,
    enonce="""Implement an ADAPTIVE embedded Runge-Kutta integrator for scalar ODEs:

    rk_adaptive(f, y0::Float64, tspan::Tuple{Float64,Float64}, tol::Float64) -> (ts, ys)

`f(t, y)` returns dy/dt. The integrator must use an EMBEDDED pair of methods of
different order sharing the SAME stage evaluations, use the difference between the
two as a local error estimate, accept or reject each step against `tol`, and adapt
the step size from that estimate. Fixed-step integration is NOT acceptable: on a
problem with a sharp feature the accepted steps must become much shorter there and
much longer elsewhere.

`ts` and `ys` are `Vector{Float64}` of the accepted points, strictly increasing in
`ts`, with `ts[1] == tspan[1]` and `ts[end] == tspan[2]` EXACTLY -- the last step
must be clipped so the final point lands on the end of the interval.""",
    ref="""# Paire encastree de Bogacki-Shampine 3(2), quatre etages, FSAL.
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
""",
    bad="""# BAD: RK4 a pas FIXE. Precis, mais le pas ne s'adapte jamais -- sur un
# probleme a pic il gaspille partout et rate le pic.
function rk_adaptive(f, y0::Float64, tspan::Tuple{Float64,Float64}, tol::Float64)
    t0, tf = tspan
    n = 20000
    h = (tf - t0) / n
    ts = Vector{Float64}(undef, n + 1)
    ys = Vector{Float64}(undef, n + 1)
    ts[1] = t0
    ys[1] = y0
    t = t0
    y = y0
    for i in 1:n
        k1 = f(t, y)
        k2 = f(t + h / 2, y + h * k1 / 2)
        k3 = f(t + h / 2, y + h * k2 / 2)
        k4 = f(t + h, y + h * k3)
        y += h * (k1 + 2k2 + 2k3 + k4) / 6
        t += h
        ts[i + 1] = t
        ys[i + 1] = y
    end
    ts[end] = tf
    (ts, ys)
end
""",
    checks="""using .Sol: rk_adaptive

# 1. exactitude sur une primitive connue
let (ts, ys) = rk_adaptive((t, y) -> cos(t), 0.0, (0.0, 10.0), 1e-9)
    @assert length(ts) == length(ys)             "ts et ys de longueurs differentes"
    @assert ts[1] == 0.0                         "ts[1] doit valoir exactement le debut"
    @assert ts[end] == 10.0                      "ts[end] doit valoir EXACTEMENT la fin : $(ts[end])"
    @assert all(diff(ts) .> 0)                   "ts doit etre strictement croissant"
    @assert abs(ys[end] - sin(10.0)) < 1e-6      "y(10) = $(ys[end]) au lieu de $(sin(10.0))"
end

# 2. exactitude sur une decroissance exponentielle
let (ts, ys) = rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-9)
    @assert abs(ys[end] - exp(-5.0)) / exp(-5.0) < 1e-5  "y(5) = $(ys[end]) au lieu de $(exp(-5.0))"
end

# 3. LE point : le pas doit VRAIMENT s'adapter. Pic etroit en t = 2.
let (ts, _) = rk_adaptive((t, y) -> 1 / ((t - 2)^2 + 1e-3), 0.0, (0.0, 4.0), 1e-8)
    d = diff(ts)
    r = maximum(d) / minimum(d)
    @assert r > 10                               "pas non adaptatif : rapport max/min des pas = $(r), il faut > 10"
end

# 4. et il ne doit pas y arriver en prenant 20000 pas partout
let (ts, _) = rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-6)
    @assert length(ts) < 5000                    "$(length(ts)) pas pour une exponentielle a tol 1e-6 : le pas ne grandit pas"
end

# 5. une tolerance plus lache doit couter moins de pas
let n1 = length(first(rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-10))),
    n2 = length(first(rk_adaptive((t, y) -> -y, 1.0, (0.0, 5.0), 1e-4)))
    @assert n2 < n1                              "tol 1e-4 coute $(n2) pas et tol 1e-10 en coute $(n1) : la tolerance n'agit pas"
end
""")

# ----------------------------------------------------------------- t23 Pratt
T["t23"] = dict(
    externe=False,
    enonce="""Implement `evaluate(s::AbstractString) -> Float64`, a complete evaluator for
arithmetic expressions written in infix notation. It must handle:

- decimal literals (`2`, `3.5`), and whitespace anywhere between tokens;
- the binary operators `+` `-` `*` `/` `^` and parentheses;
- unary `-` and unary `+`.

The precedence and associativity must be the usual ones, and they are the hard part:
`^` binds tighter than `*` and `/`, which bind tighter than `+` and `-`; `^` is
RIGHT-associative while the others are LEFT-associative; and unary minus binds
LOOSER than `^` -- so `-2^2` is `-4`, not `4`.

Any malformed input (a trailing operator, an unclosed parenthesis, two numbers in a
row, an unknown character) must throw an exception rather than return a value.""",
    ref="""struct Lexeme
    kind::Symbol      # :num, :op, :lpar, :rpar
    val::Float64
    op::Char
end

function lexer(s::AbstractString)
    cs = collect(s)
    n = length(cs)
    out = Lexeme[]
    i = 1
    while i <= n
        c = cs[i]
        if isspace(c)
            i += 1
        elseif isdigit(c) || c == '.'
            j = i
            while j <= n && (isdigit(cs[j]) || cs[j] == '.')
                j += 1
            end
            push!(out, Lexeme(:num, parse(Float64, String(cs[i:j-1])), ' '))
            i = j
        elseif c in ('+', '-', '*', '/', '^')
            push!(out, Lexeme(:op, 0.0, c))
            i += 1
        elseif c == '('
            push!(out, Lexeme(:lpar, 0.0, ' '))
            i += 1
        elseif c == ')'
            push!(out, Lexeme(:rpar, 0.0, ' '))
            i += 1
        else
            throw(ArgumentError("caractere inattendu"))
        end
    end
    out
end

const PREC = Dict('+' => 1, '-' => 1, '*' => 2, '/' => 2, '^' => 3)

mutable struct Etat
    lx::Vector{Lexeme}
    p::Int
end

pic(e::Etat) = e.p <= length(e.lx) ? e.lx[e.p] : nothing

function atome(e::Etat)
    t = pic(e)
    t === nothing && throw(ArgumentError("expression tronquee"))
    if t.kind == :num
        e.p += 1
        return t.val
    elseif t.kind == :op && (t.op == '-' || t.op == '+')
        e.p += 1
        v = expr(e, 3)          # l'unaire lie MOINS fort que ^ : il laisse ^ manger
        return t.op == '-' ? -v : v
    elseif t.kind == :lpar
        e.p += 1
        v = expr(e, 1)
        t2 = pic(e)
        (t2 === nothing || t2.kind != :rpar) && throw(ArgumentError("parenthese non fermee"))
        e.p += 1
        return v
    end
    throw(ArgumentError("jeton inattendu"))
end

function expr(e::Etat, minp::Int)
    lhs = atome(e)
    while true
        t = pic(e)
        (t === nothing || t.kind != :op) && break
        p = PREC[t.op]
        p < minp && break
        e.p += 1
        rhs = expr(e, t.op == '^' ? p : p + 1)     # ^ associe a DROITE
        lhs = t.op == '+' ? lhs + rhs :
              t.op == '-' ? lhs - rhs :
              t.op == '*' ? lhs * rhs :
              t.op == '/' ? lhs / rhs : lhs^rhs
    end
    lhs
end

function evaluate(s::AbstractString)
    e = Etat(lexer(s), 1)
    v = expr(e, 1)
    e.p <= length(e.lx) && throw(ArgumentError("entree residuelle"))
    Float64(v)
end
""",
    bad="""struct Lexeme
    kind::Symbol
    val::Float64
    op::Char
end

function lexer(s::AbstractString)
    cs = collect(s)
    n = length(cs)
    out = Lexeme[]
    i = 1
    while i <= n
        c = cs[i]
        if isspace(c)
            i += 1
        elseif isdigit(c) || c == '.'
            j = i
            while j <= n && (isdigit(cs[j]) || cs[j] == '.')
                j += 1
            end
            push!(out, Lexeme(:num, parse(Float64, String(cs[i:j-1])), ' '))
            i = j
        elseif c in ('+', '-', '*', '/', '^')
            push!(out, Lexeme(:op, 0.0, c))
            i += 1
        elseif c == '('
            push!(out, Lexeme(:lpar, 0.0, ' '))
            i += 1
        elseif c == ')'
            push!(out, Lexeme(:rpar, 0.0, ' '))
            i += 1
        else
            throw(ArgumentError("caractere inattendu"))
        end
    end
    out
end

const PREC = Dict('+' => 1, '-' => 1, '*' => 2, '/' => 2, '^' => 3)

mutable struct Etat
    lx::Vector{Lexeme}
    p::Int
end

pic(e::Etat) = e.p <= length(e.lx) ? e.lx[e.p] : nothing

function atome(e::Etat)
    t = pic(e)
    t === nothing && throw(ArgumentError("expression tronquee"))
    if t.kind == :num
        e.p += 1
        return t.val
    elseif t.kind == :op && (t.op == '-' || t.op == '+')
        e.p += 1
        v = expr(e, 3)
        return t.op == '-' ? -v : v
    elseif t.kind == :lpar
        e.p += 1
        v = expr(e, 1)
        t2 = pic(e)
        (t2 === nothing || t2.kind != :rpar) && throw(ArgumentError("parenthese non fermee"))
        e.p += 1
        return v
    end
    throw(ArgumentError("jeton inattendu"))
end

function expr(e::Etat, minp::Int)
    lhs = atome(e)
    while true
        t = pic(e)
        (t === nothing || t.kind != :op) && break
        p = PREC[t.op]
        p < minp && break
        e.p += 1
        # BAD: ^ traite comme les autres, donc associatif a GAUCHE.
        # 2^3^2 rend (2^3)^2 = 64 au lieu de 2^(3^2) = 512.
        rhs = expr(e, p + 1)
        lhs = t.op == '+' ? lhs + rhs :
              t.op == '-' ? lhs - rhs :
              t.op == '*' ? lhs * rhs :
              t.op == '/' ? lhs / rhs : lhs^rhs
    end
    lhs
end

function evaluate(s::AbstractString)
    e = Etat(lexer(s), 1)
    v = expr(e, 1)
    e.p <= length(e.lx) && throw(ArgumentError("entree residuelle"))
    Float64(v)
end
""",
    checks="""using .Sol: evaluate

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
    @assert ok                                   "l'entree malformee \\"$(mauvais)\\" doit lever"
end
""")

# ------------------------------------------------------------- t24 MessagePack
T["t24"] = dict(
    externe=True,
    enonce="""Implement `mp_decode(bytes::Vector{UInt8})` decoding a value serialised in the
MessagePack binary format, and returning the corresponding Julia value.

You must support: nil, the two booleans, positive fixint and negative fixint,
uint 8 / uint 16 / uint 32, int 8 / int 16 / int 32, float 64, fixstr and str 8,
fixarray and array 16, and fixmap.

- nil decodes to `nothing`, integers to `Int`, float 64 to `Float64`, strings to `String`.
- Arrays decode to `Vector{Any}`, maps to `Dict{String,Any}` (keys are always strings).
- Arrays and maps nest arbitrarily.
- `mp_decode` receives the whole buffer and returns the single value it encodes.

Decoding must be exact, including the byte order the format specifies for its
multi-byte integers and floats. Getting that order wrong is the classic failure here,
and it is silent: small values still decode, large ones come out scrambled.""",
    ref="""function decode_at(b::Vector{UInt8}, i::Int)
    c = b[i]
    if c <= 0x7f
        return Int(c), i + 1
    elseif c >= 0xe0
        return Int(reinterpret(Int8, c)), i + 1
    elseif 0xa0 <= c <= 0xbf
        n = Int(c & 0x1f)
        return String(b[i+1:i+n]), i + 1 + n
    elseif 0x90 <= c <= 0x9f
        n = Int(c & 0x0f)
        v = Any[]
        j = i + 1
        for _ in 1:n
            x, j = decode_at(b, j)
            push!(v, x)
        end
        return v, j
    elseif 0x80 <= c <= 0x8f
        n = Int(c & 0x0f)
        d = Dict{String,Any}()
        j = i + 1
        for _ in 1:n
            k, j = decode_at(b, j)
            v, j = decode_at(b, j)
            d[String(k)] = v
        end
        return d, j
    elseif c == 0xc0
        return nothing, i + 1
    elseif c == 0xc2
        return false, i + 1
    elseif c == 0xc3
        return true, i + 1
    elseif c == 0xcc
        return Int(b[i+1]), i + 2
    elseif c == 0xcd
        return Int(UInt16(b[i+1]) << 8 | UInt16(b[i+2])), i + 3
    elseif c == 0xce
        u = UInt32(b[i+1]) << 24 | UInt32(b[i+2]) << 16 | UInt32(b[i+3]) << 8 | UInt32(b[i+4])
        return Int(u), i + 5
    elseif c == 0xd0
        return Int(reinterpret(Int8, b[i+1])), i + 2
    elseif c == 0xd1
        return Int(reinterpret(Int16, UInt16(b[i+1]) << 8 | UInt16(b[i+2]))), i + 3
    elseif c == 0xd2
        u = UInt32(b[i+1]) << 24 | UInt32(b[i+2]) << 16 | UInt32(b[i+3]) << 8 | UInt32(b[i+4])
        return Int(reinterpret(Int32, u)), i + 5
    elseif c == 0xcb
        u = UInt64(0)
        for k in 1:8
            u = (u << 8) | UInt64(b[i+k])
        end
        return reinterpret(Float64, u), i + 9
    elseif c == 0xd9
        n = Int(b[i+1])
        return String(b[i+2:i+1+n]), i + 2 + n
    elseif c == 0xdc
        n = Int(UInt16(b[i+1]) << 8 | UInt16(b[i+2]))
        v = Any[]
        j = i + 3
        for _ in 1:n
            x, j = decode_at(b, j)
            push!(v, x)
        end
        return v, j
    end
    throw(ArgumentError("octet de tete non supporte"))
end

mp_decode(b::Vector{UInt8}) = first(decode_at(b, 1))
""",
    bad="""function decode_at(b::Vector{UInt8}, i::Int)
    c = b[i]
    if c <= 0x7f
        return Int(c), i + 1
    elseif c >= 0xe0
        return Int(reinterpret(Int8, c)), i + 1
    elseif 0xa0 <= c <= 0xbf
        n = Int(c & 0x1f)
        return String(b[i+1:i+n]), i + 1 + n
    elseif 0x90 <= c <= 0x9f
        n = Int(c & 0x0f)
        v = Any[]
        j = i + 1
        for _ in 1:n
            x, j = decode_at(b, j)
            push!(v, x)
        end
        return v, j
    elseif 0x80 <= c <= 0x8f
        n = Int(c & 0x0f)
        d = Dict{String,Any}()
        j = i + 1
        for _ in 1:n
            k, j = decode_at(b, j)
            v, j = decode_at(b, j)
            d[String(k)] = v
        end
        return d, j
    elseif c == 0xc0
        return nothing, i + 1
    elseif c == 0xc2
        return false, i + 1
    elseif c == 0xc3
        return true, i + 1
    elseif c == 0xcc
        return Int(b[i+1]), i + 2
    elseif c == 0xcd
        # BAD: petit-boutiste. MessagePack est GROS-boutiste. 0xcd 0x01 0x00
        # vaut 256 et sort a 1. Les petites valeurs, elles, passent.
        return Int(UInt16(b[i+2]) << 8 | UInt16(b[i+1])), i + 3
    elseif c == 0xce
        u = UInt32(b[i+4]) << 24 | UInt32(b[i+3]) << 16 | UInt32(b[i+2]) << 8 | UInt32(b[i+1])
        return Int(u), i + 5
    elseif c == 0xd0
        return Int(reinterpret(Int8, b[i+1])), i + 2
    elseif c == 0xd1
        return Int(reinterpret(Int16, UInt16(b[i+2]) << 8 | UInt16(b[i+1]))), i + 3
    elseif c == 0xd2
        u = UInt32(b[i+4]) << 24 | UInt32(b[i+3]) << 16 | UInt32(b[i+2]) << 8 | UInt32(b[i+1])
        return Int(reinterpret(Int32, u)), i + 5
    elseif c == 0xcb
        u = UInt64(0)
        for k in 8:-1:1
            u = (u << 8) | UInt64(b[i+k])
        end
        return reinterpret(Float64, u), i + 9
    elseif c == 0xd9
        n = Int(b[i+1])
        return String(b[i+2:i+1+n]), i + 2 + n
    elseif c == 0xdc
        n = Int(UInt16(b[i+3]) << 8 | UInt16(b[i+2]))
        v = Any[]
        j = i + 3
        for _ in 1:n
            x, j = decode_at(b, j)
            push!(v, x)
        end
        return v, j
    end
    throw(ArgumentError("octet de tete non supporte"))
end

mp_decode(b::Vector{UInt8}) = first(decode_at(b, 1))
""",
    checks="""using .Sol: mp_decode

o(v...) = UInt8[v...]

@assert mp_decode(o(0x00)) === 0                 "fixint positif 0"
@assert mp_decode(o(0x7f)) === 127               "fixint positif 127"
@assert mp_decode(o(0xff)) === -1                "fixint negatif -1"
@assert mp_decode(o(0xe0)) === -32               "fixint negatif -32"
@assert mp_decode(o(0xc0)) === nothing           "nil"
@assert mp_decode(o(0xc2)) === false             "false"
@assert mp_decode(o(0xc3)) === true              "true"

@assert mp_decode(o(0xcc, 0xc8)) === 200         "uint8"
@assert mp_decode(o(0xcd, 0x01, 0x00)) === 256   "uint16 GROS-boutiste : $(mp_decode(o(0xcd,0x01,0x00))) au lieu de 256"
@assert mp_decode(o(0xce, 0x00, 0x01, 0x00, 0x00)) === 65536  "uint32 gros-boutiste : $(mp_decode(o(0xce,0x00,0x01,0x00,0x00))) au lieu de 65536"
@assert mp_decode(o(0xd0, 0x80)) === -128        "int8"
@assert mp_decode(o(0xd1, 0xff, 0x38)) === -200  "int16 gros-boutiste : $(mp_decode(o(0xd1,0xff,0x38))) au lieu de -200"

@assert mp_decode(o(0xcb, 0x3f, 0xf8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)) === 1.5  "float64 gros-boutiste"

@assert mp_decode(o(0xa3, 0x61, 0x62, 0x63)) == "abc"          "fixstr"
@assert mp_decode(o(0xd9, 0x03, 0x78, 0x79, 0x7a)) == "xyz"    "str8"
@assert mp_decode(o(0xa0)) == ""                               "fixstr vide"

@assert mp_decode(o(0x93, 0x01, 0x02, 0x03)) == Any[1, 2, 3]   "fixarray"
@assert mp_decode(o(0x90)) == Any[]                            "fixarray vide"
@assert mp_decode(o(0x91, 0x91, 0xc3)) == Any[Any[true]]       "tableaux imbriques"

@assert mp_decode(o(0x82, 0xa1, 0x61, 0x01, 0xa1, 0x62, 0xc3)) == Dict{String,Any}("a" => 1, "b" => true)  "fixmap"
@assert mp_decode(o(0x81, 0xa1, 0x6b, 0x92, 0x01, 0xc0)) == Dict{String,Any}("k" => Any[1, nothing])       "map contenant un tableau"

let b = vcat(o(0xdc, 0x00, 0x11), fill(0x01, 17))
    @assert mp_decode(b) == Any[fill(1, 17)...]  "array16 : longueur gros-boutiste"
end
""")

# ---------------------------------------------------------------- t25 Tarjan
T["t25"] = dict(
    externe=False,
    enonce="""Implement two functions on a directed graph given as adjacency lists, where
`adj[v]` lists the successors of vertex `v` and vertices are `1:length(adj)`.

`sccs(adj::Vector{Vector{Int}}) -> Vector{Vector{Int}}` returns the strongly connected
components. Every vertex appears in exactly one component.

`condensation(adj) -> (comp, dag)` returns `comp::Vector{Int}`, where `comp[v]` is the
index of the component holding `v` (indices matching the order returned by `sccs`), and
`dag::Vector{Vector{Int}}`, the adjacency list of the condensation: one node per
component, with an edge from component `a` to component `b` whenever the original graph
has an edge from a vertex of `a` to a vertex of `b` AND `a != b`. `dag` must therefore
contain NO self-loop and NO duplicate edge, and it must be acyclic.

The graph can hold 200000 vertices in a single chain. A traversal that recurses on graph
depth blows the stack there: the traversal must be iterative.""",
    ref="""function sccs(adj::Vector{Vector{Int}})
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
    for v in 1:n, w in adj[v]
        a, b = comp[v], comp[w]
        a != b && push!(ens[a], b)
    end
    (comp, [sort!(collect(s)) for s in ens])
end
""",
    bad="""function sccs(adj::Vector{Vector{Int}})
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
""",
    checks="""using .Sol: sccs, condensation

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
""")

# ----------------------------------------------------------------- t26 gemm5!
T["t26"] = dict(
    externe=True,
    enonce="""Implement `gemm5!(C, A, B, alpha, beta)` computing IN PLACE and returning `C`:

    C  <-  alpha * (A * B)  +  beta * C

following exactly the contract of the five-argument `mul!` of `LinearAlgebra`. Two
points of that contract decide the result and both are easy to get wrong:

- `alpha` scales ONLY the product `A*B`. It must NOT be applied to the `beta*C` term.
- When `beta` is zero, the previous contents of `C` are NOT read at all: they are
  overwritten. `C` may hold `NaN` or `Inf` beforehand and the result must still be
  finite. Multiplying them by a zero `beta` is not the same thing and does not satisfy it.

`A` is m-by-k, `B` is k-by-n, `C` is m-by-n; they need not be square, and mismatched
dimensions must throw a `DimensionMismatch`.

Do NOT call `LinearAlgebra.mul!`, matrix `*`, or BLAS -- write the loops. The
implementation must stay generic: it has to work on `Rational{Int}` entries, which
BLAS cannot touch, exactly as it does on `Float64`.""",
    ref="""function gemm5!(C, A, B, alpha, beta)
    m, k = size(A)
    k2, n = size(B)
    (k == k2 && size(C) == (m, n)) || throw(DimensionMismatch("dimensions incompatibles"))
    T = eltype(C)
    @inbounds for j in 1:n, i in 1:m
        s = zero(T)
        for p in 1:k
            s += A[i, p] * B[p, j]
        end
        # beta nul : on ECRASE, on ne lit pas C -- sinon un NaN deja present survit
        C[i, j] = iszero(beta) ? alpha * s : alpha * s + beta * C[i, j]
    end
    C
end
""",
    bad="""function gemm5!(C, A, B, alpha, beta)
    m, k = size(A)
    k2, n = size(B)
    (k == k2 && size(C) == (m, n)) || throw(DimensionMismatch("dimensions incompatibles"))
    T = eltype(C)
    @inbounds for j in 1:n, i in 1:m
        s = zero(T)
        for p in 1:k
            s += A[i, p] * B[p, j]
        end
        # BAD: pas de cas particulier pour beta nul. C est LU quand meme, donc
        # 0 * NaN = NaN et le resultat est empoisonne par ce qui trainait dans C.
        C[i, j] = alpha * s + beta * C[i, j]
    end
    C
end
""",
    checks="""using .Sol: gemm5!

A = [1.0 2.0; 3.0 4.0]
B = [5.0 6.0; 7.0 8.0]
P = [19.0 22.0; 43.0 50.0]

let C = fill(NaN, 2, 2)
    gemm5!(C, A, B, 1.0, 0.0)
    @assert all(isfinite, C)                     "beta nul doit ECRASER C sans le lire : le NaN a survecu"
    @assert C == P                               "beta=0, alpha=1 : produit faux"
end

let C = [1.0 1.0; 1.0 1.0]
    gemm5!(C, A, B, 2.0, 3.0)
    @assert C == 2 .* P .+ 3.0                   "alpha ne doit PAS multiplier beta*C : $(C) au lieu de $(2 .* P .+ 3.0)"
end

let C = [7.0 8.0; 9.0 10.0], D = copy(C)
    gemm5!(C, A, B, 0.0, 1.0)
    @assert C == D                               "alpha=0, beta=1 : C doit rester inchange"
end

let C = zeros(2, 2)
    @assert gemm5!(C, A, B, 1.0, 0.0) === C      "gemm5! doit rendre C lui-meme"
end

let A2 = [1.0 2.0 3.0; 4.0 5.0 6.0],
    B2 = [1.0 0.0; 0.0 1.0; 1.0 1.0],
    C2 = fill(NaN, 2, 2)
    gemm5!(C2, A2, B2, 1.0, 0.0)
    @assert C2 == A2 * B2                        "cas non carre"
end

let Ar = Rational{Int}[1//2 1//3; 1//4 1//5],
    Br = Rational{Int}[1//1 2//1; 3//1 4//1],
    Cr = zeros(Rational{Int}, 2, 2)
    gemm5!(Cr, Ar, Br, 1//1, 0//1)
    @assert eltype(Cr) == Rational{Int}          "le type d'element doit rester Rational"
    @assert Cr == Ar * Br                        "doit rester generique : BLAS ne sait pas multiplier des Rational"
end

let ok = false
    try
        gemm5!(zeros(2, 2), zeros(2, 3), zeros(2, 2), 1.0, 0.0)
    catch e
        ok = isa(e, DimensionMismatch)
    end
    @assert ok                                   "dimensions incompatibles doivent lever DimensionMismatch"
end
""")


def ecrire(chemin, contenu):
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(contenu)
    os.replace(tmp, chemin)


n = 0
ext = []
for nom in sorted(T):
    d = T[nom]
    ecrire(os.path.join(BASE, "prompts", "%s.txt" % nom),
           ENTETE + d["enonce"].strip() + "\n" + REGLES)
    ecrire(os.path.join(BASE, "tasks", "%s_checks.jl" % nom), d["checks"])
    ecrire(os.path.join(BASE, "ref", "%s.jl" % nom), d["ref"])
    ecrire(os.path.join(BASE, "bad", "%s.jl" % nom), d["bad"])
    n += 1
    if d["externe"]:
        ext.append(nom)

# La liste des taches a fait externe est ecrite a cote du corpus : c'est elle
# qui rend le bras "avec web" interpretable, et elle doit etre lisible par
# l'analyse sans qu'on la retape.
ecrire(os.path.join(BASE, "tasks", "expert_faits_externes.txt"),
       "\n".join(ext) + "\n")

print("palier expert ecrit : %d taches (t21..t26), 4 fichiers chacune" % n)
print("  a fait externe (le web peut aider) : %s" % ", ".join(ext))
print("  temoins sans fait externe          : %s" % ", ".join(sorted(set(T) - set(ext))))
