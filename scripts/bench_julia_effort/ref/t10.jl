struct Interval{T<:Real}
    lo::T
    hi::T
end
Interval(lo, hi) = Interval(promote(lo, hi)...)
Base.:+(a::Interval, b::Interval) = Interval(a.lo + b.lo, a.hi + b.hi)
function Base.:*(a::Interval, b::Interval)
    p = (a.lo*b.lo, a.lo*b.hi, a.hi*b.lo, a.hi*b.hi)
    Interval(minimum(p), maximum(p))
end
