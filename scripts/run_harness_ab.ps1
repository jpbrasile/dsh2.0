# run_harness_ab.ps1 -- coding-agent A/B harness: OpenCode (leg A) vs DSH
# (DeepSeek Harness, leg B), both driven through the SAME local spec-dec bench
# server on :8005. Decision metric (docs/SPECDEC_4090_BENCH.md): median
# wall-clock per SUCCESSFULLY SOLVED task for Qwen3.8-27B served as
# q38-plain / q38-mtp / q38-dflash2. This harness is the honest consumer test:
# server-level tok/s numbers are never the decision.
#
# Repair 2026-08-19 (human-approved: "do the real work, if it fails we will
# correct"). Defects fixed vs the previous 372-line draft:
#   D1  leg B used a CLI grammar that does not exist in
#       @deepseek-ai/dsh@0.1.0-rc.7 (no `run` subcommand, no --cwd/--base-url/
#       --model). Grammar: `dsh --profile headless "<task text>"`, single
#       positional; task scope = process cwd (set via -WorkingDirectory here).
#   D1a config keys verified (details + evidence in the findings block below).
#       Anything unverified -> exit 4 BEFORE :8004 is stopped.
#   D2  stray `profile headless` probe inside leg B's stopwatch removed -- only
#       the actual task run is timed. The dsh --help probe runs ONCE at harness
#       start, outside any stopwatch.
#   D3  config loop really iterates q38-plain / q38-mtp / q38-dflash2 (the old
#       draft only ever used $aliasList[0]).
#   D4  solved-task grading: each (config, arm, task) ends with the task's
#       unittests; solved = exit 0. Missing module / import error = UNSOLVED,
#       never a harness crash.
#   D5  server orchestration: launcher + health poll (<= 10 min, early-exit on
#       launcher death) + port-scoped stop per config; :8004 outage discipline;
#       production restore ALWAYS in a finally block.
#   D6  watchdog exit codes (measured 2026-08-19): Start-Process -PassThru +
#       -RedirectStandardOutput returns a process object that cannot report
#       ExitCode ("the process was not started by this object", PS 5.1 cmdlet
#       bug) -- every normal-exit child read exit=$null, so gradings mapped to
#       -1 (solved=false even for a passing suite) and launcher gates read
#       `$null -ne 0` => "refused". Invoke-WatchdogProcess now launches via
#       [System.Diagnostics.Process]::Start (real owner object, reliable
#       ExitCode) with async stdout/stderr drains to the log files.
#
# Pre-run fix pass 2026-08-19 (review-mandated, applied and covered by
# scripts/test_specdec_tooling.py):
#   F1  Resolve-LauncherExe viaFile path: the .ps1 shim source is now QUOTED at
#       the join point ('"{0}"' -f $r.source) -- an unquoted spaced path would
#       split into two argv tokens and break every such launch. A leg-A launch
#       probe (`opencode --version` under the watchdog, offline-safe) runs in
#       the D1a gate area of -Run and exits 4 BEFORE :8004 is stopped if the
#       launcher cannot start.
#   F2  Invoke-WatchdogProcess timeout path: kill the tree FIRST, then wait the
#       drains (1-2 s), then write the logs -- previously the drains were
#       awaited while the pipes were still open and the logs were written as "".
#       The hanging-module fixture prints "ALIVE-BEFORE-HANG" before sleeping;
#       the watchdog probe asserts the marker survives into the grade log.
#   F4  after each stop_llama_port.ps1 call in the config loop, poll up to 30 s
#       until no llama-server process remains and :$BenchPort is free, so the
#       next config's launcher GPU guard cannot trip on a dying server.
#   F7  grading hijack via cwd shadowing: Write-ReferenceTest deletes
#       unittest.py / unittest/ / sitecustomize.py / usercustomize.py from the
#       task dir before grading (a fake unittest.py that exits 0 unconditionally
#       could otherwise make every task "solved").
#   F7b Write-ScaffoldTask wipes the task dir before re-seeding (stale
#       solutions from a previous -Run must not leak into the next scaffold),
#       guarded to the harness scratch root only.
#   Bonus: a bare invocation refuses with exit 4 (like the window script), and
#       -Run gates on task-brief quoting safety (no '"' or '%' in any brief).
#
# ---------------------------------------------------------------------------
# FIREWALL WAIVER (2026-08-19, human-authorized -- NOT executed by this script):
#   Outbound firewall rules were NOT added. Compensating controls implemented
#   HERE instead:
#     * env scrub for every child process: any var matching API_KEY / _TOKEN /
#       SECRET / PASSWORD, GOOGLE_APPLICATION_CREDENTIALS, and the prefixes
#       HF_*, GITHUB_*, SUPABASE_*, ANTHROPIC_*, OPENROUTER_* is stripped from
#       the child env (a reference dump is available via -TestScrub).
#     * DSH_TELEMETRY_DISABLED=1 is set explicitly in the leg B child env (in
#       addition to the scrub).
#     * the dsh version is PINNED (@deepseek-ai/dsh@0.1.0-rc.7); the version is
#       never re-resolved at run time.
#     * the three tasks are self-contained toy tasks (scratch root only, no
#       repo access, no secrets anywhere).
#   Residual risk: DSH plugin telemetry if any (default-off per rc.7 docs); the
#   pinned package is fetched once over npm at run start.
#
# ---------------------------------------------------------------------------
# DSH @deepseek-ai/dsh@0.1.0-rc.7 -- CLI GRAMMAR + CONFIG RESOLUTION
# (verified 2026-08-19; the authoring session could not run `npx --help` -- the
# environment refused the invocation -- so every claim below is cited, and the
# real run RE-VERIFIES it all empirically at start via Test-DshConfigKnown;
# any unconfirmed item -> exit 4 BEFORE :8004 is stopped):
#
#   CLI grammar (package docs, deepseekdocs.com/en/docs/user-guide/cli):
#     dsh --profile headless "<task text>"   # one-off task; exits when done
#     dsh --profile web | dsh web | dsh plugin ...
#   There is NO `run` subcommand and NO --cwd/--base-url/--model flags.
#   Workspace = the process working directory (we pass -WorkingDirectory).
#
#   Config keys (package docs: deepseekdocs.com/en/docs/user-guide/configuration,
#   /features/multi-model, /user-guide/credentials, /reference/env-vars; source:
#   github.com/deepseek-ai/deepseek-harness packages/*):
#     * settings file:        $DSH_HOME/settings.yaml   (default ~/.dsh)
#     * agent default model:  agent-default-model: { provider, model }
#                             (shared by web/headless/API entry points)
#     * custom provider:      llm-pi-ai.providers.<route>:
#                               apiKeyEnv: <ENV_VAR>    (credential REFERENCE,
#                                                        never the key itself)
#                               api: openai-completions
#                               baseURL: <endpoint>
#                               models: [ { id: <name> } ]
#     * credentials file:     $DSH_HOME/.credentials.yaml (CREDENTIALS_FILENAME).
#
#   What is NOT confirmed from the package and therefore NOT used:
#     * an invoking-directory `.env` pickup by dsh (the old plan's mechanism).
#       Only ~/.dsh/.env for the OFFICIAL DEEPSEEK_API_KEY is documented. The
#       harness uses the CONFIRMED settings.yaml route instead; no task-dir
#       .env is written (it could also be picked up by leg A's opencode).
#
# ---------------------------------------------------------------------------
# CO-DEGRADATION NOTES (read before approving an outage; copied from
# run_specdec_window.ps1):
#   * memory_guard hook: while :8004 is down, any memory_guard invocation that
#     health-checks the local LLM will observe the outage and may take its
#     configured action (alert / halt dependent work).
#   * codegen_* skills/agents default to :8004 as their LLM base URL: requests
#     issued during the window fail with connection refused (fail-fast, no
#     silent degradation) and retry on the next attempt.
#   * local_bridge defaults to :8004: every call routed through it fails
#     during the window.
#   * The 03:00 nightly probe (agentic-flow-nightly-llm-probe) may alert if a
#     window overlaps it -- scheduled work is NOT paused by this script.
#
# ALIAS NOTE (deviation from the plan, with repo evidence): the launcher builds
#   --alias specdec-$Config  (start_llama_qwen38_27b_specdec.ps1, line 131;
#   asserted by scripts/test_specdec_tooling.py test_a_golden_argv_plain:
#   "--alias specdec-q38-plain"). The plan's AC3 said the alias is
#   "specdec-plain"; the real server alias is specdec-q38-<cfg>. The model id
#   sent by BOTH arms therefore is specdec-q38-<cfg> -- matching the launcher's
#   registered alias exactly (llama.cpp tolerates unknown model strings -- the
#   bench driver sends "model":"specdec" -- but matching the alias is the
#   correct, non-guessing choice).
#
# FAIRNESS NOTE: every (config, arm, task) starts from a FRESH scaffold of the
# task dir (seed files + brief.txt rewritten; opencode.json written for leg A),
# so no arm inherits files a previous arm left behind. Logs live OUTSIDE the
# re-scaffolded dir (report logs\ subfolder).
#
# ---------------------------------------------------------------------------
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -CheckOnly
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -TestScrub
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -TestInternals
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -GradeProbeDir <fixture> [-GradeProbeModule test_rate_limiter] [-GradeProbeTimeoutSeconds 5]
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -Run
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -Run -Dflash2BinaryPath C:\Users\test\tools\llama-cpp\llama-cuda-pr27342-5ecbe1a\llama-server.exe
#
# -Dflash2BinaryPath <path>: optional; used ONLY for the q38-dflash2 config and
# passed to the launcher as -BinaryPath. Without it, q38-dflash2 is SKIPPED
# with a recorded warning (the default b10488 binary is refused by the
# launcher's DFlash2 gate by design).
#
# -TaskTimeoutSeconds <n>: per-arm-task watchdog hard cap (default 900 = 15 min;
# on timeout the child process tree is killed and the run is recorded
# solved=false, timeout=true).
#
# Flow (real run, -Run):
#   1. D1a config gate (empirically re-verifies the dsh grammar + settings keys
#      from the installed package; exit 4 with a clear message on ANY
#      unconfirmed item -- BEFORE :8004 is stopped)
#   2. record :8004 listener state -> <report>\state_8004_before.json
#   3. stop :8004 via stop_llama_port.ps1 -Port 8004 (refusal aborts the config
#      sequence and is recorded)
#   4. per config q38-plain / q38-mtp / q38-dflash2:
#        a. launcher -CheckOnly (gate); q38-dflash2 failure = SKIP + warning,
#           other configs = recorded failure
#        b. write the per-config DSH settings ($DSH_HOME\settings.yaml, backed
#           up; llm-pi-ai.providers.bench + agent-default-model = current alias)
#        c. launch the bench server (launcher -LogPath <report>\harness_<cfg>-server.log)
#        d. health-poll http://127.0.0.1:8005/health <= 10 min with early-exit
#           detection on the launcher process (Wait-HealthOrExit)
#        e. per task (t1, t2, t3): leg A (opencode) then grade, leg B (dsh)
#           then grade -- DSH always after OpenCode so a DSH crash cannot lose
#           leg A
#        f. port-scoped stop of the 8005 server
#   5. finally (ALWAYS): restore $DSH_HOME\settings.yaml, restart_production.ps1,
#      poll http://localhost:8004/health <= 10 min,
#      write <report>\production_restored.json
#   6. write <report>\harness_ab.json and exit:
#        0 = completed + production restored
#        1 = production NOT restored (FATAL message)
#        2 = completed, restore ok, but an ATTEMPTED config produced zero graded
#           runs (or nothing was attempted at all)
#        4 = refusal / unconfirmed-config gate
#
# -CheckOnly: FULLY OFFLINE (no network, no model, no child process): validates
# the scratch root is creatable, opencode is on PATH, prints the per-config
# plan (including the dflash2 binary presence when -Dflash2BinaryPath is given),
# exits 0.
#
# -TestScrub: prints the scrubbed-key list and proves the scrub hides those vars
# from a spawned child; exits 0. (Unchanged in spirit from the earlier draft.)
#
# -TestInternals: offline probes of the new pure logic for
# scripts/test_specdec_tooling.py -- grading decision fixtures, watchdog
# constant, tasks.json/brief scaffolding, DSH settings writer keys, the grading
# watchdog (hanging agent module, cap 5 s) and the reference-test overwrite.
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$Run,
    [switch]$TestScrub,
    [switch]$TestInternals,
    [switch]$OpenCodeOnly,
    [string[]]$Configs = @("q38-plain", "q38-mtp", "q38-dflash2"),
    [string]$ReportTag,
    [string]$Dflash2BinaryPath,
    [int]$TaskTimeoutSeconds = 900,
    # OFFLINE grading self-test (used by scripts/test_specdec_tooling.py):
    # grade ONE fixture dir under the same watchdog + scrub + reference-overwrite
    # path the real run uses, with a caller-provided hard cap. No network/GPU.
    [string]$GradeProbeDir,
    [string]$GradeProbeModule = "test_grade_probe",
    [int]$GradeProbeTimeoutSeconds = 300
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScratchRoot = "C:\Users\test\AppData\Local\Temp\opencode\specdec-ab"
$DshVersion  = "0.1.1-rc.2"   # pinned 2026-08-24; NEVER re-resolved at run time
# Pin history: 0.1.0-rc.7 (2026-08-19) until 2026-08-24. Bumped because the
# machine's dsh ecosystem migrated to 0.1.1-rc.2 (daily launcher scripts/dsh.ps1,
# profiles, and ~/.dsh/.credentials.yaml versioned format `version:`+`refs:`);
# rc.7's credentials-local reads only the old flat map and dies at boot
# ("the value for \"version\" ... must be a string", run 2 of 2026-08-24).
# The D1a gate below still empirically re-verifies grammar + config keys against
# THIS pin at every -Run and exits 4 before any outage on a mismatch.
# 2026-08-24 (2): rc.2 is NEVER invoked via bare npx. `npx -y @deepseek-ai/dsh@<v>`
# pins only the app package; its 65 caret deps re-resolve at install time and the
# tree DRIFTS (measured 21/08 in scripts/dsh.ps1: app rc.7 + plugins rc.8, presets
# broken; measured today: bare-npx rc.2 --help hung >300 s at 2 GB RSS and was
# watchdog-killed). The machine's real dsh is the LOCKED runtime tree below
# (harness/runtime/package-lock.json, 511 packages, verified by
# `python harness/pin_check.py`); its --help answers in <1 s. Leg B and both
# D1a probes therefore run `node <runtime bin.js>` -- also the reference
# invocation of scripts/bench_julia_effort/bench.py::commande_dsh() (the .cmd
# shim truncates multi-line args, so node+bin.js directly). rc.2 renamed
# --dump-default-config to --dump-config (empirical: --help 2026-08-24).
$DshRuntimeDir = Join-Path (Join-Path (Join-Path $env:USERPROFILE ".dsh") "runtime") ("dsh-" + $DshVersion)
$DshBinJs      = Join-Path $DshRuntimeDir "node_modules\@deepseek-ai\dsh\lib\bin.js"
$BenchPort   = 8005
$ProdPort    = 8004
$Launcher    = Join-Path $RepoRoot "scripts\start_llama_qwen38_27b_specdec.ps1"
$Stopper     = Join-Path $RepoRoot "scripts\stop_llama_port.ps1"
$Restart     = Join-Path $RepoRoot "scripts\restart_production.ps1"
$ValidConfigs = @("q38-plain", "q38-mtp", "q38-dflash2")
# Normalize -Configs (comma-joined via -File arrives as ONE string element).
$NormalizedConfigs = @()
foreach ($c in $Configs) {
    foreach ($part in ($c -split ',')) {
        $t = $part.Trim()
        if ($t) { $NormalizedConfigs += $t }
    }
}
$Configs = $NormalizedConfigs
# The launcher's --alias IS specdec-q38-<cfg> (see the ALIAS NOTE in the header).
$AliasMap    = @{
    "q38-plain"    = "specdec-q38-plain"
    "q38-mtp"      = "specdec-q38-mtp"
    "q38-dflash2"  = "specdec-q38-dflash2"
}
$DshApiKeyEnv = "DSH_BENCH_API_KEY"   # apiKeyEnv reference we configure (dummy key, local server)
$DshRoute     = "bench"               # llm-pi-ai.providers.<route> we configure

# Common system prompt (2026-08-20): the SAME instruction text is injected into
# BOTH arms so the A/B compares agent machinery, not a prompt-skill asymmetry.
# leg B (dsh) reads it via settings.yaml `system-prompt.persona`; leg A (opencode)
# reads it via an AGENTS.md written into the task dir. No {{...}} braces (dsh
# interpolates complete {{group}} strictly and would throw on an unknown ref),
# and no double-quote / percent (the same argv-quoting fragility the brief gate
# guards). Kept deliberately tool-agnostic and behavior-only.
$CommonSystemPrompt = @'
You are a coding agent completing one self-contained programming task.
Work only inside the current working directory.
Read brief.txt for the exact task instructions.
Create or edit the requested files, run the tests with `python -m unittest`, and make all tests pass.
Do not read or write anything outside this directory, and do not use the network.
Be concise: finish as soon as the tests pass.
'@

function Log([string]$msg) { Write-Host ("[harness] {0}" -f $msg) }

# ----------------------------------------------------------------------------
# env scrubbing for child processes (kept from the earlier draft)
# ----------------------------------------------------------------------------
function Is-ScubbedKey([string]$name) {
    if ($name -match "API_KEY|_TOKEN|SECRET|PASSWORD") { return $true }
    if ($name -eq "GOOGLE_APPLICATION_CREDENTIALS") { return $true }
    foreach ($prefix in @("HF_", "GITHUB_", "SUPABASE_", "ANTHROPIC_", "OPENROUTER_")) {
        if ($name.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Get-ScrubbedKeys {
    $names = @()
    foreach ($k in [System.Environment]::GetEnvironmentVariables().Keys) {
        $name = [string]$k
        if (Is-ScubbedKey $name) { $names += $name }
    }
    return $names
}

function Invoke-ScrubbedChild {
    param([scriptblock]$Body)
    $saved = @{}
    foreach ($k in @(Get-ScrubbedKeys)) {
        if (Test-Path ("env:" + $k)) {
            $saved[$k] = (Get-Item ("env:" + $k)).Value
            Remove-Item ("env:" + $k) -ErrorAction SilentlyContinue
        }
    }
    try {
        & $Body
    } finally {
        foreach ($k in $saved.Keys) { Set-Item -Path ("env:" + $k) -Value $saved[$k] }
    }
}

# ----------------------------------------------------------------------------
# health helpers (copied from run_specdec_window.ps1)
# ----------------------------------------------------------------------------
function Test-Health([string]$url, [int]$timeoutSec = 5) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
    } catch { return $false }
}

function Wait-Health([string]$url, [int]$timeoutSec = 600) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health $url 5) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Wait-HealthOrExit([string]$url, [int]$timeoutSec, $proc) {
    # Health-poll while also watching the launched launcher process. If the
    # launcher itself exits (refused / crashed) we surface that immediately
    # instead of burning the full wait. Returns
    #   @{ Healthy = bool; Exited = bool; ExitCode = <int or $null> }
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health $url 5) { return @{ Healthy = $true; Exited = $false; ExitCode = $null } }
        if ($proc -and $proc.HasExited) {
            return @{ Healthy = $false; Exited = $true; ExitCode = $proc.ExitCode }
        }
        Start-Sleep -Seconds 5
    }
    $exited = ($proc -and $proc.HasExited)
    return @{ Healthy = $false; Exited = $exited; ExitCode = $(if ($exited) { $proc.ExitCode } else { $null }) }
}

function Wait-LlamaServerGone([int]$port, [int]$maxSeconds = 30) {
    # F4: after stop_llama_port.ps1 returns, the killed llama-server may still
    # be shutting down (taskkill signals; the process list / port linger for a
    # moment). The NEXT config's launcher starts with a GPU guard (nvidia-smi
    # process scan); a dying llama-server still in the process list would trip
    # that guard and cascade-fail the whole window. Poll until no llama-server
    # process remains AND :$port is free, bounded $maxSeconds. Returns $true if
    # clean, $false if the bound expired (caller logs a warning and continues).
    $deadline = (Get-Date).AddSeconds($maxSeconds)
    while ((Get-Date) -lt $deadline) {
        $procs = @(Get-Process llama-server -ErrorAction SilentlyContinue)
        if ($procs.Count -eq 0) {
            # port check: a connect that SUCCEEDS means something still listens
            $portFree = $true
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                try {
                    $tcp.Connect("127.0.0.1", $port)
                    $portFree = $false
                } catch { $portFree = $true }
                finally { $tcp.Close() }
            } catch { $portFree = $true }
            if ($portFree) { return $true }
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

# ----------------------------------------------------------------------------
# task definitions (self-contained: no repo access). Every arm starts from a
# fresh scaffold, so the seeds are byte-identical for every (config, arm).
# t1's brief was corrected 2026-08-19: it said "fix-rate_limiter.py" (a file
# name that cannot be imported); grading runs `python -m unittest
# test_rate_limiter`, so the module written by the arm must be importable
# (rate_limiter.py).
# ----------------------------------------------------------------------------
function New-TaskSpecs {
    return @(
        @{
            id = "t1-write-module"
            test_module = "test_rate_limiter"
            brief = "Write a self-contained Python module rate_limiter.py: class FixedWindowLimiter(capacity, window_seconds) with methods try_acquire() -> bool and reset(), thread-safe, stdlib-only, plus a unittest file test_rate_limiter.py exercising it. Both files must live in THIS directory. Run the tests with `python -m unittest test_rate_limiter` and ensure they pass. No external dependencies, no repo access."
            seed = @{}
        },
        @{
            id = "t2-fix-bug"
            test_module = "test_seed"
            brief = "A seeded bug is present in seed.py in this directory. The companion test_seed.py currently FAILS. Fix seed.py (ONLY; never modify test_seed.py) so ALL tests pass. Run `python -m unittest test_seed` to confirm. No repo access."
            seed = @{
                "seed.py" = @'
import math

def primes_upto(n):
    """Return a list of primes <= n (n >= 2)."""
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(math.isqrt(n)) + 1):
        if sieve[i]:
            # SEEDED BUG: the step is i, not i+1, so composites are never cleared.
            for j in range(i * i, n + 1, i + 1):
                sieve[j] = False
    return [i for i in range(2, n + 1) if sieve[i]]
'@
                "test_seed.py" = @'
import unittest
from seed import primes_upto

class TestPrimes(unittest.TestCase):
    def test_first(self):
        self.assertEqual(primes_upto(10), [2, 3, 5, 7])
    def test_limit(self):
        self.assertEqual(primes_upto(30)[-1], 29)
    def test_count(self):
        self.assertEqual(len(primes_upto(100)), 25)

if __name__ == "__main__":
    unittest.main()
'@
            }
        },
        @{
            id = "t3-refactor"
            test_module = "test_seed"
            brief = "seed.py in this directory works for the common case but contains duplicated logic (two nearly identical helpers for min/max clipping) and fails when the min and max bounds are given in reversed order. Refactor seed.py (ONLY; never modify test_seed.py) to remove the duplication AND make normalize(vals, lo, hi) clamp each value into the inclusive interval [min(lo, hi), max(lo, hi)], i.e. it must also give a correct result when lo > hi. Run `python -m unittest test_seed` to verify all tests pass before finishing. No repo access."
            seed = @{
                "seed.py" = @'
def clamp_low(x, lo):
    if x < lo:
        return lo
    return x

def clamp_high(x, hi):
    if x > hi:
        return hi
    return x

def normalize(vals, lo, hi):
    return [clamp_low(clamp_high(v, hi), lo) for v in vals]
'@
                "test_seed.py" = @'
import unittest
from seed import normalize

class TestNormalize(unittest.TestCase):
    def test_in_range(self):
        self.assertEqual(normalize([1, 5, 9], 0, 10), [1, 5, 9])
    def test_low(self):
        self.assertEqual(normalize([-3, 0], 0, 10), [0, 0])
    def test_high(self):
        self.assertEqual(normalize([11, 20], 0, 10), [10, 10])
    def test_reversed_bounds(self):
        # lo > hi: the interval is [min(lo, hi), max(lo, hi)] = [0, 10].
        # A clamp written as clamp_low(clamp_high(v, hi), lo) gives
        # [10, 10, 10] here (wrong); the correct result is [0, 5, 10].
        self.assertEqual(normalize([-5, 5, 15], 10, 0), [0, 5, 10])

if __name__ == "__main__":
    unittest.main()
'@
            }
        }
    )
}

function Test-TaskBriefsSafe {
    # Bonus gate: briefs reach the child argv as '"{0}"' (pre-quoted by the
    # callers, since Invoke-WatchdogProcess space-joins and never re-quotes). A
    # double quote inside a brief would break that fragile-by-construction
    # quoting, and '%' is fragile-by-construction in Windows argument strings.
    # Fail fast at harness start if any task brief violates this. Returns
    # @{ ok = bool; task = <id or $null>; char = <char or $null> }.
    foreach ($s in @(New-TaskSpecs)) {
        foreach ($ch in @('"', '%')) {
            if ($s.brief.IndexOf($ch) -ge 0) {
                return @{ ok = $false; task = $s.id; char = $ch }
            }
        }
    }
    return @{ ok = $true; task = $null; char = $null }
}

function Write-ScaffoldTask([hashtable]$spec, [string]$root) {
    # (Re)create one task dir from seed: identical inputs every call. F7b: the
    # dir PERSISTS across runs (and across arms), so a stale solution from a
    # previous -Run could leak into the next scaffold -- wipe it first, then
    # recreate. Defense in depth: refuse to remove anything not under the
    # harness scratch root ($ScratchRoot).
    $dir = Join-Path $root $spec.id
    if (Test-Path -LiteralPath $dir) {
        $resolved = [System.IO.Path]::GetFullPath($dir)
        $scratch = [System.IO.Path]::GetFullPath($ScratchRoot).TrimEnd('\')
        $prefix = $scratch + '\'
        if (-not $resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "REFUS: refusing to wipe '$resolved' -- not under the harness scratch root '$scratch'"
        }
        Remove-Item -LiteralPath $dir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Set-Content -Path (Join-Path $dir "brief.txt") -Value $spec.brief -Encoding ascii
    foreach ($name in $spec.seed.Keys) {
        [System.IO.File]::WriteAllText((Join-Path $dir $name), [string]$spec.seed[$name])
    }
    return $dir
}

function Write-TasksJson([object[]]$specs, [string]$root) {
    $payload = @{ tasks = @($specs | ForEach-Object {
        @{ id = $_.id; test_module = $_.test_module; brief = $_.brief }
    }) }
    $payload | ConvertTo-Json -Depth 6 |
        Out-File -FilePath (Join-Path $root "tasks.json") -Encoding ascii
}

# ----------------------------------------------------------------------------
# grading (AC4): after EVERY (config, arm, task), run the task's unittests in
# the task dir. solved = exit 0. Missing module / import error / failing test
# = UNSOLVED, never a harness crash.
# ----------------------------------------------------------------------------
function Remove-GradingHijackFiles([string]$dir) {
    # F7: grading runs `python -m unittest ...` with cwd = the task dir, so a
    # stale file named unittest.py (or a unittest/ package) would SHADOW the
    # stdlib module and let an agent hijack grading (a fake unittest.py that
    # exits 0 unconditionally would make every task "solved"). sitecustomize.py
    # / usercustomize.py are auto-imported by CPython at startup when cwd is on
    # sys.path and are never legitimate for these toy tasks. All four are
    # deleted before grading.
    foreach ($name in @("unittest.py", "sitecustomize.py", "usercustomize.py")) {
        $p = Join-Path $dir $name
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
    }
    $pkg = Join-Path $dir "unittest"
    if (Test-Path -LiteralPath $pkg) {
        Remove-Item -LiteralPath $pkg -Recurse -Force
    }
}

function Write-ReferenceTest([hashtable]$task, [string]$dir) {
    # Neutralizes self-grading bias: overwrite the arm-authored test file with a
    # HARNESS-HELD reference BEFORE grading; also removes cwd-shadowing files
    # (F7) that could hijack grading itself.
    #   * t1 (test_rate_limiter): a reference test exercising the CORRECT
    #     FixedWindowLimiter(capacity, window_seconds) contract -- try_acquire()
    #     up to capacity then False, reset() then True again. A trivial
    #     always-pass arm test can no longer win solved + a tiny wall_s.
    #   * t2/t3 (test_seed): rewrite test_seed.py from the task spec (also
    #     undoes any tampering with a test the arm was told NOT to modify).
    # Returns $true if a reference test was written, $false if none is known for
    # this module (e.g. an external grading fixture -- left untouched).
    Remove-GradingHijackFiles $dir
    $testName = $task.test_module
    $path = Join-Path $dir ($testName + ".py")
    if ($testName -eq "test_rate_limiter") {
        [System.IO.File]::WriteAllText($path, @'
import unittest
from rate_limiter import FixedWindowLimiter

class TestFixedWindowLimiter(unittest.TestCase):
    def test_allows_up_to_capacity(self):
        l = FixedWindowLimiter(2, 1.0)
        self.assertTrue(l.try_acquire())
        self.assertTrue(l.try_acquire())
        self.assertFalse(l.try_acquire())

    def test_reset_reopens_window(self):
        l = FixedWindowLimiter(1, 1.0)
        self.assertTrue(l.try_acquire())
        self.assertFalse(l.try_acquire())
        l.reset()
        self.assertTrue(l.try_acquire())

if __name__ == "__main__":
    unittest.main()
'@)
        return $true
    }
    if ($task.seed -and $task.seed.ContainsKey(($testName + ".py"))) {
        [System.IO.File]::WriteAllText($path, [string]$task.seed[($testName + ".py")])
        return $true
    }
    return $false
}

function Invoke-GradeUnittest([hashtable]$task, [string]$taskDir, [string]$gradeLog,
                              [int]$timeoutSec = 300) {
    # (1) overwrite the arm-written test with the harness-held reference;
    # (2) run the grading unittests under the WATCHDOG (hard cap, default 300 s)
    #     inside a SCRUBBED child env (agent code cannot dump OPENROUTER_API_KEY
    #     into the grade log) -- a blocking agent module times out to
    #     solved=false / grade_exit=-2 instead of hanging the whole outage
    #     session before the finally restores :8004.
    $solved = $false
    $exit = $null
    $timedOut = $false
    try {
        Write-ReferenceTest $task $taskDir
        $r = Invoke-ScrubbedChild {
            Invoke-WatchdogCommand "python" @("-m", "unittest", $task.test_module) $taskDir $gradeLog $timeoutSec
        }
        if ($r.timed_out) {
            $timedOut = $true
            $exit = -2
            Add-Content -Path $gradeLog -Value ("GRADE TIMEOUT (hard cap >= {0}s): agent-written code blocked; treated as solved=false." -f $timeoutSec) -Encoding ascii
        } else {
            $exit = $r.exit
            # e.g. python missing / command not resolvable -> unsolved, never a
            # harness crash.
            if ($null -eq $exit) { $exit = -1 }
        }
        $solved = ($exit -eq 0)
    } catch {
        # e.g. a terminating error inside the call: unsolved, harness keeps going.
        $solved = $false
        if ($null -eq $exit) { $exit = -1 }
        Add-Content -Path $gradeLog -Value ("GRADE ERROR (unsolved, not a harness crash): {0}" -f $_) -Encoding ascii
    }
    return @{ solved = $solved; exit = $exit; log = $gradeLog; timed_out = $timedOut }
}

# ----------------------------------------------------------------------------
# watchdog (AC3): Start-Process -PassThru + WaitForExit(ms); on timeout kill
# the child process TREE (taskkill /T /F; fallback Stop-Process) and record
# timeout. PS 5.1 compatible.
# ----------------------------------------------------------------------------
function Stop-ProcessTree([int]$processId) {
    try {
        & taskkill.exe /PID $processId /T /F 2>&1 | Out-Null
    } catch { }
    try { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue } catch { }
}

function Invoke-WatchdogProcess([string]$exe, [object[]]$argList, [string]$cwd,
                                [string]$logPath, [int]$timeoutSec) {
    # Returns @{ exit; wall_s; timed_out; error }
    # PS 5.1 defect (measured 2026-08-19): Start-Process -PassThru combined with
    # -RedirectStandardOutput returns a process object whose ExitCode access
    # throws "the process was not started by this object" -- every NORMAL-exit
    # child came back exit=$null (grading mapped it to -1 => solved=false even
    # for a passing suite; launcher gates read `$null -ne 0` => "refused").
    # Fixed by launching through [System.Diagnostics.Process]::Start (the
    # returned object OWNS the process, ExitCode is reliable) with async
    # stdout/stderr drains to the same <logPath>/<logPath>.err files. The drains
    # start BEFORE WaitForExit so a chatty child cannot deadlock on the pipe
    # buffer (4 KB). On TIMEOUT the order matters (F2): kill the tree FIRST --
    # only a dead process tree closes the pipe handles, and only then can the
    # drain tasks complete -- then wait the drains briefly, then write the
    # logs. The partial output that the kill leaves in the pipe buffers
    # survives as evidence.
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = [string]::Join(" ", $argList)
    $psi.WorkingDirectory = $cwd
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    try {
        $p = [System.Diagnostics.Process]::Start($psi)
    } catch {
        $sw.Stop()
        return @{ exit = $null; wall_s = [math]::Round($sw.Elapsed.TotalSeconds, 1); timed_out = $false; error = $_.Exception.Message }
    }
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    $exited = $p.WaitForExit($timeoutSec * 1000)
    if (-not $exited) {
        # F2 timeout path: kill the tree FIRST (the pipes stay open while any
        # process in the tree lives, so waiting for the drains before the kill
        # would hang and write ""), then wait the drains 1-2 s, then write the
        # logs. Killing closes the pipes; partial output survives.
        Stop-ProcessTree $p.Id
        $p.WaitForExit(2000) | Out-Null
        try { $outTask.Wait(2000) | Out-Null } catch { }
        try { $errTask.Wait(2000) | Out-Null } catch { }
        try {
            [System.IO.File]::WriteAllText($logPath, $(if ($outTask.IsCompleted) { $outTask.Result } else { "" }))
            [System.IO.File]::WriteAllText("$logPath.err", $(if ($errTask.IsCompleted) { $errTask.Result } else { "" }))
        } catch { }
        $sw.Stop()
        return @{ exit = $null; wall_s = [math]::Round($sw.Elapsed.TotalSeconds, 1); timed_out = $true; error = $null }
    }
    try { $outTask.Wait(5000) | Out-Null } catch { }
    try { $errTask.Wait(5000) | Out-Null } catch { }
    try {
        [System.IO.File]::WriteAllText($logPath, $(if ($outTask.IsCompleted) { $outTask.Result } else { "" }))
        [System.IO.File]::WriteAllText("$logPath.err", $(if ($errTask.IsCompleted) { $errTask.Result } else { "" }))
    } catch { }
    $sw.Stop()
    return @{ exit = $p.ExitCode; wall_s = [math]::Round($sw.Elapsed.TotalSeconds, 1); timed_out = $false; error = $null }
}

function Resolve-LauncherExe([string]$commandName) {
    # Resolve a PATH command to something Invoke-WatchdogProcess can launch (a
    # real executable for [Process]::Start). .ps1 shims go through powershell
    # -File; everything else launches directly.
    $cmd = Get-Command $commandName -ErrorAction SilentlyContinue
    if (-not $cmd) { return $null }
    if ($cmd.Source -and $cmd.Source.ToLower().EndsWith(".ps1")) {
        return @{ exe = "powershell.exe"; viaFile = $true; source = $cmd.Source }
    }
    return @{ exe = $cmd.Source; viaFile = $false; source = $cmd.Source }
}

function Invoke-WatchdogCommand([string]$commandName, [object[]]$argList, [string]$cwd,
                                [string]$logPath, [int]$timeoutSec) {
    # Wrapper: resolves $commandName on PATH, then runs it under the watchdog
    # with its arguments. Args are pre-quoted by the caller when they contain
    # spaces (the naive space-join in Invoke-WatchdogProcess does not re-quote).
    $r = Resolve-LauncherExe $commandName
    if (-not $r) {
        return @{ exit = $null; wall_s = $null; timed_out = $false; error = "$commandName not on PATH" }
    }
    if ($r.viaFile) {
        # F1: quote the .ps1 source AT THE JOIN POINT. Invoke-WatchdogProcess
        # space-joins the args and never re-quotes, so an unquoted spaced path
        # ("C:\Program Files\...") would split into two argv tokens and every
        # such launch would fail. Callers pre-quote args with spaces the same
        # way ('"{0}"' -f ...).
        $full = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ('"{0}"' -f $r.source))
        $full += $argList
        return Invoke-WatchdogProcess $r.exe $full $cwd $logPath $timeoutSec
    }
    return Invoke-WatchdogProcess $r.exe $argList $cwd $logPath $timeoutSec
}

# ----------------------------------------------------------------------------
# leg A (AC3): per-task PROJECT-scoped opencode.json in the task dir (never the
# global config), provider baseURL http://127.0.0.1:8005/v1, model = the server
# alias of the CURRENT config. `opencode run --dangerously-skip-permissions`
# cwd=task dir, scrubbed env, watchdog cap.
# ----------------------------------------------------------------------------
function Write-OpencodeJson([string]$taskDir, [string]$modelAlias) {
    # DEFECT 1 fix (2026-08-20): the schema shape the INSTALLED opencode
    # (npm build 1.18.18) actually accepts. The old shape wrote top-level
    # "provider" as the STRING "bench" plus a bogus "providers" (plural) key;
    # 1.18.18 refused it with "Expected object | undefined, got 'bench' provider"
    # and every leg-A arm exited 1 in ~1.3 s BEFORE any model call. This socket
    # shape was derived EMPIRICALLY 2026-08-20 (scratch dir under
    # %TEMP%\opencode\ocdiag + `opencode agent list` -> exit 0, `opencode models`
    # -> bench/specdec-q38-plain) and matches the repo's own root opencode.json:
    #   * top-level "provider" is an OBJECT keyed by provider id
    #   * each provider block: { npm, name, options: { baseURL, apiKey } }
    #   * "models" is an OBJECT map keyed by model id (not an array)
    #   * NO "providers" (plural) top-level key
    $models = @{}
    $models[$modelAlias] = @{ id = $modelAlias; name = $modelAlias }
    # D4 (2026-08-20): the top-level "model" (and the `--model` CLI arg) must be
    # the providerID/modelID form "bench/<alias>", NOT the bare alias. The bare
    # alias is not resolvable to a provider, so opencode silently fell back to
    # the default provider (openrouter/deepseek) and every leg-A arm died in
    # ~1 s with "Unexpected server error" (measured: stub server on :8005 never
    # received the request; "bench/specdec-q38-plain" DOES reach it).
    $modelRef = "bench/$modelAlias"
    $cfg = @{
        model = $modelRef
        provider = @{
            bench = @{
                npm = "@ai-sdk/openai-compatible"
                name = "local spec-dec bench (port 8005)"
                options = @{
                    baseURL = "http://127.0.0.1:$BenchPort/v1"
                    apiKey = "bench"
                }
                models = $models
            }
        }
    }
    [System.IO.File]::WriteAllText((Join-Path $taskDir "opencode.json"), ($cfg | ConvertTo-Json -Depth 8))
}

function Resolve-OpencodeNpmBin {
    # D3 (2026-08-20): leg A must launch the NPM opencode binary directly, NOT
    # the repo's opencode.ps1 shim. The shim runs its A4/G4 pre-flight
    # (opencode agent list + resolve_perms.py) from the child's cwd -- and
    # Invoke-LegOpenCode runs the child from the TASK DIR, where the repo's
    # .opencode/agents are out of scope, so the G4 gate refuses every leg-A
    # launch (measured 2026-08-20: 6/6 arms exit 1 in ~2 s before any model
    # call). The raw npm binary has no such shim pre-flight. Resolution order:
    #   1. $env:APPDATA\npm\node_modules\opencode-ai\bin\opencode.exe (npm
    #      install, the 1.18.x build the harness schema was validated against)
    #   2. any bare 'opencode.cmd' / 'opencode.exe' on PATH (npm shim or
    #      standalone), as long as it is NOT the repo-root opencode.ps1.
    $npmBin = Join-Path $env:APPDATA "npm\node_modules\opencode-ai\bin\opencode.exe"
    if (Test-Path -LiteralPath $npmBin) { return @{ exe = $npmBin; viaFile = $false } }
    $cmd = Get-Command opencode -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.CommandType -ne "ExternalScript") { return @{ exe = $cmd.Source; viaFile = $false } }
    if ($cmd -and $cmd.CommandType -eq "ExternalScript" -and $cmd.Source -and -not $cmd.Source.ToLower().EndsWith("opencode.ps1")) {
        return @{ exe = $cmd.Source; viaFile = $false }
    }
    return $null
}

function Invoke-LegOpenCode([hashtable]$task, [string]$alias, [string]$logPath, [int]$timeoutSec) {
    Write-OpencodeJson $task.dir $alias
    # Inject the COMMON system prompt via AGENTS.md in the task dir (opencode
    # reads it as global agent instructions; dsh gets the same text through
    # settings.yaml `system-prompt.persona`). Written here -- not in
    # Write-ScaffoldTask -- so the dsh task dir never contains an AGENTS.md
    # that could asymmetrically instruct that arm.
    [System.IO.File]::WriteAllText((Join-Path $task.dir "AGENTS.md"), $CommonSystemPrompt)
    # The brief is the positional prompt; it contains spaces but no double
    # quotes, so pre-quoting it for Start-Process is safe.
    $briefArg = '"{0}"' -f $task.brief
    $oc = Resolve-OpencodeNpmBin
    if (-not $oc) {
        return @{
            arm = "opencode"
            exit = -1
            wall_s = $null
            timeout = $false
            error = "no npm opencode binary found (APPDATA npm node_modules nor a non-shim opencode on PATH)"
            turns = $null
            log = $logPath
        }
    }
    $r = Invoke-ScrubbedChild {
        Invoke-WatchdogProcess $oc.exe @("run", "--dangerously-skip-permissions", "--model", "bench/$alias", $briefArg) $task.dir $logPath $timeoutSec
    }
    $turns = (Select-String -Path $logPath -Pattern 'step|Turn \d+|---' -AllMatches -ErrorAction SilentlyContinue | Measure-Object).Count
    return @{
        arm = "opencode"
        exit = $r.exit
        wall_s = $r.wall_s
        timeout = $r.timed_out
        error = $r.error
        turns = $(if ($turns -gt 0) { $turns } else { $null })
        log = $logPath
    }
}

# ----------------------------------------------------------------------------
# leg B (AC5/D1a): single invocation
#   npx -y @deepseek-ai/dsh@0.1.0-rc.7 --profile headless "<brief text>"
# with WorkingDirectory = task dir. BEFORE the run, the per-config provider
# settings were written to $DSH_HOME\settings.yaml (llm-pi-ai.providers.bench
# + agent-default-model = current alias) -- the CONFIRMED mechanism (see the
# findings block in the header). DSH_TELEMETRY_DISABLED=1 is set explicitly in
# the child env IN ADDITION to the scrub; the dummy bench key is injected under
# $DshApiKeyEnv (apiKeyEnv is a reference: the key value lives in the child
# env, never in any settings file).
# ----------------------------------------------------------------------------
function Invoke-LegDsh([hashtable]$task, [string]$alias, [string]$logPath, [int]$timeoutSec) {
    $briefArg = '"{0}"' -f $task.brief
    $r = Invoke-ScrubbedChild {
        # PS 5.1 rejects $env:$var (drive-qualified var needs a literal name);
        # Set-Item on the env: provider achieves the same.
        Set-Item -Path ("env:" + $DshApiKeyEnv) -Value "bench-dummy-local-server"
        Set-Item -Path env:DSH_TELEMETRY_DISABLED -Value "1"
        try {
            Invoke-WatchdogCommand "node" @($DshBinJs, "--profile", "headless", $briefArg) $task.dir $logPath $timeoutSec
        } finally {
            Remove-Item ("env:" + $DshApiKeyEnv) -ErrorAction SilentlyContinue
            Remove-Item env:DSH_TELEMETRY_DISABLED -ErrorAction SilentlyContinue
        }
    }
    $turns = (Select-String -Path $logPath -Pattern '^>\s|Action|Observation|turn \d+' -AllMatches -ErrorAction SilentlyContinue | Measure-Object).Count
    return @{
        arm = "dsh"
        exit = $r.exit
        wall_s = $r.wall_s
        timeout = $r.timed_out
        error = $r.error
        turns = $(if ($turns -gt 0) { $turns } else { $null })
        log = $logPath
    }
}

# ----------------------------------------------------------------------------
# DSH settings writer (CONFIRMED keys only, see the header findings block).
# Get-DshSettingsYaml is pure (also probed by -TestInternals); the real run
# backs up $DSH_HOME\settings.yaml and restores it in the finally.
# ----------------------------------------------------------------------------
function Get-DshSettingsYaml([string]$alias) {
    # The common system prompt is injected via `system-prompt.persona`. dsh
    # renders it as the order-0 section, with {{model}}/{{cwd}} interpolated
    # (the common text has no braces, so interpolation is a no-op).
    $persona = $CommonSystemPrompt -replace '(?m)^', '    '
    @"
agent-default-model:
  provider: $DshRoute
  model: $alias
llm-pi-ai:
  providers:
    ${DshRoute}:
      apiKeyEnv: $DshApiKeyEnv
      api: openai-completions
      baseURL: http://127.0.0.1:$BenchPort/v1
      models:
        - id: $alias
system-prompt:
  persona: |-
$persona
# D5 (2026-08-20): the session-title LLM plugins would otherwise fall back to
# the DEFAULT provider (deepseek-official) when generating a session title from
# the first prompt, and abort the whole task with MISSING_CREDENTIAL (measured:
# plain t2 dsh exit 1 in ~2.6 s). Pin them to the bench route like
# agent-default-model.
session-title-first-prompt-llm:
  provider: $DshRoute
  model: $alias
session-title-llm:
  provider: $DshRoute
  model: $alias
"@
}

function Resolve-DshHome {
    if ($env:DSH_HOME) { return $env:DSH_HOME }
    return (Join-Path $env:USERPROFILE ".dsh")
}

function Backup-DshSettings([string]$dshHome) {
    $p = Join-Path $dshHome "settings.yaml"
    if (Test-Path $p) {
        $bak = Join-Path $dshHome ("settings.yaml.harnessbak.{0}" -f (Get-Date -Format "yyyyMMddHHmmss"))
        try {
            # -ErrorAction Stop: under $ErrorActionPreference="Continue" a failed
            # copy would be SILENT, and the finally would then claim a restore
            # that never happened. Fail closed: never overwrite the original
            # without a verified backup in place.
            Copy-Item $p $bak -Force -ErrorAction Stop
        } catch {
            Log ("FAIL: could not back up '{0}' -> '{1}': {2}. Aborting before any harness-written settings.yaml; the original is left untouched." -f $p, $bak, $_)
            throw
        }
        return @{ existed = $true; original = $p; backup = $bak }
    }
    return @{ existed = $false; original = $p; backup = $null }
}

function Write-DshSettings([string]$alias, [string]$dshHome, [string]$auditPath) {
    New-Item -ItemType Directory -Path $dshHome -Force | Out-Null
    $content = Get-DshSettingsYaml $alias
    [System.IO.File]::WriteAllText((Join-Path $dshHome "settings.yaml"), $content)
    if ($auditPath) {
        [System.IO.File]::WriteAllText($auditPath, $content)
    }
    return (Join-Path $dshHome "settings.yaml")
}

function Restore-DshSettings($state) {
    # Returns $true ONLY after a VERIFIED restore (backup back in place, or a
    # harness-written settings.yaml removed so pre-state == post-state). A
    # failed/partial copy THROWS (-ErrorAction Stop) so the caller records
    # dsh_settings_restored=$false honestly instead of fabricating evidence.
    if ($state.existed) {
        Copy-Item $state.backup $state.original -Force -ErrorAction Stop
        if (-not (Test-Path $state.original)) {
            throw "restore copy did not leave '$($state.original)' in place"
        }
    } elseif (Test-Path $state.original) {
        Remove-Item $state.original -Force -ErrorAction Stop
        if (Test-Path $state.original) {
            throw "failed to remove harness-written '$($state.original)'"
        }
    }
    return $true
}

# ----------------------------------------------------------------------------
# D1a run-start gate (AC5): empirically re-verify the pinned dsh package:
#   1. `npx -y @deepseek-ai/dsh@0.1.0-rc.7 --help` must expose the headless
#      grammar (--profile + headless).
#   2. the setting keys we write (agent-default-model, llm-pi-ai) must be
#      CONFIRMED: PRIMARY via the `--dump-default-config` probe (the pinned
#      package's composed config -- dump-config is the PRIMARY key evidence; the
#      needle text lives in SIBLING @deepseek-ai sub-packages, not only the dsh
#      package dir's own files); FALLBACK (only if the dump probe fails/times
#      out/returns empty) = scan ALL files <= 4 MB (no name filter) under the
#      PARENT node_modules dir of $pkgDir, covering every sibling sub-package.
#      The dump is cached in the report dir (dsh_dumpcfg_<version>.txt) and the
#      installed package version must equal the pinned 0.1.0-rc.7.
# The help + dump snapshots are cached in the report dir as evidence.
# Any failure -> exit 4 naming exactly what is unconfirmed, BEFORE :8004 stop.
# ----------------------------------------------------------------------------
function Find-DshPackageDir {
    # 2026-08-24: the authoritative install is the LOCKED runtime tree, not an
    # npx cache. Prefer it; the npx-cache hunt below stays as a fallback only.
    $runtimePkg = Join-Path $DshRuntimeDir "node_modules\@deepseek-ai\dsh"
    if (Test-Path (Join-Path $runtimePkg "package.json")) { return $runtimePkg }
    $candidates = @()
    if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA "npm-cache\_npx") }
    if ($env:APPDATA) { $candidates += (Join-Path $env:APPDATA "npm-cache\_npx") }
    foreach ($c in $candidates) {
        if (-not (Test-Path $c)) { continue }
        $hits = @(Get-ChildItem -Path $c -Recurse -Directory -Depth 5 -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq "dsh" -and $_.FullName -like "*node_modules\@deepseek-ai\dsh" })
        foreach ($h in $hits) {
            if (Test-Path (Join-Path $h.FullName "package.json")) { return $h.FullName }
        }
    }
    return $null
}

function Test-DshConfigKnown([string]$evidenceDir) {
    # Returns @{ ok = bool; keys = string[]; helpPath = <path or $null>; notes = string[] }
    $notes = @()
    $keys = @()
    $helpPath = $null

    # Route the --help probe through the WATCHDOG (300 s hard cap): a blocking /
    # hanging npx must never stall the harness start. The snapshot is written to
    # a temp file and read back; a probe that could not be produced becomes an
    # UNCONFIRMED item below (fail-closed), never a hang.
    $npxLog = Join-Path ([IO.Path]::GetTempPath()) ("specdec_dsh_help_{0}.txt" -f $DshVersion)
    $npxErr = "$npxLog.err"
    Remove-Item $npxLog, $npxErr -Force -ErrorAction SilentlyContinue
    try {
        # scrubbed child: the dsh telemetry/credential env must not leak here either
        $npx = Invoke-ScrubbedChild {
            Invoke-WatchdogCommand "node" @($DshBinJs, "--help") $RepoRoot $npxLog 300
        }
    } catch {
        $npx = $null
    }
    $helpText = ""
    if ($npx -and -not $npx.error -and (Test-Path $npxLog)) {
        $helpText = try { [System.IO.File]::ReadAllText($npxLog) } catch { "" }
    } else {
        $why = if ($npx -and $npx.error) { $npx.error }
               elseif ($npx -and $npx.timed_out) { "the probe exceeded the 300 s watchdog cap (timed out; treated as UNCONFIRMED, fail-closed)" }
               else { "probe produced no --help output" }
        $notes += "UNCONFIRMED: the pinned-package --help probe failed -> $why"
    }
    if ($evidenceDir) {
        $helpPath = Join-Path $evidenceDir ("dsh_help_{0}.txt" -f $DshVersion)
        [System.IO.File]::WriteAllText($helpPath, $helpText)
        $notes += "help snapshot cached -> $helpPath"
    }
    $grammarOk = ($helpText -match "--profile") -and ($helpText -match "headless")
    if ($grammarOk) {
        $keys += "cli:--profile/headless"
        $notes += "CLI grammar confirmed from the installed package --help (rc.7 docs: dsh --profile headless <task>)"
    } else {
        $notes += "UNCONFIRMED: --help did not expose --profile/headless (grammar per deepseekdocs.com/en/docs/user-guide/cli)"
    }

    $pkgDir = Find-DshPackageDir
    $versionOk = $false
    $needleOk = @{}
    if ($pkgDir) {
        $notes += "dsh package dir: $pkgDir"
        # 1) installed package version must EQUAL the pinned $DshVersion.
        try {
            $pkg = Get-Content -Raw -Path (Join-Path $pkgDir "package.json") | ConvertFrom-Json
            if ($pkg.version -eq $DshVersion) {
                $versionOk = $true
                $keys += "pkg:version=$DshVersion"
                $notes += "installed package version matches the pinned $DshVersion"
            } else {
                $notes += "UNCONFIRMED: installed package version is '$($pkg.version)', not the pinned '$DshVersion'"
            }
        } catch {
            $notes += "UNCONFIRMED: could not read/parse package.json under $pkgDir ($_)"
        }
        # (the setting-key scan no longer lives here -- KEY CONFIRMATION is a
        #   two-tier gate below, gated on the authoritative --dump-config probe
        #   with a sibling-package fallback bootstrap; this branch stays version
        #   only.)
    } else {
        $notes += "UNCONFIRMED: no npx-cached @deepseek-ai/dsh package dir found (Find-DshPackageDir -> null); installed version unverifiable (the independent --dump-config key probe below still runs)"
    }

    # ---------------------------------------------------------------------------
    # 2) KEY CONFIRMATION — two-tier (repair 2026-08-20). The previous gate only
    #    scanned files named README/conaverse/settings under the dsh package dir,
    #    but the needle text really lives in SIBLING @deepseek-ai sub-packages
    #    (dsh-agent-default-model-config, dsh-llm-prompt, dsh-agent-prompt...) and
    #    in the COMPOSED config — so that narrow scan FALSE-REFUSED (exit 4) on a
    #    warm cache. New spirit, kept fail-closed:
    #      tier 1 (PRIMARY, authoritative): run the pinned --dump-config probe
    #          through the SAME watchdog/scrub path as --help, both needle
    #          strings present in its output? -> both CONFIRMED (notes say
    #          "confirmed from --dump-config"); cache dsh_dumpcfg_<version>.txt
    #          in the report dir (the help snapshot).
    #      tier 2 (FALLBACK, only if the probe fails / times out / returns
    #          empty): scan files <= 4 MB (no filename filter) under the PARENT
    #          node_modules dir of $pkgDir ($pkgDir\..\.. -> every @deepseek-ai
    #          sibling sub-package), skipping unreadable files per-file and
    #          noting the scanned count.
    #      both tiers miss a needle -> UNCONFIRMED instead (exit 4 downstream).
    #    $keys / $needleOk / $notes plumbing unchanged.
    # ---------------------------------------------------------------------------
    $needleList = @("agent-default-model", "llm-pi-ai")

    # tier 1 (PRIMARY): --dump-config probe (watchdog-capped, scrubbed child,
    # 300 s hard cap -- the same guardrail as the --help probe). The composed
    # --dump-config of the pinned package is the AUTHORITATIVE source for both
    # needles (they live in sibling sub-packages, not only the dsh dir files).
    $dumpLog = Join-Path ([IO.Path]::GetTempPath()) ("specdec_dsh_dumpcfg_{0}.txt" -f $DshVersion)
    $dumpErr = "$dumpLog.err"
    Remove-Item $dumpLog, $dumpErr -Force -ErrorAction SilentlyContinue
    try {
        $dumpCfg = Invoke-ScrubbedChild {
            Invoke-WatchdogCommand "node" @($DshBinJs, "--profile", "headless", "--dump-config") $RepoRoot $dumpLog 300
        }
    } catch {
        $dumpCfg = $null
    }
    $dumpText = ""
    if ($dumpCfg -and -not $dumpCfg.error -and (Test-Path $dumpLog)) {
        $dumpText = try { [System.IO.File]::ReadAllText($dumpLog) } catch { "" }
    } else {
        $why = if ($dumpCfg -and $dumpCfg.error) { $dumpCfg.error }
               elseif ($dumpCfg -and $dumpCfg.timed_out) { "the --dump-config probe exceeded the 300 s watchdog cap (timed out)" }
               else { "the --dump-config probe produced no output" }
        $notes += "UNCONFIRMED (tier-1 --dump-config probe): $why -> falling back to the sibling-package scan per needle"
    }
    if ($evidenceDir) {
        $dumpCachePath = Join-Path $evidenceDir ("dsh_dumpcfg_{0}.txt" -f $DshVersion)
        [System.IO.File]::WriteAllText($dumpCachePath, $dumpText)
        $notes += "dump-config snapshot cached -> $dumpCachePath"
    }

    # tier-1 confirmation per needle (a needle the dump output carries is
    # CONFIRMED). Needles the dump could not prove are left open for tier 2.
    $needleOk = @{}   # needle -> evidence path / label, the SAME map the gate reads
    foreach ($needle in $needleList) {
        if ($dumpText.Contains($needle)) {
            $needleOk[$needle] = "dump-config"
            $keys += "pkg:$needle"
            $notes += "setting key '$needle' confirmed from --profile headless --dump-config"
        } else {
            $needleOk[$needle] = $null   # NOT clamped here; tier-2 may fill it
        }
    }

    # tier 2 (FALLBACK, only for needles the primary did not confirm): scan ALL
    # files <= 4 MB (no name filter) under the PARENT node_modules dir of
    # $pkgDir ($pkgDir\..\..) -- that covers every @deepseek-ai sibling
    # sub-package, which is where the needles actually live. If a needle still
    # finds no hit, the aggregate note below stays UNCONFIRMED (fail-closed).
    $missingNeeds = @($needleList | Where-Object { -not $needleOk[$_] })
    if ($missingNeeds.Count -gt 0) {
        if (-not $pkgDir) {
            $note = "UNCONFIRMED: needle '" + ($missingNeeds -join "', '") + "' not confirmed by --dump-config AND no package dir for the tier-2 sibling scan"
            $notes += $note
        } else {
            $siblingRoot = Join-Path $pkgDir "..\.."
            $files = @(Get-ChildItem -Path $siblingRoot -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Length -le 4MB })
            $notes += "tier-2: sibling scan of $($files.Count) files (<=4MB, no name filter) under $siblingRoot"
            foreach ($needle in $missingNeeds) {
                $hitPath = $null
                foreach ($f in $files) {
                    try {
                        $text = [System.IO.File]::ReadAllText($f.FullName)
                        if ($text.Contains($needle)) {
                            $hitPath = $f.FullName
                            break
                        }
                    } catch { }
                }
                if ($hitPath) {
                    $needleOk[$needle] = $hitPath
                    $keys += "pkg:$needle"
                    $notes += "setting key '$needle' found (tier-2) in $hitPath"
                } else {
                    $notes += "UNCONFIRMED: setting key '$needle' not confirmed by --dump-config nor found in any <=4MB sibling file under $siblingRoot"
                }
            }
        }
    }

    $needlesOk = ($needleOk.Count -eq 2)
    return @{
        ok = ($grammarOk -and $versionOk -and $needlesOk)
        keys = $keys
        helpPath = $helpPath
        notes = $notes
    }
}

# ----------------------------------------------------------------------------
# -TestScrub: expose the scrub helper for the tooling test (F1). Prints the
# scrubbed-key list AND proves the scrub actually hides those vars from a
# spawned child (a tiny python prober) -- used by
# scripts/test_specdec_tooling.py. Restored from the earlier draft verbatim in
# spirit; exits 0.
# ----------------------------------------------------------------------------
if ($TestScrub) {
    Write-Host "===== run_harness_ab -TestScrub ====="
    $scrubKeys = @(Get-ScrubbedKeys | Sort-Object)
    Write-Host ("scrubbed keys ({0}):" -f $scrubKeys.Count)
    foreach ($k in $scrubKeys) { Write-Host "  SCRUB $k" }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pyFile = Join-Path $env:TEMP "specdec_scrub_probe.py"
        [System.IO.File]::WriteAllText($pyFile, @'
import os, sys
names = sys.argv[1].split(",")
visible = [n for n in names if os.environ.get(n)]
print("CHILD_VISIBLE=" + (",".join(visible) if visible else "none"))
'@)
        $names = ($scrubKeys -join ",")
        Invoke-ScrubbedChild {
            $childOut = & python $pyFile $names 2>&1
            foreach ($l in $childOut) { Write-Host "  $l" }
        }
    } else {
        Write-Host "  (python not on PATH; skipping child-visibility probe)"
    }
    Write-Host "(TestScrub complete -- only the scrub helper was exercised; nothing launched.)"
    exit 0
}

# ----------------------------------------------------------------------------
# -TestInternals: offline probes of the pure logic (grading decisions, watchdog
# default, tasks.json scaffold, DSH settings writer keys). No npx, no network,
# no GPU. Exits 0.
# ----------------------------------------------------------------------------
if ($TestInternals) {
    Write-Host "===== run_harness_ab -TestInternals ====="
    Write-Host "(offline: no npx, no network, no GPU)"
    $fixRoot = Join-Path $ScratchRoot "internals-fixtures"
    if (Test-Path $fixRoot) { Remove-Item -Path $fixRoot -Recurse -Force }
    New-Item -ItemType Directory -Path $fixRoot -Force | Out-Null

    Write-Host ""
    Write-Host "1) grading fixture decisions (Invoke-GradeUnittest):"
    $specs = @(New-TaskSpecs)
    $t1 = $specs[0]
    $t2 = $specs[1]

    # solved fixture: correct FixedWindowLimiter + a passing unittest module
    $solvedDir = Write-ScaffoldTask $t1 (Join-Path $fixRoot "solved")
    [System.IO.File]::WriteAllText((Join-Path $solvedDir "rate_limiter.py"), @'
import threading
import time

class FixedWindowLimiter:
    def __init__(self, capacity, window_seconds):
        if capacity <= 0 or window_seconds <= 0:
            raise ValueError("capacity and window_seconds must be positive")
        self.capacity = capacity
        self.window_seconds = float(window_seconds)
        self._lock = threading.Lock()
        self._count = 0
        self._window_start = time.monotonic()

    def try_acquire(self):
        with self._lock:
            now = time.monotonic()
            if now - self._window_start >= self.window_seconds:
                self._count = 0
                self._window_start = now
            if self._count < self.capacity:
                self._count += 1
                return True
            return False

    def reset(self):
        with self._lock:
            self._count = 0
            self._window_start = time.monotonic()
'@)
    [System.IO.File]::WriteAllText((Join-Path $solvedDir "test_rate_limiter.py"), @'
import unittest
from rate_limiter import FixedWindowLimiter

class TestFixedWindowLimiter(unittest.TestCase):
    def test_allows_capacity(self):
        l = FixedWindowLimiter(2, 1.0)
        self.assertTrue(l.try_acquire())
        self.assertTrue(l.try_acquire())
        self.assertFalse(l.try_acquire())
    def test_reset(self):
        l = FixedWindowLimiter(1, 1.0)
        l.try_acquire()
        self.assertFalse(l.try_acquire())
        l.reset()
        self.assertTrue(l.try_acquire())

if __name__ == "__main__":
    unittest.main()
'@)

    # unsolved fixture: t2's seeded seed.py carries the step bug, so test_seed
    # must FAIL -> solved=false (unsolved, never a harness crash).
    $unsolvedDir = Write-ScaffoldTask $t2 (Join-Path $fixRoot "unsolved")

    $gradeLogS = Join-Path $fixRoot "grade_solved.log"
    $gradeLogU = Join-Path $fixRoot "grade_unsolved.log"
    $gSolved = Invoke-GradeUnittest $t1 $solvedDir $gradeLogS
    $gUnsolved = Invoke-GradeUnittest $t2 $unsolvedDir $gradeLogU
    Write-Host ("  solved fixture   -> solved={0} exit={1}" -f $gSolved.solved, $gSolved.exit)
    Write-Host ("  unsolved fixture -> solved={0} exit={1}" -f $gUnsolved.solved, $gUnsolved.exit)

    Write-Host ""
    Write-Host ("2) watchdog default: TaskTimeoutSeconds = {0} (per-arm-task hard cap)" -f $TaskTimeoutSeconds)

    Write-Host ""
    Write-Host "3) tasks.json brief scaffold (Write-TasksJson):"
    $tjDir = Join-Path $fixRoot "tasks"
    New-Item -ItemType Directory -Path $tjDir -Force | Out-Null
    Write-TasksJson $specs $tjDir
    Get-Content -Raw -Path (Join-Path $tjDir "tasks.json") | Write-Host

    Write-Host ""
    Write-Host ("4) DSH settings YAML keys (Get-DshSettingsYaml; route={0} apiKeyEnv={1}):" -f $DshRoute, $DshApiKeyEnv)
    $yaml = Get-DshSettingsYaml $AliasMap[$Configs[0]]
    foreach ($line in ($yaml -split "`n")) {
        if ($line -match "^\S") { Write-Host ("  {0}" -f $line) }
    }
    Write-Host ("  contains agent-default-model: {0}" -f ($yaml -match "agent-default-model:"))
    Write-Host ("  contains llm-pi-ai: {0}" -f ($yaml -match "llm-pi-ai:"))
    Write-Host ("  baseURL: http://127.0.0.1:{0}/v1" -f $BenchPort)

    Write-Host ""
    Write-Host "5) grading watchdog probe (agent module blocking at import; cap 5 s):"
    $hangDir = Join-Path $fixRoot "hang"
    New-Item -ItemType Directory -Path $hangDir -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $hangDir "hang_module.py"), @'
import sys
print("ALIVE-BEFORE-HANG", flush=True)   # marker: partial output must survive the timeout kill
import time
time.sleep(9999)   # agent-written module that blocks forever at import scope
'@)
    [System.IO.File]::WriteAllText((Join-Path $hangDir "test_hang.py"), @'
import unittest
import hang_module  # importing this blocks forever -> grading must TIME OUT

class TestHang(unittest.TestCase):
    def test_x(self):
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
'@)
    $hangTask = @{ id = "probe-hang"; test_module = "test_hang"; brief = ""; seed = @{} }
    $hangLog = Join-Path $hangDir "grade_hang.log"
    $swHang = [System.Diagnostics.Stopwatch]::StartNew()
    $gHang = Invoke-GradeUnittest $hangTask $hangDir $hangLog 5
    $swHang.Stop()
    Write-Host ("  HANGPROBE solved={0} grade_exit={1} timed_out={2} probe_wall_s={3}" -f $gHang.solved, $gHang.exit, $gHang.timed_out, [math]::Round($swHang.Elapsed.TotalSeconds, 1))
    foreach ($l in @(Get-Content -Path $hangLog -ErrorAction SilentlyContinue)) { Write-Host "    $l" }

    Write-Host ""
    Write-Host "6) reference-test overwrite probes (arm-authored test replaced before grading):"
    $sabotagedTest = @'
import unittest

class TestSabotage(unittest.TestCase):
    def test_trivial(self):
        self.assertTrue(True)   # arm-authored always-pass test

if __name__ == "__main__":
    unittest.main()
'@
    # correct impl + sabotaged test -> the reference must replace it and PASS
    $refOkDir = Join-Path $fixRoot "refoverwrite_ok"
    New-Item -ItemType Directory -Path $refOkDir -Force | Out-Null
    Copy-Item (Join-Path $solvedDir "rate_limiter.py") (Join-Path $refOkDir "rate_limiter.py") -Force
    [System.IO.File]::WriteAllText((Join-Path $refOkDir "test_rate_limiter.py"), $sabotagedTest)
    # WRONG impl + sabotaged test -> after the overwrite the reference must FAIL
    $refBadDir = Join-Path $fixRoot "refoverwrite_bad"
    New-Item -ItemType Directory -Path $refBadDir -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $refBadDir "rate_limiter.py"), @'
class FixedWindowLimiter:
    def __init__(self, capacity, window_seconds):
        self.capacity = capacity

    def try_acquire(self):
        return False   # WRONG: never admits a request

    def reset(self):
        pass
'@)
    [System.IO.File]::WriteAllText((Join-Path $refBadDir "test_rate_limiter.py"), $sabotagedTest)
    $gRefOk = Invoke-GradeUnittest $t1 $refOkDir (Join-Path $refOkDir "grade.log")
    $gRefBad = Invoke-GradeUnittest $t1 $refBadDir (Join-Path $refBadDir "grade.log")
    $refOkTest = [System.IO.File]::ReadAllText((Join-Path $refOkDir "test_rate_limiter.py"))
    $overwritten = (-not ($refOkTest -match "TestSabotage")) -and ($refOkTest -match "class TestFixedWindowLimiter")
    Write-Host ("  REFOVERWRITE correct_impl solved={0} grade_exit={1} overwritten={2}" -f $gRefOk.solved, $gRefOk.exit, $overwritten)
    Write-Host ("  REFOVERWRITE wrong_impl solved={0} grade_exit={1}" -f $gRefBad.solved, $gRefBad.exit)

    Write-Host ""
    Write-Host "7) task-brief quoting safety (Test-TaskBriefsSafe):"
    $bs = Test-TaskBriefsSafe
    Write-Host ("  BRIEFSAFE ok={0} (no brief contains a double quote or a percent sign)" -f $bs.ok)

    Write-Host ""
    Write-Host "8) grading-hijack cleanup (F7: cwd-shadowing unittest.py / sitecustomize.py removed before grading):"
    # correct impl + a fake unittest.py that would exit 0 unconditionally +
    # a fake sitecustomize.py -> after the cleanup + reference overwrite, the
    # REAL unittest must decide: solved=True for the correct impl.
    $shadowOkDir = Join-Path $fixRoot "shadow_ok"
    New-Item -ItemType Directory -Path $shadowOkDir -Force | Out-Null
    Copy-Item (Join-Path $solvedDir "rate_limiter.py") (Join-Path $shadowOkDir "rate_limiter.py") -Force
    [System.IO.File]::WriteAllText((Join-Path $shadowOkDir "unittest.py"), "import sys; sys.exit(0)`n")
    [System.IO.File]::WriteAllText((Join-Path $shadowOkDir "sitecustomize.py"), "import sys; sys.exit(0)`n")
    # WRONG impl + fake unittest.py: only the REAL unittest can reject it
    # (a hijacked grader would exit 0 and mark it solved).
    $shadowBadDir = Join-Path $fixRoot "shadow_bad"
    New-Item -ItemType Directory -Path $shadowBadDir -Force | Out-Null
    Copy-Item (Join-Path $refBadDir "rate_limiter.py") (Join-Path $shadowBadDir "rate_limiter.py") -Force
    [System.IO.File]::WriteAllText((Join-Path $shadowBadDir "unittest.py"), "import sys; sys.exit(0)`n")
    [System.IO.File]::WriteAllText((Join-Path $shadowBadDir "sitecustomize.py"), "import sys; sys.exit(0)`n")
    $gShadowOk = Invoke-GradeUnittest $t1 $shadowOkDir (Join-Path $shadowOkDir "grade.log")
    $gShadowBad = Invoke-GradeUnittest $t1 $shadowBadDir (Join-Path $shadowBadDir "grade.log")
    $shadowOkGone = (-not (Test-Path -LiteralPath (Join-Path $shadowOkDir "unittest.py"))) -and (-not (Test-Path -LiteralPath (Join-Path $shadowOkDir "sitecustomize.py")))
    $shadowBadGone = (-not (Test-Path -LiteralPath (Join-Path $shadowBadDir "unittest.py"))) -and (-not (Test-Path -LiteralPath (Join-Path $shadowBadDir "sitecustomize.py")))
    Write-Host ("  SHADOWCLEAN correct_impl solved={0} grade_exit={1} fake_gone={2}" -f $gShadowOk.solved, $gShadowOk.exit, $shadowOkGone)
    Write-Host ("  SHADOWCLEAN wrong_impl solved={0} grade_exit={1} fake_gone={2}" -f $gShadowBad.solved, $gShadowBad.exit, $shadowBadGone)

    Write-Host ""
    Write-Host "9) scaffold wipe (F7b: Write-ScaffoldTask removes stale files before re-seeding):"
    $wipeRoot = Join-Path $fixRoot "wipe"
    New-Item -ItemType Directory -Path $wipeRoot -Force | Out-Null
    # t2 has real seed files (seed.py + test_seed.py), so re-seeding is provable
    $w1 = Write-ScaffoldTask $t2 $wipeRoot
    $stray = Join-Path $w1 "stale_solution.py"
    [System.IO.File]::WriteAllText($stray, "STALE SOLUTION FROM A PREVIOUS RUN")
    $w2 = Write-ScaffoldTask $t2 $wipeRoot
    $strayGone = -not (Test-Path -LiteralPath $stray)
    $reseeded = (Test-Path -LiteralPath (Join-Path $w2 "brief.txt")) -and (Test-Path -LiteralPath (Join-Path $w2 "seed.py"))
    Write-Host ("  SCAFFOLDWIPE stray_gone={0} reseeded_brief={1}" -f $strayGone, $reseeded)

    Write-Host ""
    Write-Host "(TestInternals complete -- offline probes only; fixtures left under $fixRoot for inspection.)"
    exit 0
}

# ----------------------------------------------------------------------------
# -CheckOnly: FULLY OFFLINE readiness plan (no network, no model, no child
# process). Test-DshConfigKnown is NOT invoked here: it runs a network npx and
# only the real -Run may. Exits 0 on success, 4 on a failed validation.
# ----------------------------------------------------------------------------
if ($CheckOnly) {
    Write-Host "===== run_harness_ab -CheckOnly ====="
    Write-Host "(FULLY OFFLINE: no network, no model, no child process; Test-DshConfigKnown is NOT invoked -- it runs a network npx and only the real -Run may)"
    try {
        New-Item -ItemType Directory -Path $ScratchRoot -Force -ErrorAction Stop | Out-Null
        Write-Host "scratch root: CREATABLE -> $ScratchRoot"
    } catch {
        Write-Host "FAIL: cannot create scratch root $ScratchRoot : $_"
        exit 4
    }
    $oc = Get-Command opencode -ErrorAction SilentlyContinue
    if ($oc) {
        Write-Host "opencode: on PATH -> $($oc.Source)"
    } else {
        Write-Host "FAIL: 'opencode' not on PATH (leg A would be unavailable in a real run)"
        exit 4
    }
    Write-Host ""
    Write-Host "PLAN (per config; real run = -Run with the approved outage window):"
    foreach ($cfg in $Configs) {
        Write-Host ("  [{0}] alias={1}" -f $cfg, $AliasMap[$cfg])
        Write-Host ("    launcher: {0} -Config {1} -LogPath <report>\harness_{1}-server.log (+ -BinaryPath for q38-dflash2)" -f $Launcher, $cfg)
        Write-Host ("    arms: opencode (leg A) then dsh (leg B) over 3 tasks; per-arm unittest grading; DSH_TELEMETRY_DISABLED=1 + scrubbed child env")
        if ($cfg -eq "q38-dflash2") {
            if ($Dflash2BinaryPath) {
                $present = Test-Path $Dflash2BinaryPath
                Write-Host ("    dflash2 binary (-BinaryPath): {0} -> {1}" -f $Dflash2BinaryPath, $(if ($present) { "PRESENT" } else { "MISSING" }))
                if (-not $present) { Write-Host "      (missing: the real run's launcher gate would refuse; config recorded as SKIP + warning)" }
            } else {
                Write-Host "    dflash2 binary (-BinaryPath): NOT GIVEN -> q38-dflash2 SKIPPED with a warning (default b10488 is refused by the launcher's DFlash2 gate by design)"
            }
        }
        Write-Host ""
    }
    Write-Host "watchdog: -TaskTimeoutSeconds default 900 (pass to override)."
    Write-Host "(CheckOnly complete -- nothing was built, launched, or modified.)"
    exit 0
}

# ----------------------------------------------------------------------------
# -GradeProbeDir: OFFLINE grading self-test (no network, no GPU). Grades ONE
# fixture dir through the exact same watchdog + scrub + reference-overwrite path
# the real run uses, with a caller-provided hard cap (default 300). Used by
# scripts/test_specdec_tooling.py to prove (a) the grade path cannot hang on
# blocking agent code and (b) arm-authored tests are overwritten by the
# harness-held reference before grading. Exits 0 when the probe ran (the grade
# decision is in the output), 4 if the dir is missing.
# ----------------------------------------------------------------------------
if ($GradeProbeDir) {
    Write-Host "===== run_harness_ab -GradeProbeDir (offline grading self-test) ====="
    if (-not (Test-Path $GradeProbeDir)) {
        Write-Host "FAIL: -GradeProbeDir not found: $GradeProbeDir"
        exit 4
    }
    $probeTask = @{
        id = "probe-grade"
        test_module = $GradeProbeModule
        brief = ""
        seed = @{}
    }
    $probeLog = Join-Path $GradeProbeDir "grade_probe.log"
    Remove-Item $probeLog, "$probeLog.err" -Force -ErrorAction SilentlyContinue
    $g = Invoke-GradeUnittest $probeTask $GradeProbeDir $probeLog $GradeProbeTimeoutSeconds
    Write-Host ("GRADEPROBE module={0} cap={1} solved={2} grade_exit={3} timed_out={4}" -f $probeTask.test_module, $GradeProbeTimeoutSeconds, $g.solved, $g.exit, $g.timed_out)
    foreach ($l in (Get-Content -Path $probeLog -ErrorAction SilentlyContinue)) { Write-Host "  $l" }
    Write-Host "(GradeProbe complete -- offline; the only child was the graded python process under the watchdog + scrub.)"
    exit 0
}

# ----------------------------------------------------------------------------
# refusal gate (no valid switch). GATED on -not $Run so the real-run path below
# is actually reachable with -Run (previously this block exited 4 unconditionally
# and the entire -Run path was dead code).
# ----------------------------------------------------------------------------
if (-not $Run) {
    Write-Host "REFUS (exit 4): this harness is FUTURE-only and is not run without an"
    Write-Host "  explicit switch:"
    Write-Host "    -CheckOnly      offline readiness plan (exit 0)"
    Write-Host "    -TestScrub      proof the scrubbed env hides secrets from a child"
    Write-Host "    -TestInternals  offline probes of the pure logic"
    Write-Host "    -Run            the real A/B bench -- ONLY from the outage-window"
    Write-Host "                    orchestrator after the D1a config gate passes and the"
    Write-Host "                    FIREWALL WAIVER compensating controls (header, 2026-08-19)"
    Write-Host "                    are in force: env scrub + DSH_TELEMETRY_DISABLED=1 +"
    Write-Host "                    pinned @deepseek-ai/dsh@$DshVersion + toy tasks."
    exit 4
}

# ----------------------------------------------------------------------------
# REAL RUN PATH (-Run). Reached only via an explicit -Run; executed only within
# an approved outage window. All server orchestration mirrors the header flow
# (steps 1-6 there).
# ----------------------------------------------------------------------------
Log "===== run_harness_ab -Run ====="
foreach ($cfg in $Configs) {
    if ($ValidConfigs -notcontains $cfg) {
        Log "REFUS (exit 4): unknown -Configs entry '$cfg' (valid: $($ValidConfigs -join ', '))."
        exit 4
    }
}
$ReportDir = Join-Path $RepoRoot ("reports\specdec_{0}" -f (Get-Date -Format "yyyyMMdd"))
if ($ReportTag) { $ReportDir = "$ReportDir`_$ReportTag" }
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
New-Item -ItemType Directory -Path $ScratchRoot -Force | Out-Null

# --- step 0: task-brief quoting safety gate (fail fast, before ANY server work)
$briefSafe = Test-TaskBriefsSafe
if (-not $briefSafe.ok) {
    Log "REFUS (exit 4): task brief of '$($briefSafe.task)' contains a forbidden character '$($briefSafe.char)' (double quote / percent are fragile-by-construction in the child-argv quoting). Fix the brief, then retry."
    exit 4
}
Log "task-brief quoting gate PASSED (no task brief contains a double quote or a percent sign)"

# --- step 1: D1a config gate (may npx-fetch the pinned package once) ---------
Log "step 1/6: D1a config gate (Test-DshConfigKnown; network npx allowed HERE only)"
$gate = Test-DshConfigKnown $ReportDir
foreach ($n in @($gate.notes)) { Log "  gate note: $n" }
if (-not $gate.ok) {
    Log "REFUS (exit 4): dsh config is NOT empirically confirmed. Unconfirmed items:"
    foreach ($n in @($gate.notes)) {
        if ($n -match "^UNCONFIRMED") { Log "  $n" }
    }
    Log "Aborting BEFORE :8004 is stopped. Fix the items above, then retry."
    exit 4
}
Log "D1a gate PASSED; confirmed:"
foreach ($k in @($gate.keys)) { Log "  $k" }

# --- step 1b: leg A (opencode) launch probe -----------------------------------
# F1: prove the leg-A launcher can actually be STARTED under the watchdog
# BEFORE :8004 is stopped. Offline-safe: `opencode --version` -- no network, no
# model call, no GPU. opencode's PRESENCE is already checked by -CheckOnly;
# this probe targets LAUNCHABILITY (a .ps1 shim resolving to a spaced path, or
# a broken install, would otherwise fail silently at the first task INSIDE the
# outage). Any failure -> exit 4 naming it.
Log "step 1b/6: leg A launch probe (opencode --version under the watchdog; offline-safe)"
$ocProbeLog = Join-Path $ReportDir "opencode_version_probe.log"
$ocProbe = Invoke-ScrubbedChild {
    Invoke-WatchdogCommand "opencode" @("--version") $RepoRoot $ocProbeLog 120
}
$probeOk = ($null -ne $ocProbe.exit -and $ocProbe.exit -eq 0)
if (-not $probeOk) {
    Log "REFUS (exit 4): leg A launch probe FAILED (opencode --version): error=$($ocProbe.error) exit=$($ocProbe.exit) timed_out=$($ocProbe.timed_out). Probe log -> $ocProbeLog"
    Log "Aborting BEFORE :8004 is stopped. Fix the opencode launcher (PATH entry / .ps1 shim quoting), then retry."
    exit 4
}
Log "  leg A launch probe PASSED (opencode --version exit 0)."

# --- step 2: record + stop :8004 (approved outage window) ---------------------
Log "step 2/6: record :8004 state and stop it (approved outage window)"
$before8004 = @{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    healthy = (Test-Health ("http://127.0.0.1:{0}/health" -f $ProdPort) 5)
}
$before8004 | ConvertTo-Json -Depth 4 | Out-File -FilePath (Join-Path $ReportDir "state_8004_before.json") -Encoding ascii
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Stopper -Port $ProdPort
$stop8004Exit = $LASTEXITCODE
if ($stop8004Exit -ne 0) {
    Log "FATAL: stop_llama_port.ps1 refused :$ProdPort (exit $stop8004Exit). Outage ABORTED."
    Log "  production was NOT stopped (never touched); state recorded -> state_8004_before.json"
    $abort = @{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        aborted = "stop_llama_port exit $stop8004Exit"
        production_touched = $false
        production_restored = $true
        runs = @()
        dsh_version = $DshVersion
        telemetry_disabled = $true
    }
    $abort | ConvertTo-Json -Depth 6 | Out-File -FilePath (Join-Path $ReportDir "harness_ab.json") -Encoding ascii
    exit 1
}
Log "  :8004 stopped (or had no listener)."

# --- steps 3-5: DSH settings lifecycle + per-config bench ----------------------
$configResults = @()
$runRecords = @()
$productionRestored = $false
$runError = $null

try {
    # Backup-DshSettings happens BEFORE the first Invoke-LegDsh (any config
    # writes settings.yaml at config start); Restore-DshSettings runs in the
    # SAME finally as the production restore below.
    $dshHome = Resolve-DshHome
    $dshBackup = Backup-DshSettings $dshHome
    if ($dshBackup.existed) { Log "  backed up $dshHome\settings.yaml -> $($dshBackup.backup)" }
    else { Log "  no pre-existing $dshHome\settings.yaml (harness-written settings will be removed on restore)" }

    foreach ($cfg in $Configs) {
        $cfgRecord = @{
            config = $cfg
            alias = $AliasMap[$cfg]
            skipped = $false
            skipReason = $null
            gate_exit = $null
            server_ok = $false
            serverNote = $null
            stop_8005_exit = $null
            runs = 0
            graded = 0
            solved = @{ opencode = 0; dsh = 0 }
        }

        if ($cfg -eq "q38-dflash2" -and -not $Dflash2BinaryPath) {
            Log "SKIP $cfg : -Dflash2BinaryPath not given (default b10488 is refused by the launcher's DFlash2 gate by design)."
            $cfgRecord.skipped = $true
            $cfgRecord.skipReason = "no -Dflash2BinaryPath"
            $configResults += $cfgRecord
            continue
        }

        # launcher -CheckOnly gate (guards + artifact checks; GPU busy only warns)
        Log "config $cfg : launcher -CheckOnly gate"
        $gateArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Launcher, "-Config", $cfg, "-CheckOnly")
        if ($cfg -eq "q38-dflash2" -and $Dflash2BinaryPath) { $gateArgs += @("-BinaryPath", ('"{0}"' -f $Dflash2BinaryPath)) }
        $gateRes = Invoke-WatchdogProcess "powershell.exe" $gateArgs $RepoRoot (Join-Path $ReportDir ("harness_{0}-gate.log" -f $cfg)) 300
        $cfgRecord.gate_exit = $gateRes.exit
        if ($gateRes.exit -ne 0) {
            if ($cfg -eq "q38-dflash2") {
                Log "SKIP $cfg : launcher gate refused (exit $($gateRes.exit)); recorded as warning. See harness_$cfg-gate.log"
                $cfgRecord.skipped = $true
                $cfgRecord.skipReason = "launcher gate exit $($gateRes.exit)"
            } else {
                Log "FAIL $cfg : launcher gate refused (exit $($gateRes.exit)); config recorded as failed."
                $cfgRecord.skipped = $true
                $cfgRecord.skipReason = "launcher gate exit $($gateRes.exit)"
            }
            $configResults += $cfgRecord
            continue
        }

        # write per-config DSH settings (backed up once above, restored in the finally)
        Log "config $cfg : write $dshHome\settings.yaml (agent-default-model + llm-pi-ai.providers.$DshRoute)"
        $auditPath = Join-Path $ReportDir ("harness_{0}-dsh-settings.yaml" -f $cfg)
        Write-DshSettings $AliasMap[$cfg] $dshHome $auditPath

        # launch the bench server; health-poll :8005 <= 10 min with early-exit
        # detection on the launcher process
        Log "config $cfg : launch $Launcher -Config $cfg -LogPath <report>\harness_$cfg-server.log"
        $launchArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Launcher, "-Config", $cfg, "-LogPath", (Join-Path $ReportDir ("harness_{0}-server.log" -f $cfg)))
        if ($cfg -eq "q38-dflash2" -and $Dflash2BinaryPath) { $launchArgs += @("-BinaryPath", ('"{0}"' -f $Dflash2BinaryPath)) }
        $serverProc = $null
        try {
            $serverProc = Start-Process -FilePath "powershell.exe" -ArgumentList $launchArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
        } catch {
            Log "  Start-Process for the launcher FAILED: $_"
        }
        if ($serverProc) {
            $health = Wait-HealthOrExit ("http://127.0.0.1:{0}/health" -f $BenchPort) 600 $serverProc
        } else {
            $health = @{ Healthy = $false; Exited = $true; ExitCode = $null }
        }
        if (-not $health.Healthy) {
            Log "FAIL $cfg : :$BenchPort never became healthy (launcher exited=$($health.Exited) exitCode=$($health.ExitCode)). See harness_$cfg-server.log"
            $cfgRecord.server_ok = $false
            $cfgRecord.serverNote = "launcher exited=$($health.Exited) exitCode=$($health.ExitCode)"
        } else {
            $cfgRecord.server_ok = $true
            Log "  :$BenchPort healthy for $cfg"

            # per task: FRESH scaffold per (config, arm, task) so no arm inherits
            # files a previous arm left behind (FAIRNESS NOTE in the header);
            # grade after EVERY arm.
            foreach ($t in @(New-TaskSpecs)) {
                $dirA = Write-ScaffoldTask $t (Join-Path $ScratchRoot ("run-{0}-{1}-opencode" -f $cfg, $t.id))
                $t.dir = $dirA
                $logA = Join-Path $ReportDir ("harness_{0}-{1}-opencode.log" -f $cfg, $t.id)
                Log "  $cfg t=$($t.id) : leg A (opencode) starts"
                $armA = Invoke-LegOpenCode $t $AliasMap[$cfg] $logA $TaskTimeoutSeconds
                $gradeLogA = Join-Path $ReportDir ("harness_{0}-{1}-opencode-grade.log" -f $cfg, $t.id)
                $gradeA = Invoke-GradeUnittest $t $dirA $gradeLogA
                $runRecords += @{
                    config = $cfg; arm = "opencode"; task = $t.id
                    wall_s = $armA.wall_s; exit = $armA.exit
                    solved = $gradeA.solved; grade_exit = $gradeA.exit
                    timeout = $armA.timeout; turns = $armA.turns; error = $armA.error; log = $logA
                }
                $cfgRecord.runs = $cfgRecord.runs + 1
                $cfgRecord.graded = $cfgRecord.graded + 1
                if ($gradeA.solved) { $cfgRecord.solved.opencode = $cfgRecord.solved.opencode + 1 }
                Log ("    opencode solved={0} exit={1} wall_s={2} timeout={3}" -f $gradeA.solved, $armA.exit, $armA.wall_s, $armA.timeout)

                if ($OpenCodeOnly) { continue }

                $dirB = Write-ScaffoldTask $t (Join-Path $ScratchRoot ("run-{0}-{1}-dsh" -f $cfg, $t.id))
                $t.dir = $dirB
                $logB = Join-Path $ReportDir ("harness_{0}-{1}-dsh.log" -f $cfg, $t.id)
                Log "  $cfg t=$($t.id) : leg B (dsh) starts -- DSH always after OpenCode"
                $armB = Invoke-LegDsh $t $AliasMap[$cfg] $logB $TaskTimeoutSeconds
                $gradeLogB = Join-Path $ReportDir ("harness_{0}-{1}-dsh-grade.log" -f $cfg, $t.id)
                $gradeB = Invoke-GradeUnittest $t $dirB $gradeLogB
                $runRecords += @{
                    config = $cfg; arm = "dsh"; task = $t.id
                    wall_s = $armB.wall_s; exit = $armB.exit
                    solved = $gradeB.solved; grade_exit = $gradeB.exit
                    timeout = $armB.timeout; turns = $armB.turns; error = $armB.error; log = $logB
                }
                $cfgRecord.runs = $cfgRecord.runs + 1
                $cfgRecord.graded = $cfgRecord.graded + 1
                if ($gradeB.solved) { $cfgRecord.solved.dsh = $cfgRecord.solved.dsh + 1 }
                Log ("    dsh solved={0} exit={1} wall_s={2} timeout={3}" -f $gradeB.solved, $armB.exit, $armB.wall_s, $armB.timeout)
            }
        }

        # port-scoped stop of :8005 (even on the unhealthy path: partial start)
        Log "config $cfg : stop :$BenchPort"
        try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Stopper -Port $BenchPort
            $cfgRecord.stop_8005_exit = $LASTEXITCODE
        } catch {
            $cfgRecord.stop_8005_exit = $null
            Log "  stop :$BenchPort invocation failed: $_"
        }
        # F4: wait for the dying llama-server to fully exit before the next
        # config's launcher gate/GPU-guard runs (a lingering process would trip
        # it and cascade-fail the window). Bounded; warn and continue.
        if (-not (Wait-LlamaServerGone $BenchPort 30)) {
            Log "  WARN: after 30 s a llama-server process and/or :$BenchPort still up after stop; continuing (next config's GPU guard may trip)"
        }
        $configResults += $cfgRecord
    }
} catch {
    $runError = $_
    Log "FATAL (caught): $_"
} finally {
    # ALWAYS: restore DSH settings + production, and record it.
    Log "finally: restore DSH settings"
    $dshSettingsRestored = $false   # honest flag: $true ONLY after a verified restore
    try {
        if ($dshBackup) {
            $dshSettingsRestored = (Restore-DshSettings $dshBackup)
            if ($dshSettingsRestored) { Log "  DSH settings restored (pre-state -> $($dshBackup.original))" }
        } else {
            Log "  WARN: no DSH settings backup object exists; restore NOT verified -> dsh_settings_restored=false"
        }
    } catch {
        $dshSettingsRestored = $false
        Log "  WARN: DSH settings restore FAILED -> dsh_settings_restored=false: $_"
    }
    if (-not $dshSettingsRestored) {
        Log "  LOUD WARN: $dshHome\settings.yaml may be the harness's bench config; recorded dsh_settings_restored=false."
    }

    Log "finally: restart production :$ProdPort (restart_production.ps1)"
    $restartExit = $null
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Restart
        $restartExit = $LASTEXITCODE
    } catch {
        Log "  WARN: restart_production.ps1 invocation failed: $_"
    }
    $prodHealthy = Wait-Health ("http://127.0.0.1:{0}/health" -f $ProdPort) 600
    $productionRestored = $prodHealthy
    $prodRec = @{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        restored = $prodHealthy
        restart_exit = $restartExit
        dsh_settings_restored = $dshSettingsRestored
    }
    $prodRec | ConvertTo-Json -Depth 4 | Out-File -FilePath (Join-Path $ReportDir "production_restored.json") -Encoding ascii
    Log ("  production restored={0} (restart exit {1}) -> production_restored.json" -f $prodHealthy, $restartExit)
}

# --- step 6: report + exit code ----------------------------------------------
# per-config per-arm solved counts (x/3) + median wall_s over SOLVED runs only
$solvedCounts = @{}
foreach ($cfgRec in $configResults) {
    $solvedCounts[$cfgRec.config] = @{
        alias = $cfgRec.alias
        skipped = $cfgRec.skipped
        skip_reason = $cfgRec.skipReason
        gate_exit = $cfgRec.gate_exit
        server_ok = $cfgRec.server_ok
        server_note = $cfgRec.serverNote
        stop_8005_exit = $cfgRec.stop_8005_exit
        runs = $cfgRec.runs
        graded = $cfgRec.graded
        solved = @{ opencode = $cfgRec.solved.opencode; dsh = $cfgRec.solved.dsh }
    }
}
$medians = @{}
foreach ($cfg in $Configs) {
    $medians[$cfg] = @{}
    foreach ($arm in @("opencode", "dsh")) {
        $times = @($runRecords | Where-Object { $_.config -eq $cfg -and $_.arm -eq $arm -and $_.solved -and $null -ne $_.wall_s } | ForEach-Object { [double]$_.wall_s } | Sort-Object)
        if ($times.Count -gt 0) {
            $mid = [int][math]::Floor($times.Count / 2)
            if ($times.Count % 2 -eq 1) { $medians[$cfg][$arm] = $times[$mid] }
            else { $medians[$cfg][$arm] = [math]::Round(($times[$mid - 1] + $times[$mid]) / 2, 1) }
        } else {
            $medians[$cfg][$arm] = $null
        }
    }
}
$harness = @{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    started_at = $before8004.timestamp
    dsh_version = $DshVersion
    telemetry_disabled = $true
    bench_base_url = ("http://127.0.0.1:{0}/v1" -f $BenchPort)
    task_timeout_seconds = $TaskTimeoutSeconds
    configs = $solvedCounts
    median_wall_s_solved_only = $medians
    runs = $runRecords
    run_error = $(if ($runError) { [string]$runError } else { $null })
    production_restored = $productionRestored
    dsh_settings_restored = $dshSettingsRestored
    production_restored_json = (Join-Path $ReportDir "production_restored.json")
    state_8004_before = (Join-Path $ReportDir "state_8004_before.json")
}
$harnessPath = Join-Path $ReportDir "harness_ab.json"
$harness | ConvertTo-Json -Depth 8 | Out-File -FilePath $harnessPath -Encoding ascii
Log "report written -> $harnessPath"

if ($runError) {
    Log "FATAL: run aborted by an exception; report still written; production restore attempted above."
    exit 1
}
if (-not $productionRestored) {
    Log "FATAL (exit 1): production NOT restored on :$ProdPort. See production_restored.json."
    exit 1
}
$anyAttempted = $false
$zeroGradedAttempt = $false
foreach ($cfgRec in $configResults) {
    if ($cfgRec.skipped) { continue }
    $anyAttempted = $true
    if ($cfgRec.graded -eq 0) { $zeroGradedAttempt = $true }
}
if ($zeroGradedAttempt -or -not $anyAttempted) {
    Log "exit 2: completed + production restored, but an attempted config produced zero graded runs (or nothing was attempted)."
    exit 2
}
Log "DONE: run completed; production restored; exit 0."
exit 0