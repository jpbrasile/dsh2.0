#!/usr/bin/env python3
"""bench_specdec_4090.py — controlled 4090 spec-decoding benchmark driver.

Drives the /v1/chat/completions endpoint of a llama-server already running on
the bench port (default 8005). It NEVER starts or stops a server; the launcher
(scripts/start_llama_qwen38_27b_specdec.ps1) and the outage orchestrator
(scripts/run_specdec_window.ps1) are the only things that manage the server.

Methodology (lossless spec-dec compare):
  * Prompts come from bench/prompts_specdec.json (3 workloads: code, prose,
    tool_json). Every request fixes seed=42 and temperature=0.6 so output is
    deterministic; spec decoding is LOSSLESS, so two configs must generate
    token-identical text for the same (workload, rep).
  * A unique per-rep nonce line is appended INSIDE the user prompt. The nonce
    differs on every rep so the server's prefix cache cannot serve rep>=2 from
    a cached completion / inflate the throughput numbers.
  * The first request after the driver starts is a warmup, excluded from stats.
  * 3 reps per workload; medians are reported (not means).
  * VRAM (nvidia-smi memory.used) is captured before and after the run.
  * The Tee'd server log is best-effort regex-parsed for spec/acceptance lines;
    null if none are found (parse status is recorded regardless).

Usage:
  python bench/bench_specdec_4090.py --config-label q38-mtp --argv-file server.argv.txt
  python bench/bench_specdec_4090.py --config-label q36-dflash --argv "llama-server.exe --model ... "
  python bench/bench_specdec_4090.py --config-label q38-plain --dry-run
  python bench/bench_specdec_4090.py --compare reports/specdec_20260819

--dry-run: build every payload, assert each carries seed+max_tokens+nonce,
print them, and exit 0 WITHOUT writing anything or touching the network.
--compare DIR: load the run-record JSON files in DIR (must contain >=2 records)
and diff the generated text per (workload, rep) across configs. Lossless spec
decoding means texts should be identical; a mismatch prints a loud WARN with a
diff summary but exit stays 0 (it is a detector, not a gate).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import re
import shlex
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROMPTS_FILE = Path(__file__).with_name("prompts_specdec.json")

# --- long-context filler calibration -----------------------------------------
# Chars-per-token for the longctx generator. ~3.6 is a sane start for English
# technical prose (roughly 1 token per 4 characters on average across BPE
# tokenizers; this constant is the single place to re-tune it). The honest
# evidence of how many tokens actually landed is `usage.prompt_tokens` captured
# from the server on every rep -- the generator's char-based estimate never
# substitutes for it.
CHARS_PER_TOKEN = 3.6

# A pool of varied technical sentences (sections stay distinct, never a single
# repeated line). Each section is a short, numbered technical paragraph built
# from a seeded rotation of these sentences so any two workloads with different
# (id, fill_seed) expand to byte-different blocks.
_LONGCTX_TECH_SENTENCES = [
    "Spectral analysis of the pulsed discharge shows the bulk of the energy lands in the 0.5-8 kHz band.",
    "A swept-frequency probe confirmed the resonant Q-factor drifts less than 4%% across the operating range.",
    "Calibration against a traceable standard reduces the systematic bias term by an order of magnitude.",
    "Plateau drying of the intermediate layer keeps the residual solvent fraction below 200 ppm.",
    "Closed-loop setpoint scheduling lowers peak overshoot without sacrificing steady-state accuracy.",
    "The waveguide coupler design trades insertion loss against bandwidth, and the 3 dB point sits at 2.4 GHz.",
    "Vortex shedding at the trailing edge imposes a Strouhal constraint on the inlet geometry.",
    "Common-mode rejection improves sharply once the differential front end is balanced to a few microvolts.",
    "A two-stage precipitation cut recovers the target cut above 93 percent by mass.",
    "Reverse-bias leakage stays bounded by the carrier concentration profile across the junction.",
    "Hysteresis in the actuator curve is dominated by the creep term, not the static friction floor.",
    "The phase accumulator wraps cleanly at the 2^power boundary, so no jitter accumulates over long runs.",
    "Electrode erosion tracks the accumulated pulse count, flattening once breakdown energy reaches a plateau.",
    "Thermal stitching across the seam reduces outgassing that would otherwise contaminate the neighboring stage.",
    "Dither injection on the sample axis whitens the quantization noise already at one-half LSB.",
    "The decarbonizing sweep ramps the outlet temperature before the pressure turndown budget is committed.",
    "Grating roll shifts the diffraction order map, so the bench must re-verify the peak before the run.",
    "Buffer depth on the ingest path hides a periodic stall that showed mock execution is never load-neutral.",
    "The reactor wall absorbance dominates below 400 nm, narrowing the effective UV window for the step.",
    "Discrete cosine pruning truncates the low-energy tail without biasing the reconstruction fit.",
    "Field-winding mutual inductance couples the two sub-systems unless a counter-phase thread is applied.",
    "The feed-forward compensator anticipates the second resonance well before the regulator sees it.",
    "Longitudinal stress trails the elastic limit when the cross-section thins faster than the load ramps.",
    "Baseline subtraction must be recomputed after each warm start; the zero snapshot ages with wall time.",
]

# Sections per filler paragraph -- each "Section N" block carries this many of
# the sentences above (rotation index advances monotonically, so long runs stay
# varied and never repeat a line).
_LONGCTX_SENTS_PER_SECTION = 4


def _longctx_seed(w: dict) -> int:
    """Deterministic filler seed for a longctx workload.

    Mixes the declared fill_seed with a stable hash of the workload id so (a)
    the same (id, fill_seed) always yields the identical byte stream, and (b)
    two longctx workload ids never share a filler block.
    """
    idhash = 0
    for ch in w["id"]:
        idhash = (idhash * 31 + ord(ch)) & 0x7FFFFFFF
    fseed = int(w.get("fill_seed", 0)) & 0xFFFFFFFF
    return (fseed * 0x9E3779B9 ^ idhash) & 0xFFFFFFFF


def _build_longctx_filler(w: dict, budget_chars: int) -> str:
    """Deterministically build <budget_chars> chars of varied technical prose."""
    rng = random.Random(_longctx_seed(w))
    pool = list(_LONGCTX_TECH_SENTENCES)
    rng.shuffle(pool)
    idx = 0
    parts = []
    total = 0
    n = 0
    while total < budget_chars:
        n += 1
        sents = []
        for _ in range(_LONGCTX_SENTS_PER_SECTION):
            sents.append(pool[idx % len(pool)])
            idx += 1
        blk = f"Section {n} ({w['id']}). " + " ".join(sents) + "\n\n"
        parts.append(blk)
        total += len(blk)
    return "".join(parts)


def resolve_prompt(w: dict) -> str:
    """The instruction text actually sent upstream, after longctx expansion."""
    if w.get("kind") == "longctx":
        instr = w["prompt"]
        budget = max(0, int(w["fill_target_tokens"]) * CHARS_PER_TOKEN - len(instr) - 2)
        return _build_longctx_filler(w, budget) + instr
    return w["prompt"]


def estimate_prompt_tokens(text: str) -> int:
    """Best-effort token estimate from chars; the run's source of truth is the
    server-reported usage.prompt_tokens, never this heuristic."""
    return max(1, round(len(text) / CHARS_PER_TOKEN))


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def nvidia_smi_mem_mb() -> int | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
        first = r.stdout.strip().splitlines()
        return int(first[0].strip()) if first else None
    except Exception:
        return None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_workloads(prompts_file: Path | None = None) -> list[dict]:
    pf = prompts_file or PROMPTS_FILE
    with io.open(pf, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit(f"{pf}: expected a JSON array of workloads")
    for w in data:
        for k in ("id", "kind", "prompt", "max_tokens", "seed"):
            if k not in w:
                raise SystemExit(f"{pf}: workload missing key {k!r}: {w.get('id')}")
        if w["kind"] == "longctx":
            for k in ("fill_target_tokens", "fill_seed"):
                if k not in w:
                    raise SystemExit(f"{pf}: longctx workload {w.get('id')!r} missing key {k!r}")
    return data


def make_prompt_with_nonce(w: dict, rep: int, nonce: str) -> str:
    """Append a per-rep nonce line INSIDE the user prompt so rep>=2 cannot be
    served from a prefix-cached completion (nonce differs every rep)."""
    return f"{resolve_prompt(w)}\n\n[bench-nonce-{w['id']}-rep{rep}: {nonce}]"


def shlex_split_win(cmd: str) -> list[str]:
    """Split a command-line string the way cmd.exe / Windows argv works.

    shlex.split(posix=True) treats backslashes as escape characters and would
    eat them in Windows paths (e.g. ``\\models\\qwen.gguf``); posix=False keeps
    them verbatim while still grouping double-quoted spans. posix=False retains
    the surrounding quotes, so this strips one balanced pair per token.
    """
    out = []
    for t in shlex.split(cmd, posix=False):
        if len(t) >= 2 and t[0] == t[-1] and t[0] in ('"', "'"):
            t = t[1:-1]
        out.append(t)
    return out


def read_argv(args) -> list[str] | None:
    if args.argv_file:
        p = Path(args.argv_file)
        if not p.exists():
            print(f"[bench] WARN: --argv-file {p} not found; argv recorded as null")
            return None
        lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if ln]
    if args.argv:
        return shlex_split_win(args.argv)
    return None


def read_log_text(path: str | Path) -> str:
    """Read a server log with BOM sniffing.

    The launcher Tees the server log with Tee-Object: Windows PowerShell 5.1
    writes UTF-16LE (leading \\xff\\xfe BOM). A utf-8 read of such a file never
    matches the regexes, so sniff the BOM and decode accordingly.
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8", errors="replace")


def parse_binary_build(log_path: str | None) -> tuple[str | None, str]:
    """Best-effort build string from the server log. Returns (build, status)."""
    if not log_path:
        return None, "no-log"
    p = Path(log_path)
    if not p.exists():
        return None, "log-missing"
    try:
        text = read_log_text(p)
    except Exception as e:
        return None, f"parse-error:{e}"
    # llama.cpp prints e.g. "build: 2a5cecd (..." or a build id.
    m = re.search(r"(?i)build(?:_id)?\s*[:=]\s*([0-9a-zA-Z]+)", text)
    if m:
        return m.group(1), "parsed"
    return None, "no-match"


def parse_spec_log(log_path: str | None) -> dict:
    """Best-effort scan of the Tee'd server log for spec/accept lines."""
    if not log_path:
        return {"status": "no-log", "matches": None}
    p = Path(log_path)
    if not p.exists():
        return {"status": "log-missing", "matches": None}
    try:
        text = read_log_text(p)
    except Exception as e:
        return {"status": f"parse-error:{e}", "matches": None}
    pat = re.compile(r"(?i)(accept|draft|speculat|spec_type|spec_draft|n_accept)")
    matches = []
    for line in text.splitlines():
        if pat.search(line):
            s = line.strip()
            if s and s not in matches:
                matches.append(s)
    if matches:
        return {"status": "parsed", "matches": matches[:200]}
    return {"status": "no-match", "matches": None}


def stream_chat(url: str, body: dict, timeout: int = 900):
    """POST streaming chat.completions; yields result dict.

    Token count is taken from the final `usage.completion_tokens` chunk when the
    server sends one (stream_options.include_usage) because counting raw SSE
    chunks conflates a chunk with a token (one chunk may carry several tokens).
    `token_count_method` records which source was used: "usage" or "chunks".
    """
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    t0 = time.perf_counter()
    ttft = None
    chunks = []
    usage_tokens = None
    prompt_tokens = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            # OpenAI-compatible usage chunk carries `usage` at the top level,
            # typically as the last chunk before [DONE] (no choices).
            usage = obj.get("usage")
            if isinstance(usage, dict):
                # completion_tokens is the source of the tok/s number ...
                if usage.get("completion_tokens") is not None:
                    try:
                        usage_tokens = int(usage["completion_tokens"])
                    except (TypeError, ValueError):
                        usage_tokens = None
                # ... and prompt_tokens is the honest proof of the long-context
                # fill level (the generator's char estimate never substitutes).
                if usage.get("prompt_tokens") is not None:
                    try:
                        prompt_tokens = int(usage["prompt_tokens"])
                    except (TypeError, ValueError):
                        prompt_tokens = None
            choices = obj.get("choices") or [{}]
            delta = (choices[0] or {}).get("delta", {})
            tok = delta.get("content") or ""
            now = time.perf_counter()
            if tok:
                if ttft is None:
                    ttft = now - t0
                chunks.append(tok)
    wall = time.perf_counter() - t0
    text = "".join(chunks)
    token_count_method = "chunks"
    tokens = len(chunks)
    if usage_tokens is not None and usage_tokens > 0:
        tokens = usage_tokens
        token_count_method = "usage"
    tps = tokens / wall if wall > 0 else 0.0
    return {
        "ttft_s": round(ttft, 4) if ttft is not None else round(wall, 4),
        "wall_s": round(wall, 4),
        "tokens": tokens,
        "token_count_method": token_count_method,
        "tok_per_s": round(tps, 3),
        "prompt_tokens": prompt_tokens,
        "text": text,
    }


def build_body(w: dict, nonce: str, rep: int, port: int) -> dict:
    return {
        "model": "specdec",
        "messages": [{"role": "user", "content": make_prompt_with_nonce(w, rep, nonce)}],
        "seed": int(w["seed"]),
        "max_tokens": int(w["max_tokens"]),
        "temperature": 0.6,
        "stream": True,
        # Ask the server to include usage in the final chunk so token counts are
        # taken from usage.completion_tokens, not from counting SSE chunks.
        "stream_options": {"include_usage": True},
    }


def nonce(workload_id: str, rep: int) -> str:
    return f"{workload_id}-r{rep}-{os.urandom(6).hex()}"


def dry_run(args) -> int:
    workloads = load_workloads(args.prompts_file and Path(args.prompts_file))
    print(f"[bench] DRY-RUN config-label={args.config_label} workloads={[w['id'] for w in workloads]}")
    ok = True
    for w in workloads:
        resolved = resolve_prompt(w)
        est = estimate_prompt_tokens(resolved)
        print(f"  w={w['id']:12s} kind={w['kind']:10s} est_prompt_tok={est}")
        for rep in range(1, args.reps + 1):
            n = nonce(w["id"], rep)
            body = build_body(w, n, rep, args.port)
            prompt = body["messages"][0]["content"]
            checks = {
                "seed": body.get("seed") == int(w["seed"]),
                "max_tokens": body.get("max_tokens") == int(w["max_tokens"]),
                "nonce-in-prompt": n in prompt,
                "temperature-0.6": body.get("temperature") == 0.6,
            }
            bad = [k for k, v in checks.items() if not v]
            status = "OK" if not bad else f"FAIL {bad}"
            if bad:
                ok = False
            print(f"    rep={rep} seed={body['seed']} max_tokens={body['max_tokens']} "
                  f"nonce={n.split('-')[-1]:12s} {status}")
    print("[bench] DRY-RUN: nothing written, no HTTP sent.")
    return 0 if ok else 3


def run_bench(args) -> int:
    workloads = load_workloads(args.prompts_file and Path(args.prompts_file))
    port = args.port
    completions_url = f"http://127.0.0.1:{port}/v1/chat/completions"
    health_url = f"http://127.0.0.1:{port}/health"
    print(f"[bench] config-label={args.config_label} endpoint={completions_url}")

    # Wait for server readiness.
    deadline = time.time() + 60
    ready = False
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=5) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(2)
    if not ready:
        print(f"[bench] FATAL: server not healthy at {health_url}", file=sys.stderr)
        return 2

    vram_before = nvidia_smi_mem_mb()

    # Warmup — first request after driver start, excluded from stats.
    warm = build_body(workloads[0], nonce(workloads[0]["id"], 0), 0, port)
    warm["max_tokens"] = 16
    print("[bench] warmup...", flush=True)
    try:
        stream_chat(completions_url, warm)
        print("[bench] warmup done", flush=True)
    except Exception as e:
        print(f"[bench] WARN: warmup failed ({e}); continuing", file=sys.stderr)

    argv = read_argv(args)
    build, build_status = parse_binary_build(args.server_log)
    spec = parse_spec_log(args.server_log)

    record = {
        "config_label": args.config_label,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "argv": argv,
        "argv_source": ("file" if args.argv_file else "inline" if args.argv else None),
        "binary_build": build,
        "binary_build_status": build_status,
        "server_log_parse": spec,
        "model_path": args.model_path,
        "binary_path": args.binary_path,
        "draft_path": args.draft_path,
        "model_sha256": sha256_file(args.model_path) if (args.sha and args.model_path and
                                                         Path(args.model_path).exists()) else None,
        "vram_before_mb": vram_before,
        "workloads": [],
        "medians": {},
    }

    reps = args.reps
    for w in workloads:
        wl = {"id": w["id"], "kind": w["kind"], "max_tokens": int(w["max_tokens"]),
              "seed": int(w["seed"]), "reps": []}
        for rep in range(1, reps + 1):
            n = nonce(w["id"], rep)
            body = build_body(w, n, rep, port)
            print(f"[bench] w={w['id']} rep={rep} ...", end="", flush=True)
            try:
                m = stream_chat(completions_url, body)
            except Exception as e:
                m = {"ttft_s": None, "wall_s": None, "tokens": 0, "token_count_method": "error",
                     "tok_per_s": 0.0, "text": None, "error": str(e)}
            wl["reps"].append({"rep": rep, "nonce": n, **m})
            if "error" not in m:
                print(f" ttft={m['ttft_s']}s wall={m['wall_s']}s tok/s={m['tok_per_s']} "
                      f"tokens={m['tokens']}", flush=True)
            else:
                print(f" ERROR: {m['error']}", flush=True)
        record["workloads"].append(wl)
        valid = [r for r in wl["reps"] if r.get("text") is not None]
        if valid:
            record["medians"][w["id"]] = {
                "ttft_s": round(statistics.median(r["ttft_s"] for r in valid if r["ttft_s"] is not None), 4),
                "wall_s": round(statistics.median(r["wall_s"] for r in valid if r["wall_s"] is not None), 4),
                "tok_per_s": round(statistics.median(r["tok_per_s"] for r in valid), 3),
                "n_valid": len(valid),
            }

    vram_after = nvidia_smi_mem_mb()
    record["vram_after_mb"] = vram_after

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"run_{args.config_label}.json"
    out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(f"[bench] wrote {out_path}")
    print("[bench] medians:", json.dumps(record["medians"], indent=2))
    # Total failure = no workload produced any valid rep. Distinguish it from a
    # completed-but-mediocre run (exit 0): the orchestrator must notice.
    if not record["medians"]:
        print("[bench] FATAL: no workload produced any valid rep (see record).",
              file=sys.stderr)
        return 3
    return 0


def compare(args) -> int:
    d = Path(args.compare)
    if not d.is_dir():
        print(f"[compare] FATAL: {d} is not a directory", file=sys.stderr)
        return 2
    records = sorted(d.glob("run_*.json"))
    if len(records) < 2:
        print(f"[compare] need >=2 run records in {d}; found {len(records)}", file=sys.stderr)
        return 2
    configs = {}
    for rp in records:
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[compare] WARN: unreadable {rp}: {e}")
            continue
        configs[rec["config_label"]] = rec
    if len(configs) < 2:
        print(f"[compare] need >=2 distinct configs; found {len(configs)}", file=sys.stderr)
        return 2

    print(f"[compare] comparing {sorted(configs)}")
    mismatches = 0
    for w in configs[list(configs)[0]]["workloads"]:
        wid = w["id"]
        per_cfg = {}
        for cfg, rec in configs.items():
            wmap = next((x for x in rec["workloads"] if x["id"] == wid), None)
            per_cfg[cfg] = {r["rep"]: (r.get("text") or "").strip() for r in (wmap["reps"] if wmap else [])}
        reps = sorted({r for m in per_cfg.values() for r in m})
        for rep in reps:
            texts = {cfg: per_cfg[cfg].get(rep, "") for cfg in configs}
            ref, others = list(texts.items())[0], list(texts.items())[1:]
            for cfg, t in others:
                if t != ref[1]:
                    mismatches += 1
                    print(f"[compare] WARN: MISMATCH workload={wid} rep={rep}: "
                          f"config '{ref[0]}' != '{cfg}'")
                    print(f"  len: {len(ref[1])} vs {len(t)}; "
                          f"common-prefix: {os.path.commonprefix([ref[1], t])[:120]!r} ...")
    if mismatches:
        print(f"[compare] {mismatches} mismatch(es) detected (exit stays 0: detector, not gate).")
    else:
        print(f"[compare] all workloads x reps token-identical across {len(configs)} configs "
              "(lossless spec-dec confirmed).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="4090 spec-decoding benchmark driver (stdlib only)")
    p.add_argument("--port", type=int, default=8005, help="llama-server bench port (default 8005)")
    p.add_argument("--config-label", default=None, help="config label written into the record")
    p.add_argument("--binary-path", default=None, help="server binary path (recorded only)")
    p.add_argument("--model-path", default=None, help="model path (recorded only)")
    p.add_argument("--draft-path", default=None, help="draft GGUF path (recorded only; q38-dflash2)")
    p.add_argument("--reps", type=int, default=3, help="reps per workload (default 3)")
    p.add_argument("--out-dir", default=str(REPO / "reports" / f"specdec_{today()}"),
                   help="output directory for run records")
    p.add_argument("--server-log", default=None, help="path to the Tee'd server log for parsing")
    p.add_argument("--argv-file", default=None, help="file with the server argv (one arg per line)")
    p.add_argument("--argv", default=None, help="full server argv as a single quoted string")
    p.add_argument("--sha", action="store_true", help="compute model sha256 (default off)")
    p.add_argument("--prompts-file", default=None,
                   help="workload JSON file (default bench/prompts_specdec.json)")
    p.add_argument("--dry-run", action="store_true", help="build+assert payloads, print, write nothing")
    p.add_argument("--compare", default=None, help="diff generated text across run records in this dir")
    args = p.parse_args()

    if args.dry_run and args.compare:
        print("--dry-run and --compare are mutually exclusive", file=sys.stderr)
        return 2
    if args.compare:
        return compare(args)
    # Real runs require a config label and an argv file so a run-record always
    # has provenance (executable argv). A --dry-run builds+prints payloads and
    # writes NOTHING, so it works fully offline without an argv file.
    if not args.config_label:
        print("--config-label is required", file=sys.stderr)
        return 2
    if not args.dry_run and not args.argv_file:
        print("--argv-file is required (provenance of the server argv)", file=sys.stderr)
        return 2
    if args.dry_run:
        return dry_run(args)
    return run_bench(args)


if __name__ == "__main__":
    sys.exit(main())
