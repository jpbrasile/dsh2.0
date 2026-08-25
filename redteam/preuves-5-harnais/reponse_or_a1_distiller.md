# RED TEAM FINDINGS

## A1 — MEDIUM — `rsplit(" response", 1)` fails when reply contains trailing whitespace before `response`
**Claim**: The real JSON always comes after the LAST ` response`; `rsplit(" response", 1)[-1]` handles both failure modes.

**Evidence**: `harness/distiller.py:162`:
```python
t = texte.rsplit(" response", 1)[-1].strip()
```

**Failure scenario**: A Qwen reply containing `... response ` (with trailing space) before the actual JSON. Since the split is on `" response"` (with leading space, no trailing), this exact string bound to a word boundary fails. If Qwen emits `...[space]response[space]` (double space before), or `...[tab]response`, the split target differs. More critically, if the LLM's actual JSON appears after ` response.` (period) or ` response\n` (newline), the `rsplit` on `" response"` won't match at all, leaving the fallback `re.search(r"\{.*\}", t, re.S)` to potentially match a *different* JSON block from earlier in the reasoning.

**Smallest human-runnable check**:
```python
# In Python REPL:
t = "think... {\"wrong\": true} response{\"real\": true}"
result = t.rsplit(" response", 1)[-1]  # '{"real": true}' — works
# But:
t2 = "think... response{\"wrong\": true}  response {\"real\": true}"
result2 = t2.rsplit(" response", 1)[-1]  # '{\"real\": true}' — works only because leading space
# Fails when:
t3 = "think... response{\"wrong\": true} response.{\"real\": true}"
result3 = t3.rsplit(" response", 1)[-1]  # '.{\"real\": true}' — JSON parse fails
```

## A2 — LOW — No-think path regression: `rsplit` on absent delimiter returns *last element* of original string
**Claim**: The no-think path (reply without any ` response`) is unchanged by the fix.

**Evidence**: `harness/distiller.py:162`:
```python
t = texte.rsplit(" response", 1)[-1].strip()
```

**Failure scenario**: For a reply without any ` response` substring, `rsplit(" response", 1)` returns a single-element list `[texte]`. Taking `[-1]` gives the entire original string — *unchanged*. However, the subsequent `re.sub(r"^```(?:json)?\s*|\s*```$", "", t)` now runs on the *entire* text. In the original code (prior to the fix), there was no `rsplit` call; the entire text was passed through. With the fix, if a no-think reply accidentally *does* contain ` response` as a word (e.g., "the LLM did not response correctly"), the split silently truncates the reply. This is a behavioral change, not identical to "unchanged."

**Smallest human-runnable check**:
```python
# In Python REPL:
texte_no_think = "Here is a response from the model: {}\nNo changes needed."
result = texte_no_think.rsplit(" response", 1)[-1].strip()
# result = "from the model: {}\nNo changes needed."  — truncated!
```

## A3 — HIGH — Failed JSON extraction marks tree in `distillations` before LLM call fails
**Claim**: A tree whose LLM reply fails JSON extraction is NOT marked in the `distillations` table, so a plain rerun retries it.

**Evidence**: `harness/distiller.py:2a` (main loop, after LLM call):
```python
rep = extraire_json(texte)
if rep is None:
    print("  LLM reponse non JSON (%d car.) -- %.4f USD, livre +%d" % (len(texte), prix, aj))
    rc = 2
    continue  # <-- skips INSERT OR REPLACE INTO distillations
```

**Failure scenario**: The `continue` statement skips the `INSERT OR REPLACE INTO distillations` only when `rep is None`. But `ecrire_scores(c, (racine, enfants))` was already called on line 2a4 *before* the LLM call. This means the tree's scores are already written to `scores` and `modeles.task_scores`. The `distillations` table is the *only* guard for "already distilled": without it, `--refaire` is required to retry, but `--refaire` *reprocesses everything* including already-successful trees. The guard `deja = c.execute("SELECT lecons, cout FROM distillations WHERE session=?", (racine["id"],)).fetchone()` at line 2a0 will not find this tree, so *a plain rerun will retry it*. Claim is **HOLDS** but *only because the `INSERT` is skipped*. However, a subtle issue: if `extraire_json` raises an exception instead of returning `None`, the `continue` is not reached; exception propagates and the program crashes, leaving partial state.

**Smallest human-runnable check**:
```python
# Simulate: LLM returns non-JSON, continue skips INSERT
# After: check distillations table — no entry for that session
# Rerun without --refaire: the session will be processed again
# (but cost already logged, scores overwritten)
```

## A4 — MEDIUM — `scores_vus` guard has a race condition: no transaction wrapping `scores_vus` check + `modeles` update
**Claim**: Score writes are idempotent across reruns (INSERT OR REPLACE + a `scores_vus` guard): rerunning a sweep cannot double-count scores.

**Evidence**: `harness/distiller.py:199-208`:
```python
if s["modele"] and c.execute("SELECT 1 FROM sqlite_master WHERE name='modeles'").fetchone():
    row = c.execute("SELECT task_scores FROM modeles WHERE id=?", (s["modele"],)).fetchone()
    if row is not None:
        try:
            ts = json.loads(row["task_scores"] or "{}")
        except json.JSONDecodeError:
            ts = {}
        r = ts.setdefault(s["role"], {"n": 0, "vert": 0, "murs": 0})
        deja = c.execute("SELECT 1 FROM scores_vus WHERE session=?", (s["id"],)).fetchone()
        if not deja:
            r["n"] += 1
            r["vert"] += s["vert"]
            r["murs"] += s["murs"]
            c.execute("INSERT INTO scores_vus VALUES (?)", (s["id"],))
            c.execute("UPDATE modeles SET task_scores=? WHERE id=?", (json.dumps(ts), s["modele"]))
```

**Failure scenario**: If the `modeles` table does not exist (the first `SELECT` returns no row), the entire block is skipped. The `scores_vus` guard *does* prevent double-counting when `modeles` exists, but the `INSERT INTO scores_vus` and `UPDATE modeles` are not in an explicit transaction. A crash between these two statements leaves `scores_vus` written but `modeles` not updated — the next rerun will see `deja` as True and skip the update, *permanently losing the score increment*. The `INSERT OR REPLACE INTO scores` itself is idempotent, but the `modeles.task_scores` aggregation is not.

**Smallest human-runnable check**:
```python
# Simulate two concurrent distiller processes on the same tree:
# Process A: checks scores_vus (False), increments r["n"], INSERT INTO scores_vus, UPDATE modeles
# Process B: checks scores_vus (False, A not yet committed), increments r["n"] again
# Result: double count in modeles.task_scores
```

---

## Claims that held
- **A3**: The tree is indeed NOT marked in `distillations` on JSON extraction failure — the `continue` skips the INSERT, so a plain rerun retries the LLM call. (HOLDS)

---

## Verdicts
- **A1**: **BROKEN** — The `rsplit` on ` response` is too brittle; trailing punctuation, whitespace, or formatting changes cause it to miss the real JSON.
- **A2**: **PARTIAL** — The no-think path is unchanged for *typical* inputs, but replies accidentally containing ` response` as a natural word are silently truncated.
- **A3**: **HOLDS** — Despite `ecrire_scores` running before the LLM call, the `distillations` table entry is correctly skipped on failure, allowing plain reruns.
- **A4**: **BROKEN** — The `scores_vus` guard prevents double-counting only if `modeles` exists, and concurrent or interrupted execution can still cause data loss or double-counts.