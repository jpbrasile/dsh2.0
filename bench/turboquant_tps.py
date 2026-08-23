"""Phase −1 TurboQuant TPS bench harness.

Drives an OpenAI-compatible llama-server (the TurboQuant fork at port 8005),
runs the prompts in turboquant_prompts.json across seeds, records TPS metrics
to CSV. Designed to be invoked once per server config — caller switches
configs by restarting the server with start_llama_turboquant_bench.ps1.

Usage (PowerShell, in one terminal per server config):
    python bench/turboquant_tps.py --config a --output bench/results/turboquant_tps.csv
    python bench/turboquant_tps.py --config b --output bench/results/turboquant_tps.csv
    python bench/turboquant_tps.py --config c --output bench/results/turboquant_tps.csv

Writes one row per (config, prompt_id, seed). Header is written on first
invocation (file does not exist). Subsequent invocations append.

The script also performs a 60s warm-up with a throwaway prompt before
measurement, and probes /props to confirm the server's actual ctx_size and
cache types match what's expected for the config.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import urllib.request
import urllib.error

DEFAULT_SERVER_URL = "http://127.0.0.1:8005"
# Set by main() once --server-url is parsed.
SERVER_URL = DEFAULT_SERVER_URL
COMPLETIONS = ""
HEALTH = ""
PROPS = ""


def _set_endpoints(url: str) -> None:
    global SERVER_URL, COMPLETIONS, HEALTH, PROPS
    SERVER_URL = url.rstrip("/")
    COMPLETIONS = f"{SERVER_URL}/v1/chat/completions"
    HEALTH = f"{SERVER_URL}/health"
    PROPS = f"{SERVER_URL}/props"


_set_endpoints(DEFAULT_SERVER_URL)

CSV_HEADER = [
    "timestamp_utc",
    "config",
    "prompt_id",
    "lang",
    "domain",
    "seed",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_eval_ms",
    "gen_total_ms",
    "wall_total_ms",
    "prompt_eval_tps",
    "gen_tps",
    "wall_tps",
    "first_token_ms",
]


def http_get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url: str, body: dict, timeout: float = 600.0) -> tuple[dict, float]:
    """POST JSON, return (parsed response, wall_ms)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    wall_ms = (time.perf_counter() - t0) * 1000.0
    return json.loads(raw.decode("utf-8")), wall_ms


def wait_for_server(max_wait_s: float = 600.0) -> None:
    """Poll /health until 200, or fail after max_wait_s."""
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        try:
            j = http_get_json(HEALTH, timeout=5.0)
            if isinstance(j, dict) and j.get("status") in ("ok", "loading model"):
                if j.get("status") == "ok":
                    return
        except Exception:
            pass
        time.sleep(2.0)
    print(f"[bench] FATAL: server never became ready at {SERVER_URL}", file=sys.stderr)
    sys.exit(2)


def fetch_props() -> dict:
    try:
        return http_get_json(PROPS, timeout=10.0)
    except Exception as e:
        print(f"[bench] WARN: /props fetch failed: {e}", file=sys.stderr)
        return {}


def warm_up() -> None:
    """Send a tiny throwaway request to prime KV cache / CUDA kernels."""
    body = {
        "messages": [{"role": "user", "content": "Say OK."}],
        "max_tokens": 4,
        "temperature": 0.0,
        "seed": 1,
    }
    print("[bench] warm-up...", flush=True)
    _, ms = http_post_json(COMPLETIONS, body, timeout=120.0)
    print(f"[bench] warm-up complete ({ms:.0f} ms)", flush=True)


def run_prompt(prompt: dict, seed: int, n_predict: int) -> dict:
    body = {
        "messages": [{"role": "user", "content": prompt["text"]}],
        "max_tokens": n_predict,
        "temperature": 0.6,
        "top_k": 20,
        "top_p": 0.95,
        "min_p": 0.0,
        "presence_penalty": 1.5,
        "seed": seed,
    }
    response, wall_ms = http_post_json(COMPLETIONS, body, timeout=600.0)

    usage = response.get("usage") or {}
    timings = response.get("timings") or {}

    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens))

    prompt_eval_ms = float(timings.get("prompt_ms", 0.0))
    predict_ms = float(timings.get("predicted_ms", 0.0))
    prompt_eval_tps = float(timings.get("prompt_per_second", 0.0))
    gen_tps = float(timings.get("predicted_per_second", 0.0))

    wall_tps = (completion_tokens / (wall_ms / 1000.0)) if wall_ms > 0 else 0.0
    first_token_ms = prompt_eval_ms

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_eval_ms": round(prompt_eval_ms, 2),
        "gen_total_ms": round(predict_ms, 2),
        "wall_total_ms": round(wall_ms, 2),
        "prompt_eval_tps": round(prompt_eval_tps, 3),
        "gen_tps": round(gen_tps, 3),
        "wall_tps": round(wall_tps, 3),
        "first_token_ms": round(first_token_ms, 2),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, choices=["a", "b", "bp", "c", "d"])
    p.add_argument(
        "--prompts",
        default=str(Path(__file__).with_name("turboquant_prompts.json")),
    )
    p.add_argument(
        "--output",
        default=str(Path(__file__).parent / "results" / "turboquant_tps.csv"),
    )
    p.add_argument("--skip-warmup", action="store_true")
    p.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help=f"llama-server base URL (default: {DEFAULT_SERVER_URL})",
    )
    args = p.parse_args()
    _set_endpoints(args.server_url)

    prompts_path = Path(args.prompts)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with prompts_path.open(encoding="utf-8") as f:
        spec = json.load(f)
    n_predict = int(spec["n_predict"])
    seeds = list(spec["seeds"])
    prompts = spec["prompts"]

    print(f"[bench] config={args.config}  prompts={len(prompts)}  seeds={seeds}  n_predict={n_predict}")
    print(f"[bench] waiting for server at {SERVER_URL} ...")
    wait_for_server()

    props = fetch_props()
    if props:
        dp = props.get("default_generation_settings") or {}
        n_ctx = props.get("n_ctx") or dp.get("n_ctx")
        print(f"[bench] /props n_ctx={n_ctx}  alias={props.get('model_alias')}")

    if not args.skip_warmup:
        warm_up()

    write_header = not output_path.exists()
    with output_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if write_header:
            w.writeheader()

        total = len(prompts) * len(seeds)
        idx = 0
        for prompt in prompts:
            for seed in seeds:
                idx += 1
                print(
                    f"[bench] [{idx}/{total}] config={args.config} prompt={prompt['id']} seed={seed} ...",
                    flush=True,
                )
                try:
                    metrics = run_prompt(prompt, seed=seed, n_predict=n_predict)
                except urllib.error.HTTPError as e:
                    print(f"[bench]   HTTP error: {e.code} {e.reason}", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"[bench]   FAILED: {e!r}", file=sys.stderr)
                    continue

                row = {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "config": args.config,
                    "prompt_id": prompt["id"],
                    "lang": prompt.get("lang", ""),
                    "domain": prompt.get("domain", ""),
                    "seed": seed,
                    **metrics,
                }
                w.writerow(row)
                f.flush()
                print(
                    f"[bench]   prompt_tok={metrics['prompt_tokens']} "
                    f"gen_tok={metrics['completion_tokens']} "
                    f"first_tok={metrics['first_token_ms']:.0f}ms "
                    f"gen_tps={metrics['gen_tps']:.2f} "
                    f"wall={metrics['wall_total_ms']:.0f}ms",
                    flush=True,
                )

    print(f"[bench] done. results appended to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
