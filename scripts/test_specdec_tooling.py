#!/usr/bin/env python3
"""test_specdec_tooling.py -- stdlib unittest for the 4090 spec-dec tooling.

Run:  python scripts/test_specdec_tooling.py
Bounds: <2 min, no network beyond localhost, NO GPU, invokes the .ps1 scripts
through Windows PowerShell 5.1. All scratch lives under
C:\\Users\\test\\AppData\\Local\\Temp\\opencode\\ and is cleaned up.

Covers (per the accepted plan):
  (a) golden argv per config via the launcher -CheckOnly (fake model/draft +
      a .cmd stub binary whose --help contains draft-dflash; the dflash2
      golden passes -AssumeDflash2Capable because the generic stub's
      --version matches no allowlist entry -- the allowlist currently holds
      only the locally built PR #27342 marker; an allowlisted stub passes
      WITHOUT the hatch, see (i)).
  (b) refusals: q38-dflash2 missing draft -> 4; stub --help WITHOUT
      draft-dflash -> 4 mentioning PR #27342; q38-plain missing model -> 4.
  (c) GPU guard via a fake nvidia-smi.cmd prepended to PATH: empty output
      passes; one-PID output -> 2 (with -CheckOnly -> 0 + warning); stub
      exit 1 -> 3.
  (d) bench --dry-run: exit 0, payloads carry seed/max_tokens/nonce, nothing
      written.
  (e) stop_llama_port: a python subprocess holding an ephemeral port (name NOT
      llama-server) -> stop exits 1 and the process stays alive (then killed
      in teardown).
  (f) run_specdec_window: without -ApproveOutage -> 4; -CheckOnly -> 0.
  (g) q38-dflash2 + stub whose --help HAS draft-dflash and whose --version
      carries a b10488-like marker (r788) -> exit 4 mentioning PR #27342
      (b10488 is DFlash v1 only; DFlash2 is open/unmerged).
  (h) F9: same b10488-like stub + -AssumeDflash2Capable -> exit 4 (the b10488
      hard-refusal now sits ABOVE the expert hatch, so the hatch cannot
      override a known D-D-Flash-v1-only build).
  (i) allowlist entry: a stub whose --version carries the locally built
      PR #27342 marker (0.1.2-dev (build 1, commit 5ecbe1a)) passes the
      q38-dflash2 gate WITHOUT -AssumeDflash2Capable.
  (f1) run_harness -TestScrub: plants a fake scrub var (Z_TEST_FAKE_API_KEY) +
       HF_TOKEN, asserts both appear in the printed scrub list AND are hidden
       from a spawned python child (CHILD_VISIBLE=none).
  (f2) bench UTF-16LE (Tee-Object BOM) log: parse_binary_build / parse_spec_log
       extract values via the BOM-sniffing reader.
  (f3) bench stream_chat: synthetic SSE with a multi-token delta + a final
       usage chunk -> token count taken from usage.completion_tokens
       (token_count_method == "usage"), never conflated with chunk count.
  (j)  AC5: longctx generator determinism + estimate-in-range + instruction
       survival; --prompts-file plumbing through --dry-run; window param
       guards (-PromptsFile without -ReportTag -> 4, bogus -Configs -> 4);
       launcher rope flags absent from -CheckOnly argv when unset.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "scripts" / "start_llama_qwen38_27b_specdec.ps1"
STOPPER = REPO / "scripts" / "stop_llama_port.ps1"
WINDOW = REPO / "scripts" / "run_specdec_window.ps1"
HARNESS = REPO / "scripts" / "run_harness_ab.ps1"
BENCH = REPO / "bench" / "bench_specdec_4090.py"

# Import the bench module directly so the new F2/F3 tests can call its pure
# parsing helpers (read_log_text / parse_binary_build / parse_spec_log /
# stream_chat) instead of round-tripping through subprocesses.
sys.path.insert(0, str(REPO / "bench"))
import bench_specdec_4090 as bench  # noqa: E402

BASE_TMP = Path(
    os.environ.get("TEMP", r"C:\Users\test\AppData\Local\Temp")
) / "opencode"
SUITE_TMP = BASE_TMP / f"specdec-tooling-test-{int(time.time())}"

# The harness hardcodes its offline scratch root; -TestInternals leaves its
# fixtures under <scratch>\internals-fixtures for inspection.
SCRATCH_AB = Path(
    os.environ.get("TEMP", r"C:\Users\test\AppData\Local\Temp")
) / "opencode" / "specdec-ab"
INTERNALS_FIX = SCRATCH_AB / "internals-fixtures"

PWSH = "powershell"


def run_ps(script: Path, args, env=None) -> subprocess.CompletedProcess:
    cmd = [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=240)


def run_py(args, env=None, cwd=None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(BENCH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd, timeout=120)


def with_path(extra_dirs) -> dict:
    e = dict(os.environ)
    e["PATH"] = os.pathsep.join([str(d) for d in extra_dirs] + [e.get("PATH", "")])
    return e


def write_cmd(path: Path, content: str) -> Path:
    # cmd.exe is safest with CRLF; write the fake batch in CRLF.
    path.write_bytes(content.replace("\n", "\r\n").encode("ascii"))
    return path


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class SpecDeclToolingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = SUITE_TMP / "sandbox"
        cls.tmp.mkdir(parents=True, exist_ok=True)
        # fake artifacts
        cls.model = cls.tmp / "model.gguf"
        cls.model.write_bytes(b"FAKE MODEL")
        cls.draft = cls.tmp / "draft.gguf"
        cls.draft.write_bytes(b"FAKE DRAFT")

        cls.bin_dflash = write_cmd(
            cls.tmp / "stub_dflash.cmd",
            "@echo off\r\necho Llama server help\r\necho   --spec-type regex (draft-mtp, draft-dflash)\r\nexit /b 0\r\n",
        )
        cls.bin_nodflash = write_cmd(
            cls.tmp / "stub_nodflash.cmd",
            "@echo off\r\necho Llama server help\r\necho   --spec-type regex (draft-mtp only)\r\nexit /b 0\r\n",
        )
        # b10488-like: --help HAS draft-dflash (v1 flag, passes the necessary
        # check) but --version carries a b10488 marker (r788) -> DFlash v1
        # only, must be refused for q38-dflash2.
        cls.bin_b10488 = write_cmd(
            cls.tmp / "stub_b10488.cmd",
            "@echo off\r\necho Llama server help\r\necho   --spec-type regex (draft-mtp, draft-dflash)\r\necho build: 10488 (r788)\r\nexit /b 0\r\n",
        )
        # Allowlisted: --help HAS draft-dflash AND --version carries the
        # locally built PR #27342 marker (0.1.2-dev (build 1, commit 5ecbe1a))
        # -> must pass the q38-dflash2 gate WITHOUT -AssumeDflash2Capable.
        cls.bin_allowlisted = write_cmd(
            cls.tmp / "stub_allowlisted.cmd",
            "@echo off\r\necho Llama server help\r\necho   --spec-type regex (draft-mtp, draft-dflash)\r\necho version: 0.1.2-dev (build 1, commit 5ecbe1a)\r\nexit /b 0\r\n",
        )

        cls.smi_dir_empty = cls.tmp / "smi_empty"
        cls.smi_dir_pid = cls.tmp / "smi_pid"
        cls.smi_dir_fail = cls.tmp / "smi_fail"
        for d in (cls.smi_dir_empty, cls.smi_dir_pid, cls.smi_dir_fail):
            d.mkdir(exist_ok=True)
        write_cmd(cls.smi_dir_empty / "nvidia-smi.cmd", "@echo off\r\nexit /b 0\r\n")
        write_cmd(cls.smi_dir_pid / "nvidia-smi.cmd", "@echo off\r\necho 4321\r\nexit /b 0\r\n")
        write_cmd(cls.smi_dir_fail / "nvidia-smi.cmd", "@echo off\r\nexit /b 1\r\n")

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(SUITE_TMP, ignore_errors=True)
        except Exception:
            pass

    # ---- (a) golden argv per config ---------------------------------------
    def test_a_golden_argv_plain(self):
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout
        self.assertIn("--flash-attn on", out)
        self.assertIn("--cache-type-k q8_0", out)
        self.assertIn("--host 127.0.0.1", out)
        self.assertIn("--alias specdec-q38-plain", out)
        self.assertNotIn("--spec-type", out)

    def test_a_golden_argv_mtp(self):
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-mtp", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout
        self.assertIn("--spec-type draft-mtp", out)
        self.assertIn("--spec-draft-p-min 0.75", out)
        self.assertIn("--spec-draft-n-max 2", out)
        self.assertIn("--spec-draft-n-min 1", out)

    def test_a_golden_argv_dflash2(self):
        # The DFlash2 allowlist holds only the locally built PR #27342 marker,
        # so the generic draft-dflash stub (--version carries no allowlisted
        # marker) still needs the expert hatch for the golden-argv run.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-DraftPath", str(self.draft), "-BinaryPath", str(self.bin_dflash),
                              "-AssumeDflash2Capable", "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout
        self.assertIn("--spec-type draft-dflash", out)
        self.assertIn("-md", out)
        self.assertIn(str(self.draft), out)
        self.assertIn("--spec-draft-n-max 7", out)

    def test_a_golden_argv_dflash2_spec_draft_n_max(self):
        # F13: the q38-dflash2 flag set carries the official incoai README
        # block-8 flag --spec-draft-n-max 7 alongside --spec-type draft-dflash
        # and -md <draft>.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-DraftPath", str(self.draft), "-BinaryPath", str(self.bin_dflash),
                              "-AssumeDflash2Capable", "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--spec-draft-n-max 7", r.stdout)

    # ---- (b) refusals ------------------------------------------------------
    def test_b_dflash2_missing_draft_returns_4(self):
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)

    def test_b_binary_without_dflash_returns_4_pr(self):
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-DraftPath", str(self.draft), "-BinaryPath", str(self.bin_nodflash),
                              "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("PR #27342", r.stdout)

    def test_b_plain_missing_model_returns_4(self):
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain",
                              "-ModelPath", str(self.tmp / "nonexistent.gguf"),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)

    # ---- (g/h) b10488-like binary: DFlash v1 only ---------------------------
    def test_g_b10488_like_binary_returns_4_pr27342(self):
        # --help HAS draft-dflash (necessary check passes) but --version
        # carries a b10488 marker (r788): the capability allowlist is empty
        # and b10488 is refused-by-design (DFlash v1 only; DFlash2 is
        # PR #27342, open/unmerged as of 2026-08-19).
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-DraftPath", str(self.draft), "-BinaryPath", str(self.bin_b10488),
                              "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("#27342", r.stdout)

    def test_h_b10488_like_hatch_now_refused(self):
        # F9: the b10488 hard-refusal was moved ABOVE the -AssumeDflash2Capable
        # hatch, so the EXPERT-ONLY override can no longer hatch a known
        # D-Flash-v1-only b10488 build. The hatch never even runs: exit 4 with
        # the b10488/PR #27342 message and NO "ASSUMED" warning.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-DraftPath", str(self.draft), "-BinaryPath", str(self.bin_b10488),
                              "-AssumeDflash2Capable", "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("#27342", r.stdout)
        self.assertNotIn("ASSUMED", r.stdout)

    def test_i_allowlisted_stub_passes_without_hatch(self):
        # The allowlist now carries the locally built PR #27342 marker
        # (0.1.2-dev (build 1, commit 5ecbe1a)); a stub whose --version matches
        # it passes the q38-dflash2 gate WITHOUT -AssumeDflash2Capable.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-dflash2", "-ModelPath", str(self.model),
                              "-DraftPath", str(self.draft), "-BinaryPath", str(self.bin_allowlisted),
                              "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("matches known DFlash2-capable marker", r.stdout)
        self.assertNotIn("ASSUMED", r.stdout)

    # ---- (c) GPU guard -----------------------------------------------------
    def test_c_empty_smi_passes(self):
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_c_busy_without_check_returns_2(self):
        env = with_path([self.smi_dir_pid])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash)], env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_c_busy_with_check_returns_0_warning(self):
        env = with_path([self.smi_dir_pid])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("GPU", r.stdout)

    def test_c_smi_fail_returns_3(self):
        env = with_path([self.smi_dir_fail])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash)], env=env)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    # ---- (d) bench --dry-run ----------------------------------------------
    def test_d_bench_dry_run(self):
        argv_file = self.tmp / "argv.txt"
        argv_file.write_text("--model fake\n--port 8005\n", encoding="utf-8")
        no_out = SUITE_TMP / "no_dry_out_dir"
        r = run_py(["--dry-run", "--config-label", "dryrun-check",
                    "--argv-file", str(argv_file), "--out-dir", str(no_out)])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("seed=42", r.stdout)
        self.assertIn("max_tokens", r.stdout)
        self.assertIn("nonce", r.stdout)
        self.assertFalse(no_out.exists(), f"dry-run must not create {no_out}")

    # ---- (e) stop helper against a non-llama-server ------------------------
    def test_e_stop_refuses_non_llama(self):
        port = free_port()
        child_script = (
            "import socket,sys,time\n"
            "p=int(sys.argv[1])\n"
            "s=socket.socket()\n"
            "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
            "s.bind(('127.0.0.1',p))\n"
            "s.listen(1)\n"
            "print('READY', flush=True)\n"
            "time.sleep(120)\n"
        )
        child = subprocess.Popen([sys.executable, "-c", child_script, str(port)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = child.stdout
        stderr = child.stderr
        try:
            deadline = time.time() + 20
            while time.time() < deadline:
                if child.poll() is not None:
                    self.fail("child exited early")
                line = stdout.readline()
                if "READY" in line:
                    break
            r = run_ps(STOPPER, ["-Port", str(port)])
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIsNone(child.poll(), "non-llama-server must NOT be killed")
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except Exception:
                child.kill()
            for f in (stdout, stderr):
                try:
                    f.close()
                except Exception:
                    pass

    # ---- (f) window gate / CheckOnly ---------------------------------------
    def test_f_window_requires_approval(self):
        r = run_ps(WINDOW, [])
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)

    def test_f_window_checkonly_returns_0(self):
        r = run_ps(WINDOW, ["-CheckOnly"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # ---- F1: env scrub is exposed AND actually hides secrets from a child -----
    def test_f1_scrub_prints_and_hides_fake_var(self):
        env = dict(os.environ)
        env["Z_TEST_FAKE_API_KEY"] = "planted-fake"
        env["HF_TOKEN"] = "planted-hf"
        r = run_ps(HARNESS, ["-TestScrub"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # the fake scrub var (and the widened *_TOKEN* pattern) show up in the
        # printed scrub list ...
        self.assertIn("Z_TEST_FAKE_API_KEY", r.stdout)
        self.assertIn("HF_TOKEN", r.stdout)
        # ... and -TestScrub actually spawns a python child under the scrubbed
        # env; that child must NOT see either planted secret.
        self.assertIn("CHILD_VISIBLE=none", r.stdout)

    # ---- F2: Tee-Object UTF-16LE logs parse via BOM sniff --------------------
    def test_f2_utf16_log_parses(self):
        bom = b"\xff\xfe"
        build_log = self.tmp / "utf16_server.log"
        build_log.write_bytes(bom + "build: a1b2c3d (r999)\n".encode("utf-16-le"))
        build, status = bench.parse_binary_build(str(build_log))
        self.assertEqual(status, "parsed")
        self.assertEqual(build, "a1b2c3d")

        spec_log = self.tmp / "utf16_spec.log"
        spec_log.write_bytes(bom + "n_accept=5 draft tokens\n".encode("utf-16-le"))
        spec = bench.parse_spec_log(str(spec_log))
        self.assertEqual(spec["status"], "parsed")
        self.assertIsNotNone(spec["matches"])

    # ---- F3: usage.completion_tokens preferred over chunk count --------------
    def test_f3_sse_usage_tokens_used(self):
        sse_body = (
            "data: " + json.dumps({"choices": [{"delta": {"content": "hello "}}]}) + "\n\n"
            "data: " + json.dumps({"choices": [{"delta": {"content": "world"}}]}) + "\n\n"
            "data: " + json.dumps({"choices": []}) + "\n\n"
            "data: " + json.dumps({"usage": {"completion_tokens": 12}}) + "\n\n"
            "data: [DONE]\n\n"
        ).encode("utf-8")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(sse_body)
                self.wfile.flush()

            def log_message(self, *args):
                pass

        port = free_port()
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            res = bench.stream_chat(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                {"model": "x", "stream": True, "stream_options": {"include_usage": True}},
            )
        finally:
            srv.shutdown()
            srv.server_close()
            t.join(timeout=5)

        # 2 content deltas -> text is "hello world", but usage says 12 tokens.
        self.assertEqual(res["text"], "hello world")
        self.assertEqual(res["token_count_method"], "usage")
        self.assertEqual(res["tokens"], 12)

    def test_f3_build_body_requests_usage(self):
        body = bench.build_body({"prompt": "x", "id": "w", "seed": 42, "max_tokens": 16},
                                "nonce-1", 1, 8005)
        self.assertTrue(body["stream_options"]["include_usage"])

    # ---- AC5: long-context workload generator ------------------------------
    def _longctx_workload(self, wid="longctx_ut", target=300, seed=42,
                          instruction="INSTRUCTION"):
        return {"id": wid, "kind": "longctx", "prompt": instruction,
                "fill_target_tokens": target, "fill_seed": seed,
                "max_tokens": 256, "seed": 42}

    def test_ac5_longctx_generator_deterministic(self):
        # Same (id, fill_seed) => byte-identical expanded prompt; a different
        # workload id => different filler block.
        w = self._longctx_workload()
        w_other = self._longctx_workload("longctx_ut_other")
        p1 = bench.resolve_prompt(w)
        p2 = bench.resolve_prompt(w)
        p3 = bench.resolve_prompt(w_other)
        self.assertEqual(p1, p2)
        self.assertNotEqual(p1, p3)

    def test_ac5_longctx_estimate_and_instruction(self):
        # Estimated size within +-20% of fill_target_tokens AND the instruction
        # survives the expansion.
        target = 8000
        w = self._longctx_workload(target=target)
        text = bench.resolve_prompt(w)
        est = bench.estimate_prompt_tokens(text)
        self.assertTrue(0.8 * target <= est <= 1.2 * target,
                        f"est {est} outside +-20% of {target}")
        self.assertIn("INSTRUCTION", text)
        self.assertGreater(len(text), 1000)

    def test_ac5_prompts_file_plumbing_dry_run(self):
        # --prompts-file must reach the workload loader through --dry-run,
        # fully offline (no server, no writes).
        pf = REPO / "bench" / "prompts_specdec_longctx.json"
        r = run_py(["--config-label", "dry-longctx-test", "--dry-run",
                    "--prompts-file", str(pf)], cwd=REPO)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("longctx_32k", r.stdout)
        self.assertIn("longctx_64k", r.stdout)
        self.assertIn("est_prompt_tok", r.stdout)

    # ---- AC5: window param guards ------------------------------------------
    def test_ac5_window_promptsfile_requires_reporttag(self):
        # Evidence preservation: a non-default workload set must not write into
        # the default report dir; -PromptsFile without -ReportTag/-OutDir is a
        # refusal (exit 4) even under -CheckOnly.
        pf = REPO / "bench" / "prompts_specdec_longctx.json"
        r = run_ps(WINDOW, ["-CheckOnly", "-PromptsFile", str(pf)])
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("PromptsFile", r.stdout)

    def test_ac5_window_bogus_config_rejected(self):
        r = run_ps(WINDOW, ["-CheckOnly", "-Configs", "q38-fake"])
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("unknown -Configs", r.stdout)

    # ---- AC5: launcher rope flags absent when unset ------------------------
    def test_ac5_launcher_rope_absent_when_unset(self):
        # argv identical to today: with -RopeScaling/-RopeScale unset the
        # printed effective argv carries NO rope flags.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("--rope-scaling", r.stdout)
        self.assertNotIn("--rope-scale", r.stdout)

    # ---- KV-cache type / ubatch overrides (2026-08-19 f16 experiment) -------
    def test_kv_defaults_in_argv(self):
        # No -Ctk/-Ctv/-UbatchSize: the effective argv keeps the hardcoded
        # defaults (q8_0 / q4_0 / 512) -- byte-identical to today.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--cache-type-k q8_0", r.stdout)
        self.assertIn("--cache-type-v q4_0", r.stdout)
        self.assertIn("--ubatch-size 512", r.stdout)

    def test_kv_overrides_in_argv(self):
        # -Ctk f16 -Ctv f16 -UbatchSize 1024: the three overrides appear in the
        # effective argv and the hardcoded defaults do NOT.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly",
                              "-Ctk", "f16", "-Ctv", "f16", "-UbatchSize", "1024"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--cache-type-k f16", r.stdout)
        self.assertIn("--cache-type-v f16", r.stdout)
        self.assertIn("--ubatch-size 1024", r.stdout)
        self.assertNotIn("--cache-type-k q8_0", r.stdout)
        self.assertNotIn("--cache-type-v q4_0", r.stdout)
        self.assertNotIn("--ubatch-size 512", r.stdout)

    def test_kv_bogus_ctk_refused(self):
        # An unknown -Ctk value is a fail-closed refusal (exit 4), never a
        # silent fallback to the default.
        env = with_path([self.smi_dir_empty])
        r = run_ps(LAUNCHER, ["-Config", "q38-plain", "-ModelPath", str(self.model),
                              "-BinaryPath", str(self.bin_dflash), "-CheckOnly",
                              "-Ctk", "bogus"], env=env)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("invalid KV-cache type", r.stdout)
        self.assertIn("f16", r.stdout)

    # ---- harness repair 2026-08-19: refusal gate / grading watchdog / ref test --

    def test_harn_refusal_gate_requires_run(self):
        # BLOCKER regression net: the 'REFUS (exit 4)' block must be GATED on
        # -not $Run (a bare invocation still refuses) and the real-run path must
        # sit AFTER the gate (previously the gate was unconditional and the whole
        # -Run path below it was dead code).
        text = HARNESS.read_text(encoding="utf-8")
        guard = text.find("if (-not $Run)")
        refusal = text.find("REFUS (exit 4)")
        run_path = text.find("REAL RUN PATH")
        self.assertGreaterEqual(guard, 0, "missing 'if (-not $Run)' gate in run_harness_ab.ps1")
        self.assertGreaterEqual(refusal, 0, "missing 'REFUS (exit 4)' block in run_harness_ab.ps1")
        self.assertLess(guard, refusal,
                        "'if (-not $Run)' must precede the REFUS block (dead -Run path would return)")
        self.assertGreater(run_path, refusal,
                           "the real-run path must follow the refusal gate (or it is dead code)")

    def test_harn_grading_watchdog_times_out(self):
        # The grading python child must run under a hard watchdog cap: a module
        # that blocks at import (time.sleep(9999)) must be killed after the cap
        # (5 s in the -TestInternals probe) -> solved=False / grade_exit=-2 /
        # timed_out=True, the grade log carries the timeout line, and the probe
        # itself returns promptly (never hangs inside the outage window).
        # F2: the hanging module prints "ALIVE-BEFORE-HANG" (flushed) BEFORE
        # sleeping; the timeout path must kill the tree FIRST and then flush
        # the drains, so that marker survives into the grade log (it would
        # previously have been written as "" because the drains were awaited
        # while the pipes were still open).
        t0 = time.time()
        r = run_ps(HARNESS, ["-TestInternals"])
        elapsed = time.time() - t0
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("HANGPROBE solved=False grade_exit=-2 timed_out=True", r.stdout)
        self.assertIn("GRADE TIMEOUT", r.stdout)
        self.assertIn("ALIVE-BEFORE-HANG", r.stdout,
                      "HANGPROBE output must echo the marker line from the grade log")
        self.assertLess(elapsed, 90,
                        f"hanging-fixture probe must return promptly (took {elapsed:.1f}s)")
        # Re-read the leftover grade log itself: the marker must have been
        # flushed by the kill-first-then-drain order.
        hang_log = INTERNALS_FIX / "hang" / "grade_hang.log"
        if not hang_log.exists():
            # harness scratch hardcodes the default TEMP location; tolerate a
            # different TEMP here before failing the fixture-read assertion
            hang_log = Path(r"C:\Users\test\AppData\Local\Temp\opencode\specdec-ab") \
                / "internals-fixtures" / "hang" / "grade_hang.log"
        self.assertTrue(hang_log.exists(), f"hang grade log missing: {hang_log}")
        hang_text = hang_log.read_text(encoding="utf-8", errors="replace")
        self.assertIn("ALIVE-BEFORE-HANG", hang_text,
                      "partial output before the hang must survive into the grade log")

    def test_harn_reference_test_overwrite(self):
        # t1 self-grading bias: the arm-authored test must be overwritten with
        # the harness-held reference BEFORE grading. A sabotaged always-pass
        # test must NOT win solved for a correct impl (it grades True via the
        # reference) and must NOT rescue a wrong impl (grades False). The
        # -TestInternals probe prints both decisions and verifies the on-disk
        # replacement; we assert the output AND re-read the leftover fixture.
        r = run_ps(HARNESS, ["-TestInternals"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REFOVERWRITE correct_impl solved=True grade_exit=0 overwritten=True", r.stdout)
        self.assertIn("REFOVERWRITE wrong_impl solved=False", r.stdout)
        replaced = INTERNALS_FIX / "refoverwrite_ok" / "test_rate_limiter.py"
        if not replaced.exists():
            # harness scratch hardcodes the default TEMP location; tolerate a
            # different TEMP here before failing the fixture-read assertion
            replaced = Path(r"C:\Users\test\AppData\Local\Temp\opencode\specdec-ab") \
                / "internals-fixtures" / "refoverwrite_ok" / "test_rate_limiter.py"
        self.assertTrue(replaced.exists(), f"reference-overwrite fixture missing: {replaced}")
        text = replaced.read_text(encoding="utf-8")
        self.assertNotIn("TestSabotage", text, "arm-authored test must be replaced, not kept")
        self.assertIn("class TestFixedWindowLimiter", text,
                      "replacement must be the harness-held reference test")

    def test_harn_bare_invocation_refuses(self):
        # Bonus net (same as the window script): a bare invocation must refuse
        # with exit 4 so a mis-typed orchestration call can never fall through
        # to the real-run path by accident.
        r = run_ps(HARNESS, [])
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("REFUS (exit 4)", r.stdout)

    def test_harn_shadow_cleanup_and_scaffold_wipe(self):
        # F7: a fake unittest.py / sitecustomize.py in the task dir could hijack
        # grading (exit 0 unconditionally) via cwd shadowing. Write-ReferenceTest
        # must delete them before grading: the correct impl then grades via the
        # REAL unittest (solved=True) and the wrong impl fails (solved=False),
        # with the fake files gone. The -TestInternals probe prints all three.
        # F7b: Write-ScaffoldTask must wipe stale files (a previous -Run's
        # solution) before re-seeding the same task dir.
        # Bonus: the task-brief quoting-safety gate is asserted offline.
        r = run_ps(HARNESS, ["-TestInternals"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SHADOWCLEAN correct_impl solved=True grade_exit=0 fake_gone=True", r.stdout)
        self.assertIn("SHADOWCLEAN wrong_impl solved=False", r.stdout)
        self.assertIn("fake_gone=True", r.stdout)
        self.assertIn("SCAFFOLDWIPE stray_gone=True", r.stdout)
        self.assertIn("BRIEFSAFE ok=True", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
