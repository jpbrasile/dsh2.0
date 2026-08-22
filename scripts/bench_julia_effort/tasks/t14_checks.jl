using .Sol: CIStr

@assert isequal(CIStr("aB"), CIStr("Ab"))              "isequal insensible a la casse"
@assert hash(CIStr("aB")) == hash(CIStr("Ab"))         "hash doit suivre isequal"
@assert !isequal(CIStr("a"), CIStr("b"))               "chaines vraiment differentes"

let d = Dict(CIStr("Foo") => 1)
    @assert haskey(d, CIStr("FOO"))                    "cle de Dict interchangeable"
    @assert d[CIStr("FOO")] == 1                       "valeur retrouvee"
end

@assert length(Set([CIStr("x"), CIStr("X")])) == 1     "Set doit dedupliquer"
