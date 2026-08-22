using .Sol: sumsq
@assert sumsq(10) == 385   "sumsq(10)"
@assert sumsq(1)  == 1     "sumsq(1)"
@assert sumsq(0)  == 0     "sumsq(0)"
@assert sumsq(100) == 338350 "sumsq(100)"
@assert sumsq(1000) == 333833500 "sumsq(1000)"
