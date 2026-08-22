# -*- coding: utf-8 -*-
"""Ecrit le palier DUR du corpus : t11..t16, enonces + verificateurs + bras
known-GOOD et known-BAD.

Pourquoi ce palier existe : sur la campagne one-shot de 50 runs, SIX taches sur
dix n'ont jamais echoue, a aucun niveau d'effort. Une tache que tout le monde
reussit ne porte aucune information -- elle occupe une case et dilue le signal.
Les six ci-dessous visent des pieges qui, eux, separent :

  t11  instabilite numerique  -- la formule naive perd TOUT sur des grands nombres
  t12  allocations            -- correct mais alloue = echec, et il y a des vues
  t13  protocole d'iteration  -- implementer iterate ne suffit pas, length ment
  t14  contrat hash/isequal   -- definir == seul casse silencieusement les Dict
  t15  stabilite de type      -- un accumulateur en dur contamine le resultat
  t16  interface AbstractArray-- se sous-typer donne sum et * gratuitement, si l'index est bon

Chaque bras known-BAD porte UN defaut nomme, et c'est l'assertion qui le nomme
qui doit tomber -- pas une erreur generique. Un verificateur casse attrape 6/6
lui aussi ; ce qui distingue les deux, c'est PAR QUOI chacun tombe.

Ce script est un generateur, pas un livrable : il vit a cote du corpus pour que
les six taches restent modifiables ensemble plutot qu'a la main, une par une.
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

# ---------------------------------------------------------------- t11 Welford
T["t11"] = dict(
    enonce="""Define a mutable struct `Welford` with a zero-argument constructor `Welford()`
starting empty, a function `update!(w::Welford, x::Real)` that folds one more value in and
returns `w`, and a function `variance(w::Welford)` returning the SAMPLE variance (divide by
n-1) of every value pushed so far, or 0.0 when fewer than two values have been pushed.

`Welford` must NOT store the values: none of its fields may be an array, and its memory must
not grow with the number of updates. The result must stay accurate when the values are large
and close together -- computing the variance from the running sum and the running sum of
squares loses all precision there and is not acceptable.""",
    ref="""mutable struct Welford
    n::Int
    mean::Float64
    m2::Float64
    Welford() = new(0, 0.0, 0.0)
end

function update!(w::Welford, x::Real)
    w.n += 1
    d = x - w.mean
    w.mean += d / w.n
    w.m2 += d * (x - w.mean)
    w
end

variance(w::Welford) = w.n < 2 ? 0.0 : w.m2 / (w.n - 1)
""",
    bad="""mutable struct Welford
    n::Int
    s::Float64
    s2::Float64
    Welford() = new(0, 0.0, 0.0)
end

function update!(w::Welford, x::Real)
    w.n += 1
    w.s += x
    w.s2 += x * x
    w
end

# BAD: somme des carres -- annulation catastrophique sur de grandes valeurs
variance(w::Welford) = w.n < 2 ? 0.0 : (w.s2 - w.s^2 / w.n) / (w.n - 1)
""",
    checks="""using .Sol: Welford, update!, variance

let w = Welford()
    for x in (1.0, 2.0, 3.0, 4.0); update!(w, x); end
    @assert isapprox(variance(w), 5/3; rtol=1e-12)  "variance simple"
end

let w = Welford()
    @assert variance(w) == 0.0                      "aucune valeur"
    update!(w, 3.0)
    @assert variance(w) == 0.0                      "une seule valeur"
end

let w = Welford()
    for x in (1e8, 1e8 + 1.0, 1e8 + 2.0); update!(w, x); end
    v = variance(w)
    @assert isapprox(v, 1.0; rtol=1e-9)             "annulation catastrophique : variance = $v au lieu de 1.0"
end

@assert !any(t -> t <: AbstractArray, fieldtypes(Welford))  "Welford stocke les valeurs"
""")

# ----------------------------------------------------------------- t12 axpy!
T["t12"] = dict(
    enonce="""Define `axpy!(y::AbstractVector, a::Number, x::AbstractVector)` which adds `a * x`
into `y` ELEMENTWISE AND IN PLACE, then returns `y` itself (the same object, not a copy).

It must allocate ZERO bytes when called on vectors of the same element type, it must work for
Float32 as well as Float64, and it must work when `y` or `x` is a `view` into a larger array.
Do not call BLAS.""",
    ref="""function axpy!(y::AbstractVector, a::Number, x::AbstractVector)
    length(y) == length(x) || throw(DimensionMismatch("axpy!"))
    @inbounds @simd for i in eachindex(y, x)
        y[i] += a * x[i]
    end
    y
end
""",
    bad="""# BAD: construit un nouveau vecteur, n'ecrit rien dans y, et alloue
axpy!(y::AbstractVector, a::Number, x::AbstractVector) = y + a * x
""",
    checks="""using .Sol: axpy!

let y = [1.0, 2.0, 3.0], x = [10.0, 20.0, 30.0]
    r = axpy!(y, 2.0, x)
    @assert y == [21.0, 42.0, 63.0]   "axpy! doit ecrire DANS y, y vaut $y"
    @assert r === y                   "axpy! doit rendre y lui-meme"
end

let y = Float32[1, 2], x = Float32[3, 4]
    axpy!(y, 2.0f0, x)
    @assert y == Float32[7, 10]       "Float32"
end

let Y = zeros(200), X = ones(200)
    axpy!(view(Y, 1:100), 3.0, view(X, 51:150))
    @assert all(Y[1:100] .== 3.0) && all(Y[101:200] .== 0.0)  "vues"
end

let y = rand(1000), x = rand(1000)
    axpy!(y, 1.5, x)                  # rechauffe la compilation
    a = @allocated axpy!(y, 1.5, x)
    @assert a == 0                    "axpy! alloue $a octets, il en faut 0"
end
""")

# ---------------------------------------------------------------- t13 Chunks
T["t13"] = dict(
    enonce="""Define `struct Chunks{V<:AbstractVector}` with fields `v::V` and `k::Int`, in that
order, holding a vector and a chunk size. Implement `Base.iterate`, `Base.length` and
`Base.eltype` so that iterating a `Chunks` yields the successive slices of `v` of length `k`,
the last one being shorter when `k` does not divide the length.

Each yielded chunk must be a `Vector`. `collect(Chunks(1:7, 3))` must give `[[1,2,3],[4,5,6],[7]]`,
`length` must equal the number of chunks actually produced, and `for c in Chunks(...)` must work.
Do not use `Iterators.partition`.""",
    ref="""struct Chunks{V<:AbstractVector}
    v::V
    k::Int
end

Base.length(c::Chunks) = cld(length(c.v), c.k)
Base.eltype(::Type{Chunks{V}}) where {V} = Vector{eltype(V)}

function Base.iterate(c::Chunks, i::Int=1)
    i > length(c.v) && return nothing
    j = min(i + c.k - 1, length(c.v))
    (collect(c.v[i:j]), j + 1)
end
""",
    bad="""struct Chunks{V<:AbstractVector}
    v::V
    k::Int
end

# BAD: div au lieu de cld -- le dernier morceau partiel n'est pas compte
Base.length(c::Chunks) = div(length(c.v), c.k)
Base.eltype(::Type{Chunks{V}}) where {V} = Vector{eltype(V)}

function Base.iterate(c::Chunks, i::Int=1)
    i > length(c.v) && return nothing
    j = min(i + c.k - 1, length(c.v))
    (collect(c.v[i:j]), j + 1)
end
""",
    checks="""using .Sol: Chunks

@assert collect(Chunks(1:7, 3)) == [[1,2,3],[4,5,6],[7]]  "decoupage"
@assert length(Chunks(1:7, 3)) == 3                       "length : $(length(Chunks(1:7,3))) au lieu de 3"
@assert length(Chunks(1:10, 4)) == length(collect(Chunks(1:10, 4)))  "length ne suit pas collect"

let n = 0
    for _ in Chunks(1:10, 4); n += 1; end
    @assert n == 3                                        "boucle for"
end

@assert collect(Chunks([5, 6], 5)) == [[5, 6]]            "k plus grand que le vecteur"
@assert eltype(Chunks(1:7, 3)) <: AbstractVector          "eltype"
""")

# ----------------------------------------------------------------- t14 CIStr
T["t14"] = dict(
    enonce="""Define `struct CIStr` with a single field `s::String`, a string wrapper that compares
WITHOUT regard to case. Two `CIStr` holding the same letters in different cases must be fully
interchangeable: as `Dict` keys, as `Set` members, and under `isequal`.""",
    ref="""struct CIStr
    s::String
end

Base.isequal(a::CIStr, b::CIStr) = isequal(lowercase(a.s), lowercase(b.s))
Base.:(==)(a::CIStr, b::CIStr) = isequal(a, b)
Base.hash(a::CIStr, h::UInt) = hash(lowercase(a.s), h)
""",
    bad="""struct CIStr
    s::String
end

# BAD: == seul. Dict et Set indexent par hash : deux valeurs egales dont les
# hash different ne se retrouvent jamais.
Base.:(==)(a::CIStr, b::CIStr) = lowercase(a.s) == lowercase(b.s)
""",
    checks="""using .Sol: CIStr

@assert isequal(CIStr("aB"), CIStr("Ab"))              "isequal insensible a la casse"
@assert hash(CIStr("aB")) == hash(CIStr("Ab"))         "hash doit suivre isequal"
@assert !isequal(CIStr("a"), CIStr("b"))               "chaines vraiment differentes"

let d = Dict(CIStr("Foo") => 1)
    @assert haskey(d, CIStr("FOO"))                    "cle de Dict interchangeable"
    @assert d[CIStr("FOO")] == 1                       "valeur retrouvee"
end

@assert length(Set([CIStr("x"), CIStr("X")])) == 1     "Set doit dedupliquer"
""")

# ---------------------------------------------------------------- t15 horner
T["t15"] = dict(
    enonce="""Define `horner(x::Number, c::AbstractVector)` evaluating the polynomial
`c[1] + c[2]*x + c[3]*x^2 + ...` by Horner's rule.

It must be TYPE STABLE: the element type must be carried through, so a Float32 point and
Float32 coefficients must give a `Float32` back, and integer inputs must give an integer back.
A hard-coded Float64 accumulator is not acceptable.""",
    ref="""function horner(x::Number, c::AbstractVector)
    T = promote_type(typeof(x), eltype(c))
    isempty(c) && return zero(T)
    s = convert(T, c[end])
    @inbounds for i in lastindex(c)-1:-1:firstindex(c)
        s = s * x + c[i]
    end
    s
end
""",
    bad="""function horner(x::Number, c::AbstractVector)
    s = 0.0                    # BAD: accumulateur Float64 en dur
    for i in length(c):-1:1
        s = s * x + c[i]
    end
    s
end
""",
    checks="""using .Sol: horner
using Test

@assert horner(2.0, [1.0, 2.0, 3.0]) == 17.0     "valeur"
@assert horner(3, [1, 0, 2]) == 19               "entiers"

let r = horner(2.0f0, Float32[1, 2, 3])
    @assert r isa Float32                        "Float32 doit rendre Float32, pas $(typeof(r))"
end

let r = horner(3, [1, 0, 2])
    @assert r isa Integer                        "entier doit rendre un entier, pas $(typeof(r))"
end

try
    @inferred horner(2.0f0, Float32[1, 2, 3])
catch e
    error("horner n'est pas de type stable : ", sprint(showerror, e))
end
""")

# ------------------------------------------------------------- t16 Circulant
T["t16"] = dict(
    enonce="""Define `struct Circulant{T} <: AbstractMatrix{T}` with a single field `c::Vector{T}`,
representing the n-by-n circulant matrix whose first COLUMN is `c`, that is
`A[i,j] == c[mod1(i - j + 1, n)]`.

Implement ONLY `Base.size` and `Base.getindex`. Do not define arithmetic, do not define `sum`,
and do not materialise a dense matrix inside the struct: `Matrix(A)`, `sum(A)` and `A * v` must
all work through the `AbstractArray` fallbacks, which they do once the subtyping and the two
methods are right.""",
    ref="""struct Circulant{T} <: AbstractMatrix{T}
    c::Vector{T}
end

Base.size(A::Circulant) = (length(A.c), length(A.c))
Base.getindex(A::Circulant, i::Int, j::Int) = A.c[mod1(i - j + 1, length(A.c))]
""",
    bad="""struct Circulant{T} <: AbstractMatrix{T}
    c::Vector{T}
end

Base.size(A::Circulant) = (length(A.c), length(A.c))
# BAD: i et j inverses -- on construit la transposee
Base.getindex(A::Circulant, i::Int, j::Int) = A.c[mod1(j - i + 1, length(A.c))]
""",
    checks="""using .Sol: Circulant

let c = [1, 2, 3], M = [1 3 2; 2 1 3; 3 2 1]
    A = Circulant(c)
    @assert A isa AbstractMatrix          "doit etre <: AbstractMatrix"
    @assert size(A) == (3, 3)             "size"
    @assert A[2, 1] == 2                  "A[2,1] vaut $(A[2,1]) au lieu de 2"
    @assert Matrix(A) == M                "matrice complete : $(Matrix(A))"
    @assert sum(A) == sum(M)              "sum par le fallback AbstractArray"
    @assert A * [1, 1, 1] == M * [1, 1, 1]  "produit matrice-vecteur"
end
""")


def ecrire(chemin, contenu):
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(contenu)
    os.replace(tmp, chemin)


n = 0
for nom in sorted(T):
    d = T[nom]
    ecrire(os.path.join(BASE, "prompts", "%s.txt" % nom),
           ENTETE + d["enonce"].strip() + "\n" + REGLES)
    ecrire(os.path.join(BASE, "tasks", "%s_checks.jl" % nom), d["checks"])
    ecrire(os.path.join(BASE, "ref", "%s.jl" % nom), d["ref"])
    ecrire(os.path.join(BASE, "bad", "%s.jl" % nom), d["bad"])
    n += 1
print("palier dur ecrit : %d taches (t11..t16), 4 fichiers chacune" % n)
