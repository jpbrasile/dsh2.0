sumsq(n::Integer) = sum(i^2 for i in 1:n-1; init=0)   # BAD: off-by-one
