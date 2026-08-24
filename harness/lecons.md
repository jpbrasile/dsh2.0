# Leçons distillées des sessions (observations, pas des instructions)

Écrit par `harness/distiller.py` ; rendu au planner par le greffon `dsh-lecons` via `{{lecons}}`.
Une ligne = `- [date session] observation`. Les plus récentes en premier ; 60 lignes max par rôle.

## orchestrator
- [2026-08-24 9d46e7e0] orchestrator verified the fix by running the unittest suite after editing only the source file.
- [2026-08-24 53b7af34] The orchestrator measured PLAN.md length with pwsh after the coder had already completed, adding an unrequested verification step.
- [2026-08-24 53b7af34] The orchestrator read and wrote DONE.md after the two required delegations, extending the run beyond the stop-after-two-delegations instruction.
- [2026-08-24 daf021e6] The orchestrator treated the planner's plan-spool acknowledgement as sufficient for the coder, but the coder still had to read PLAN.md to obtain the full contract.
- [2026-08-24 daf021e6] The orchestrator hit a write-tool error when overwriting DONE.md without reading it first, then recovered by reading the file and retrying the write.
- [2026-08-24 daf021e6] The orchestrator exceeded the two-delegation stop rule by measuring PLAN.md, globbing, reading and writing DONE.md, adding extra calls after the coder finished.
- [2026-08-24 7d3ee00d] The orchestrator completed a small single-file refactor with two reads, one write, and one unittest run, avoiding delegate overhead.
- [2026-08-24 8c265d14] orchestrator completed the task in three calls: two file writes followed by one test run.
- [2026-08-24 0e3c8d37] orchestrator completed a small single-file refactor without delegates by reading both files, grepping usage, writing seed.py, and running unittest
- [2026-08-24 53f8612a] orchestrator read the source and test files before editing, then ran the unittest suite, completing the refactor in four calls.
- [2026-08-24 70e1b2d8] orchestrator ended with error after 16.8s with zero tool calls and empty final text, so the PONG.txt creation step was not executed.
- [2026-08-24 c073bc20] The orchestrator made an extra write of DONE.md after the two required delegations, adding a call beyond the requested stop.
- [2026-08-24 e3f77830] The orchestrator’s first pwsh PLAN.md length check failed, and a simpler retry succeeded.
- [2026-08-24 e3f77830] The orchestrator made extra pwsh calls after the coder delegation even though the task said to stop after two delegations.
- [2026-08-24 073039f1] The orchestrator passed the planner's plan-spool message verbatim to the coder, which made the coder read PLAN.md instead of receiving a copied plan.
- [2026-08-24 419383c5] orchestrator verified the edit by running the unittest suite in step 6 and reported all three tests pass.
- [2026-08-24 cd93d1d9] orchestrator ran the exact specified unittest command after a verbose run, confirming the required invocation passed.
- [2026-08-24 d70397c0] The orchestrator passed the planner's short spool acknowledgement (not the full plan) to the coder, relying on the coder to read PLAN.md, which worked but added an extra read call.
- [2026-08-24 5b6f6dad] The orchestrator passed the planner's spool acknowledgement (which said to read PLAN.md) as the coder's prompt, but the coder still read PLAN.md successfully, so the indirection worked.
- [2026-08-24 86021c46] The orchestrator measured PLAN.md with pwsh to confirm the spool size before delegating, adding a verification step that was not strictly required.
- [2026-08-24 145042d0] The orchestrator wrote the planner's spool notice to a temp file instead of passing it directly to the coder, adding an unnecessary step.
- [2026-08-24 e338d7c8] The orchestrator followed its own instruction to delegate exactly once each and stop, resulting in a clean single-round VERT without loops or budget waste.
- [2026-08-24 2c2285c6] The orchestrator's final pwsh step to create DONE.md failed because the file path contained backslashes that were not properly escaped in the PowerShell command, causing exit code 1.
- [2026-08-24 9e7bf9ad] The orchestrator relayed a planner output containing computed constants and hand-checked values as the coder's prompt, but the coder needed a step-by-step implementation plan rather than raw analysis.
- [2026-08-24 0cd8718b] The orchestrator used a temporary file and pwsh to verify the planner's output character count and encoding before passing it to the coder.
- [2026-08-24 b3a5eb15] The orchestrator delegated planning and coding exactly once each in strict order, then wrote DONE.md, completing the task without any retries or corrections.
- [2026-08-24 c5180645] The orchestrator used multiple pwsh calls to inspect the planner's output for non-ASCII characters and line endings before passing it to the coder, adding latency without a gate requirement.
- [2026-08-24 bec1e852] The orchestrator wrote the planner's output to a temporary file and later read it back with pwsh to pass to the coder, adding unnecessary steps when the planner's final message could have been passed directly.
- [2026-08-24 b943981d] The orchestrator successfully delegated to planner and coder in sequence without reading source files, following its own task constraints exactly.
- [2026-08-24 9afcb1fd] The orchestrator wrote the planner's final message to a temporary file and checked its length before writing DONE.md, which was unnecessary for the task but did not cause errors.
- [2026-08-24 dbd0089c] The orchestrator used a temporary file and a PowerShell command to count planner output characters, which was unnecessary for the delegation task.
- [2026-08-24 ac70f186] The orchestrator wrote the planner's output to a temporary file and verified its length before passing it to the coder, ensuring the full plan was transmitted.
- [2026-08-23 3813a631] The orchestrator used a temporary file and PowerShell to measure the planner's output length before writing DONE.md, adding two extra tool calls that were not strictly required by the task.
- [2026-08-23 c10ce871] The orchestrator wrote the planner's full output to a temporary file and then to DONE.md, including internal reasoning, instead of extracting only the final plan.
- [2026-08-23 d0083bd3] The orchestrator wrote a DONE.md file reporting the coder's error as the final outcome without retrying the delegation, even though the task required a successful implementation.

## planner
- [2026-08-24 e3f77830] The planner read the source and test files before producing the plan, grounding the plan in actual file contents.
- [2026-08-24 073039f1] The planner used a glob to confirm the target triage file did not exist before planning its creation.
- [2026-08-24 8e2fe37f] The planner did not check whether the existing test suite already exceeded the gate budget, leading the coder to a plan that could never turn the gate green.
- [2026-08-24 86021c46] The planner wrote the full plan to PLAN.md and returned only a spool pointer, which the orchestrator then had to measure and forward correctly.
- [2026-08-24 145042d0] The planner used glob with pattern '**/VERDICT_V09*' and '**/PREREG_V09*' to find files outside the campaign directory, which was efficient.
- [2026-08-24 e338d7c8] The planner read the source file, the existing test runner, and a sample test file to derive constants and patterns, producing a plan that the coder could implement verbatim without ambiguity.
- [2026-08-24 9e7bf9ad] The planner tasked the coder with creating and editing test files, but the coder's sandbox forbids any test file writes outside the julia_gate tool.
- [2026-08-24 b3a5eb15] The planner read the source file, test file, and runtests.jl before producing the plan, which gave the coder enough context to implement without further exploration.
- [2026-08-24 c5180645] The planner read the target source file, the test runner, and the existing test file before producing the plan, ensuring line-number references were accurate.
- [2026-08-24 b943981d] The planner read the source file, the test file, and the test runner before writing the plan, which gave the coder sufficient context to implement without further reads.
- [2026-08-23 3813a631] The planner attempted to read a documentation file that did not exist, causing a tool error; verifying file existence before reading would avoid wasted calls.

## coder
- [2026-08-24 53b7af34] The coder ran julia_gate once after both file changes and reported the ORANGE verdict verbatim in its final report.
- [2026-08-24 53b7af34] The coder received a plan-spool pointer to PLAN.md and read PLAN.md plus the three referenced files before implementing, avoiding plan copying.
- [2026-08-24 daf021e6] The coder correctly reported the julia_gate ORANGE verdict verbatim after creating only documentation files, showing the gate can be non-green without code changes.
- [2026-08-24 daf021e6] The coder ran broad glob calls before writing the required triage note, even though the plan and task already named the exact file to create.
- [2026-08-24 c073bc20] The coder received an ORANGE gate verdict after implementing the plan, so the run was not fully green.
- [2026-08-24 c073bc20] The coder used multiple grep and glob calls to verify exports and module structure before writing the test file.
- [2026-08-24 c073bc20] The coder read PLAN.md and found its first line was the planner's verification preamble rather than a clean plan header.
- [2026-08-24 e3f77830] The coder read PLAN.md and the relevant source/test files before implementing, which helped it follow the plan contract.
- [2026-08-24 e3f77830] The coder repeatedly received ORANGE gate verdicts while the test server was busy, so it inserted sleeps before retrying the gate.
- [2026-08-24 073039f1] The coder treated the ORANGE julia_gate verdict as expected for a documentation-only file and did not attempt code fixes.
- [2026-08-24 073039f1] The coder re-located and re-read the six evidence files even though the planner had already read them, adding calls but preserving the plan's citation contract.
- [2026-08-24 8e2fe37f] The coder misinterpreted the ORANGE verdict with zero failures/errors/broken as a budget timeout rather than a possible server congestion issue, leading to premature acceptance of the result.
- [2026-08-24 8e2fe37f] The coder triggered a shell wall refusal by attempting to run Julia directly outside the julia_gate tool, which is explicitly forbidden for test running.
- [2026-08-24 d70397c0] The coder ran git status twice with different relative paths, both showing the same untracked file, which was unnecessary for verifying the triage note creation.
- [2026-08-24 d70397c0] The coder ran julia_gate with a file that was not modified by the triage note creation, resulting in an ORANGE verdict that may not reflect the actual change.
- [2026-08-24 d70397c0] The coder re-read four evidence files already read by the planner, despite the plan being the contract and the files being unchanged, consuming extra calls.
- [2026-08-24 5b6f6dad] The coder stopped after receiving an ORANGE gate verdict, correctly interpreting that VERT was the only acceptable green per the contract, avoiding unnecessary retries.
- [2026-08-24 5b6f6dad] The coder used glob patterns to discover files instead of relying solely on the exact file paths provided in the plan, risking reading unauthorized files.
- [2026-08-24 5b6f6dad] The coder read extra evidence files beyond the five specified in the plan (e.g., VALIDATION_SUMMARY_at_seal.md, RT_GLM_V44_BRIEF_2026-08-09.md), violating the hard reading bound.
- [2026-08-24 86021c46] The coder read PLAN.md, the source module, and the industrial orchestrator pattern before writing files, which matched the planner's intended contract.
- [2026-08-24 86021c46] The coder's first julia_gate run returned ROUGE because a placeholder assertion expected 2 errors while the committed registry actually had 0, requiring one edit to fix.
- [2026-08-24 93c42886] The coder used a glob pattern with braces '{DONE.md,docs/vv/TRIAGE_V09_2026-08-24.md}' which only returned the triage note, suggesting the glob tool may not support brace expansion.
- [2026-08-24 93c42886] The coder ran julia_gate on a non-code file (docs/vv/TRIAGE_V09_2026-08-24.md) and received an ORANGE verdict with a note that it was 'hors champ', then ran it on test/runtests.jl and got VERT.
- [2026-08-24 145042d0] The coder's final message indicates it was still verifying citations and had not yet written the triage note, suggesting the session ended before completion.
- [2026-08-24 145042d0] The coder made 44 tool calls but never invoked julia_gate, despite the orchestrator's instruction to use it after every change.
- [2026-08-24 145042d0] The coder read PLAN.md twice (calls 1 and 28) and re-read many source files multiple times, suggesting the plan was not fully internalized on first pass.
- [2026-08-24 e338d7c8] The coder read the plan file, the source, and the runtests file before writing, then used the julia_gate tool after both file changes, achieving VERT on the first attempt.
- [2026-08-24 2c2285c6] The coder's first julia_gate call returned ROUGE, but a single subsequent edit to the test file resolved the failure and produced a VERT verdict on the next attempt.
- [2026-08-24 9e7bf9ad] The coder repeated a file write operation on a test file after the first attempt was rejected by the same test wall restriction, wasting a call.
- [2026-08-24 0cd8718b] The coder's first julia_gate call returned ROUGE, requiring three subsequent edit calls before a second gate call achieved VERT.
- [2026-08-24 b3a5eb15] The coder applied three sequential edits to the same file and then called julia_gate once on that file, obtaining VERT on the first attempt.
- [2026-08-24 c5180645] The coder performed three separate edit calls on the same file to insert the four required functions, suggesting the plan's insertion point description allowed incremental application.
- [2026-08-24 bec1e852] The coder attempted to read beyond the file's end (offset 684 on a 680-line file), causing a tool error, but recovered by reading the last few lines with a corrected offset.
- [2026-08-24 b943981d] The coder achieved VERT on the first julia_gate call after two edits, showing that the plan was precise enough to avoid iterative debugging.
- [2026-08-24 9afcb1fd] The coder retried the julia_gate tool three times after ORANGE verdicts due to a busy server, and a 45-second sleep before the fourth call resolved the issue.
- [2026-08-24 dbd0089c] The coder achieved a VERT gate verdict on the first attempt by following the planner's contract exactly and using the julia_gate tool on the single changed file.
- [2026-08-24 ac70f186] The coder's first julia_gate call returned ORANGE due to a busy server, requiring two retries before achieving VERT.
- [2026-08-23 3813a631] The coder could not execute the plan's 10-point invariant self-check because it lacked direct Julia execution capability and could not add test files, so it performed only static verification.
- [2026-08-23 c10ce871] The coder misinterpreted the gate's ORANGE verdict as a transient server issue and retried instead of investigating the test timeout.
- [2026-08-23 c10ce871] The coder repeatedly called julia_gate on the same file without changing it, consuming all gate attempts without progress.
- [2026-08-23 d0083bd3] The coder repeatedly edited the same function signature (`validate_financing`) back and forth between `-> Bool` and no return type, indicating confusion about the root cause of the ROUGE verdict.
- [2026-08-23 d0083bd3] The coder triggered a wall refusal by attempting to run Julia directly via pwsh instead of using the julia_gate tool, wasting a call.
- [2026-08-23 d0083bd3] The coder spent many calls investigating a syntax error on `-> Bool` in a function signature, but the real issue was that the file was git-ignored and the gate was testing a stale committed version.
