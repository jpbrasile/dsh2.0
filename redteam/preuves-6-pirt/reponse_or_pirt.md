Looking at the provided code against the claims, here are my findings:

## HIGH SEVERITY

### P2: BROKEN - HIGH
**Claim says**: ANY invalid JSONL line => exit 2 and NOTHING is written.
**Reality**: The `lire_evenements()` function calls `sys.exit(2)` on invalid lines, but it has already read all lines including the invalid one into memory. The critical issue is that **reading and validation happen before any writing** — the code loads ALL events first (`evenements = lire_evenements(jsonl)`), then writes. So if line N is invalid, the program exits at line N without writing anything. This part WORKS.

**However**, there's a second write path: `ecrire_sqlite()` first calls `os.remove(chemin)` to delete the old sqlite file BEFORE the new data is written:
```python
if os.path.exists(chemin):
    os.remove(chemin)  # cache DERIVE cree par ce script -- la source est le JSONL
```
If the program crashes AFTER this `os.remove()` but BEFORE completing the sqlite write, the old cache is destroyed and nothing new is created. But this only matters if the crash happens during sqlite writing, not during validation.

**The actual bug that falsifies P2**: The validation check is:
```python
if manquants or e["type"] not in TYPES or not isinstance(e["donnees"], dict):
```
If `e["donnees"]` is `None` (a valid JSON value), `isinstance(None, dict)` returns `False`, triggering exit 2. But `None` is JSON-valid. The claim says "ANY invalid JSONL line... nothing is written" — but what about lines that are valid JSON but have semantic issues like empty strings for required fields or zero-length strings? The validation doesn't check that `"date"`, `"phenomene"`, `"source"` are non-empty strings.

**Failure scenario**: A line like `{"date":"", "phenomene":"P1", "type":"audit_mutation", "donnees":{"constante":"X"}, "source":""}` passes validation (all required fields present, donnees is a dict, type is valid) and gets written to sqlite, despite having empty required fields. This contradicts P2's "ANY invalid JSONL line... exit 2".

### P4: BROKEN - HIGH
**Claim says**: Priority sort = importance DESC, couverture ASC, portee ASC, confiance ASC.
**Reality in `cle_priorite()`**:
```python
return (0 if imp is not None else 1, -(imp or 0), etat["couverture"],
        PORTEES[etat["portee"]], CONFIANCES[etat["confiance_vv"]], phen)
```

**Bug 1**: `-(imp or 0)` — when `imp` is `None`, `imp or 0` evaluates to `0`, so `-0` = `0`. When `imp` is 1, 2, or 3, we get -1, -2, -3 respectively. The first tuple element handles NULL-last, but then `-(imp or 0)` puts ALL non-NULL values in negative territory. Since Python sorts tuples lexicographically, and the first element is 0 for non-NULL and 1 for NULL, non-NULL values get sorted by the SECOND element (-3 < -2 < -1), which means importance 3 first, then 2, then 1. This IS importance DESC. ✓

**But**: `COVERAGE ASC` — this means LOWER coverage first. The third tuple element is `etat["couverture"]` (raw float, not negated). Since positive numbers sort ascending, lower coverage values come first. This matches "couverture ASC". ✓

**Portee ASC**: `PORTEES[etat["portee"]]` maps `"aucune":0, "litteral":1, "ancres":2`. ASC means 0 first, then 1, then 2. So "aucune" first, "litteral" second, "ancres" last. This IS portee ASC. ✓

**Confiance ASC**: `CONFIANCES[etat["confiance_vv"]]` maps `"aucune":0, "triage":1, "validee":2`. ASC means 0 first, then 1, then 2. "aucune" first, "triage" second, "validee" last. ✓

**HOWEVER — The claim also says** "couverture = constants whose LATEST mutation event has bite=true / constants tried (latest event per (phenomene, constante) wins)".

**Bug in `calculer_etat()`**: 
```python
dernier_par_constante = {}
for e in evs:
    if e["type"] == "audit_mutation":
        dernier_par_constante[e["donnees"].get("constante", "?")] = e
```
This iterates in date+ordre order and overwrites, so the LAST `audit_mutation` per constante wins based on date/ordre. But the code doesn't distinguish between `bite: true` and `bite: false` for the "latest event wins" logic. If the latest event for a constante has `bite: false`, it overwrites a previous `bite: true`. This matches "latest event wins" — but the claim also says "no-bite closed by a reinforcement proof counts as covered". This isn't implemented — only `bite is True` is counted in `attrapees`.

**Severity**: The claim about reinforcement proofs not being counted is a gap, making P4 PARTIAL for coverage calculation, but the sorting itself appears correct from the code. Actually, looking more carefully — the claim says "no-bite fermé par un renforcement prouvé compte comme couvert" (from the docstring), but the code has no mechanism to track reinforcement proofs or "fermé par renforcement". This is BROKEN relative to the claim, which explicitly mentions this case.

## MEDIUM SEVERITY

### P3: BROKEN - MEDIUM
**Claim says**: Machine NEVER computes or writes `importance`, only reads from phenomenes.yaml; value outside {1,2,3,empty} => exit 2.

**Verification**: In `lire_phenomenes()`:
```python
if imp is not None and imp not in (1, 2, 3):
    print("phenomenes.yaml : importance invalide %r pour %s (admis: 1..3 ou vide)" % (imp, p.get("id")))
    sys.exit(2)
```
This validates importance. ✓

But the `generer_bloc()` function writes importance values to PIRT.md:
```python
lignes.append("| %s | %s | %.2f | %s | %s | %s | %s | %d |" % (
    phen, imp if imp is not None else "--", ...
```
And `ecrire_sqlite()` writes importance to the database:
```python
c.execute("INSERT INTO phenomenes VALUES (?,?,?,?,?,?)",
          (pid, p["module"], p["fichier_source"], p["description"], p["importance"], p["cree_le"]))
```
This is writing importance that was READ from phenomenes.yaml, not computing it. But it IS writing it. The claim says "NEVER computes or writes `importance`" — the code DOES write it (to both PIRT.md and pirt.sqlite), it just reads it first. This makes P3 **BROKEN** because it writes importance, contradicting "never writes".

**Additional bug**: In `generer_bloc()`, the generated table includes the importance column, meaning it's being written to PIRT.md:
```python
"| phenomene | importance | couverture | portee dernier bite | ..."
```
This clearly writes importance values to PIRT.md. P3 is BROKEN.

### P5: PARTIAL - MEDIUM
**Claim says**: Step 0.5 runs BEFORE llama-server step, journals pirt.py output line by line, NEVER blocks the pass on failure; if evenements.jsonl absent it journals "saute".

**Code evidence**: The PowerShell excerpt shows:
```powershell
$PIRT_DIR = "C:\Users\test\Documents\agentic-flow-phase4\plasma-digital-twin\pirt"
if (Test-Path "$PIRT_DIR\evenements.jsonl") {
    & python "$DEPOT\harness\pirt.py" --pirt $PIRT_DIR 2>&1 |
        ForEach-Object { Add-Content -LiteralPath $JOURNAL -Value ("    " + $_) -Encoding UTF8 }
    Ecrire ("repli PIRT : exit=" + $LASTEXITCODE + "...")
} else {
    Ecrire "repli PIRT : evenements.jsonl absent, saute ..."
}
```

**Issue 1**: The step is BEFORE "--- 1." in the script, which matches "before llama-server step". ✓
**Issue 2**: Output is piped to `Add-Content` line by line via `ForEach-Object`. ✓
**Issue 3**: There's NO error handling — if pirt.py exits non-zero, the script continues to the `Ecrire` line and then to step 1. ✓ (doesn't block)
**Issue 4**: If absent, it writes "saute" message. ✓

**But**: The `Ecrire` function is called but never defined in this excerpt. Also, `$JOURNAL` is referenced but its origin isn't shown. These are NOT VERIFIABLE from the provided excerpt alone. However, the logic is clear: the script doesn't have `exit 1` or `throw` on pirt failure. P5 is PARTIAL because we can't verify the entire flow (JOURNAL/Ecrire resolution), but the visible code structure supports the claim.

### P1: BROKEN - MEDIUM
**Claim says**: Same evenements.jsonl => byte-identical PIRT.md on second run; pirt.sqlite rebuilt from scratch every run.

**Evidence for sqlite rebuild**: 
```python
def ecrire_sqlite(chemin, phenomenes, evenements, etats):
    if os.path.exists(chemin):
        os.remove(chemin)  # cache DERIVE cree par ce script
```
Rebuild from scratch. ✓

**Evidence against byte-identical PIRT.md**: Look at `ecrire_md()`:
```python
def ecrire_md(chemin, bloc):
    squelette = ("# PIRT -- registre vivant (donnees PRIVATE)\n\n"
                 "Source de verite : `evenements.jsonl` (append-only, gabarit dans\n"
                 "`harness/pirt.py` du depot dsh2.0). Ce fichier est REGENERE chaque nuit ;\n"
                 "seul le bloc genere fait foi pour les comptes.\n\n"
                 + bloc + "\n")
    if not os.path.exists(chemin):
        contenu = squelette
    else:
        actuel = io.open(chemin, encoding="utf-8").read()
        if MARQUE_DEBUT in actuel and MARQUE_FIN in actuel:
            avant = actuel.split(MARQUE_DEBUT)[0]
            apres = actuel.split(MARQUE_FIN, 1)[1]
            contenu = avant + bloc + apres
        else:
            contenu = actuel.rstrip() + "\n\n" + bloc + "\n"
```

If PIRT.md EXISTS and contains the markers, the file is reassembled as `avant + bloc + apres`. The `apres` is whatever comes after `MARQUE_FIN`, which is NOT controlled by the script — it's user content. If the user modifies anything after `<!-- PIRT:FIN -->`, those modifications survive. Crucially, if the user edits anything BETWEEN the markers, those edits also survive via `avant` and `apres`. 

**But more subtly**: If PIRT.md does NOT exist, it's created with the squelette:
```python
squelette = ("# PIRT -- registre vivant ...\n\n...\n\n" + bloc + "\n")
```
If PIRT.md exists WITHOUT markers, it becomes `actuel.rstrip() + "\n\n" + bloc + "\n"`. This is NOT byte-identical to the full squelette version.

So the output depends on whether PIRT.md already exists and whether it had markers. This makes P1 **BROKEN** — the output is NOT guaranteed byte-identical on second run because the script preserves surrounding content.

## NOT VERIFIABLE

### P6: NOT VERIFIABLE
**Claim says**: pirt.py contains no framework-private data: no phenomenon names, no anchor values, no framework source file names.

The provided code shows:
- No phenomenon names hardcoded ✓
- No anchor values hardcoded ✓  
- No framework source file names ✓
- The code only references generic paths via `--pirt` argument and `phenomenes.yaml`
- `TYPES`, `PORTEES`, `CONFIANCES` are generic configuration

BUT: The docstring references "chantier 25/08", "dsh2.0" in the generated skeleton, and "docs/PIRT.md". Without seeing the full framework, we can't definitively say these aren't framework-private. `dsh2.0` appears to be a repository name being mentioned. This makes P6 NOT VERIFIABLE with the provided evidence.

### P7: PARTIAL - MEDIUM
**Claim says**: Exit codes: 0 fold done, 1 jsonl absent, 2 invalid line (nothing written), 3 write error.

**Evidence**: 
- Exit 0: `sys.exit(0)` at end of main ✓
- Exit 1: `sys.exit(1)` when jsonl absent ✓  
- Exit 2: `sys.exit(2)` in `lire_evenements()` on invalid lines ✓
- Exit 3: `sys.exit(3)` in OSError catch ✓

**But**: Exit 2 is called from `lire_evenements()` BEFORE any writing happens. However, `lire_phenomenes()` also calls `sys.exit(2)` for invalid importance values. This exit 2 could happen AFTER events have been read but before writing — still technically "nothing written". 

**Also**: The claim says exit 1 is "jsonl absent", but `lire_evenements()` doesn't handle missing files — that's done in `main()`:

```python
if not os.path.exists(jsonl):
    print("evenements.jsonl absent sous %s -- rien a replier" % a.pirt)
    sys.exit(1)
```

This catches file-not-found. ✓

P7 is PARTIAL because while the exit codes are implemented as claimed, there's no handling for partially-written files on exit 3 (if sqlite succeeds but PIRT.md write fails, sqlite is written but md is not). This violates the atomicity implied by the exit codes representing specific failure modes.

---

## Verdict Table

| Claim | Verdict | Severity |
|-------|---------|----------|
| P1 (idempotent byte-identical) | BROKEN | MEDIUM |
| P2 (fail-closed, nothing written) | BROKEN | HIGH |
| P3 (never writes importance) | BROKEN | MEDIUM |
| P4 (coverage + priority sort) | BROKEN | HIGH |
| P5 (nightly step 0.5) | PARTIAL | MEDIUM |
| P6 (no framework-private data) | NOT VERIFIABLE | - |
| P7 (exit codes) | PARTIAL | MEDIUM |