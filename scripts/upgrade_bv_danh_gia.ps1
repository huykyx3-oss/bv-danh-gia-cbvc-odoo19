#requires -Version 5.1
<#
.SYNOPSIS
  Copy bv_danh_gia into Odoo container, upgrade module, clear web asset attachments, restart Odoo.

.USAGE
  .\scripts\upgrade_bv_danh_gia.ps1
  .\scripts\upgrade_bv_danh_gia.ps1 -Database "mydb" -OdooContainer "odoo19_web"

.PARAM OdooContainer  Docker name of Odoo service (default: odoo)
.PARAM DbContainer     Docker name of Postgres (default: db)
.PARAM Database        PostgreSQL database name (default: DB_odoo)
.PARAM ModuleDest      Path inside container for the addon (default: /mnt/extra-addons/bv_danh_gia)
.PARAM SkipCopy        Do not docker cp (use when bind-mount already maps repo)
.PARAM SkipAssets      Do not DELETE ir_attachment assets rows
.PARAM SkipRestart     Do not docker restart Odoo after upgrade
.PARAM DbHost           Postgres hostname from Odoo container (Docker service name, default: db)
.PARAM DbPort
.PARAM DbUser
.PARAM DbPassword       Often odoo in docker-compose samples; override if yours differs
#>
param(
    [string]$OdooContainer = "odoo",
    [string]$DbContainer = "db",
    [string]$Database = "DB_odoo",
    [string]$ModuleDest = "/mnt/extra-addons/bv_danh_gia",
    [string]$DbHost = "db",
    [int]$DbPort = 5432,
    [string]$DbUser = "odoo",
    [string]$DbPassword = "odoo",
    [switch]$SkipCopy,
    [switch]$SkipAssets,
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    Write-Error "Repo root not found: $RepoRoot"
}
$ModuleSrc = Join-Path -Path $RepoRoot -ChildPath 'bv_danh_gia'
if (-not (Test-Path -LiteralPath $ModuleSrc)) {
    Write-Error "Module folder missing: $ModuleSrc"
}

function Assert-Docker {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker not running or not in PATH."
    }
}

Assert-Docker

Write-Host "==> Repo: $RepoRoot"
Write-Host "==> Module: $ModuleSrc"

if (-not $SkipCopy) {
    Write-Host "==> docker cp -> ${OdooContainer}:${ModuleDest}"
    docker cp "$ModuleSrc/." "${OdooContainer}:${ModuleDest}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker cp failed. Check container name and path inside container."
    }
} else {
    Write-Host "==> Skip copy (SkipCopy)"
}

Write-Host "==> odoo -u bv_danh_gia -d $Database (db host ${DbHost}:${DbPort} user $DbUser) --stop-after-init"
$odooArgs = @(
    '-d', $Database,
    '-u', 'bv_danh_gia',
    '--stop-after-init',
    "--db_host=$DbHost",
    "--db_port=$DbPort",
    "--db_user=$DbUser",
    "--db_password=$DbPassword"
)
docker exec $OdooContainer odoo @odooArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Module upgrade failed. Check DB password/host (params DbHost, DbUser, DbPassword) or run: docker exec -it $OdooContainer cat /etc/odoo/odoo.conf"
}

if (-not $SkipAssets) {
    Write-Host "==> Clear cached web asset attachments (ir_attachment)"
    docker exec $DbContainer psql -U odoo -d $Database -c "DELETE FROM ir_attachment WHERE name LIKE '%assets%';"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "psql asset cleanup failed (wrong DB user/name?). Continuing."
    }
} else {
    Write-Host "==> Skip asset DB cleanup (SkipAssets)"
}

if (-not $SkipRestart) {
    Write-Host "==> docker restart $OdooContainer"
    docker restart $OdooContainer
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "restart failed; reload Odoo manually."
    }
} else {
    Write-Host '==> Skip restart (SkipRestart) - reload Odoo yourself if needed.'
}

Write-Host ''
Write-Host 'Done. Open Odoo with ?debug=assets once, then hard refresh (Ctrl+F5).'
Write-Host ''
