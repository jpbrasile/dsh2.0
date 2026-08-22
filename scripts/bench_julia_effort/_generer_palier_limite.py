# -*- coding: utf-8 -*-
"""Ecrit le palier LIMITE du corpus : t31..t36.

Consigne qui a produit ce palier : "fais des taches a la limite de ce que TU sais
faire". Le critere n'est donc pas "dur pour un 27B" -- t11..t16 le sont deja --
mais "je ne parierais pas sur ma propre reference du premier coup". Chacune des
six ci-dessous a un piege ou je me suis DEJA trompe ou ou je peux me tromper :

  t31  confusion de perturbation. Le piege le plus celebre de la derivation
       automatique : deux derivations imbriquees qui partagent une etiquette
       rendent 2 au lieu de 1, et le code a l'air parfaitement juste.
  t32  machinerie de diffusion de Julia. BroadcastStyle + similar(::Broadcasted)
       est une interface a trois pieces qui ne pardonne pas ; l'oublier ne casse
       rien, ca rend juste un Vector au lieu du type qu'on voulait.
  t33  ordre binaire des Float64. Le retournement de bits qui aligne l'ordre des
       motifs binaires sur `isless` n'est pas le meme pour les negatifs et pour
       les positifs -- et NaN et -0.0 ne tombent pas la ou on croit.
  t34  multiplication modulaire sans debordement, et jeu de temoins complet.
       3215031751 est pseudo-premier fort en base 2, 3, 5 ET 7 : un jeu tronque
       le declare premier, et tous les petits tests passent.
  t35  arrondi VERS L'EXTERIEUR. Un intervalle qui ne contient plus son resultat
       exact ne sert plus a rien, et l'erreur est invisible sur les exemples.
  t36  partage de structure. Une version persistante qui recopie tout est
       CORRECTE : seule la memoire la denonce.

Axe secondaire, conserve depuis le palier expert : quelles taches dependent d'un
fait EXTERNE verifiable (la ou une recherche web peut aider) et lesquelles n'en
dependent pas du tout (les temoins du bras web).

  fait externe : t32 (interface documentee), t34 (jeu de temoins), t33 (astuce binaire)
  temoins      : t31, t35, t36 -- rien a chercher, tout a deduire

Chaque bras known-BAD porte UN defaut nomme, et c'est l'assertion qui le nomme
qui doit tomber.
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

# ------------------------------------------------------- t31 derivation imbriquee
T["t31"] = dict(
    externe=False,
    enonce="""Implement forward-mode automatic differentiation that stays correct when
derivatives are NESTED.

Provide `derivative(f, x::Number)` returning `f'(x)`, computed by propagating a dual
number through `f` -- not by finite differences, and not by symbolic manipulation.

Your dual number must support `+`, `-`, `*`, `/`, `^`, unary `-`, `sin`, `cos`, `exp`,
`log`, and the comparisons `<` and `==` (so that `f` may branch on its argument).

The hard requirement is nesting. `derivative` must be usable INSIDE the function it
differentiates, and the two differentiations must not contaminate each other. In
particular this must hold:

    derivative(x -> x * derivative(y -> x + y, 1.0), 1.0) == 1.0

Here the inner derivative is 1 whatever `x` is, so the outer function is just `x` and
its derivative is 1. An implementation that gives every dual number the same
perturbation returns 2.0 here: the inner differentiation picks up the outer one's
perturbation. That failure is called perturbation confusion, and avoiding it is the
point of this task.

Second derivatives must work the same way:
`derivative(x -> derivative(sin, x), 1.0)` must equal `-sin(1.0)`.""",
    ref="""# Etiquetage par NIVEAU d'imbrication, tenu par un compteur dynamique : chaque
# appel a derivative ouvre un niveau strictement plus profond que celui qui
# l'englobe, donc deux derivations imbriquees ne partagent jamais la meme
# perturbation. C'est ce qui evite la confusion de perturbation.
const NIVEAU = Ref(0)

# Les deux champs sont volontairement NON types. Un dual imbrique contient un
# dual de niveau inferieur dans sa valeur et un reel ordinaire dans sa
# derivee : un champ commun `T` forcerait une promotion entre Dual{1,Float64}
# et Float64, pour laquelle il faudrait ecrire convert ET promote_rule -- et
# c'est justement dans le cas imbrique que ca casserait. Pas de type commun,
# pas de promotion, pas de piege.
# La signature de l'enonce est `derivative(f, x::Number)`, PAS `x::Real` :
# imbriquer passe un dual EN TANT QUE `x`, et `x::Real` force alors un choix de
# conception qui n'est pas le piege que la tache mesure. Les deux voies ont ete
# essayees le 22/08 : un dual `<: Number` ne s'applique plus (MethodError), un
# dual `<: Real` rend `<` ambigu contre `Base.<(::Real, ::Real)`. Dans les deux
# cas la reference ET la solution known-BAD tombaient sur la MEME erreur, donc
# le bras known-BAD n'atteignait jamais son propre defaut et ne mesurait rien.
# `Number` laisse passer les deux conceptions : la confusion de perturbation
# redevient le seul discriminant.
struct Dual{L} <: Number
    v
    d
end

niv(::Type{<:Dual{L}}) where {L} = L
niv(::Type{<:Number}) = 0
niv(x::Number) = niv(typeof(x))

Base.zero(x::Dual{L}) where {L} = Dual{L}(zero(x.v), zero(x.d))
Base.one(x::Dual{L}) where {L} = Dual{L}(one(x.v), zero(x.d))

# Un reel ordinaire est constant vis-a-vis de tout niveau.
Base.:+(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v + b.v, a.d + b.d)
Base.:-(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v - b.v, a.d - b.d)
Base.:*(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v * b.v, a.d * b.v + a.v * b.d)
Base.:/(a::Dual{L}, b::Dual{L}) where {L} = Dual{L}(a.v / b.v, (a.d * b.v - a.v * b.d) / (b.v * b.v))

Base.:+(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v + b, a.d)
Base.:+(a::Number, b::Dual{L}) where {L} = Dual{L}(a + b.v, b.d)
Base.:-(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v - b, a.d)
Base.:-(a::Number, b::Dual{L}) where {L} = Dual{L}(a - b.v, -b.d)
Base.:*(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v * b, a.d * b)
Base.:*(a::Number, b::Dual{L}) where {L} = Dual{L}(a * b.v, a * b.d)
Base.:/(a::Dual{L}, b::Number) where {L} = Dual{L}(a.v / b, a.d / b)
Base.:/(a::Number, b::Dual{L}) where {L} = Dual{L}(a / b.v, -a * b.d / (b.v * b.v))
Base.:-(a::Dual{L}) where {L} = Dual{L}(-a.v, -a.d)

# Deux niveaux differents : le PLUS PROFOND est l'exterieur, l'autre lui est
# constant. Cette methode est plus specifique que les deux precedentes, donc
# elle leve l'ambiguite au lieu de la creer.
function Base.:+(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v + b, a.d) : Dual{L2}(a + b.v, b.d)
end
function Base.:-(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v - b, a.d) : Dual{L2}(a - b.v, -b.d)
end
function Base.:*(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v * b, a.d * b) : Dual{L2}(a * b.v, a * b.d)
end
function Base.:/(a::Dual{L1}, b::Dual{L2}) where {L1,L2}
    L1 > L2 ? Dual{L1}(a.v / b, a.d / b) : Dual{L2}(a / b.v, -a * b.d / (b.v * b.v))
end

Base.sin(a::Dual{L}) where {L} = Dual{L}(sin(a.v), cos(a.v) * a.d)
Base.cos(a::Dual{L}) where {L} = Dual{L}(cos(a.v), -sin(a.v) * a.d)
Base.exp(a::Dual{L}) where {L} = (e = exp(a.v); Dual{L}(e, e * a.d))
Base.log(a::Dual{L}) where {L} = Dual{L}(log(a.v), a.d / a.v)
Base.:^(a::Dual{L}, n::Integer) where {L} = Dual{L}(a.v^n, n * a.v^(n - 1) * a.d)
Base.:^(a::Dual{L}, p::Real) where {L} = Dual{L}(a.v^p, p * a.v^(p - 1) * a.d)
Base.:^(a::Dual{L}, b::Dual{L}) where {L} =
    (y = a.v^b.v; Dual{L}(y, y * (b.d * log(a.v) + b.v * a.d / a.v)))

Base.:<(a::Dual, b::Dual) = valeur(a) < valeur(b)
Base.:<(a::Dual, b::Number) = valeur(a) < b
Base.:<(a::Number, b::Dual) = a < valeur(b)
Base.:(==)(a::Dual, b::Dual) = valeur(a) == valeur(b)
Base.:(==)(a::Dual, b::Number) = valeur(a) == b
Base.:(==)(a::Number, b::Dual) = a == valeur(b)

valeur(x::Dual) = valeur(x.v)
valeur(x::Number) = x

extraire(y::Dual{L2}, L::Int) where {L2} = L2 == L ? y.d : zero(y)
extraire(y::Number, L::Int) = zero(y)

function derivative(f, x::Number)
    NIVEAU[] += 1
    L = NIVEAU[]
    try
        return extraire(f(Dual{L}(x, one(x))), L)
    finally
        NIVEAU[] -= 1
    end
end
""",
    bad="""# BAD: une SEULE etiquette pour toutes les derivations. Tout est juste tant
# qu'on ne derive qu'une fois ; des que deux derivations s'imbriquent, l'interne
# ramasse la perturbation de l'externe. C'est la confusion de perturbation.
# La signature de l'enonce est `derivative(f, x::Number)`, PAS `x::Real` :
# imbriquer passe un dual EN TANT QUE `x`, et `x::Real` force alors un choix de
# conception qui n'est pas le piege que la tache mesure. Les deux voies ont ete
# essayees le 22/08 : un dual `<: Number` ne s'applique plus (MethodError), un
# dual `<: Real` rend `<` ambigu contre `Base.<(::Real, ::Real)`. Dans les deux
# cas la reference ET la solution known-BAD tombaient sur la MEME erreur, donc
# le bras known-BAD n'atteignait jamais son propre defaut et ne mesurait rien.
# `Number` laisse passer les deux conceptions : la confusion de perturbation
# redevient le seul discriminant.
struct Dual <: Number
    v
    d
end

Base.zero(x::Dual) = Dual(zero(x.v), zero(x.d))
Base.one(x::Dual) = Dual(one(x.v), zero(x.d))

Base.:+(a::Dual, b::Dual) = Dual(a.v + b.v, a.d + b.d)
Base.:-(a::Dual, b::Dual) = Dual(a.v - b.v, a.d - b.d)
Base.:*(a::Dual, b::Dual) = Dual(a.v * b.v, a.d * b.v + a.v * b.d)
Base.:/(a::Dual, b::Dual) = Dual(a.v / b.v, (a.d * b.v - a.v * b.d) / (b.v * b.v))

Base.:+(a::Dual, b::Number) = Dual(a.v + b, a.d)
Base.:+(a::Number, b::Dual) = Dual(a + b.v, b.d)
Base.:-(a::Dual, b::Number) = Dual(a.v - b, a.d)
Base.:-(a::Number, b::Dual) = Dual(a - b.v, -b.d)
Base.:*(a::Dual, b::Number) = Dual(a.v * b, a.d * b)
Base.:*(a::Number, b::Dual) = Dual(a * b.v, a * b.d)
Base.:/(a::Dual, b::Number) = Dual(a.v / b, a.d / b)
Base.:/(a::Number, b::Dual) = Dual(a / b.v, -a * b.d / (b.v * b.v))
Base.:-(a::Dual) = Dual(-a.v, -a.d)

Base.sin(a::Dual) = Dual(sin(a.v), cos(a.v) * a.d)
Base.cos(a::Dual) = Dual(cos(a.v), -sin(a.v) * a.d)
Base.exp(a::Dual) = (e = exp(a.v); Dual(e, e * a.d))
Base.log(a::Dual) = Dual(log(a.v), a.d / a.v)
Base.:^(a::Dual, n::Integer) = Dual(a.v^n, n * a.v^(n - 1) * a.d)
Base.:^(a::Dual, p::Real) = Dual(a.v^p, p * a.v^(p - 1) * a.d)

valeur(x::Dual) = valeur(x.v)
valeur(x::Number) = x
Base.:<(a::Dual, b::Dual) = valeur(a) < valeur(b)
Base.:<(a::Dual, b::Number) = valeur(a) < b
Base.:<(a::Number, b::Dual) = a < valeur(b)
Base.:(==)(a::Dual, b::Dual) = valeur(a) == valeur(b)
Base.:(==)(a::Dual, b::Number) = valeur(a) == b
Base.:(==)(a::Number, b::Dual) = a == valeur(b)

derivative(f, x::Number) = f(Dual(x, one(x))).d
""",
    checks="""using .Sol: derivative

@assert derivative(x -> x^2, 3.0) ≈ 6.0                  "derivee de x^2"
@assert derivative(sin, 0.0) ≈ 1.0                       "derivee de sin en 0"
@assert derivative(x -> exp(2x), 0.0) ≈ 2.0              "regle de composition"
@assert derivative(x -> log(x), 2.0) ≈ 0.5               "derivee de log"
@assert derivative(x -> 1 / x, 2.0) ≈ -0.25              "derivee de 1/x"
@assert derivative(x -> x < 0 ? -x : x, 2.0) ≈ 1.0       "le dual doit se comparer, pour que f puisse brancher"

# derivee seconde par imbrication
@assert derivative(x -> derivative(sin, x), 1.0) ≈ -sin(1.0)  "derivee seconde de sin : $(derivative(x -> derivative(sin, x), 1.0)) au lieu de $(-sin(1.0))"
@assert derivative(x -> derivative(y -> y^3, x), 2.0) ≈ 12.0  "derivee seconde de y^3 en 2"

# LE test : confusion de perturbation
let r = derivative(x -> x * derivative(y -> x + y, 1.0), 1.0)
    @assert r ≈ 1.0                                      "confusion de perturbation : $(r) au lieu de 1.0 -- la derivation interne ramasse la perturbation externe"
end

let r = derivative(x -> derivative(y -> x * y, 2.0), 3.0)
    @assert r ≈ 1.0                                      "confusion de perturbation (produit) : $(r) au lieu de 1.0"
end

# une fonction constante en x a bien une derivee nulle
@assert derivative(x -> 7.0, 3.0) ≈ 0.0                  "derivee d'une constante"
""")

# ------------------------------------------------------------ t32 diffusion
T["t32"] = dict(
    externe=True,
    enonce="""Define `struct Grid{T} <: AbstractVector{T}` holding a sampled function: a
`Vector{T}` of values plus the two `Float64` fields `x0` (coordinate of the first
sample) and `dx` (spacing). Give it the constructor `Grid(v::Vector{T}, x0, dx)` and
the `AbstractVector` interface (`size`, `getindex`, `setindex!`).

The real requirement is BROADCASTING. Julia's broadcast machinery must be taught
about `Grid`, so that a fused expression over grids returns a `Grid` again, carrying
`x0` and `dx` through:

- `g1 .+ 2 .* g2` must be a `Grid` with the same `x0` and `dx`, not a plain `Vector`;
- mixing a `Grid` with scalars and with plain vectors of the same length must still
  yield a `Grid`;
- broadcasting two grids whose `x0` or `dx` differ must throw an `ArgumentError`,
  because adding samples taken on different grids is meaningless;
- the expression must FUSE: `g .+ g .+ g` must allocate one result, not a chain of
  temporaries.

Defining arithmetic operators on `Grid` directly does not satisfy this: the dotted
form goes through the broadcast machinery, and if that machinery is not taught about
`Grid` it silently returns a `Vector`.""",
    ref="""struct Grid{T} <: AbstractVector{T}
    v::Vector{T}
    x0::Float64
    dx::Float64
end

Grid(v::Vector{T}, x0, dx) where {T} = Grid{T}(v, Float64(x0), Float64(dx))

Base.size(g::Grid) = size(g.v)
Base.getindex(g::Grid, i::Int) = g.v[i]
Base.setindex!(g::Grid, x, i::Int) = (g.v[i] = x)
Base.IndexStyle(::Type{<:Grid}) = IndexLinear()

struct GridStyle <: Broadcast.AbstractArrayStyle{1} end
GridStyle(::Val{0}) = GridStyle()
GridStyle(::Val{1}) = GridStyle()
GridStyle(::Val{N}) where {N} = Broadcast.DefaultArrayStyle{N}()
Base.BroadcastStyle(::Type{<:Grid}) = GridStyle()

# Retrouver LA grille de l'expression, en verifiant au passage que toutes celles
# qui y figurent sont compatibles.
trouve(bc::Broadcast.Broadcasted) = trouve(bc.args)
trouve(t::Tuple{}) = nothing
trouve(t::Tuple) = accorde(trouve(t[1]), trouve(Base.tail(t)))
trouve(g::Grid) = g
trouve(::Any) = nothing

accorde(a, ::Nothing) = a
accorde(::Nothing, b) = b
accorde(::Nothing, ::Nothing) = nothing
function accorde(a::Grid, b::Grid)
    (a.x0 == b.x0 && a.dx == b.dx) ||
        throw(ArgumentError("grilles incompatibles : x0 ou dx different"))
    a
end

function Base.similar(bc::Broadcast.Broadcasted{GridStyle}, ::Type{T}) where {T}
    g = trouve(bc)
    Grid(similar(Vector{T}, length(axes(bc)[1])), g.x0, g.dx)
end
""",
    bad="""struct Grid{T} <: AbstractVector{T}
    v::Vector{T}
    x0::Float64
    dx::Float64
end

Grid(v::Vector{T}, x0, dx) where {T} = Grid{T}(v, Float64(x0), Float64(dx))

Base.size(g::Grid) = size(g.v)
Base.getindex(g::Grid, i::Int) = g.v[i]
Base.setindex!(g::Grid, x, i::Int) = (g.v[i] = x)
Base.IndexStyle(::Type{<:Grid}) = IndexLinear()

struct GridStyle <: Broadcast.AbstractArrayStyle{1} end
GridStyle(::Val{0}) = GridStyle()
GridStyle(::Val{1}) = GridStyle()
GridStyle(::Val{N}) where {N} = Broadcast.DefaultArrayStyle{N}()
Base.BroadcastStyle(::Type{<:Grid}) = GridStyle()

# BAD: on prend la PREMIERE grille rencontree sans verifier que les autres ont
# le meme x0 et le meme dx. Le type est preserve, la fusion marche, tout a l'air
# correct -- et on additionne des echantillons pris a des abscisses differentes.
trouve(bc::Broadcast.Broadcasted) = trouve(bc.args)
trouve(t::Tuple{}) = nothing
trouve(t::Tuple) = (a = trouve(t[1]); a === nothing ? trouve(Base.tail(t)) : a)
trouve(g::Grid) = g
trouve(::Any) = nothing

function Base.similar(bc::Broadcast.Broadcasted{GridStyle}, ::Type{T}) where {T}
    g = trouve(bc)
    Grid(similar(Vector{T}, length(axes(bc)[1])), g.x0, g.dx)
end
""",
    checks="""using .Sol: Grid

n = 10000
a = Grid(collect(1.0:n), 0.0, 0.5)
b = Grid(fill(2.0, n), 0.0, 0.5)

@assert a isa AbstractVector                     "Grid doit se sous-typer AbstractVector"
@assert length(a) == n && a[3] == 3.0            "interface AbstractVector"

r = a .+ 2 .* b
@assert r isa Grid                               "la diffusion doit rendre un Grid, pas un $(typeof(r))"
@assert r.x0 == 0.0 && r.dx == 0.5               "x0 et dx doivent traverser la diffusion"
@assert r[1] == 5.0 && r[n] == n + 4.0           "valeurs fausses"

@assert (a .+ 1.0) isa Grid                      "Grid + scalaire doit rester un Grid"
@assert (a .+ ones(n)) isa Grid                  "Grid + Vector doit rester un Grid"
@assert (a .> 500.0) isa Grid                    "une diffusion booleenne doit rester un Grid"

let c = Grid(fill(1.0, n), 1.0, 0.5), ok = false
    try
        a .+ c
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "x0 different : la diffusion doit lever ArgumentError, pas melanger deux grilles"
end

let c = Grid(fill(1.0, n), 0.0, 0.25), ok = false
    try
        a .+ c
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "dx different : la diffusion doit lever ArgumentError"
end

# fusion : une seule allocation de resultat, pas une chaine de temporaires
let _ = a .+ a .+ a
    al = @allocated (a .+ a .+ a)
    @assert al < 2.2 * 8 * n                     "la diffusion n'est pas fusionnee : $(al) octets pour $(8*n) attendus"
end
""")

# ---------------------------------------------------------- t33 tri binaire
T["t33"] = dict(
    externe=True,
    enonce="""Implement `fsort!(v::Vector{Float64})` sorting `v` IN PLACE and returning it,
in exactly the order Julia's own `sort` produces -- which is the order of `isless`.

It must be a RADIX sort on the bit patterns: no comparison of the floating point
values, no call to `sort`, `sort!`, `sortperm`, `partialsort` or `searchsorted`. Read
each `Float64` as its 64-bit pattern, map that pattern to an unsigned key whose
natural order matches `isless`, and sort the keys by successive digit passes.

The mapping is where this task is won or lost:
- for a non-negative float, flipping the sign bit is enough;
- for a negative float, the exponent and mantissa run BACKWARDS with respect to the
  value, so the whole pattern must be inverted -- flipping only the sign bit leaves
  the negatives sorted the wrong way round;
- `-0.0` must come before `+0.0`, since `isless(-0.0, 0.0)` is true;
- every `NaN` must end up at the very end, after `+Inf`, whatever its sign bit --
  which the bit order alone does NOT give you.

Subnormals, both infinities and both zeros must all land in the right place.""",
    ref="""@inline function cle(x::Float64)
    u = reinterpret(UInt64, x)
    (u & 0x8000_0000_0000_0000) != 0 ? ~u : u | 0x8000_0000_0000_0000
end

function fsort!(v::Vector{Float64})
    n = length(v)
    n <= 1 && return v

    # NaN a part : l'ordre binaire les disperse des deux cotes, isless les met
    # tous a la fin.
    j = 0
    nan = 0
    @inbounds for i in 1:n
        if isnan(v[i])
            nan += 1
        else
            j += 1
            v[j] = v[i]
        end
    end
    m = j

    cles = Vector{UInt64}(undef, m)
    @inbounds for i in 1:m
        cles[i] = cle(v[i])
    end

    tmp = Vector{UInt64}(undef, m)
    compte = Vector{Int}(undef, 256)
    @inbounds for passe in 0:7
        decal = 8 * passe
        fill!(compte, 0)
        for i in 1:m
            compte[Int((cles[i] >> decal) & 0xff) + 1] += 1
        end
        s = 0
        for k in 1:256
            c = compte[k]
            compte[k] = s
            s += c
        end
        for i in 1:m
            k = Int((cles[i] >> decal) & 0xff) + 1
            compte[k] += 1
            tmp[compte[k]] = cles[i]
        end
        cles, tmp = tmp, cles
    end

    @inbounds for i in 1:m
        u = cles[i]
        w = (u & 0x8000_0000_0000_0000) != 0 ? u & ~0x8000_0000_0000_0000 : ~u
        v[i] = reinterpret(Float64, w)
    end
    @inbounds for i in (m + 1):n
        v[i] = NaN
    end
    v
end
""",
    bad="""# BAD: le retournement ne traite pas les negatifs. On inverse le bit de signe
# pour tout le monde, ce qui envoie bien les negatifs avant les positifs -- mais
# ENTRE EUX les negatifs sortent a l'envers, du plus petit en module au plus
# grand. Sur un tableau de positifs, le tri est parfait.
@inline cle(x::Float64) = reinterpret(UInt64, x) ⊻ 0x8000_0000_0000_0000

function fsort!(v::Vector{Float64})
    n = length(v)
    n <= 1 && return v

    j = 0
    nan = 0
    @inbounds for i in 1:n
        if isnan(v[i])
            nan += 1
        else
            j += 1
            v[j] = v[i]
        end
    end
    m = j

    cles = Vector{UInt64}(undef, m)
    @inbounds for i in 1:m
        cles[i] = cle(v[i])
    end

    tmp = Vector{UInt64}(undef, m)
    compte = Vector{Int}(undef, 256)
    @inbounds for passe in 0:7
        decal = 8 * passe
        fill!(compte, 0)
        for i in 1:m
            compte[Int((cles[i] >> decal) & 0xff) + 1] += 1
        end
        s = 0
        for k in 1:256
            c = compte[k]
            compte[k] = s
            s += c
        end
        for i in 1:m
            k = Int((cles[i] >> decal) & 0xff) + 1
            compte[k] += 1
            tmp[compte[k]] = cles[i]
        end
        cles, tmp = tmp, cles
    end

    @inbounds for i in 1:m
        v[i] = reinterpret(Float64, cles[i] ⊻ 0x8000_0000_0000_0000)
    end
    @inbounds for i in (m + 1):n
        v[i] = NaN
    end
    v
end
""",
    checks="""using .Sol: fsort!

meme(a, b) = length(a) == length(b) && all(isequal(a[i], b[i]) for i in eachindex(a))

let v = [3.0, -1.0, 2.5, -7.25, 0.0, 10.0, -3.5]
    @assert meme(fsort!(copy(v)), sort(v))       "les negatifs sortent a l'envers : $(fsort!(copy(v)))"
end

let v = [0.0, -0.0, 0.0, -0.0]
    @assert meme(fsort!(copy(v)), sort(v))       "-0.0 doit preceder +0.0 (isless(-0.0, 0.0) est vrai)"
end

let v = [1.0, Inf, -Inf, 0.0, -0.0, 5e-324, -5e-324, 2.2250738585072014e-308]
    @assert meme(fsort!(copy(v)), sort(v))       "infinis et sous-normaux"
end

let v = [1.0, NaN, -1.0, NaN, 0.0]
    r = fsort!(copy(v))
    @assert meme(r[1:3], [-1.0, 0.0, 1.0])       "partie non-NaN mal triee : $(r[1:3])"
    @assert all(isnan, r[4:5])                   "les NaN doivent finir a la fin, apres +Inf"
end

let v = [-1.0, NaN, -Inf, Inf]
    r = fsort!(copy(v))
    @assert isequal(r[1], -Inf) && isequal(r[2], -1.0) && isequal(r[3], Inf) && isnan(r[4])  "NaN apres +Inf"
end

let v = fill(4.0, 100)
    @assert meme(fsort!(copy(v)), v)             "tableau constant"
end

@assert meme(fsort!(Float64[]), Float64[])       "tableau vide"
@assert meme(fsort!([2.0]), [2.0])               "tableau a un element"

let v = [(-1.0)^i * (i^3 / 7.0) for i in 1:200000]
    @assert meme(fsort!(copy(v)), sort(v))       "200000 valeurs des deux signes"
end

let v = fsort!([3.0, 1.0, 2.0])
    @assert v == [1.0, 2.0, 3.0]                 "fsort! doit trier EN PLACE et rendre le tableau"
end
""")

# ------------------------------------------------------- t34 primalite 64 bits
T["t34"] = dict(
    externe=True,
    enonce="""Implement `isprime64(n::Integer) -> Bool`, a DETERMINISTIC primality test valid
for every `n` in `0 <= n < 2^63`. No probabilistic answer is acceptable: the same `n`
must always give the same verdict, and that verdict must be right for every input in
the range.

Use a Miller-Rabin test over a fixed set of bases that is proven sufficient for the
whole 64-bit range. Two things decide whether this works:

- the SET OF BASES. A short set passes every small test and then fails on a number
  chosen to fool exactly those bases. For instance 3215031751 is a strong
  pseudoprime to bases 2, 3, 5 AND 7 simultaneously -- a test using only those four
  declares it prime, and it is 151 * 751 * 28351.
- the MODULAR MULTIPLICATION. Squaring a residue near 2^62 overflows `Int64` and
  `UInt64` silently, and the test then answers nonsense on exactly the large inputs it
  exists for. The multiplication must be done in a width that cannot overflow.

`isprime64(0)`, `isprime64(1)` and negatives are `false`; `isprime64(2)` is `true`.""",
    ref="""@inline function mulmod(a::UInt64, b::UInt64, m::UInt64)
    UInt64(mod(widemul(a, b), UInt128(m)))
end

function powmod(a::UInt64, e::UInt64, m::UInt64)
    r = UInt64(1)
    a %= m
    while e > 0
        if (e & 0x1) == 1
            r = mulmod(r, a, m)
        end
        a = mulmod(a, a, m)
        e >>= 1
    end
    r
end

# Jeu de temoins suffisant pour tout n < 3.3e24, donc a fortiori sur 64 bits.
const TEMOINS = UInt64[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]

function isprime64(n::Integer)
    n < 2 && return false
    m = UInt64(n)
    for p in TEMOINS
        m == p && return true
        m % p == 0 && return false
    end
    d = m - 1
    r = 0
    while (d & 0x1) == 0
        d >>= 1
        r += 1
    end
    for a in TEMOINS
        x = powmod(a, d, m)
        (x == 1 || x == m - 1) && continue
        compose = true
        for _ in 1:(r - 1)
            x = mulmod(x, x, m)
            if x == m - 1
                compose = false
                break
            end
        end
        compose && return false
    end
    true
end
""",
    bad="""@inline function mulmod(a::UInt64, b::UInt64, m::UInt64)
    UInt64(mod(widemul(a, b), UInt128(m)))
end

function powmod(a::UInt64, e::UInt64, m::UInt64)
    r = UInt64(1)
    a %= m
    while e > 0
        if (e & 0x1) == 1
            r = mulmod(r, a, m)
        end
        a = mulmod(a, a, m)
        e >>= 1
    end
    r
end

# BAD: jeu de temoins tronque. Suffisant jusqu'a 3215031751 exclu -- et
# 3215031751 est justement pseudo-premier fort pour ces quatre bases a la fois.
const TEMOINS = UInt64[2, 3, 5, 7]

function isprime64(n::Integer)
    n < 2 && return false
    m = UInt64(n)
    for p in TEMOINS
        m == p && return true
        m % p == 0 && return false
    end
    d = m - 1
    r = 0
    while (d & 0x1) == 0
        d >>= 1
        r += 1
    end
    for a in TEMOINS
        x = powmod(a, d, m)
        (x == 1 || x == m - 1) && continue
        compose = true
        for _ in 1:(r - 1)
            x = mulmod(x, x, m)
            if x == m - 1
                compose = false
                break
            end
        end
        compose && return false
    end
    true
end
""",
    checks="""using .Sol: isprime64

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
""")

# --------------------------------------------------------- t35 intervalles
T["t35"] = dict(
    externe=False,
    enonce="""Implement interval arithmetic with a GUARANTEED containment property.

Define `struct Iv` with fields `lo::Float64` and `hi::Float64` in that order and the
constructor `Iv(lo, hi)`, which must reject `lo > hi`. Implement `+`, `-`, `*`, `/`
between two `Iv`, and `contient(a::Iv, x::Real)`.

The contract that must hold, and that ordinary floating point breaks:

    if x is in a and y is in b, then x OP y is in (a OP b)

for every representable x and y. Because a floating point result is rounded to the
nearest value, computing the bounds directly loses the guarantee: the true result can
fall just outside the computed interval. The bounds must therefore be widened
OUTWARDS -- the lower one downwards, the upper one upwards.

Multiplication is the other trap: when the intervals straddle zero, the extreme
products are not `lo*lo` and `hi*hi`. All four corner products have to be considered.

Division by an interval that contains zero must throw an `ArgumentError`.""",
    ref="""struct Iv
    lo::Float64
    hi::Float64
    function Iv(lo::Real, hi::Real)
        l, h = Float64(lo), Float64(hi)
        l > h && throw(ArgumentError("intervalle vide : lo > hi"))
        new(l, h)
    end
end

@inline bas(x::Float64) = isfinite(x) ? prevfloat(x) : x
@inline haut(x::Float64) = isfinite(x) ? nextfloat(x) : x

contient(a::Iv, x::Real) = a.lo <= x <= a.hi

Base.:+(a::Iv, b::Iv) = Iv(bas(a.lo + b.lo), haut(a.hi + b.hi))
Base.:-(a::Iv, b::Iv) = Iv(bas(a.lo - b.hi), haut(a.hi - b.lo))

function Base.:*(a::Iv, b::Iv)
    p = (a.lo * b.lo, a.lo * b.hi, a.hi * b.lo, a.hi * b.hi)
    Iv(bas(minimum(p)), haut(maximum(p)))
end

function Base.:/(a::Iv, b::Iv)
    (b.lo <= 0.0 <= b.hi) && throw(ArgumentError("division par un intervalle contenant zero"))
    p = (a.lo / b.lo, a.lo / b.hi, a.hi / b.lo, a.hi / b.hi)
    Iv(bas(minimum(p)), haut(maximum(p)))
end
""",
    bad="""struct Iv
    lo::Float64
    hi::Float64
    function Iv(lo::Real, hi::Real)
        l, h = Float64(lo), Float64(hi)
        l > h && throw(ArgumentError("intervalle vide : lo > hi"))
        new(l, h)
    end
end

@inline bas(x::Float64) = isfinite(x) ? prevfloat(x) : x
@inline haut(x::Float64) = isfinite(x) ? nextfloat(x) : x

contient(a::Iv, x::Real) = a.lo <= x <= a.hi

Base.:+(a::Iv, b::Iv) = Iv(bas(a.lo + b.lo), haut(a.hi + b.hi))
Base.:-(a::Iv, b::Iv) = Iv(bas(a.lo - b.hi), haut(a.hi - b.lo))

# BAD: seulement deux coins sur quatre. Exact tant que les deux intervalles sont
# positifs -- donc tous les exemples de la documentation passent.
Base.:*(a::Iv, b::Iv) = Iv(bas(a.lo * b.lo), haut(a.hi * b.hi))

function Base.:/(a::Iv, b::Iv)
    (b.lo <= 0.0 <= b.hi) && throw(ArgumentError("division par un intervalle contenant zero"))
    p = (a.lo / b.lo, a.lo / b.hi, a.hi / b.lo, a.hi / b.hi)
    Iv(bas(minimum(p)), haut(maximum(p)))
end
""",
    checks="""using .Sol: Iv, contient

@assert contient(Iv(1.0, 2.0), 1.5)              "contient"
@assert !contient(Iv(1.0, 2.0), 2.5)             "contient : hors bornes"

let ok = false
    try
        Iv(2.0, 1.0)
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "lo > hi doit lever ArgumentError"
end

# arrondi vers l'exterieur : le resultat exact n'est PAS representable
let s = Iv(0.1, 0.1) + Iv(0.2, 0.2)
    @assert s.lo < 0.1 + 0.2 < s.hi              "les bornes ne sont pas elargies vers l'exterieur : [$(s.lo), $(s.hi)]"
end

# le piege du produit : quatre coins, pas deux
let p = Iv(-2.0, 3.0) * Iv(-5.0, 7.0)
    @assert p.lo <= -15.0                        "produit sur deux coins au lieu de quatre : lo = $(p.lo), il faut <= -15"
    @assert p.hi >= 21.0                         "produit sur deux coins au lieu de quatre : hi = $(p.hi), il faut >= 21"
end

let p = Iv(-3.0, -1.0) * Iv(-4.0, -2.0)
    @assert p.lo <= 2.0 && p.hi >= 12.0          "produit de deux intervalles negatifs : [$(p.lo), $(p.hi)], il faut contenir [2, 12]"
end

let p = Iv(-1.0, 1.0) * Iv(-1.0, 1.0)
    @assert p.lo <= -1.0 && p.hi >= 1.0          "produit de deux intervalles a cheval sur zero"
end

# confinement, teste sur des points reels des intervalles
let a = Iv(-2.0, 3.0), b = Iv(-5.0, 7.0)
    s, d, p = a + b, a - b, a * b
    for i in 0:40, j in 0:40
        x = a.lo + (a.hi - a.lo) * i / 40
        y = b.lo + (b.hi - b.lo) * j / 40
        @assert contient(s, x + y)               "x+y = $(x+y) sort de la somme"
        @assert contient(d, x - y)               "x-y = $(x-y) sort de la difference"
        @assert contient(p, x * y)               "x*y = $(x*y) sort du produit [$(p.lo), $(p.hi)]"
    end
end

# la dependance : a - a contient zero et n'est PAS reduit a zero
let d = Iv(1.0, 2.0) - Iv(1.0, 2.0)
    @assert contient(d, 0.0)                     "a - a doit contenir zero"
    @assert d.lo <= -1.0 && d.hi >= 1.0          "a - a vaut [-1, 1] : les deux occurrences sont independantes"
end

let ok = false
    try
        Iv(1.0, 2.0) / Iv(-1.0, 1.0)
    catch e
        ok = isa(e, ArgumentError)
    end
    @assert ok                                   "diviser par un intervalle contenant zero doit lever"
end

let q = Iv(1.0, 2.0) / Iv(2.0, 4.0)
    @assert q.lo <= 0.25 && q.hi >= 1.0          "quotient : [$(q.lo), $(q.hi)] doit contenir [0.25, 1]"
end
""")

# ------------------------------------------------- t36 vecteur persistant
T["t36"] = dict(
    externe=False,
    enonce="""Implement a PERSISTENT vector: every operation returns a new version and no
previous version is ever modified.

    PVec()                  the empty vector
    plength(v)              its length
    ppush(v, x)             a new version with `x` appended
    pget(v, i)              the i-th element, 1-based, `BoundsError` outside 1:plength(v)
    pset(v, i, x)           a new version whose i-th element is `x`

The requirement that makes this hard is not correctness -- copying the whole thing on
every operation is correct. It is STRUCTURAL SHARING: two consecutive versions must
share almost all of their storage, so that keeping N successive versions alive costs
O(N log N) memory rather than O(N^2).

The usual way is a tree of small fixed-width nodes (32 children is the common choice):
an update rebuilds only the nodes along one path from the root to the touched leaf and
reuses every other node. `pget` and `pset` then cost O(log N).

Keeping 10000 successive versions of a 10000-element vector alive must cost a few tens
of megabytes, not the four hundred that copying would.""",
    ref="""const BITS = 5
const LARG = 1 << BITS
const MASQ = LARG - 1

struct Noeud
    fils::Vector{Any}
end

struct PVec
    n::Int
    prof::Int          # la racine couvre LARG^prof elements
    racine::Union{Noeud,Nothing}
end

PVec() = PVec(0, 1, nothing)
plength(v::PVec) = v.n

function pget(v::PVec, i::Int)
    (1 <= i <= v.n) || throw(BoundsError(v, i))
    k = i - 1
    nd = v.racine
    for niveau in (v.prof - 1):-1:1
        nd = nd.fils[((k >> (BITS * niveau)) & MASQ) + 1]
    end
    nd.fils[(k & MASQ) + 1]
end

function assoc(nd, k::Int, niveau::Int, x)
    idx = ((k >> (BITS * niveau)) & MASQ) + 1
    f = nd === nothing ? Vector{Any}(undef, 0) : copy(nd.fils)
    while length(f) < idx
        push!(f, nothing)
    end
    if niveau == 0
        f[idx] = x
    else
        f[idx] = assoc(f[idx], k, niveau - 1, x)
    end
    Noeud(f)
end

function ppush(v::PVec, x)
    if v.n == LARG^v.prof
        v = PVec(v.n, v.prof + 1, Noeud(Any[v.racine]))
    end
    PVec(v.n + 1, v.prof, assoc(v.racine, v.n, v.prof - 1, x))
end

function pset(v::PVec, i::Int, x)
    (1 <= i <= v.n) || throw(BoundsError(v, i))
    PVec(v.n, v.prof, assoc(v.racine, i - 1, v.prof - 1, x))
end
""",
    bad="""# BAD: persistant et CORRECT -- mais chaque version recopie tout le tableau.
# Aucun partage de structure : garder N versions coute O(N^2).
struct PVec
    v::Vector{Any}
end

PVec() = PVec(Any[])
plength(v::PVec) = length(v.v)

function pget(v::PVec, i::Int)
    (1 <= i <= length(v.v)) || throw(BoundsError(v, i))
    v.v[i]
end

ppush(v::PVec, x) = PVec(push!(copy(v.v), x))

function pset(v::PVec, i::Int, x)
    (1 <= i <= length(v.v)) || throw(BoundsError(v, i))
    w = copy(v.v)
    w[i] = x
    PVec(w)
end
""",
    checks="""using .Sol: PVec, plength, ppush, pget, pset

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

ecrire(os.path.join(BASE, "tasks", "limite_faits_externes.txt"), "\n".join(ext) + "\n")

print("palier limite ecrit : %d taches (t31..t36), 4 fichiers chacune" % n)
print("  a fait externe (le web peut aider) : %s" % ", ".join(ext))
print("  temoins sans fait externe          : %s" % ", ".join(sorted(set(T) - set(ext))))
