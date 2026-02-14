param(
    [string]$ReplicaSetName = "rs0",
    [string]$MongoServiceName = "MongoDB",
    [bool]$AutoElevate = $true
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Yellow
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Start-ElevatedSelf {
    $scriptPath = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($scriptPath) -or -not (Test-Path $scriptPath)) {
        throw "Could not resolve script path for elevation."
    }

    $argList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$scriptPath`"",
        "-ReplicaSetName", "`"$ReplicaSetName`"",
        "-MongoServiceName", "`"$MongoServiceName`"",
        "-AutoElevate", "false"
    )

    Start-Process -FilePath "powershell.exe" -ArgumentList $argList -Verb RunAs | Out-Null
}

function Resolve-MongoServiceName([string]$PreferredName) {
    $preferred = [string]$PreferredName
    if (-not [string]::IsNullOrWhiteSpace($preferred)) {
        $direct = Get-CimInstance Win32_Service -Filter "Name='$preferred'" -ErrorAction SilentlyContinue
        if ($direct) {
            return [string]$direct.Name
        }
        Write-Host "Preferred Mongo service '$preferred' was not found. Trying auto-detection..." -ForegroundColor Yellow
    }

    $services = Get-CimInstance Win32_Service -ErrorAction SilentlyContinue
    if (-not $services) {
        throw "Could not enumerate Windows services for MongoDB detection."
    }

    $matches = @(
        $services | Where-Object {
            $name = [string]$_.Name
            $display = [string]$_.DisplayName
            $path = [string]$_.PathName
            (
                $name -match "mongo" -or
                $display -match "mongo" -or
                $path -match "mongod"
            )
        } | Sort-Object `
            @{ Expression = { if ([string]$_.State -eq "Running") { 0 } else { 1 } } }, `
            @{ Expression = { [string]$_.Name } }
    )

    if ($matches.Count -eq 0) {
        throw "MongoDB Windows service was not found. Install MongoDB service first."
    }

    return [string]$matches[0].Name
}

function Get-MongoServiceConfigPath([string]$ServiceName) {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
    if (-not $svc) {
        throw "Mongo service '$ServiceName' was not found."
    }
    $pathName = [string]$svc.PathName

    $patterns = @(
        '--config\s*=\s*"([^"]+)"',
        '--config\s+"([^"]+)"',
        '--config\s*=\s*([^\s"]+)',
        '--config\s+([^\s"]+)'
    )
    foreach ($pattern in $patterns) {
        $match = [regex]::Match(
            $pathName,
            $pattern,
            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
        if ($match.Success) {
            return $match.Groups[1].Value
        }
    }

    $exeMatch = [regex]::Match($pathName, '^"([^"]+mongod\.exe)"', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($exeMatch.Success) {
        $binDir = Split-Path $exeMatch.Groups[1].Value -Parent
        return Join-Path $binDir "mongod.cfg"
    }

    throw "Could not resolve mongod config path from service command line: $pathName"
}

function Set-ReplSetInConfig([string]$ConfigPath, [string]$SetName) {
    $lines = Get-Content -Path $ConfigPath
    $replicationIndex = -1

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $trimmed = $lines[$i].Trim()
        if ($trimmed -eq "replication:" -or $trimmed -eq "#replication:") {
            $replicationIndex = $i
            break
        }
    }

    if ($replicationIndex -eq -1) {
        $lines += ""
        $lines += "replication:"
        $lines += "  replSetName: $SetName"
        Set-Content -Path $ConfigPath -Value $lines -Encoding UTF8
        return
    }

    if ($lines[$replicationIndex].Trim() -eq "#replication:") {
        $lines[$replicationIndex] = "replication:"
    } else {
        $lines[$replicationIndex] = "replication:"
    }

    $blockEnd = $lines.Count
    for ($j = $replicationIndex + 1; $j -lt $lines.Count; $j++) {
        $line = $lines[$j]
        if ($line -match '^\S' -and $line.Trim() -ne "") {
            $blockEnd = $j
            break
        }
    }

    $before = @()
    if ($replicationIndex -gt 0) {
        $before = $lines[0..($replicationIndex - 1)]
    }

    $after = @()
    if ($blockEnd -lt $lines.Count) {
        $after = $lines[$blockEnd..($lines.Count - 1)]
    }

    $newLines = @()
    $newLines += $before
    $newLines += "replication:"
    $newLines += "  replSetName: $SetName"
    $newLines += $after

    Set-Content -Path $ConfigPath -Value $newLines -Encoding UTF8
}

function Ensure-ReplSetInitialized([string]$SetName) {
    $py = @"
import sys
import time
from pymongo import MongoClient

set_name = "$SetName"
client = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=8000)
client.admin.command("ping")

already_initialized = False
try:
    status = client.admin.command("replSetGetStatus")
    already_initialized = bool(status.get("ok") == 1)
except Exception:
    already_initialized = False

if not already_initialized:
    cfg = {"_id": set_name, "members": [{"_id": 0, "host": "127.0.0.1:27017"}]}
    try:
        client.admin.command("replSetInitiate", cfg)
    except Exception as exc:
        msg = str(exc).lower()
        if "already initialized" not in msg and "already exists" not in msg:
            raise

for _ in range(30):
    hello = client.admin.command("hello")
    if hello.get("setName") == set_name and (
        hello.get("isWritablePrimary") or hello.get("ismaster")
    ):
        print("Replica set is ready")
        sys.exit(0)
    time.sleep(1)

print("Replica set was not ready within timeout")
sys.exit(2)
"@

    $py | python -
}

function Update-LocalCloudConfig([string]$SetName) {
    $configPath = Join-Path (Get-Location) "cloud_config.json"
    if (-not (Test-Path $configPath)) {
        return
    }

    $raw = Get-Content -Path $configPath -Raw
    $cfg = $raw | ConvertFrom-Json
    $uri = [string]($cfg.MONGO_URI)
    if ([string]::IsNullOrWhiteSpace($uri)) {
        return
    }

    $newUri = $uri
    if ($newUri -notmatch 'replicaSet=') {
        if ($newUri.Contains("?")) {
            $newUri = "$newUri&replicaSet=$SetName"
        } else {
            $newUri = "$newUri/?replicaSet=$SetName"
        }
    }
    if ($newUri -notmatch 'directConnection=') {
        if ($newUri.Contains("?")) {
            $newUri = "$newUri&directConnection=false"
        } else {
            $newUri = "$newUri/?directConnection=false"
        }
    }
    $cfg.MONGO_URI = $newUri

    $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $configPath -Encoding UTF8
    Write-Host "Updated cloud_config.json with replicaSet=$SetName" -ForegroundColor Green
}

if (-not (Test-IsAdmin)) {
    if ($AutoElevate) {
        Write-Host "Administrator privileges are required. Requesting elevation..." -ForegroundColor Yellow
        try {
            Start-ElevatedSelf
            exit 0
        } catch {
            Write-Host "Failed to elevate automatically: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    Write-Host "Run this script as Administrator." -ForegroundColor Red
    exit 1
}

Write-Host "SkyWaveERP - Enable Local MongoDB Replica Set" -ForegroundColor Cyan
Write-Host "Replica Set: $ReplicaSetName" -ForegroundColor Cyan

Write-Step "Resolving MongoDB service name"
$MongoServiceName = Resolve-MongoServiceName -PreferredName $MongoServiceName
Write-Host "Mongo Service: $MongoServiceName" -ForegroundColor Green

Write-Step "Resolving MongoDB service config path"
$configPath = Get-MongoServiceConfigPath -ServiceName $MongoServiceName
if (-not (Test-Path $configPath)) {
    throw "Mongo config file not found: $configPath"
}
Write-Host "Config: $configPath" -ForegroundColor Green

Write-Step "Backing up current config"
$backupPath = "$configPath.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item -Path $configPath -Destination $backupPath -Force
Write-Host "Backup: $backupPath" -ForegroundColor Green

Write-Step "Writing replication settings"
Set-ReplSetInConfig -ConfigPath $configPath -SetName $ReplicaSetName
Write-Host "Config updated." -ForegroundColor Green

Write-Step "Restarting MongoDB service"
Restart-Service -Name $MongoServiceName -Force
Start-Sleep -Seconds 2
Write-Host "MongoDB service restarted." -ForegroundColor Green

Write-Step "Initializing/verifying replica set"
Ensure-ReplSetInitialized -SetName $ReplicaSetName
Write-Host "Replica set initialized and primary is ready." -ForegroundColor Green

Write-Step "Updating local project cloud_config.json (if present)"
Update-LocalCloudConfig -SetName $ReplicaSetName

Write-Host ""
Write-Host "Done. Change Streams should now work without fallback warning." -ForegroundColor Green
