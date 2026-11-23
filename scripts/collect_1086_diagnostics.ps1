# Collects recent UE 5.5 logs, crashes and import status WITHOUT editing the project.
# User may inspect/redact local paths or other details before sharing this report.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dest=Join-Path $root 'Saved\Setup1086'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$report=Join-Path $dest '1086-Diagnostics.txt'
$lines=[System.Collections.Generic.List[string]]::new()
function Add([string]$line) { $script:lines.Add($line) }
function Collect-Logs([string]$title,[string]$path) {
  Add "== $title =="
  if (-not (Test-Path -LiteralPath $path -PathType Container)) {
    Add "Folder not found: $path"
    return
  }
  $files=@(Get-ChildItem -LiteralPath $path -Filter '*.log' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 2)
  if ($files.Count -eq 0) { Add 'No .log files found.'; return }
  foreach ($file in $files) {
    Add ("Log: {0} (modified {1})" -f $file.FullName, $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
    try {
      $contents=Get-Content -LiteralPath $file.FullName -ErrorAction Stop
      Add '-- Recent errors/warnings (at most 40 lines) --'
      @($contents | Select-String -Pattern 'Fatal error|Unhandled Exception|EXCEPTION_|LogWindows: Error|LogOutputDevice: Error|LogPython: Error|Assertion failed|ensure\(|Crash|LogPluginManager: Error|Error:|error C[0-9]{4}|error LNK[0-9]+|error:|LogLinker: Warning|Failed to load' |
        Select-Object -Last 40) | ForEach-Object { Add ([string] $_.Line) }
      Add '-- Tail (last 100 lines) --'
      @($contents | Select-Object -Last 100) | ForEach-Object { Add ([string]$_) }
    } catch { Add "Cannot read log: $($_.Exception.Message)" }
  }
}
Add "1086 diagnostic report created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add "Project: $root"
Add "Unreal Editor running: $([bool](Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue))"
$import=Join-Path $dest 'LatestImportResult.txt'
Add '== Import result =='
if(Test-Path -LiteralPath $import -PathType Leaf){
  @(Get-Content -LiteralPath $import -Tail 35 -ErrorAction SilentlyContinue) | ForEach-Object { Add ([string]$_) }
} else { Add 'No LatestImportResult.txt found.' }
Add '== Generated bus maps =='
$busContent=Join-Path $root 'Content\Kotoden1086'
if(Test-Path -LiteralPath $busContent -PathType Container) {
  @(Get-ChildItem -LiteralPath $busContent -Filter 'L_1086_Drive.umap' -File -Recurse -ErrorAction SilentlyContinue |
     Sort-Object FullName | Select-Object -ExpandProperty FullName) | ForEach-Object {Add ([string]$_)}
} else { Add 'No Content\Kotoden1086 folder found.' }
Add '== Recoverable 1086 backup snapshots =='
$backupFolder=Join-Path (Split-Path $root -Parent) 'Recovery_Backup'
$backups=@()
if(Test-Path -LiteralPath $backupFolder -PathType Container) {
  foreach($snapshot in @(Get-ChildItem -LiteralPath $backupFolder -Directory -ErrorAction SilentlyContinue)) {
    $busFolder=Join-Path $snapshot.FullName 'Content\Kotoden1086'
    if(Test-Path -LiteralPath $busFolder -PathType Container) {
      $maps=@(Get-ChildItem -LiteralPath $busFolder -Filter 'L_1086_Drive.umap' -File -Recurse -ErrorAction SilentlyContinue)
      if($maps.Count -gt 0) {
        $backups += [pscustomobject]@{Path=$snapshot.FullName;Modified=$snapshot.LastWriteTimeUtc;Maps=$maps.Count}
      }
    }
  }
}
if($backups.Count -eq 0) {Add 'No 1086 backups found in Recovery_Backup (Git stash not inspected).'}
else {
  @($backups | Sort-Object Modified -Descending | Select-Object -First 5) | ForEach-Object {Add ("$($_.Path) ($($_.Maps) maps)")}
}

Collect-Logs 'Setup and upgrade' $dest
Get-ChildItem -LiteralPath $dest -Filter '*-UpgradeResult.json' -File |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object {
    Add "Upgrade result: $($_.Name)"
    Add (Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8)
  }
Collect-Logs 'Project logs' (Join-Path $root 'Saved\Logs')
Collect-Logs 'UE 5.5 user logs' (Join-Path $env:LOCALAPPDATA 'UnrealEngine\5.5\Saved\Logs')
Add '== Crash folders (names and recent time only) =='
$crash=Join-Path $root 'Saved\Crashes'
if(Test-Path -LiteralPath $crash -PathType Container){
  @(Get-ChildItem -LiteralPath $crash -Directory -ErrorAction SilentlyContinue |
     Sort-Object LastWriteTime -Descending | Select-Object -First 5) |
     ForEach-Object { Add ($_.FullName + ' | ' + $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')) }
} else { Add 'No Saved\Crashes directory.' }
[System.IO.File]::WriteAllLines($report,$lines,[System.Text.UTF8Encoding]::new($true))
Write-Host "Read-only diagnostics saved: $report"
Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $report) | Out-Null
