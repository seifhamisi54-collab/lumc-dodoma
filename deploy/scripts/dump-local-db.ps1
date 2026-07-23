# Dump LUMC PostGIS from local Windows (PowerShell).
# Requires: pg_dump on PATH (PostgreSQL bin) OR full path below.

param(
    [string]$OutDir = ".\deploy\db-dumps",
    [string]$DbHost = "localhost",
    [string]$Port = "5433",
    [string]$User = "postgres",
    [string]$Password = "1701",
    [string]$PgDump = "pg_dump"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$env:PGPASSWORD = $Password

Write-Host "Dumping tanzania_gis_db ..."
& $PgDump -h $DbHost -p $Port -U $User -Fc -f (Join-Path $OutDir "tanzania_gis_db_$stamp.dump") tanzania_gis_db

Write-Host "Dumping DETAILED PLANNNING  ..."
& $PgDump -h $DbHost -p $Port -U $User -Fc -f (Join-Path $OutDir "detailed_planning_$stamp.dump") "DETAILED PLANNNING "

Write-Host "Done:"
Get-ChildItem $OutDir -Filter "*$stamp.dump" | Format-Table Name, Length
