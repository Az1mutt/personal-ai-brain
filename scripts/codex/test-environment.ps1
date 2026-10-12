#requires -Version 7.0
[CmdletBinding()]
param([Parameter(Mandatory)][string]$FixtureRoot)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $FixtureRoot) { throw 'Fixture destination already exists' }
$null = New-Item -ItemType Directory -Path $FixtureRoot
$user = Join-Path $FixtureRoot 'user'
$projects = Join-Path $FixtureRoot 'projects'
foreach ($dir in @('.codex','.ssh','Documents/Codex')) {
    $null = New-Item -ItemType Directory -Path (Join-Path $user $dir) -Force
}
$null = New-Item -ItemType Directory -Path $projects
$null = New-Item -ItemType Directory -Path (Join-Path $projects 'fixture-repo/.git') -Force
Set-Content -LiteralPath (Join-Path $user '.codex/config.toml') -Value '# synthetic fixture'
Set-Content -LiteralPath (Join-Path $user '.codex/AGENTS.md') -Value '# synthetic fixture'
Set-Content -LiteralPath (Join-Path $user '.ssh/config') -Value "Host homelab"
Set-Content -LiteralPath (Join-Path $user 'Documents/Codex/.env') -Value 'SYNTHETIC_VALUE=must-not-appear-in-report'
$global:CodexAuditTestProbeCount = 0
function ssh {
    if ($args -contains '-G') { 'identityfile ~/.ssh/synthetic-fixture' }
    else { $global:CodexAuditTestProbeCount++ }
    $global:LASTEXITCODE = 0
}
function gh { $global:LASTEXITCODE = 0 }
function git { $global:LASTEXITCODE = 0 }
function Assert($Condition, $Message) { if (!$Condition) { throw $Message } }
$auditScript = Join-Path $PSScriptRoot 'audit-environment.ps1'
$verifyScript = Join-Path $PSScriptRoot 'verify-environment.ps1'
$report = & $auditScript -UserRoot $user -ProjectRoot $projects -AsObject
Assert ($global:CodexAuditTestProbeCount -eq 0) 'Default audit must not probe SSH'
Assert ($report.CredentialFilenameCandidates.Count -eq 1) 'Expected filename-only candidate'
Assert (($report | ConvertTo-Json -Depth 8) -notmatch 'must-not-appear-in-report') 'Credential fixture contents leaked'
$manifest = Get-Content (Join-Path $PSScriptRoot '../../config/codex/environment-manifest.yaml') -Raw | ConvertFrom-Json -AsHashtable
$manifest.profiles['local-homelab-admin'].project_root = $projects
$manifestPath = Join-Path $FixtureRoot 'manifest.yaml'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath
$verified = & $verifyScript local-homelab-admin -ManifestPath $manifestPath -UserRoot $user -AsObject
Assert ($verified.Overall -eq 'PASS_WITH_WARNINGS') 'Expected successful profile with candidate warning'
Assert ($global:CodexAuditTestProbeCount -eq 1) 'Local verification must probe once'
$skipped = & $verifyScript local-homelab-admin -ManifestPath $manifestPath -UserRoot $user -SkipHomelabProbe -AsObject
Assert ($skipped.Overall -eq 'INCOMPLETE') 'Skipped required probe must not pass'
$cloudUnknown = & $verifyScript cloud-github-dev -ManifestPath $manifestPath -SkipGitHubProbe -AsObject
Assert ($cloudUnknown.Overall -eq 'INCOMPLETE') 'Unknown required GitHub capability must not pass'
Set-Content -LiteralPath (Join-Path $user '.ssh/config') -Value "Include other-config"
$complex = & $auditScript -UserRoot $user -ProjectRoot $projects -ProbeHomelab -AsObject
Assert ($global:CodexAuditTestProbeCount -eq 1) 'Complex SSH config must not be evaluated'
Assert (@($complex.Checks | Where-Object { $_.Name -eq 'homelab alias' -and $_.Status -eq 'UNKNOWN' }).Count -eq 1) 'Include must be UNKNOWN'
$cloud = & $verifyScript cloud-github-dev -ManifestPath $manifestPath -UserRoot 'nonexistent-path' -AsObject
Assert ($global:CodexAuditTestProbeCount -eq 1) 'Cloud must not probe SSH'
Assert ($cloud.Audit.CredentialFilenameCandidates.Count -eq 0) 'Cloud must not scan local credentials'
Assert ($cloud.Overall -eq 'PASS_WITH_WARNINGS') 'Cloud isolation must remain an explicit warning'
$unknownRejected = $false
try { & $verifyScript not-a-profile -ManifestPath $manifestPath -AsObject }
catch { $unknownRejected = $true }
Assert $unknownRejected 'Unknown profile must be rejected'
'PASS: offline profile, redaction, SSH opt-in, complex-config and cloud-boundary checks'
