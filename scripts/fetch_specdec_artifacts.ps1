# fetch_specdec_artifacts.ps1 -- download + verify the pinned spec-dec bench
# artifacts (final 2026-08-19 artifact set). Single source of truth.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1 -SkipDraft
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1 -SkipTarget -SkipDraft -SkipBinary   # le mmproj seul
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1 -SkipBinary -SkipTarget
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1 -Dflash2BinaryTag b10489
#
# Switches:
#   -SkipTarget         skip the Qwen3.8-27B main model (HF, unsloth).
#   -SkipDraft          skip the Qwen3.8-27B DFlash2 draft (HF, incoai).
#   -SkipMmproj         skip the Qwen3.8-27B vision projector (HF, unsloth).
#                       Without mmproj-F16.gguf the server loads TEXT-ONLY:
#                       llama.cpp keeps the vision tower in a SEPARATE file, so
#                       a Qwen3.8-27B GGUF alone CANNOT read an image.
#   -SkipBinary         skip ALL llama.cpp CUDA binaries (b10488 and any
#                       -Dflash2BinaryTag binaries) from GitHub.
#   -Dflash2BinaryTag   optional release tag (e.g. "b104XX") of a post-merge
#                       llama.cpp release that includes DFlash2 (PR #27342).
#                       When given, that release's win-cuda-12.4-x64 zip is also
#                       downloaded, digest-verified, extracted to
#                       C:\Users\test\tools\llama-cpp\llama-cuda-<tag>\.
#
# Behavior:
#   * Pre-check: >= 25 GB free on C: or exit 4.
#   * HF files: expected sha256 is fetched LIVE from the huggingface tree API
#     (each entry's lfs.oid) at download time -- never hardcoded. An existing
#     local file whose size AND hash already match is skipped (idempotent).
#     Downloads use `curl.exe -L -C - --fail --retry 2 -o` (resumable). On a
#     hash mismatch we retry once (delete partial, full re-download); if it
#     still mismatches we STOP that artifact (delete partial), keep going with
#     the remaining ones, and exit 5 at the end.
#   * HF token: loaded from .env via the Import-DotEnv pattern (names-only
#     logging); passed to curl via Authorization: Bearer -- the value is never
#     printed. Repos are ungated so anonymous download also works (the header
#     is only added when a token exists).
#   * GitHub zip: the release API JSON is fetched for the authoritative asset
#     URL and its `.digest` (sha256). The zip is downloaded with curl -L -C -,
#     the digest verified, Expand-Archive to llama-cuda-<tag>\, then the
#     extracted llama-server.exe is run once with `--version` (CPU-only, safe)
#     and that output printed.
#
# Exit codes:
#   0   everything processed; every attempted artifact verified or skipped.
#   4   refused: C: has < 25 GB free before downloading.
#   5   one or more artifacts could not be verified after one retry.
[CmdletBinding()]
param(
    [switch]$SkipTarget,
    [switch]$SkipDraft,
    [switch]$SkipMmproj,
    [switch]$SkipBinary,
    [string]$Dflash2BinaryTag
)

$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Continue"

# ----------------------------------------------------------------------------
# free-space pre-check
# ----------------------------------------------------------------------------
$drive = Get-PSDrive -Name C
$freeBytes = [double]$drive.Free
$needBytes = 25 * 1GB
if ($freeBytes -lt $needBytes) {
    Write-Host ("REFUS (exit 4): only {0:n1} GB free on C:; need >= 25 GB for ~18.4 GB + extracts." -f ($freeBytes / 1GB))
    exit 4
}
Write-Host ("Free space OK: {0:n1} GB free on C:" -f ($freeBytes / 1GB))

# ----------------------------------------------------------------------------
# Import-DotEnv (names-only logging) -- copy of the repo pattern.
# ----------------------------------------------------------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
function Import-DotEnv([string]$path, [string[]]$keys) {
    if (-not (Test-Path $path)) { Write-Host "WARN: .env not found at $path"; return $false }
    $loaded = @()
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $k = $matches[1]; $v = $matches[2].Trim()
            if ($v.StartsWith('"') -and $v.EndsWith('"')) { $v = $v.Substring(1, $v.Length - 2) }
            elseif ($v.StartsWith("'") -and $v.EndsWith("'")) { $v = $v.Substring(1, $v.Length - 2) }
            if ($keys -contains $k) {
                Set-Item -Path ("env:{0}" -f $k) -Value $v
                $loaded += $k
            }
        }
    }
    Write-Host ("loaded from .env (names only): {0}" -f ($loaded -join ", "))
    return $loaded.Count -gt 0
}

$HfToken = $null
$envPath = Join-Path $RepoRoot ".env"
if (Import-DotEnv $envPath @("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")) {
    foreach ($k in @("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")) {
        $v = Get-Item -Path ("env:{0}" -f $k) -ErrorAction SilentlyContinue
        if ($v -and $v.Value) { $HfToken = $v.Value; break }
    }
    if ($HfToken) { Write-Host "Using an HF token for downloads (value never printed)." }
}

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
function Get-ExpectedHfMeta([string]$repo, [string]$filename) {
    # Live fetch of the tree API; expected sha256 comes from lfs.oid.
    $url = "https://huggingface.co/api/models/$repo/tree/main"
    try {
        $json = Invoke-RestMethod -Uri $url -TimeoutSec 60
        foreach ($e in $json) {
            if ($e.path -eq $filename) {
                return @{
                    Found = $true
                    Size  = [long]$e.size
                    Oid   = ($e.lfs.oid -replace '[^0-9a-fA-F]', '').ToLower()
                }
            }
        }
    } catch {
        Write-Host "  ERROR: tree API failed for $repo/$filename : $_"
    }
    return @{ Found = $false }
}

function Get-GithubZipMeta([string]$tag) {
    # Fetch the release API JSON; authoritative asset URL + .digest (sha256).
    $url = "https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/$tag"
    $assetName = "llama-$tag-bin-win-cuda-12.4-x64.zip"
    try {
        $rel = Invoke-RestMethod -Uri $url -TimeoutSec 60 -Headers @{ "User-Agent" = "specdec-fetch" }
        foreach ($a in $rel.assets) {
            if ($a.name -eq $assetName) {
                $digest = ""
                if ($a.digest) { $digest = ($a.digest -replace '^sha256:', '').ToLower().Trim() }
                return @{
                    Found  = $true
                    Url    = $a.browser_download_url
                    Digest = $digest
                    Size   = [long]$a.size
                }
            }
        }
    } catch {
        Write-Host "  ERROR: GitHub release API failed for $tag : $_"
    }
    return @{ Found = $false }
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -Algorithm SHA256 -Path $path).Hash.ToLower()
}

function Remove-Partial([string]$path) {
    if (Test-Path $path) { try { Remove-Item -LiteralPath $path -Force -ErrorAction Stop } catch {} }
}

function Invoke-Curl([string]$url, [string]$outPath) {
    $cargs = @("-L", "-C", "-", "--fail", "--retry", "2", "--output", $outPath)
    # F7: attach the HF bearer header ONLY when talking to huggingface.co --
    # never to GitHub / objects.githubusercontent.com. The header stays on the
    # curl command line (an inline -H), so the token is visible to process-
    # listing tools (Task Manager / Win32_Process). Moving it to `-H @file`
    # would hide it from argv, but that syntax is not guaranteed on older curl
    # builds; the host-gate is the hard security boundary here and the inline
    # -H is retained with this acknowledged argv-visibility caveat.
    $isHf = $url -match '(?i)^https://huggingface\.co/'
    if ($isHf -and $script:HfToken) {
        $cargs += @("-H", "Authorization: Bearer $script:HfToken")
    }
    $cargs += $url
    & curl.exe @cargs
    return $LASTEXITCODE
}

# ----------------------------------------------------------------------------
# artifact table (2026-08-19 pinned set)
# ----------------------------------------------------------------------------
$targetDir = "C:\Users\test\models\qwen38-27b"
$draftDir  = "C:\Users\test\models\dflash2-qwen38-27b"
$toolsDir  = "C:\Users\test\tools\llama-cpp"

$artifacts = @()

$artifacts += @{
    Name = "target model (Qwen3.8-27B Q4_K_M, unsloth)"
    Kind = "hf"; Repo = "unsloth/Qwen3.8-27B-GGUF"; File = "Qwen3.8-27B-Q4_K_M.gguf"
    Dir = $targetDir; Skip = $SkipTarget
}
$artifacts += @{
    # The vision half of the SAME unsloth repo the target model came from. The
    # weights GGUF carries the language model only; mtmd loads the projector
    # from this second file (b10488 exposes -mm/--mmproj, verified 2026-08-21).
    # F16 over BF16: F16 is the projector dtype every CUDA build handles.
    Name = "vision projector (Qwen3.8-27B mmproj F16, unsloth)"
    Kind = "hf"; Repo = "unsloth/Qwen3.8-27B-GGUF"; File = "mmproj-F16.gguf"
    Dir = $targetDir; Skip = $SkipMmproj
}
$artifacts += @{
    Name = "dflash2 draft (Qwen3.8-27B DFlash2 Q4_K_M, incoai)"
    Kind = "hf"; Repo = "incoai/Qwen3.8-27B-DFlash2-GGUF"; File = "Qwen3.8-27B-DFlash2-Q4_K_M.gguf"
    Dir = $draftDir; Skip = $SkipDraft
}

# GitHub binaries: b10488 always (unless -SkipBinary); plus any -Dflash2BinaryTag.
if (-not $SkipBinary) {
    $artifacts += @{
        Name = "llama.cpp CUDA bin (b10488)"
        Kind = "github"; Tag = "b10488"; Dest = Join-Path $toolsDir "llama-cuda-b10488"; Skip = $false
    }
    if ($Dflash2BinaryTag) {
        $artifacts += @{
            Name = "llama.cpp CUDA bin ($Dflash2BinaryTag, DFlash2/PR #27342)"
            Kind = "github"; Tag = $Dflash2BinaryTag; Dest = Join-Path $toolsDir "llama-cuda-$Dflash2BinaryTag"; Skip = $false
        }
    }
} else {
    Write-Host ""
    Write-Host "SKIP all GitHub CUDA binary downloads (-SkipBinary)."
}

# ----------------------------------------------------------------------------
# process loop
# ----------------------------------------------------------------------------
$results = @()
$failed = $false

foreach ($a in $artifacts) {
    if ($a.Skip) { Write-Host ""; Write-Host ("SKIP {0}" -f $a.Name); continue }
    Write-Host ""
    Write-Host ("===== {0} =====" -f $a.Name)

    try {
        $row = @{ Artifact = $a.Name; Path = ""; Size = 0; Verified = "no" }

        if ($a.Kind -eq "hf") {
            New-Item -ItemType Directory -Path $a.Dir -Force | Out-Null
            $local = Join-Path $a.Dir $a.File
            $row.Path = $local

            $meta = Get-ExpectedHfMeta $a.Repo $a.File
            if (-not $meta.Found) {
                Write-Host "  FATAL: file $($a.File) not in tree API for $($a.Repo)."
                $failed = $true
                $results += $row
                continue
            }
            $expected = $meta.Oid
            $expectedSize = $meta.Size
            Write-Host ("  expected size={0}  sha256={1}..." -f $expectedSize, $expected.Substring(0, 16))

            # Skip if a matching file already exists (size + hash) -> idempotent.
            if (Test-Path $local) {
                $cur = (Get-Item -LiteralPath $local).Length
                if ($cur -eq $expectedSize) {
                    $h = Get-Sha256 $local
                    if ($h -eq $expected) {
                        Write-Host "  SKIP: already present with matching size + hash."
                        $row.Size = $cur; $row.Verified = "yes"
                        $results += $row
                        continue
                    }
                    Write-Host "  existing file size matches but hash differs -> full re-download (resume will not help)."
                } else {
                    Write-Host "  existing partial size $cur != $expectedSize ($expectedSize) -> curl -C - resumes from $cur (F6: partial NOT deleted across invocations)."
                }
                # F6: do NOT delete a size-mismatched partial here. `curl -C -`
                # below resumes from the current size on this and later runs, so
                # a cross-invocation partial is recoverable. A wrong-hash file is
                # only deleted when curl finished a complete download with a
                # confirmed hash mismatch (see the retry branch below).
            }

            # Attempt 1: resumable curl download.
            Write-Host "  downloading ..."
            $rc = Invoke-Curl "https://huggingface.co/$($a.Repo)/resolve/main/$($a.File)" $local
            $h1 = if (Test-Path $local) { Get-Sha256 $local } else { "" }

            if ($rc -ne 0 -or $h1 -ne $expected) {
                Write-Host "  attempt 1 failed (curl exit=$rc) or hash mismatch; retry once (resume)."
                if ($rc -eq 0 -and $h1) { Remove-Partial $local }  # wrong bytes -> clean restart
                $rc2 = Invoke-Curl "https://huggingface.co/$($a.Repo)/resolve/main/$($a.File)" $local
                $h2 = if (Test-Path $local) { Get-Sha256 $local } else { "" }
                if ($rc2 -ne 0 -or $h2 -ne $expected) {
                    Write-Host ("  FATAL: {0} could not be verified after one retry. Deleting partial." -f $a.Name)
                    Remove-Partial $local
                    $failed = $true
                    $results += $row
                    continue
                }
            }
            $sz = (Get-Item -LiteralPath $local).Length
            $row.Size = $sz; $row.Verified = "yes"
            Write-Host ("  OK: {0} verified (size={1}, sha256 ok)" -f $a.File, $sz)
            $results += $row

        } else {
            # GitHub zip artifact.
            New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
            New-Item -ItemType Directory -Path $a.Dest -Force | Out-Null
            $zipFile = Join-Path $toolsDir "llama-$($a.Tag)-bin-win-cuda-12.4-x64.zip"
            $row.Path = $zipFile

            $g = Get-GithubZipMeta $a.Tag
            if (-not $g.Found) {
                Write-Host "  FATAL: asset llama-$($a.Tag)-bin-win-cuda-12.4-x64.zip not found in GitHub release $($a.Tag)."
                $failed = $true
                $results += $row
                continue
            }
            $expectedDigest = [string]$g.Digest
            Write-Host ("  expected size={0}  sha256={1}..." -f $g.Size, $(if ($expectedDigest) { $expectedDigest.Substring(0, [Math]::Min(16, $expectedDigest.Length)) } else { "(no digest in API)" }))

            # Idempotent: skip a fully-verified zip.
            if (Test-Path $zipFile) {
                $cur = (Get-Item -LiteralPath $zipFile).Length
                if ($expectedDigest -and $cur -eq $g.Size) {
                    $h = Get-Sha256 $zipFile
                    if ($h -eq $expectedDigest) {
                        Write-Host "  SKIP: zip already present with matching size + digest."
                        $row.Size = $cur; $row.Verified = "yes"
                        # still (re)print the extracted --version below
                        $results += $row
                    } else { $row.Verified = "no" }
                } else { $row.Verified = "no" }
            } else { $row.Verified = "no" }

            if ($row.Verified -ne "yes") {
                Write-Host "  downloading zip ..."
                $rc = Invoke-Curl $g.Url $zipFile
                $h1 = if (Test-Path $zipFile) { Get-Sha256 $zipFile } else { "" }
                $ok = ($rc -eq 0 -and $h1 -eq $expectedDigest)
                if (-not $ok) {
                    Write-Host "  attempt 1 failed (curl exit=$rc) or digest mismatch; retry once."
                    if ($rc -eq 0 -and $h1) { Remove-Partial $zipFile }
                    $rc2 = Invoke-Curl $g.Url $zipFile
                    $h2 = if (Test-Path $zipFile) { Get-Sha256 $zipFile } else { "" }
                    if ($rc2 -ne 0 -or $h2 -ne $expectedDigest) {
                        Write-Host "  FATAL: zip $($a.Tag) failed digest verification after one retry. Deleting partial."
                        Remove-Partial $zipFile
                        $failed = $true
                        $results += $row
                        continue
                    }
                }
                $row.Size = (Get-Item -LiteralPath $zipFile).Length
                $row.Verified = "yes"
            }

            Write-Host "  extracting to $($a.Dest) ..."
            Expand-Archive -LiteralPath $zipFile -DestinationPath $a.Dest -Force
            $exe = Get-ChildItem -Path $a.Dest -Recurse -Filter "llama-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($exe) {
                $row.Path = $exe.FullName
                Write-Host ("  binary: {0}" -f $exe.FullName)
                Write-Host "  --version (CPU-only):"
                $verOut = & $exe.FullName --version 2>&1
                foreach ($v in $verOut) { Write-Host ("    {0}" -f $v) }
                $row.Verified = "yes"
            } else {
                Write-Host "  WARN: llama-server.exe not found under $($a.Dest)."
                $failed = $true
            }
            $results += $row
        }
    } catch {
        Write-Host ("  ERROR unexpected: {0}" -f $_)
        $failed = $true
        $results += $row
    }
}

# ----------------------------------------------------------------------------
# final table
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "===== ARTIFACT SUMMARY ====="
Write-Host ("{0,-46} {1,-66} {2,14}  {3}" -f "artifact", "path", "size", "verified")
foreach ($r in $results) {
    Write-Host ("{0,-46} {1,-66} {2,14}  {3}" -f $r.Artifact, $r.Path, $r.Size, $r.Verified)
}

if ($failed) {
    Write-Host ""
    Write-Host "One or more artifacts are missing/not-verified. Re-run after fixing (resumable)."
    exit 5
}
Write-Host ""
Write-Host "All requested artifacts present and verified."
exit 0
