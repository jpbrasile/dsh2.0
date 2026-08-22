struct CIStr
    s::String
end

Base.isequal(a::CIStr, b::CIStr) = isequal(lowercase(a.s), lowercase(b.s))
Base.:(==)(a::CIStr, b::CIStr) = isequal(a, b)
Base.hash(a::CIStr, h::UInt) = hash(lowercase(a.s), h)
