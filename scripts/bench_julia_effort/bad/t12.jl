# BAD: construit un nouveau vecteur, n'ecrit rien dans y, et alloue
axpy!(y::AbstractVector, a::Number, x::AbstractVector) = y + a * x
