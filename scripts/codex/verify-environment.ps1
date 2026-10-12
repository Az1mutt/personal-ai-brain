#requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Position=0,Mandatory)][string]$Profile,
    [string]$ManifestPath = (Join-Path $PSScriptRoot '../../config/codex/environment-manifest.yaml'),
    [string]$UserRoot = $env:USERPROFILE,
    [switch]$SkipHomelabProbe,
    [switch]$SkipGitHubProbe,
    [switch]$AsObject
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Manifest uses the JSON-compatible subset of YAML 1.2; no module installation.
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json -AsHashtable
if ($manifest.schema_version -ne 1 -or !$manifest.profiles.ContainsKey($Profile)) {
    throw 'Unsupported manifest version or unknown profile'
}
$selected = $manifest.profiles[$Profile]
$cloud = $selected.surface -eq 'codex-cloud'
if (!$cloud -and $selected.surface -ne 'codex-desktop/local') { throw 'Unsupported profile surface' }
if ($cloud -and $selected.capabilities.homelab_ssh -ne 'forbidden') { throw 'Cloud SSH must remain forbidden' }
$params = @{ AsObject=$true; Cloud=$cloud; SkipGitHubProbe=$SkipGitHubProbe }
if (!$cloud) {
    $params.ProjectRoot = $selected.project_root
    $params.UserRoot = $UserRoot
    $params.ProbeHomelab = !$SkipHomelabProbe
}
$audit = & (Join-Path $PSScriptRoot 'audit-environment.ps1') @params
$requiredFailures = @($selected.required_checks | Where-Object {
    $name = $_
    $match = @($audit.Checks | Where-Object Name -eq $name)
    $match.Count -ne 1 -or $match[0].Status -ne 'PASS'
})
$warnings = @($audit.Checks | Where-Object Status -ne 'PASS').Count -gt 0 -or @($audit.Repositories | Where-Object Status -ne 'PASS').Count -gt 0
$overall = if ($requiredFailures.Count) {'INCOMPLETE'} elseif ($warnings) {'PASS_WITH_WARNINGS'} else {'PASS'}
$result = [pscustomobject]@{ Profile=$Profile; Overall=$overall; RequiredChecksNotPassed=$requiredFailures; Audit=$audit }
if ($AsObject) { return $result }
"Profile: $Profile"
foreach ($check in $audit.Checks) { "$($check.Name): $($check.Status)" }
"Overall: $overall"
if ($requiredFailures.Count) { "Required checks not passed: $($requiredFailures -join ', ')"; exit 1 }
