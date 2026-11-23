# One-click setup for Kotoden 1086 on UE 5.5.4 / Windows.
# This script backs up local assets, generates project files, builds Editor, then starts the Editor with an import script.
# It never performs git stash, checkout, reset, clean, or modifies the source Blender/FBX files.
[CmdletBinding()]
param(
    [switch] $Upgrade,
    [string] $UnrealRoot = 'C:\Program Files\Epic Games\UE_5.5'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$projectFile = Join-Path $projectRoot 'KotodenBusSimulator.uproject'
$buildBat = Join-Path $UnrealRoot 'Engine\Build\BatchFiles\Build.bat'
$editorExe = Join-Path $UnrealRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$versionFile = Join-Path $UnrealRoot 'Engine\Build\Build.version'
$importScript = Join-Path $PSScriptRoot 'launch_kotoden1086.py'
$timestamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$logFolder = Join-Path $projectRoot 'Saved\Setup1086'
New-Item -ItemType Directory -Force -Path $logFolder | Out-Null

function Assert-File([string] $Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }
}

function Invoke-UnrealBuild([string] $Step, [string[]] $Parameters) {
    $log = Join-Path $logFolder "$timestamp-$Step.log"
    Write-Host ""
    Write-Host "== $Step =="
    Write-Host "Log: $log"
    $savedPreference = $ErrorActionPreference
    $code = -1
    try {
        # A native Unreal tool may write warnings to stderr. Capture them rather than treating them as PowerShell exceptions.
        $ErrorActionPreference = 'Continue'
        & $buildBat @Parameters *>&1 | Tee-Object -FilePath $log
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedPreference
    }
    if ($code -ne 0) {
        throw "$Step failed (exit $code). Send the last error lines from $log."
    }
    Write-Host "$Step succeeded."
}

$mutex = New-Object System.Threading.Mutex($false,'Kotoden1086Setup')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another 1086 setup is running.' }
    Write-Host 'Kotoden 1086 setup: safe backup, UE project generation, Editor build, automated import.'
    Write-Host "Project: $projectRoot"
    Write-Host "Engine: $UnrealRoot"

    foreach ($path in @($projectFile, $buildBat, $editorExe, $versionFile, $importScript,
        (Join-Path $PSScriptRoot 'import_kotoden1086.py'),
        (Join-Path $projectRoot 'Source\KotodenBusSimulatorEditor\KotodenBusSimulatorEditor.Build.cs'))) {
        Assert-File $path
    }

    $version = Get-Content -LiteralPath $versionFile -Raw | ConvertFrom-Json
    $actual = '{0}.{1}.{2}' -f $version.MajorVersion, $version.MinorVersion, $version.PatchVersion
    if ($actual -ne '5.5.4') {
        throw "Expected UE 5.5.4, found $actual. Specify -UnrealRoot with the correct engine path."
    }
    if (Get-Process -Name 'UnrealEditor','UnrealEditor-Cmd' -ErrorAction SilentlyContinue) {
        throw 'Unreal Editor is running. Save All, close Unreal Editor, and retry this script.'
    }

    # Back up even if a previous manual recovery was performed.
    # The backup stays outside the git repository and never overwrites a prior backup.
    $backupRoot = Join-Path (Split-Path $projectRoot -Parent) ("Recovery_Backup\Kotoden1086-" + $timestamp)
    New-Item -ItemType Directory -Path $backupRoot | Out-Null
    foreach ($directory in @('Content', 'Config')) {
        $source = Join-Path $projectRoot $directory
        if (Test-Path -LiteralPath $source -PathType Container) {
            Write-Host "Backing up $directory ..."
            Copy-Item -LiteralPath $source -Destination (Join-Path $backupRoot $directory) -Recurse -Force
        }
    }
    Write-Host "Backup folder: $backupRoot"

    # Existing imported bus assets must always open normally (no Python command line).
    # This is independent of the previous SUCCESS report, preventing duplicate imports
    # if the report is missing/stale or an old launcher was used.
    $busContent = Join-Path $projectRoot 'Content\Kotoden1086'
    if ($Upgrade) {
        . (Join-Path $PSScriptRoot 'find_1086_level.ps1')
        Invoke-UnrealBuild -Step 'BuildEditor' -Parameters @('KotodenBusSimulatorEditor', 'Win64', 'Development', "-Project=$projectFile", '-WaitMutex')
        $selected = Find-1086Level $busContent
        if ($null -eq $selected) {
            $stage = Join-Path $PSScriptRoot 'prepare_1086_upgrade.py'
            Assert-File $stage
            $resultFile = Join-Path $logFolder "$timestamp-UpgradeResult.json"
            $env:KOTODEN_UPGRADE_RESULT = $resultFile
            $stageArgs = @(('"{0}"' -f $projectFile), ('-ExecutePythonScript="{0}"' -f $stage), '-unattended', '-nosplash', '-log')
            $process = Start-Process -FilePath $editorExe -WorkingDirectory $projectRoot -ArgumentList $stageArgs -Wait -PassThru
            if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $resultFile -PathType Leaf)) {
                throw "Asset preparation failed (exit $($process.ExitCode)). Check the Editor log and $resultFile."
            }
            $result = Get-Content -LiteralPath $resultFile -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($result.status -ne 'ok') { throw "Asset preparation failed: $($result.error)" }
            $selected = Find-1086Level $busContent
            if ($null -eq $selected -or $result.level -ne "/Game/Kotoden1086/$($selected.Directory.Name)/L_1086_Drive") {
                throw "Generated level did not pass the file checks. See $resultFile."
            }
        }
        Write-Host "Ready: $($selected.FullName). Opening the normal Editor."
        & (Join-Path $PSScriptRoot 'open_kotoden1086.ps1') -UnrealRoot $UnrealRoot
        if (-not $?) { throw 'Normal Editor launch failed.' }
        exit 0
    }
    if (Test-Path -LiteralPath $busContent -PathType Container) {
        $maps = @(Get-ChildItem -LiteralPath $busContent -Filter 'L_1086_Drive.umap' -File -Recurse -ErrorAction SilentlyContinue)
        if ($maps.Count -gt 0) {
            Write-Host "Found previously imported bus level(s). Skipping project generation, build and Python import."
            & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'open_kotoden1086.ps1') -UnrealRoot $UnrealRoot
            if ($LASTEXITCODE -ne 0) {
                throw 'Could not open the existing bus map. Use CHECK_1086_ERROR.cmd; do not reimport.'
            }
            exit 0
        }
    }

    Invoke-UnrealBuild -Step 'GenerateProjectFiles' -Parameters @('-projectfiles', "-project=$projectFile", '-game', '-rocket', '-progress')
    Invoke-UnrealBuild -Step 'BuildEditor' -Parameters @('KotodenBusSimulatorEditor', 'Win64', 'Development', "-Project=$projectFile", '-WaitMutex')

    # UE runs the Python script after the Editor starts. A result file is written inside Saved\Setup1086.
    # Launch the GUI Editor (not a commandlet) because the importer needs editor/world subsystems.
    Write-Host ''
    Write-Host 'Starting Unreal Editor with automatic 1086 import ...'
    Write-Host "Import report: $logFolder\LatestImportResult.txt"
    $args = @(
        ('"{0}"' -f $projectFile),
        ('-ExecutePythonScript="{0}"' -f $importScript),
        '-log'
    )
    Start-Process -FilePath $editorExe -WorkingDirectory $projectRoot -ArgumentList $args | Out-Null
    Write-Host 'Editor launch requested. Wait for its Output Log / new L_1086_Drive map.'
    Write-Host 'If the import fails, share Saved\Setup1086\LatestImportResult.txt.'
} catch {
    Write-Host ''
    "FAILED: $($_.Exception.Message)" | Out-File -LiteralPath (Join-Path $logFolder "$timestamp-SetupFailure.log") -Encoding utf8
    Write-Host "SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Existing Content and Config were not deleted. Check Saved\Setup1086 for logs."
    exit 1
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
