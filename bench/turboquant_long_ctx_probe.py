"""Long-context VRAM probe.

Sends a ~100K-token prompt through production llama-server, samples nvidia-smi
in a background thread, and reports VRAM growth as the KV cache fills. The
goal: validate that TurboQuant turbo4/turbo3 KV cache delivers the predicted
~2.6 GB at-fill savings vs the pre-switch q8_0/q4_0 baseline.

Usage:
    python bench/turboquant_long_ctx_probe.py \
        --target-tokens 100000 \
        --server-url http://127.0.0.1:8004 \
        --label post-switch
"""

import argparse
import csv
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import urllib.request


def build_prompt(target_tokens: int) -> str:
    """Build a prompt that should tokenize to roughly target_tokens.
    Heuristic: ~0.7 tokens per English word, ~0.9 per French word average.
    We use a mixed-language paragraph and over-shoot, the server reports actual
    token count via usage.prompt_tokens.
    """
    paragraph_en = (
        "Plasma is the fourth state of matter, distinct from solid, liquid, and gas, "
        "characterized by partial or complete ionization of its constituent atoms. "
        "In atmospheric-pressure dielectric barrier discharges, electron energy distribution "
        "functions deviate substantially from Maxwellian, with high-energy tails driving "
        "selective chemistry. Filamentary regimes dominate in air due to electronegative "
        "attachment processes, while pure helium can sustain homogeneous glow discharges "
        "owing to long-lived metastable states and absence of attachment. The memory effect "
        "stored in residual surface charges modifies subsequent breakdown thresholds. "
    )
    paragraph_fr = (
        "Une décharge à barrière diélectrique atmosphérique est typiquement filamentaire "
        "dans l'air en raison de l'attachement électronique sur les molécules d'oxygène. "
        "Le temps de vie des charges résiduelles à la surface du diélectrique conditionne "
        "l'effet mémoire, qui modifie le champ de claquage du cycle suivant. Dans l'hélium "
        "pur, le régime homogène devient possible grâce aux métastables 2³S₁ et 2¹S₀, "
        "qui jouent un rôle de réservoir d'énergie et déclenchent l'ionisation Penning. "
        "La modélisation requiert au minimum une description fluide à deux fluides ou "
        "un schéma cinétique Boltzmann pour les électrons. "
    )
    chunk = paragraph_en + paragraph_fr  # ~150 words; measured ~310 tokens/chunk
    repeats_needed = max(1, target_tokens // 310)
    text = (chunk + "\n\n") * repeats_needed
    return text


def sample_vram() -> int | None:
    """One-shot nvidia-smi probe, returns memory_used MiB or None on failure."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None
        return int(r.stdout.strip().split("\n")[0])
    except Exception:
        return None


class VramSampler:
    def __init__(self, interval_s: float = 0.5):
        self.interval = interval_s
        self.samples: list[tuple[float, int]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        t0 = time.perf_counter()
        while not self._stop.is_set():
            v = sample_vram()
            if v is not None:
                self.samples.append((time.perf_counter() - t0, v))
            self._stop.wait(self.interval)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)


def http_post_json(url: str, body: dict, timeout: float = 1800.0) -> tuple[dict, float]:
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--server-url", default="http://127.0.0.1:8004")
    p.add_argument("--target-tokens", type=int, default=100000)
    p.add_argument("--max-completion", type=int, default=16)
    p.add_argument("--label", default="post-switch", help="Label for CSV row.")
    p.add_argument(
        "--output",
        default=str(Path(__file__).parent / "results" / "turboquant_long_ctx_probe.csv"),
    )
    args = p.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[probe] target ~{args.target_tokens} tokens, server={args.server_url}")
    print("[probe] building prompt...", flush=True)
    prompt = build_prompt(args.target_tokens)
    print(f"[probe] prompt char count: {len(prompt)}", flush=True)

    print("[probe] baseline VRAM samples (3s)...", flush=True)
    baseline_sampler = VramSampler(interval_s=0.5)
    baseline_sampler.start()
    time.sleep(3.0)
    baseline_sampler.stop()
    if not baseline_sampler.samples:
        print("[probe] FATAL: nvidia-smi not available", file=sys.stderr)
        return 2
    baseline_vram = max(v for _, v in baseline_sampler.samples)
    print(f"[probe] baseline VRAM peak: {baseline_vram} MiB", flush=True)

    print("[probe] launching probe + sampler...", flush=True)
    probe_sampler = VramSampler(interval_s=0.5)
    probe_sampler.start()

    body = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": args.max_completion,
        "temperature": 0.0,
        "seed": 1,
    }
    completions_url = args.server_url.rstrip("/") + "/v1/chat/completions"
    try:
        response, wall_ms = http_post_json(completions_url, body, timeout=1800.0)
    except Exception as e:
        probe_sampler.stop()
        print(f"[probe] FAILED: {e!r}", file=sys.stderr)
        return 3

    probe_sampler.stop()

    usage = response.get("usage") or {}
    timings = response.get("timings") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    prompt_ms = float(timings.get("prompt_ms", 0.0))
    predicted_ms = float(timings.get("predicted_ms", 0.0))
    prompt_per_second = float(timings.get("prompt_per_second", 0.0))
    predicted_per_second = float(timings.get("predicted_per_second", 0.0))

    if probe_sampler.samples:
        peak_vram = max(v for _, v in probe_sampler.samples)
        end_vram = probe_sampler.samples[-1][1]
        n_samples = len(probe_sampler.samples)
    else:
        peak_vram = end_vram = baseline_vram
        n_samples = 0

    delta_vs_baseline = peak_vram - baseline_vram

    print()
    print("=== probe results ===")
    print(f"  prompt_tokens     = {prompt_tokens}")
    print(f"  completion_tokens = {completion_tokens}")
    print(f"  prompt_eval_ms    = {prompt_ms:.0f}")
    print(f"  prompt_eval_tps   = {prompt_per_second:.1f}")
    print(f"  generation_ms     = {predicted_ms:.0f}")
    print(f"  generation_tps    = {predicted_per_second:.1f}")
    print(f"  wall_ms           = {wall_ms:.0f}")
    print(f"  baseline_vram_MiB = {baseline_vram}")
    print(f"  peak_vram_MiB     = {peak_vram}")
    print(f"  end_vram_MiB      = {end_vram}")
    print(f"  delta_vs_baseline = {delta_vs_baseline:+d} MiB")
    print(f"  vram_samples      = {n_samples}")

    write_header = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "timestamp_utc",
                "label",
                "target_tokens",
                "prompt_tokens",
                "completion_tokens",
                "prompt_eval_ms",
                "prompt_eval_tps",
                "generation_ms",
                "generation_tps",
                "wall_ms",
                "baseline_vram_MiB",
                "peak_vram_MiB",
                "end_vram_MiB",
                "delta_vram_MiB",
                "vram_samples",
            ])
        w.writerow([
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            args.label,
            args.target_tokens,
            prompt_tokens,
            completion_tokens,
            f"{prompt_ms:.2f}",
            f"{prompt_per_second:.3f}",
            f"{predicted_ms:.2f}",
            f"{predicted_per_second:.3f}",
            f"{wall_ms:.2f}",
            baseline_vram,
            peak_vram,
            end_vram,
            delta_vs_baseline,
            n_samples,
        ])
    print(f"[probe] result appended to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
