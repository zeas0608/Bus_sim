# Collects one compact Stage 1 troubleshooting report. Does not modify UE assets.
[CmdletBinding()]
param([switch] $NoOpen)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$saved = Join-Path $root 'Saved\TakamatsuStage1'
New-Item -ItemType Directory -Force -Path $saved | Out-Null
$output = Join-Path $saved 'Stage1-Diagnostics.txt'
$lines = [System.Collections.Generic.List[string]]::new()
function Add-Line([string] $Text) { $script:lines.Add($Text) }
function Read-Snippet([string] $Heading, [string] $Path) {
    Add-Line "== $Heading =="
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-Line "Missing: $Path"
        return
    }
    Add-Line "Path: $Path"
    try {
        $content = @(Get-Content -LiteralPath $Path -ErrorAction Stop)
        Add-Line '-- Recent compile, import and runtime errors --'
        @($content | Select-String -Pattern 'error C[0-9]{4}|error LNK[0-9]+|error:|ERROR:|FAILED|Traceback|RuntimeError|AssertionError|Exception|Fatal error|warning:|Warning:' |
            Select-Object -Last 55) | ForEach-Object { Add-Line ([string] $_.Line) }
        Add-Line '-- Last 110 lines --'
        @($content | Select-Object -Last 110) | ForEach-Object { Add-Line ([string] $_) }
    } catch { Add-Line "Cannot read: $($_.Exception.Message)" }
}

Add-Line "Takamatsu Stage 1 report: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add-Line "Project: $root"
Add-Line "Unreal Editor running: $([bool](Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue))"
Add-Line "Stage1 branch expected: feature/takamatsu-map-stage1"
$busRoot = Join-Path $root 'Content\Kotoden1086'
Add-Line '== Local bus assets =='
if (Test-Path -LiteralPath $busRoot -PathType Container) {
    $maps = @(Get-ChildItem -LiteralPath $busRoot -Filter 'L_1086_Drive.umap' -File -Recurse -ErrorAction SilentlyContinue)
    Add-Line "1086 maps: $($maps.Count)"
    @($maps | Select-Object -First 8) | ForEach-Object { Add-Line $_.FullName }
} else { Add-Line 'No local Content\Kotoden1086 found.' }

Add-Line '== Stage maps =='
$stageRoot = Join-Path $root 'Content\TakamatsuRoute\Stage01'
if (Test-Path -LiteralPath $stageRoot -PathType Container) {
    @((Get-ChildItem -LiteralPath $stageRoot -Filter 'L_TakamatsuStation47.umap' -File -Recurse -ErrorAction SilentlyContinue) |
        Select-Object -First 8) | ForEach-Object { Add-Line $_.FullName }
} else { Add-Line 'No locally generated stage folder yet.' }

Add-Line '== Prepared data =='
foreach ($name in @('geometry.sha256','installed.json','stage1-bus-backup.json')) {
    $path = Join-Path $saved $name
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        Add-Line ("$name : " + (Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue).Trim())
    } else { Add-Line "$name : missing" }
}
$survey = Join-Path $saved 'survey.json'
if (Test-Path -LiteralPath $survey -PathType Leaf) {
    try {
        $data = Get-Content -LiteralPath $survey -Encoding UTF8 -Raw | ConvertFrom-Json
        Add-Line "Survey path source: $($data.survey.path_source)"
        Add-Line "Survey platform evidence: $($data.survey.platform_evidence)"
        Add-Line "Survey terrain: $($data.terrain)"
        Add-Line "Survey warnings: $($data.warnings -join ' | ')"
    } catch { Add-Line "Survey could not be parsed: $($_.Exception.Message)" }
}
$recentRun = @(Get-ChildItem -LiteralPath (Join-Path $saved 'Runs') -Directory -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1)
if ($recentRun.Count -gt 0) {
    $runPath = $recentRun[0].FullName
    Add-Line "Latest run: $runPath"
    Read-Snippet 'Installer transcript' (Join-Path $runPath 'install.log')
    Read-Snippet 'Editor map import log' (Join-Path $runPath 'UnrealImport.log')
    Read-Snippet 'Editor import result' (Join-Path $runPath 'result.json')
} else { Add-Line 'No stage installer runs found.' }
$logs = Join-Path $root 'Saved\Logs'
if (Test-Path -LiteralPath $logs -PathType Container) {
    $log = Get-ChildItem -LiteralPath $logs -Filter '*.log' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -ne $log) { Read-Snippet 'Latest UE project log' $log.FullName }
}
$buildLogs = Join-Path $root 'Saved\Setup1086'
if (Test-Path -LiteralPath $buildLogs -PathType Container) {
    $log = Get-ChildItem -LiteralPath $buildLogs -Filter '*-BuildEditor.log' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -ne $log) { Read-Snippet 'Previous 1086 build log' $log.FullName }
}
[System.IO.File]::WriteAllLines($output, $lines, [System.Text.UTF8Encoding]::new($true))
Write-Host "Stage 1 diagnostics saved: $output"
if (-not $NoOpen) {
    Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $output) | Out-Null
}
