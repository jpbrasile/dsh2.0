# dsh on OpenRouter — the harness's working route (decision 2026-08-23)

**Why this route first.** The user decided on 2026-08-23 to tune the harness (README) on
OpenRouter before any local or FreeLLMAPI port: several workers in parallel, no provider
deaths, and a model that is the same as the local one. Measured grounds in
`ETAT_DES_LIEUX_2026-08-23.md` §2.1 (free remote APIs die mid-run) and §2.2 (local is not a
speed lever: 3 remote workers at 31 t/s beat 1 local worker at 70 t/s).

## Models

| role | id | price (2026-08-23) | notes |
|---|---|---|---|
| worker | `qwen/qwen3.8-27b` | $0.40 / $3.00 per M in/out | same model as the local `specdec-q38-*` server → later A/B at equal model |
| red team | `deepseek/deepseek-v4-pro` | see OpenRouter | **another family**, as the README requires for the red-team step |
| free spare | `stealth/ox-alpha` | $0 | stealth model, used by the t31e campaigns; may vanish |

Scale: the t31e campaign (15 runs, 443 k output tokens) would cost ≈ $1.5 with the worker.

## Context window: 64k, on purpose

`contextWindow: 65536` on both harness models. It is the size dsh uses to decide when to
compact the conversation; declaring 1 M means "never compact" and the session grows until a
local server refuses it. 64k is what the RTX 4090 holds (19–23 GB measured up to 98k,
`LOCAL_LLM.md`), so what is tuned here stays true locally. It also caps billed input tokens.

## Where it lives (`~/.dsh/settings.yaml`, not in this repo)

Two provider blocks, already present (keys masked):

```yaml
    openrouter-banc:                    # RECORDED route: baseURL -> proxy.mjs -> openrouter.ai
      api: openai-completions
      baseURL: http://127.0.0.1:8050/api/v1
      models:
        - id: qwen/qwen3.8-27b
          contextWindow: 65536
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
        - id: deepseek/deepseek-v4-pro
          contextWindow: 65536
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
    openrouter:                         # DIRECT route for interactive use
      baseURL: https://openrouter.ai/api/v1
      models:
        - id: qwen/qwen3.8-27b
          contextWindow: 65536
```

Default model for interactive dsh: `openrouter` / `qwen/qwen3.8-27b` / effort `off`.
Two traps met on 2026-08-23, both caught by the smoke test below:

- a model entry **without `reasoningEfforts`** makes dsh refuse effort `off`
  (`UNSUPPORTED_REASONING_EFFORT`) — copy the block above;
- the pinned runtime `~/.dsh/runtime/dsh-0.1.1-rc.2` was found **emptied** (197/197
  packages, 84 files left, deletion at 10:47:28 — cause not identified). Rebuilt in 15 s with
  `.\scripts\dsh.ps1 -InstallRuntime` (29 505 files, `bin.js` back). If `dsh` dies with
  `Cannot find module ... lib/bin.js`, that is the fix.

## The control: `scripts/bench_julia_effort/fumee_route.py`

```
python fumee_route.py                          # worker through the recorder
python fumee_route.py deepseek/deepseek-v4-pro # red team
```

One headless dsh run ("write PONG.txt"), isolated `DSH_HOME` and workspace under `_fumee/`,
recorder on :8050 → `openrouter.ai`. It passes only if **every call in `wire.jsonl` says
`servi == <model>`** and the file exists — an HTTP 200 proves nothing about who answered.
Known-BAD arm: `python fumee_route.py qwen/n-existe-pas` must print ECHEC (it does:
`UNKNOWN_MODEL`). Run it after any change to the settings, the runtime or the proxy.

Measured 2026-08-23: worker 3 calls / 15.7 s / 170+445+78 output tokens; red team
4 calls / 11.7 s. Both `servi` by the pinned model on every call.

## Running a campaign on this route

```powershell
$env:BENCH_PROVIDER   = 'openrouter-banc'
$env:BENCH_MODEL      = 'qwen/qwen3.8-27b'
$env:BENCH_PAR_AMONT  = 'openrouter.ai'
$env:BENCH_PAR_TLS    = '1'
$env:BENCH_PAR_CHEMIN = 'api/v1'     # no leading slash (bench.py adds it; a Git-bash '/api/v1' gets mangled)
$env:BENCH_ETIQUETTE  = 'essai1'
python bench.py medium t31 --boucle 2 --par 3 --reps 3 --bras sans
```

`--par N` gives N workers, each with its own recorder port (8020+k) and its own
`_par/<etiq>/wK/wire.jsonl`; `analyse.py _par/<etiq>` assembles them.
