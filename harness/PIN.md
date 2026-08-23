# dsh — the pin (Phase 0, step "dsh from source, version pinned")

| what | value |
|---|---|
| package | `@deepseek-ai/dsh` **0.1.1-rc.2** (npm registry tarball) |
| tarball integrity | `sha512-UP1UIh6q3Gme/yXRn/QL2P8IsVlv8Shpg22TRJIZPsCRWLm4CBiA1MUvXmJAfsOEETBMLAl+xWPtFw6ICsN3wg==` |
| upstream tag | `dsh-v0.1.1-rc.2` on `github.com/deepseek-ai/deepseek-harness` |
| upstream commit | `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e` (the tag's commit, read 2026-08-23 via `gh api repos/deepseek-ai/deepseek-harness/tags`) |
| scope pinned | 188 `@deepseek-ai/dsh*` packages, all forced to 0.1.1-rc.2 by `overrides` |
| lock | [`runtime/package-lock.json`](runtime/package-lock.json) — 511 resolved packages, every one with a registry URL and an sha512 |
| live tree | `~/.dsh/runtime/dsh-0.1.1-rc.2/` (outside the repo; rebuilt from this lock by `.\scripts\dsh.ps1 -InstallRuntime`) |

## What "pinned" means here, and what it does not

- `npm ci` in a copy of [`runtime/`](runtime/) rebuilds the exact tree: same 511 packages, same
  hashes. `-InstallRuntime` now does precisely that when the lock is present (and says so); it only
  falls back to resolving from caret ranges when the lock is missing, and announces it.
- `python harness/pin_check.py` compares the tree that runs with the tree the repo versions: lock
  byte-identical, main package integrity equal to this file, every `dsh*` package installed at the
  pinned version, `lib/bin.js` present. Exit 1 names each gap.
- **Not built from source.** The spec says "dsh from source"; what is installed is the registry
  tarball of that version. The tarball ↔ commit link is the upstream *tag name* (`dsh-v0.1.1-rc.2`),
  read from GitHub, not a content comparison of the tarball against the tag's tree. The upstream is a
  pnpm monorepo (`apps/cli` + ~190 packages); `npm install github:deepseek-ai/deepseek-harness#b150a55`
  would install the monorepo root, not the CLI, so the `github:owner/repo#sha` form of the Rules
  section cannot express this pin for dsh itself. It still applies to third-party plugins, of which
  there are none yet (the two local plugins live in this repo).
- The bump procedure of the README (apply in `staging` → replay suite → red-team the diff →
  `--dump-config` diff against last known-good → promote) starts by changing `runtime/package.json`
  and `-DshVersion`, re-running `-InstallRuntime`, then `python harness/lean_check.py` (the
  `--dump-config` drift check of the Lean layer) and `pin_check.py`.

Measured 2026-08-23: `pin_check.py` → OK (188 packages, lock identical, bin.js present).
