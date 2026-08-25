# Claims P1-P7 soumis au red team D4 (25/08)

CLAIMS to falsify (implementation commits 81c6e5a, done-criteria D1-D3):
P1. The fold is idempotent: same evenements.jsonl => byte-identical PIRT.md on
    a second run; pirt.sqlite is rebuilt from scratch every run (derived cache,
    the JSONL is the only source of truth).
P2. Fail-closed: ANY invalid JSONL line (bad JSON, missing required field,
    unknown type, non-dict donnees) => exit 2 and NOTHING is written -- no
    sqlite, no PIRT.md modification.
P3. The machine NEVER computes or writes `importance`: it is only read from
    phenomenes.yaml; a value outside {1,2,3,empty} => exit 2.
P4. couverture = constants whose LATEST mutation event has bite=true / constants
    tried (latest event per (phenomene, constante) wins); `portee` ranks
    ancres > litteral > aucune; priority sort = importance DESC (unclassified
    last), couverture ASC, portee ASC, confiance ASC.
P5. Nightly step 0.5 runs BEFORE the llama-server step, journals pirt.py output
    line by line, and NEVER blocks the pass on a pirt failure; if
    evenements.jsonl is absent it journals "saute" and moves on.
P6. The OPEN tooling file pirt.py contains no framework-private data: no
    phenomenon names, no anchor values, no framework source file names.
P7. Exit codes: 0 fold done (including "no change"), 1 jsonl absent, 2 invalid
    line (nothing written), 3 write error.

