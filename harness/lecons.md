# Leçons distillées des sessions (observations, pas des instructions)

Écrit par `harness/distiller.py` ; rendu au planner par le greffon `dsh-lecons` via `{{lecons}}`.
Une ligne = `- [date session] observation`. Les plus récentes en premier ; 60 lignes max par rôle.

## orchestrator
- [2026-08-23 3813a631] The orchestrator used a temporary file and PowerShell to measure the planner's output length before writing DONE.md, adding two extra tool calls that were not strictly required by the task.
- [2026-08-23 c10ce871] The orchestrator wrote the planner's full output to a temporary file and then to DONE.md, including internal reasoning, instead of extracting only the final plan.
- [2026-08-23 d0083bd3] The orchestrator wrote a DONE.md file reporting the coder's error as the final outcome without retrying the delegation, even though the task required a successful implementation.

## planner
- [2026-08-23 3813a631] The planner attempted to read a documentation file that did not exist, causing a tool error; verifying file existence before reading would avoid wasted calls.

## coder
- [2026-08-23 3813a631] The coder could not execute the plan's 10-point invariant self-check because it lacked direct Julia execution capability and could not add test files, so it performed only static verification.
- [2026-08-23 c10ce871] The coder misinterpreted the gate's ORANGE verdict as a transient server issue and retried instead of investigating the test timeout.
- [2026-08-23 c10ce871] The coder repeatedly called julia_gate on the same file without changing it, consuming all gate attempts without progress.
- [2026-08-23 d0083bd3] The coder repeatedly edited the same function signature (`validate_financing`) back and forth between `-> Bool` and no return type, indicating confusion about the root cause of the ROUGE verdict.
- [2026-08-23 d0083bd3] The coder triggered a wall refusal by attempting to run Julia directly via pwsh instead of using the julia_gate tool, wasting a call.
- [2026-08-23 d0083bd3] The coder spent many calls investigating a syntax error on `-> Bool` in a function signature, but the real issue was that the file was git-ignored and the gate was testing a stale committed version.
