using .Sol: mp_decode

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
