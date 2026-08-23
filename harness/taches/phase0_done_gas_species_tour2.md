Task (Julia, test-only, second turn): your previous edit of `test/physics/test_gas_species.jl` — the new testset `"GasSpecies Generic Helpers"` (about lines 43–122) — was run by the test gate and is RED: 107 passed, 3 failed, 3 errored. Fix it so the file is fully green. The gate output, verbatim:

```
Error During Test at test_gas_species.jl:99
  Expression: is_inelastic(_StubProcess(:stub, 5.0f0, INELASTIC))
  MethodError: no method matching process_type(::Main.Porte1._StubProcess)
Error During Test at test_gas_species.jl:100
  Expression: !(is_inelastic(_StubProcess(:stub, 0.0f0, ELASTIC)))
  MethodError: no method matching process_type(::Main.Porte1._StubProcess)
Test Failed at test_gas_species.jl:105
  Expression: occursin(":attachment", sprint(showerror, err))
   Evaluated: occursin(":attachment", "Test Passed\n      Thrown: ErrorException")
Test Failed at test_gas_species.jl:106
  Expression: occursin("ArGas", sprint(showerror, err))
   Evaluated: occursin("ArGas", "Test Passed\n      Thrown: ErrorException")
Test Failed at test_gas_species.jl:108
  Expression: get_process(_StubGas(_StubProcess[]), :anything)
    Expected: ErrorException
      Thrown: MethodError: no method matching collision_processes(::Main.Porte1._StubGas)
Error During Test at test_gas_species.jl:44
  MethodError: no method matching mass(::Main.Porte1._StubGas)
```

Diagnosis to act on:
1. Inside the testset, `symbol(p::_StubProcess) = ...`, `mass(g::_StubGas) = ...` etc. define NEW local functions; they do not add methods to the interface functions of `GasSpecies`. Qualify them: `Physics.GasSpecies.symbol(p::_StubProcess) = ...`, `Physics.GasSpecies.process_type(...)`, `Physics.GasSpecies.mass(...)`, `Physics.GasSpecies.ion_mass`, `Physics.GasSpecies.ion_charge`, `Physics.GasSpecies.collision_processes`, `Physics.GasSpecies.threshold`, `Physics.GasSpecies.energy_loss`, `Physics.GasSpecies.cross_section`. Note the file is included from a test runner where the module is reachable as `Physics` (you already use `Physics.GasSpecies.is_inelastic`). Check how the existing file refers to the module and follow it.
2. `err = @test_throws ErrorException f(...)` binds a `Test.Pass` result, not the exception. To inspect the message, catch it: `err = try; get_process(ar, :attachment); nothing; catch e; e; end` then `@test err isa ErrorException` and `@test occursin(":attachment", sprint(showerror, err))`.
3. If Julia refuses `struct` definitions inside the testset's local scope, move the two stub structs and their methods to top level of the file, just before `@testset "Physics Module Tests"`, guarded by `if !@isdefined(_StubProcess)` like the existing module guard.

Rules:
- Modify ONLY `test/physics/test_gas_species.jl`. Do not touch `src/`, do not create other files, do not run git commands.
- Do NOT run Julia yourself: the operator runs the gate after you finish.
- Keep the edit small: fix the listed lines, do not rewrite the rest of the testset or the file.
- When done, reply with the line numbers you changed and stop.
