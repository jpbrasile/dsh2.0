Task (Julia, test-only): extend `test/physics/test_gas_species.jl` with one new testset that covers the generic helpers of `src/physics/GasSpecies.jl` which no test exercises today.

Add, inside the top-level `@testset "Physics Module Tests"` block and just before its closing `end`, a testset named `"Display and error paths"` with exactly these checks, using `ar = create_argon()`:

1. `sprint(show, ar)` contains `"ArGas("` and `"processes)"`.
2. `sprint(show, ar.elastic)` contains `String(symbol(ar.elastic))` and `"ELASTIC"`.
3. `get_process(ar, :this_process_does_not_exist)` throws `ErrorException` (`@test_throws`).
4. `total_cross_section(ar, 20f0)` is approximately equal (`isapprox`, `rtol=1e-6`) to `sum(cross_section(p, 20f0) for p in collision_processes(ar))`.
5. `is_inelastic(first(ar.excitations))` is true and `is_inelastic(ar.elastic)` is false; `creates_negative_ion(ar.elastic)` is false.

Rules:
- Read the two files first (`src/physics/GasSpecies.jl` for the helper definitions and the `Base.show` methods, the test file for its style). Match the existing 4-space indentation and testset style.
- Modify ONLY `test/physics/test_gas_species.jl`. Do not touch `src/`, do not create other files, do not run git commands.
- Do NOT run Julia yourself: the test gate is run by the operator after you finish.
- When the edit is done, reply with the exact line numbers of the inserted block and stop.
