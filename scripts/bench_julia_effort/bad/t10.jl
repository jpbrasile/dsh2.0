struct Interval{T<:Real}; lo::T; hi::T; end
Interval(lo,hi) = Interval(promote(lo,hi)...)
Base.:+(a::Interval,b::Interval) = Interval(a.lo+b.lo, a.hi+b.hi)
Base.:*(a::Interval,b::Interval) = Interval(a.lo*b.lo, a.hi*b.hi)   # BAD: signes
