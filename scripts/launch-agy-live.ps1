<#
.SYNOPSIS
    Buka Antigravity CLI (agy) berdampingan dengan Companion Braille TUI di Windows Terminal.

.EXAMPLE
    .\scripts\launch-agy-live.ps1
    .\scripts\launch-agy-live.ps1 --theme amber
    .\scripts\launch-agy-live.ps1 --theme pastel --character neko -p "tolong review folder ini"
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RawArgs
)

$ErrorActionPreference = "Stop"

# Pisahkan opsi khusus companion (--theme, --character, --sleepy-after, --no-stats, --log)
# dari argumen yang diteruskan ke `agy`.
$CompanionExtraArgs = @()
$AgyArgs = @()

$i = 0
$passAllToAgy = $false
while ($RawArgs -and $i -lt $RawArgs.Count) {
    $tok = $RawArgs[$i]

    if ($passAllToAgy) {
        $AgyArgs += $tok
        $i++
        continue
    }

    if ($tok -eq "--") {
        $passAllToAgy = $true
        $i++
        continue
    }

    if ($tok -match "^(--theme|-Theme)$") {
        if ($i + 1 -ge $RawArgs.Count) { throw "Opsi $tok membutuhkan nilai tema (mono|amber|green|cyan|pastel)." }
        $CompanionExtraArgs += @("--theme", $RawArgs[$i + 1])
        $i += 2
        continue
    }
    if ($tok -match "^--theme=(.+)$") {
        $CompanionExtraArgs += @("--theme", $Matches[1])
        $i++
        continue
    }

    if ($tok -match "^(--character|-Character)$") {
        if ($i + 1 -ge $RawArgs.Count) { throw "Opsi $tok membutuhkan ID character pack." }
        $CompanionExtraArgs += @("--character", $RawArgs[$i + 1])
        $i += 2
        continue
    }
    if ($tok -match "^--character=(.+)$") {
        $CompanionExtraArgs += @("--character", $Matches[1])
        $i++
        continue
    }

    if ($tok -match "^(--persona|-Persona)$") {
        if ($i + 1 -ge $RawArgs.Count) { throw "Opsi $tok membutuhkan nama persona (santai|formal|tsundere|zen)." }
        $CompanionExtraArgs += @("--persona", $RawArgs[$i + 1])
        $i += 2
        continue
    }
    if ($tok -match "^--persona=(.+)$") {
        $CompanionExtraArgs += @("--persona", $Matches[1])
        $i++
        continue
    }

    if ($tok -match "^(--sleepy-after|-SleepyAfter)$") {
        if ($i + 1 -ge $RawArgs.Count) { throw "Opsi $tok membutuhkan nilai detik." }
        $CompanionExtraArgs += @("--sleepy-after", $RawArgs[$i + 1])
        $i += 2
        continue
    }
    if ($tok -match "^--sleepy-after=(.+)$") {
        $CompanionExtraArgs += @("--sleepy-after", $Matches[1])
        $i++
        continue
    }

    if ($tok -match "^(--no-stats|-NoStats)$") {
        $CompanionExtraArgs += "--no-stats"
        $i++
        continue
    }

    if ($tok -match "^(--log|-Log)$") {
        $CompanionExtraArgs += "--log"
        $i++
        continue
    }

    $AgyArgs += $tok
    $i++
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CompanionScript = Join-Path $ProjectRoot "companion.py"
$StateDir = Join-Path $HOME ".agy-companion"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# Bersihkan file state/exit sesi lama (> 24 jam) agar folder ~/.agy-companion tetap bersih
$Cutoff = (Get-Date).AddHours(-24)
Get-ChildItem -Path $StateDir -Filter "state_*.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $Cutoff } |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $StateDir -Filter "exit_*.flag" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $Cutoff } |
    Remove-Item -Force -ErrorAction SilentlyContinue

# Isolasi state & exit flag per sesi agar beberapa tab agy-live tidak saling menimpa
$SessionId = [guid]::NewGuid().ToString("N").Substring(0, 8)
$StateFile = Join-Path $StateDir "state_$SessionId.json"
$ExitFile = Join-Path $StateDir "exit_$SessionId.flag"
$WorkDir = (Get-Location).Path

# Tulis state awal UTF-8 tanpa BOM agar aman di PowerShell 5.1 maupun 7+
$InitialState = @{
    state = "idle"
    detail = "ready"
    event = "LauncherStart"
    updatedAt = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
} | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($StateFile, $InitialState, [System.Text.UTF8Encoding]::new($false))

function ConvertTo-PsSingleQuoted {
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

function ConvertTo-PsArrayLiteral {
    param([string[]]$Items)
    if (-not $Items -or $Items.Count -eq 0) {
        return "@()"
    }
    $escaped = foreach ($item in $Items) { ConvertTo-PsSingleQuoted $item }
    return "@(" + ($escaped -join ", ") + ")"
}

function ConvertTo-EncodedCommand {
    param([string]$ScriptText)
    return [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($ScriptText))
}

$EscCompanion = ConvertTo-PsSingleQuoted $CompanionScript
$EscStateFile = ConvertTo-PsSingleQuoted $StateFile
$EscExitFile = ConvertTo-PsSingleQuoted $ExitFile
$CompanionExtraExpr = ConvertTo-PsArrayLiteral $CompanionExtraArgs
$AgyArgsExpr = ConvertTo-PsArrayLiteral $AgyArgs

$CompanionPs = @"
`$extraArgs = $CompanionExtraExpr
try {
    & python $EscCompanion --state-file $EscStateFile --exit-file $EscExitFile @extraArgs
} finally {
    Remove-Item -Path $EscStateFile -Force -ErrorAction SilentlyContinue
}
"@

$AgyPs = @"
`$env:AGY_COMPANION_STATE_FILE = $EscStateFile
`$agyArgs = $AgyArgsExpr
try {
    & agy @agyArgs
} finally {
    New-Item -ItemType File -Force -Path $EscExitFile | Out-Null
}
"@

$CompanionEncoded = ConvertTo-EncodedCommand $CompanionPs
$AgyEncoded = ConvertTo-EncodedCommand $AgyPs

wt -w 0 new-tab -d "$WorkDir" --title "agy-live" `
    powershell -NoLogo -NoProfile -EncodedCommand $CompanionEncoded `; `
    split-pane -V -s 0.68 -d "$WorkDir" `
    powershell -NoLogo -NoProfile -EncodedCommand $AgyEncoded
