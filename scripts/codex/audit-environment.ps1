#requires -Version 7.0
[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Projects',
    [string]$UserRoot = $env:USERPROFILE,
    [switch]$ProbeHomelab,
    [switch]$SkipGitHubProbe,
    [switch]$AsObject,
    [switch]$Cloud
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$checks = [Collections.Generic.List[object]]::new()
$repos = [Collections.Generic.List[object]]::new()
$candidates = [Collections.Generic.List[string]]::new()
function Add-Check($Name, $Status, $Detail) {
    $checks.Add([pscustomobject]@{ Name=$Name; Status=$Status; Detail=$Detail })
}
function Test-Presence($Name, $Path, [switch]$File) {
    try {
        $kind = if ($File) { 'Leaf' } else { 'Container' }
        $present = Test-Path -LiteralPath $Path -PathType $kind -ErrorAction Stop
        Add-Check $Name $(if ($present) {'PASS'} else {'MISSING'}) $Path
    } catch { Add-Check $Name 'UNKNOWN' 'Metadata access unavailable' }
}
function Find-Files($Root, [switch]$Repositories) {
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($Root)
    $errors = 0
    while ($pending.Count) {
        $dir = $pending.Pop()
        try { $items = @(Get-ChildItem -LiteralPath $dir -Force -ErrorAction Stop) }
        catch { $errors++; continue }
        foreach ($item in $items) {
            # Never follow junctions/symlinks outside the explicitly selected root.
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $errors++; continue }
            if ($Repositories -and $item.Name -eq '.git') {
                $r = if ($item.PSIsContainer) { $item.Parent.FullName } else { $item.DirectoryName }
                if (Get-Command git -ErrorAction SilentlyContinue) {
                    $opts = @('--no-optional-locks','-c','core.fsmonitor=false','-C',$r)
                    # Do not weaken persistent or per-command ownership checks.
                    $state = @(& git @opts status --porcelain=v1 --untracked-files=normal 2>$null)
                    $ok = $LASTEXITCODE -eq 0
                    $branch = @(& git @opts symbolic-ref --short -q HEAD 2>$null)
                    $headId = @(& git @opts rev-parse HEAD 2>$null)
                    $repos.Add([pscustomobject]@{
                        Path=$r
                        Branch=($branch -join '')
                        HEAD=($headId -join '')
                        Status=$(if (!$ok) {'UNKNOWN'} elseif ($state.Count) {'WARN'} else {'PASS'})
                        State=$(if (!$ok) {'Unreadable or untrusted'} elseif ($state.Count) {'Dirty'} else {'Clean'})
                    })
                } else { $errors++ }
                continue
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName); continue }
            if (!$Repositories -and $item.Name -match '(?i)^id_(rsa|dsa|ecdsa|ed25519)(?!.*\.pub$)|\.(pem|ppk|p12|pfx|key)$|^\.env($|\.)|credential|secret|token|^auth\.json$') {
                $candidates.Add($item.FullName)
            }
        }
    }
    return $errors
}
$git = Get-Command git -ErrorAction SilentlyContinue
Add-Check 'Git' $(if ($git) {'PASS'} else {'MISSING'}) 'Executable availability'
if (!$SkipGitHubProbe -and (Get-Command gh -ErrorAction SilentlyContinue)) {
    # Suppress all output: auth status can contain credential identifiers.
    & gh auth status *> $null
    Add-Check 'GitHub' $(if ($LASTEXITCODE -eq 0) {'PASS'} else {'WARN'}) 'Local CLI authentication status only; connector access is independent'
} else {
    Add-Check 'GitHub' 'UNKNOWN' 'No safe local CLI check; connector status must be verified in its own access plane'
}
if ($Cloud) {
    Add-Check 'homelab policy' 'PASS' 'Forbidden by cloud profile; no local SSH/config/credential paths inspected or network probe attempted'
    Add-Check 'Cloud credential isolation' 'UNKNOWN' 'Requires platform/operator verification; not proven by this script'
} else {
    if ([string]::IsNullOrWhiteSpace($UserRoot)) { throw 'UserRoot is required for a local audit' }
    Test-Presence 'Codex config' (Join-Path $UserRoot '.codex/config.toml') -File
    Test-Presence 'Global AGENTS' (Join-Path $UserRoot '.codex/AGENTS.md') -File
    Test-Presence 'Project root' $ProjectRoot
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    # CLI startup can write aliases/state. Read executable metadata instead.
    $version = if ($codex -and $codex.Source) { (Get-Item -LiteralPath $codex.Source).VersionInfo.ProductVersion } else { $null }
    Add-Check 'Codex version/surface' $(if ($version) {'PASS'} else {'UNKNOWN'}) $(if ($version) {"Executable version: $version; surface not inferred"} else {'Version/surface unavailable from read-only metadata; no CLI startup'})
    $sshConfig = Join-Path $UserRoot '.ssh/config'
    $sshSafe = $false
    $aliasPresent = $false
    try {
        if (Test-Path -LiteralPath $sshConfig -PathType Leaf) {
            $lines = @(Get-Content -LiteralPath $sshConfig)
            $aliasPresent = @($lines | Where-Object { $_ -match '^\s*Host\s+([^#]+)' -and (($Matches[1] -split '\s+') -contains 'homelab') }).Count -gt 0
            # Includes and Match exec could invoke external code during ssh -G.
            $complex = @($lines | Where-Object { $_ -match '^\s*(Include\s|Match\s)' }).Count -gt 0
            $sshSafe = !$complex
            Add-Check 'homelab alias' $(if ($complex) {'UNKNOWN'} elseif ($aliasPresent) {'PASS'} else {'MISSING'}) $(if ($complex) {'Include/Match requires separate review; SSH evaluation skipped'} else {'Explicit alias metadata only'})
        } else { Add-Check 'homelab alias' 'MISSING' 'SSH config absent' }
    } catch { Add-Check 'homelab alias' 'UNKNOWN' 'SSH config metadata unavailable' }
    if ($aliasPresent -and $sshSafe -and (Get-Command ssh -ErrorAction SilentlyContinue)) {
        # Ignore system config and disable local/proxy commands. Print identity paths only.
        $resolved = @(& ssh -G -F $sshConfig -o PermitLocalCommand=no -o ProxyCommand=none -o ProxyJump=none homelab 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $identities = @($resolved | Where-Object { $_ -match '^identityfile ' } | ForEach-Object { $_ -replace '^identityfile ', '' })
            Add-Check 'SSH identity paths' 'PASS' ($identities -join '; ')
            if ($ProbeHomelab) {
                & ssh -F $sshConfig -o BatchMode=yes -o ConnectTimeout=10 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ControlMaster=no -o ControlPath=none -o PermitLocalCommand=no -o ProxyCommand=none -o ProxyJump=none -o KnownHostsCommand=none -o RemoteCommand=none -o RequestTTY=no -o ForwardAgent=no -o ClearAllForwardings=yes homelab true *> $null
                Add-Check 'homelab BatchMode' $(if ($LASTEXITCODE -eq 0) {'PASS'} else {'WARN'}) 'Noninteractive direct connection; no host-key writes or forwarding'
            } else { Add-Check 'homelab BatchMode' 'UNKNOWN' 'Not requested; use -ProbeHomelab' }
        } else { Add-Check 'homelab BatchMode' 'UNKNOWN' 'SSH resolution unavailable' }
    } else { Add-Check 'homelab BatchMode' 'UNKNOWN' 'Alias/config/executable unavailable or requires review' }
    if (Test-Path -LiteralPath $ProjectRoot -PathType Container) {
        $errors = Find-Files $ProjectRoot -Repositories
        Add-Check 'Repository inventory' $(if ($errors -or @($repos | Where-Object Status -eq 'UNKNOWN').Count) {'WARN'} else {'PASS'}) "Repositories: $($repos.Count); inaccessible/skipped entries: $errors"
    }
    $scratch = Join-Path $UserRoot 'Documents/Codex'
    if (Test-Path -LiteralPath $scratch -PathType Container) {
        $errors = Find-Files $scratch
        Add-Check 'Duplicate credential staging' $(if ($candidates.Count -or $errors) {'WARN'} else {'PASS'}) "Filename candidates: $($candidates.Count); inaccessible/skipped entries: $errors. Names are not proof of secrets or duplicates."
    } else { Add-Check 'Duplicate credential staging' 'UNKNOWN' 'Scratch root unavailable' }
}
$result = [pscustomobject]@{
    Checks=@($checks.ToArray())
    Repositories=@($repos.ToArray())
    CredentialFilenameCandidates=@($candidates.ToArray())
}
if ($AsObject) { return $result }
$result.Checks | Format-Table Name,Status,Detail -Wrap
if ($result.Repositories.Count) { $result.Repositories | Format-Table Path,Branch,Status,State -Wrap }
if ($result.CredentialFilenameCandidates.Count) {
    'Credential-like filenames (contents never read):'
    $result.CredentialFilenameCandidates
}
