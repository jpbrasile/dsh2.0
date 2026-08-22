struct CIStr
    s::String
end

# BAD: == seul. Dict et Set indexent par hash : deux valeurs egales dont les
# hash different ne se retrouvent jamais.
Base.:(==)(a::CIStr, b::CIStr) = lowercase(a.s) == lowercase(b.s)
