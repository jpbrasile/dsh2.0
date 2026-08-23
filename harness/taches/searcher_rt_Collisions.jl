module Collisions
using PlasmaDigitalTwin.Physics: State, Species

"""
    rate!(s::State, dt)

Advance the ionization balance of `s` by `dt` using a Maxwellian rate table.
"""
function rate!(s::State, dt)
    for sp in s.species
        k = rate_coefficient(sp, s.Te)
        sp.n += k * s.ne * sp.n0 * dt
    end
    return s
end

rate_coefficient(sp::Species, Te) = sp.A * sqrt(Te) * exp(-sp.E_ion / Te)

end # module
