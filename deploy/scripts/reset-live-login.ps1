# Reset login passwords on Neon (live) from Windows.
# Usage:
#   .\deploy\scripts\reset-live-login.ps1 -DatabaseUrl "postgresql://..." -Password "Nlupc2026!"

param(
    [Parameter(Mandatory = $true)][string]$DatabaseUrl,
    [string]$Password = "Nlupc2026!",
    [string]$Python = ".\venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue

if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host "Resetting live login passwords..."
& $Python ".\scripts\reset_live_login.py" --url $DatabaseUrl --password $Password
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Done. Open https://lumc-dodoma.onrender.com/login/"
