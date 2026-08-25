## RED TEAM ANALYSIS — Claims Falsification

### B1. Find-or-launch of the :8004 llama server; the script leaves the world as it found it
**severity: HIGH** | claim B1 | `distiller_nightly.ps1:line 86`
*Evidence:* `if ($dejaLa) { Ecrire "serveur :8004 deja sain -- utilise tel quel, ne sera PAS arrete" }` — when server is found healthy, script skips stop logic entirely, but **never verifies the server is still healthy after distillation**; if the distillation process itself (python calls) crashes or hangs the server, script exits without restoring the found server to its original (healthy) state.
*Failure scenario:* Server is found healthy at start → script runs python concurrently (lines 87-99) which may exhaust memory or crash the process → script exits normally (exit 0) leaving server dead on :8004, violating "leave as found".
*Check:* `$dejaLa=$true` then force-kill server during python step → observe script exits 0, server unreachable after.

### B2. If the GPU launcher refuses, the script SKIPs; it never kills a process it did not start
**severity: MEDIUM** | claim B2 | `distiller_nightly.ps1:line 86`
*Evidence:* `if (-not $sain) { if ($lanceur.HasExited) { Ecrire ... } else { Ecrire "ECHEC : serveur muet ... arret du lanceur ..."; & powershell ... stop_llama_port.ps1 ...; exit 2 }` — the ELSE branch runs `stop_llama_port.ps1` on a port where server did NOT start, which could kill a **pre-existing** process if that process grabbed the port between the health check and the failure timeout.
*Failure scenario:* Server not listening at start → script launches launcher (fails/doesn't start) → but at time t=240s, an unrelated service starts on :8004 → script misidentifies it as "our launcher failure" and kills it with `stop_llama_port.ps1`.
*Check:* Start a dummy listener on :8004 at t=200s while script waits for launcher → observe script kills it.

### B3. Stop is VERIFIED: exit code 4 if the port is still held afterwards
**severity: LOW** | claim partially less precise | `distiller_nightly.ps1:line 86`
*Evidence:* After stop, script sleeps 2 seconds then checks `Get-NetTCPConnection -LocalPort 8004 -State Listen`. Exit 4 if tenu. Works as stated — no falsification possible.

### B4. All outcomes are journaled to %USERPROFILE%\dsh-distiller-nightly.log
**severity: MEDIUM** | claim B4 | `distiller_nightly.ps1:line 86`
*Evidence:* `Add-Content -LiteralPath $JOURNAL` writes all Ecrire calls, but the 2>&1 redirection in lines 97-99 (`for python ... 2>&1 | ForEach-Object { Add-Content ... }`) captures stderr but **not stdout** of `Invoke-WebRequest` calls in the health-check polling loop (lines 46-55). Early failures leave no journal trace before Ecrire fires.
*Failure scenario:* Script starts, launcher fails immediately, but `try { Invoke-WebRequest... } catch {}` swallows connection errors silently with no journal entry until line 73's Ecrire — which may never fire if the `while` loop's `-and` condition short-circuits.
*Check:* Block port 8004 → run script → observe no journal entries before "SAUTE" message.

### B5. If `$lanceur.HasExited` after the wait loop, script correctly reports exit code
**severity: LOW** | claim B5 | `distiller_nightly.ps1:line 86`
*Evidence:* `Ecrire ("SAUTE : lanceur refuse/mort, exit " + $lanceur.ExitCode)` — possible race where `$lanceur.HasExited` is true but `$lanceur.ExitCode` is accessed after process object is disposed. Edge case, not reliably falsifiable from code alone.

---

### C1. Exit 0 if :8077 is not listening; otherwise --arret then verify; exit 4 if port still held
**severity: MEDIUM** | claim C1 | `julia_gate_arret.ps1:line 38`
*Evidence:* Line 38: `if (-not $conn) { exit 0 }` — but script does NOT journal this case per its claim of "0 silencieuse". However line 35 says `Add-Content ...` is defined but never called in the exit-0 path. **Journal is NOT written for the idle case**, contradicting the script's own documentation of logging all outcomes.
*Failure scenario:* Port 8077 not listening → script exits 0 with no journal entry → operator has no trace this task ran at all.
*Check:* Remove any listener on 8077 → run script → verify `dsh-julia-gate-arret.log` does not exist or has no new entries.

---

### D1. Registers dsh-julia-gate-arret at 00:50 and 04:50 and dsh-distiller-nightly at 07:00
**severity: HIGH** | claim D1 | `installer_taches_nocturnes.ps1:line 22`
*Evidence:* Line 22: `$t1a = New-ScheduledTaskTrigger -Daily -At 00:50; $t1b = New-ScheduledTaskTrigger -Daily -At 04:50` — but `Register-ScheduledTask -Trigger @($t1a, $t1b)` creates an **array** of triggers. In Windows Task Scheduler, mixing multiple triggers with `-Daily` creates triggers that fire **every day at both times**, which matches the claim. **However**, line 42: `(Get-ScheduledTask -TaskName "dsh-julia-gate-arret").Triggers` will only enumerate triggers; the **claim does not specify which morning/evening** and `00:50` is ambiguous: 12:50 AM or 12:50 PM? PowerShell `-At 00:50` is 12:50 AM, but the underlying XML stores it as `00:50:00` (midnight). If the system timezone or DST handling differs, trigger may fire at unexpected times.
*Failure scenario:* System in UTC+1 with DST → "00:50" UTC becomes 02:50 local or 01:50 local depending on DST → the gate-arret fires 1-2 hours after test-all (01:00), completely missing the pre-window.
*Check:* On a UTC+2 machine, run script → `(Get-ScheduledTask ...).Triggers[0].StartBoundary` will show `2026-08-25T00:50:00` (assuming date) which is UTC — local time is 02:50, not 00:50.

---

## Claims that held
- **B3** (exit 4 logic for port held after stop): code correctly implements verification with `Get-NetTCPConnection` and `exit 4`.
- **B5** (exit code reporting after launcher death): code accesses `$lanceur.ExitCode` correctly after `HasExited` check.

## Verdicts

| Claim | Status | Reasoning |
|---|---|---|
| B1 | **BROKEN** | Script never verifies server stays healthy after distillation; a pre-existing server can be left dead |
| B2 | **PARTIAL** | SKIP logic for GPU refusal works, but timeout path `stop_llama_port.ps1` can kill pre-existing processes on the port |
| B3 | **HOLDS** | Stop verification with Get-NetTCPConnection and exit 4 is correctly implemented |
| B4 | **PARTIAL** | Ecrire() calls are journaled, but stderr from health-check polling loop is silently swallowed |
| C1 | **BROKEN** | Exit 0 path for idle port does NOT write to the journal as implied by the script's documentation |
| D1 | **PARTIAL** | Triggers registered at correct times, but timezone/DST handling may shift actual fire times |