<#
Prepare the CURRENT PowerShell tool-call for the local Post/VVF workflow — put every tool an agent
needs on PATH (and, opt-in, load the session secrets as env vars).

IMPORTANT — env does NOT persist across tool calls. Each shell tool call is a FRESH process with a
frozen inherited environment; PATH/$env changes made here (and even persistent User-PATH edits) are
NOT seen by the next tool call or by spawned agents. So there is NO "run once per session". Reach for
this ONLY when you want bare tool names (`bash`/`tsc`/`mkdocs`/`python`) WITHIN a single multi-command
call: dot-source it at the START of that same call. For the memory scripts you normally DON'T need it —
`git`/`jq`/`pnpm`/`dotnet` are already on the inherited PATH, and the robust way to run a memory tool is
by full path (bash: `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/X.sh`; python:
`.venv/Scripts/python.exe .memory/tools/scripts/X.py`). See 03 "Running memory tools (env doesn't persist)".

Usage from the repo root (affects THIS call only):
  . .\.memory\tools\scripts\session_env.ps1                 # PATH only
  . .\.memory\tools\scripts\session_env.ps1 -WithSecrets    # PATH + load PATs/user into $env (values hidden)

PATH additions (only those that exist are added): Git bash (bash/grep/jq/sed/awk), the repo .venv
(python/mkdocs), the frontend node_modules\.bin (tsc/jest/next/eslint), the memory scripts dir,
Node (nodejs + npm global = pnpm), and dotnet. `wsl.exe` already lives in System32 (on PATH);
Docker runs INSIDE WSL (Ubuntu), not on the Windows host — see 03 "WSL + Docker integration tests".

-WithSecrets loads (never prints) into the current process env only:
  DEVOPS_PAT  (Azure REST/pipelines, from PATS\AZURE-PAT.json)
  NUGET_POSTAT_USERNAME = jonas.hauser@accenture.com
  NUGET_POSTAT_CLEAR_TEXT_PASSWORD  (from PATS\NUGET-PAT.json)  +  PAT (alias, same value)
It changes only the current process; it never persists PATH and never echoes a token.
#>
param([switch]$WithSecrets)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir '..\..\..')
$memoryRoot = Join-Path $repoRoot '.memory'
$frontendRoot = Join-Path $repoRoot 'csharp\src\frontend'

$candidatePaths = @(
  'C:\Program Files\Git\bin',
  'C:\Program Files\Git\usr\bin',
  'C:\Program Files\dotnet',
  'C:\Program Files\nodejs',
  (Join-Path $env:APPDATA 'npm'),
  (Join-Path $repoRoot '.venv\Scripts'),
  (Join-Path $frontendRoot 'node_modules\.bin'),
  (Join-Path $memoryRoot 'tools\scripts')
)

$existing = $candidatePaths | Where-Object { Test-Path $_ } | ForEach-Object {
  (Resolve-Path $_).Path.TrimEnd('\')
}
$current = $env:Path -split ';' | Where-Object { $_ -ne '' } | ForEach-Object { $_.TrimEnd('\') }
$toPrepend = $existing | Where-Object { $current -notcontains $_ }
if ($toPrepend.Count -gt 0) { $env:Path = (($toPrepend + $current) -join ';') }

$env:PYTHONUTF8 = '1'

Write-Host 'Session PATH prepared for Post/VVF tooling.'
if ($toPrepend.Count -gt 0) { Write-Host 'Added:'; $toPrepend | ForEach-Object { Write-Host "  $_" } }
else { Write-Host 'No PATH additions needed.' }

if ($WithSecrets) {
  # Load secrets by PATH into env WITHOUT echoing any value (core rule: PATs are reference-only).
  $azPat = Join-Path $memoryRoot 'PATS\AZURE-PAT.json'
  $nugetPat = Join-Path $memoryRoot 'PATS\NUGET-PAT.json'
  if (Test-Path $azPat)    { $env:DEVOPS_PAT = (Get-Content -Raw $azPat | ConvertFrom-Json).pat }
  $env:NUGET_POSTAT_USERNAME = 'jonas.hauser@accenture.com'
  if (Test-Path $nugetPat) { $env:NUGET_POSTAT_CLEAR_TEXT_PASSWORD = (Get-Content -Raw $nugetPat | ConvertFrom-Json).pat }
  $env:PAT = $env:NUGET_POSTAT_CLEAR_TEXT_PASSWORD
  # The frontend .npmrc authenticates the postat npm feed with NPM_POSTAT_* (different names than the
  # NuGet ones) — set them too so `pnpm` doesn't warn "Failed to replace env in config: ${NPM_POSTAT_USERNAME}".
  $env:NPM_POSTAT_USERNAME = $env:NUGET_POSTAT_USERNAME
  $env:NPM_POSTAT_CLEAR_TEXT_PASSWORD = $env:NUGET_POSTAT_CLEAR_TEXT_PASSWORD
  Write-Host 'Loaded session secrets into $env:DEVOPS_PAT / NUGET_POSTAT_* / NPM_POSTAT_* / PAT (values hidden).'
} else {
  Write-Host 'PAT files remain reference-only under .memory\PATS; run with -WithSecrets to load them into env.'
}
