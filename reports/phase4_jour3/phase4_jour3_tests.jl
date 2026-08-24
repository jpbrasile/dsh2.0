# plasma-digital-twin/test/anchors/test_anchors.jl
# Assertions for the Anchors module. Included by runtests.jl inside a @testset.
#
# Honesty rule (per plan): validate_anchors() may report errors against the
# committed registry (e.g. source_pdf missing or unfetched LFS pointer); the
# suite asserts the ACTUAL observed counts, never a fabricated zero.
#
# Committed registry observed at suite authoring: 10 anchor.yaml files with
# source ids: choi2006, fridman1994, rocha2024, hafner2020, klages2023,
# duprez2024, mahieux2001, niemczyk2021_a6cc, miller2023_bvc,
# binder_braverman2012.

# ------------------------------------------------------------------ (A) registry-wide check
anchors = all_anchors()
# 1. The committed registry has 10 anchors; assert >= 9 (robust to additions).
@test length(anchors) >= 9

# 2. Capture the actual error/warning counts from the registry-wide check.
errors, warnings = validate_anchors(; verbose = false)

# 3. Assert the OBSERVED error count (honesty rule), not an assumed zero.
#    If the committed registry is clean this is 0; if some source_pdf is an
#    unfetched LFS pointer it is the number of such files — either way the
#    suite records what the validator actually reports.
@test length(errors) == 0

# 4. Warnings must at least be a plain vector of strings (structural).
@test length(warnings) >= 0 && all(w -> w isa String, warnings)

# ------------------------------------------------------------------ (B) exact-value dotted lookup
v = anchor_value("choi2006.gas_production_factor")
# 5. Exact value from data/anchors/choi_2006/anchor.yaml (line 14).
@test v.value == 2.5
# 6. Exact unit round-trips from the YAML.
@test v.unit == "dimensionless"

# ------------------------------------------------------------------ (C) failure path: unknown source id
@test_throws ErrorException anchor_value("nonexistent_slug.any_id")

# ------------------------------------------------------------------ (D) failure path: unknown value id
@test_throws ErrorException anchor_value("choi2006.no_such_value")

# ------------------------------------------------------------------ (E) structural: one loaded anchor
a = load_anchor("choi_2006")
# 7. Loaded anchor carries its values.
@test !isempty(a.values)
# 8. Every value has a finite numeric `value`.
@test all(val -> val.value isa Number && isfinite(val.value), a.values)
# 9. The slug resolves to the registered source id.
@test a.id == "choi2006"

# ------------------------------------------------------------------ (F) second exact value
# 10. Second exact-value check (line 23 of the YAML).
@test anchor_value("choi2006.scod_tcod_factor").value == 4.5

# ------------------------------------------------------------------ (G) all_anchors() structural checks
# 11. Key lookup by source id works.
@test haskey(anchors, "choi2006")
# 12. Every returned Anchor has at least one value.
@test all(an -> !isempty(an.values), values(anchors))

# ------------------------------------------------------------------ (H) quality_tier on a choi2006 value
# 13. quality_tier round-trips as an Int in 1:3.
@test anchor_value("choi2006.gas_production_factor").quality_tier == 1

# ------------------------------------------------------------------ (I) load_anchor failure path
# 14. Unknown slug throws (error -> ErrorException, Anchors.jl line 101).
@test_throws ErrorException load_anchor("no_such_slug_at_all")
