# Dump LUMC → restore onto Render Postgres (from Windows PC).
# Usage:
#   .\deploy\scripts\restore-to-render.ps1 `
#     -GisUrl "postgresql://user:pass@host/tanzania_gis_db" `
#     -DetailedUrl "postgresql://user:pass@host/detailed_planning" `
#     -MainDump ".\deploy\db-dumps\tanzania_gis_db_XXXX.dump" `
#     -DetailDump ".\deploy\db-dumps\detailed_planning_XXXX.dump"
#
# Use the EXTERNAL Database URL from Render Dashboard (not Internal).

param(
    [Parameter(Mandatory = $true)][string]$GisUrl,
    [Parameter(Mandatory = $true)][string]$DetailedUrl,
    [Parameter(Mandatory = $true)][string]$MainDump,
    [Parameter(Mandatory = $true)][string]$DetailDump,
    [string]$PgRestore = "C:\Program Files\PostgreSQL\13\bin\pg_restore.exe",
    [string]$Psql = "C:\Program Files\PostgreSQL\13\bin\psql.exe"
)

$ErrorActionPreference = "Stop"

function Enable-Postgis([string]$Url) {
    Write-Host "CREATE EXTENSION postgis on $Url ..."
    & $Psql $Url -c "CREATE EXTENSION IF NOT EXISTS postgis;"
}

function Restore-Dump([string]$Url, [string]$Dump) {
    if (-not (Test-Path $Dump)) { throw "Dump not found: $Dump" }
    Write-Host "Restoring $Dump → $Url ..."
    & $PgRestore --clean --if-exists --no-owner --no-acl -d $Url $Dump
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pg_restore exited $LASTEXITCODE (often OK if some objects already exist)"
    }
}

Enable-Postgis $GisUrl
Enable-Postgis $DetailedUrl
Restore-Dump $GisUrl $MainDump
Restore-Dump $DetailedUrl $DetailDump
Write-Host "Done. Redeploy / restart the web service on Render."
