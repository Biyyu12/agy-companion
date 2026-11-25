<#
.SYNOPSIS
    Installer otomatis agy-companion: pasang hook di ~/.gemini/config/hooks.json
    dan (opsional) tambahkan shortcut fungsi `agy-live` ke PowerShell $PROFILE.

.EXAMPLE
    .\scripts\install.ps1
    .\scripts\install.ps1 -InstallProfile
    .\scripts\install.ps1 -HooksPath "C:\temp\hooks.json" -SkipProfile
#>

param(
    [string]$HooksPath = (Join-Path $HOME ".gemini\config\hooks.json"),
    [switch]$InstallProfile,
    [switch]$SkipProfile
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HookReporterPath = (Join-Path $ProjectRoot "hook_reporter.py") -replace "\\", "/"
$LauncherPath = Join-Path $ProjectRoot "scripts\launch-agy-live.ps1"

if (-not (Test-Path (Join-Path $ProjectRoot "hook_reporter.py"))) {
    throw "hook_reporter.py tidak ditemukan di $ProjectRoot"
}

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

# 1. Gabungkan konfigurasi hook agy-companion ke hooks.json tanpa menimpa hook lain
$HooksDir = Split-Path -Parent $HooksPath
New-Item -ItemType Directory -Force -Path $HooksDir | Out-Null

$HooksObj = [ordered]@{}
if (Test-Path $HooksPath) {
    $RawContent = [System.IO.File]::ReadAllText($HooksPath, [System.Text.Encoding]::UTF8)
    if ($RawContent.Trim().Length -gt 0) {
        $Parsed = $RawContent | ConvertFrom-Json
        if ($Parsed -is [System.Management.Automation.PSCustomObject]) {
            foreach ($prop in $Parsed.PSObject.Properties) {
                $HooksObj[$prop.Name] = $prop.Value
            }
        }
    }
    $BackupPath = "$HooksPath.bak"
    Copy-Item -Path $HooksPath -Destination $BackupPath -Force
    Write-Host "[BACKUP] $BackupPath"
}

$CompanionHook = [ordered]@{
    enabled = $true
    SessionStart = @(
        [ordered]@{
            type = "command"
            command = "python `"$HookReporterPath`" --event SessionStart"
            timeout = 5
        }
    )
    PreInvocation = @(
        [ordered]@{
            type = "command"
            command = "python `"$HookReporterPath`" --event PreInvocation"
            timeout = 5
        }
    )
    PreToolUse = @(
        [ordered]@{
            matcher = "*"
            hooks = @(
                [ordered]@{
                    type = "command"
                    command = "python `"$HookReporterPath`" --event PreToolUse"
                    timeout = 5
                }
            )
        }
    )
    PostToolUse = @(
        [ordered]@{
            matcher = "*"
            hooks = @(
                [ordered]@{
                    type = "command"
                    command = "python `"$HookReporterPath`" --event PostToolUse"
                    timeout = 5
                }
            )
        }
    )
    Stop = @(
        [ordered]@{
            type = "command"
            command = "python `"$HookReporterPath`" --event Stop"
            timeout = 5
        }
    )
}

$HooksObj["agy-companion"] = $CompanionHook
$JsonOut = $HooksObj | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($HooksPath, $JsonOut + "`n", $Utf8NoBom)
Write-Host "[OK] Hook agy-companion terpasang di: $HooksPath"

# 2. Pasang atau update fungsi `agy-live` di PowerShell $PROFILE
$ShouldInstallProfile = $InstallProfile.IsPresent
if (-not $InstallProfile -and -not $SkipProfile) {
    $Answer = Read-Host "Pasang shortcut 'agy-live' ke PowerShell `$PROFILE ($PROFILE)? [Y/n]"
    $ShouldInstallProfile = ($Answer -eq "" -or $Answer -match "^[yY]")
}

if ($ShouldInstallProfile) {
    $ProfileDir = Split-Path -Parent $PROFILE
    if ($ProfileDir) {
        New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
    }
    $StartMarker = "# >>> agy-companion >>>"
    $EndMarker = "# <<< agy-companion <<<"
    $EscLauncher = $LauncherPath -replace '"', '`"'
    $Block = @"
$StartMarker
function agy-live {
    & "$EscLauncher" @args
}
$EndMarker
"@

    $Existing = if (Test-Path $PROFILE) {
        [System.IO.File]::ReadAllText($PROFILE, [System.Text.Encoding]::UTF8)
    } else {
        ""
    }

    $Pattern = "(?s)" + [regex]::Escape($StartMarker) + ".*?" + [regex]::Escape($EndMarker)
    if ($Existing -match $Pattern) {
        $Updated = [regex]::Replace($Existing, $Pattern, $Block)
    } elseif ($Existing.Trim().Length -gt 0) {
        $Updated = $Existing.TrimEnd() + "`n`n" + $Block + "`n"
    } else {
        $Updated = $Block + "`n"
    }

    [System.IO.File]::WriteAllText($PROFILE, $Updated, $Utf8NoBom)
    Write-Host "[OK] Fungsi 'agy-live' terpasang di: $PROFILE"
    Write-Host "Jalankan `. `$PROFILE` (atau buka terminal baru) lalu ketik `agy-live`."
} else {
    Write-Host "[INFO] Pemasangan `$PROFILE dilewati. Jalankan dengan -InstallProfile jika ingin memasangnya nanti."
}
