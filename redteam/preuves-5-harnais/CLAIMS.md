# Done-claims under review (harness deliverables, 25/08 — commits 5566ec5 + 2056259)

Your job (red team) is to FALSIFY these claims by reading the code in this
workspace. Every claim below was declared "done" by the worker session.

## A. harness/distiller.py — extraire_json fix (commit 5566ec5)
A1. The real JSON of a local-Qwen reply always comes after the LAST `</think>`;
    taking `rsplit("</think>", 1)[-1]` handles BOTH measured failure modes
    (example JSON inside the think block; a literal `</think>` mid-reasoning).
A2. The no-think path (reply without any `</think>`) is unchanged by the fix.
A3. A tree whose LLM reply fails JSON extraction is NOT marked in the
    `distillations` table, so a plain rerun retries it (no poisoned skip).
A4. Score writes are idempotent across reruns (INSERT OR REPLACE + a
    `scores_vus` guard): rerunning a sweep cannot double-count scores.

## B. scripts/ops/distiller_nightly.ps1 (commit 5566ec5)
B1. Find-or-launch of the :8004 llama server; the script leaves the world as
    it found it (a server it launched is stopped; a server it found stays).
B2. If the GPU launcher refuses, the script SKIPs; it never kills a process
    it did not start.
B3. Stop is VERIFIED: exit code 4 if the port is still held afterwards.
B4. All outcomes are journaled to %USERPROFILE%\dsh-distiller-nightly.log.

## C. scripts/ops/julia_gate_arret.ps1 (commit 5566ec5)
C1. Exit 0 if :8077 is not listening (idempotent); otherwise --arret then
    verify; exit 4 if the port is still held.

## D. scripts/ops/installer_taches_nocturnes.ps1 (commit 5566ec5)
D1. Registers dsh-julia-gate-arret at 00:50 and 04:50 and
    dsh-distiller-nightly at 07:00, pointing at the two scripts above.

## E. scripts/dsh.ps1 — freellm key block (commit 2056259)
E1. DSH_FREELLM_API_KEY is read per-launch via scripts/freellm_key.py ONLY
    when the env var is absent; on failure a warning names the missing
    credential; the key value is NEVER displayed (length only) and never
    written to a file.

## F. harness/providers.yaml — freellm block (commit 2056259)
F1. The block is a faithful copy of the live settings block (12 models);
    context windows are prudent FLOORS, not catalog peaks.
F2. `auto`/`auto:<profile>` are documented as FORBIDDEN for measurement
    (pin the model); no cohere model appears on any freellm route.
