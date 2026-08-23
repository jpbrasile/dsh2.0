# Local LLM — serving setup the harness relies on

**Status:** measured 2026-08-23. Every number and path below is a snapshot; re-measure
before relying on it. **Source of truth stays in the plasma repo** (`agentic-flow`,
`C:\Users\test\Documents\agentic-flow-fresh`): the launchers, the 4090 benchmark
(`docs/SPECDEC_4090_BENCH.md`) and the production server are maintained there because they
also serve that project. This page is the harness-side pointer so `dsh2.0` can use the local
route without owning it.

## What the harness sees (`~/.dsh/settings.yaml`, provider block `llm-pi-ai`)

| provider | baseURL | model id served | role |
|---|---|---|---|
| `local` | `http://127.0.0.1:8004/v1` | `qwen36-35b-a3b` | production llama-server (plasma project). **Down on 2026-08-23.** |
| `local-vision` | `http://127.0.0.1:8005/v1` | `specdec-q38-plain-vision` (or whatever `-Config` the launcher served: `specdec-q38-mtp` on 2026-08-23) | bench / vision server, launched on demand |
| `local-think` | `http://127.0.0.1:8006/v1` | same as 8005 | **recorder proxy** `scripts/bench_julia_effort/proxy.mjs` 8006 → 8005; `wire.jsonl` says what really left |
| `freellm` | `http://127.0.0.1:8007/v1` | `auto`, `auto:smartest`, pinned ids | recorder proxy 8007 → FreeLLMAPI Desktop `:31415` (see `DSH_FREELLMAPI_ROUTE.md`) |

Auth: llama-server authenticates nothing. pi-ai still requires a key variable, so the routes
reference `DSH_LOCAL_API_KEY`; the bench sets it to `local-loopback-noauth`
(`bench.py`), `dsh.ps1` to `local-dummy`. It is a placeholder, not a secret.

Check what is actually served before a campaign (the alias, not the file name, is what dsh
asks for):

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8005/v1/models | Select-Object -Expand Content
```

## Launcher (lives in `agentic-flow`, not here)

`agentic-flow-fresh\scripts\start_llama_qwen38_27b_specdec.ps1`

- `-Config` ∈ `q38-plain` | `q38-mtp` | `q38-dflash2` → served alias `specdec-<Config>`
  (`-Mmproj` adds a `-vision` suffix).
- `-Port` 8005 (default) — **never 8004**, that is production; `-CtxSize` 32768 default;
  `-Ctk` / `-Ctv` KV cache types; `-UbatchSize`; `-Mmproj` + `-ImageMaxTokens` for vision;
  `-LogPath` (default `%USERPROFILE%\llama-server-specdec-<Config>.log`).
- Fails closed (exit 4) if the binary lacks the needed `--spec-type`, an artifact is missing,
  or the GPU state is unknown.
- Companions in the same folder: `stop_llama_port.ps1`, `restart_production.ps1`
  (restores `:8004`), `bench_llama_ctx.py` (throughput vs ctx).

Artifacts (absolute, this machine):

| | |
|---|---|
| model | `C:\Users\test\models\qwen38-27b\Qwen3.8-27B-Q4_K_M.gguf` (unsloth, 17.1 GB) |
| DFlash2 draft | `C:\Users\test\models\dflash2-qwen38-27b\Qwen3.8-27B-DFlash2-Q4_K_M.gguf` |
| binary | `C:\Users\test\tools\llama-cpp\llama-cuda-b10488\llama-server.exe` (CUDA, b10488) |
| GPU | RTX 4090, 24 564 MiB |

## Sizing (measured 2026-08-22 on this card, KV f16, mmproj loaded, `-ImageMaxTokens 1024`)

| ctx | VRAM |
|---|---|
| 16 384 | 18 192 MiB |
| 32 768 | 19 232 MiB |
| 98 304 | 23 392 MiB (1 172 MiB margin) |

Raising ctx does not slow a short request. Native model ctx is 262 144.

## The one rule that matters (from `docs/SPECDEC_4090_BENCH.md`, 2026-08-19)

**Keep the KV cache at f16 for long contexts.** Quantized KV (q8_0/q4_0) collapsed decode to
1.2–4.0 tok/s at 29k/58k filled tokens with a 55–65 min first-fill stall; f16 KV kept
38.8–41.7 tok/s and the prefix cache engaged. The stall was the KV quantization, not the model
or the card. Short-context speculation gains (dflash2 +28…+80 % tok/s) do not carry to long
context. The decision rule for keeping/removing DFlash2 is written in that document.

## How the harness spec uses this

Spec Phase 5 ("Local Qwen (RTX 4090)": embeddings, repo index, digests, log distillation,
probation as coder) targets this server. Until then the bench campaigns
(`scripts/bench_julia_effort/`, `docs/DSH_QWEN_LOCAL_LOGBOOK.md`) are the only consumer.
A campaign that needs the local route: start the launcher from `agentic-flow-fresh`, confirm
the alias with the `/v1/models` call above, then run `bench.py` from this repo.
