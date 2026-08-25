### Findings

**HIGH** | `stealth/ox-alpha` context window is catalog peak, not a prudent floor | **F1**  
`harness/providers.yaml` lines 282, 290:  
`contextWindow: 1048576` — the comment at lines 34–35 admits `/v1/models` announces 1048576 but calls it a catalog peak, yet this model uses that same peak value.  
**Failure scenario**: A benchmark run using `stealth/ox-alpha` with `contextWindow: 1048576` will allocate memory/state for 1M tokens, but the free provider likely enforces a far smaller limit (e.g., 128k). The harness will either receive a 400 error or produce inconsistent results when the upstream truncates.  
**Check**: Run `grep -n 'contextWindow: 1048576' harness/providers.yaml` and read the comment context.

**MEDIUM** | `auto:smartest` is not documented as forbidden for measurement | **F2**  
`harness/providers.yaml` lines 263–270:  
The `auto:smartest` entry has no warning comment; only the `auto` entry at line 272 says “ne pas mesurer avec”. The claim asserts both are documented as forbidden.  
**Failure scenario**: A user selects `auto:smartest` for a measurement, believing it’s pinned because no prohibition is stated; in reality the router may fall back to a different model, invalidating the measurement.  
**Check**: Inspect the YAML block; `auto:smartest` lacks any “do not measure” comment.

---

### Claims that held

- **E1**: The key is read only when env var absent, failure warning names the missing credential, and the key value is never displayed (only length) nor written to a file.

---

### Verdict per claim

- **E1**: HOLDS — all stated properties are confirmed by the code.  
- **F1**: BROKEN — two model entries use a catalog‑peak context window (1 048 576) instead of a prudent floor.  
- **F2**: BROKEN — `auto:smartest` is not documented as forbidden for measurement, violating the claim that both `auto` and `auto:<profile>` are prohibited.