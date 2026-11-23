[CmdletBinding()]
param([string] $UnrealRoot = 'C:\Program Files\Epic Games\UE_5.5', [switch] $Offline)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$project = Join-Path $projectRoot 'KotodenBusSimulator.uproject'
$saved = Join-Path $projectRoot 'Saved\TakamatsuStage1'
$revision = [guid]::NewGuid().ToString('N')
$run = Join-Path $saved "Runs\$revision"
New-Item -ItemType Directory -Path $run -Force | Out-Null
$editor = Join-Path $UnrealRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$python = Join-Path $UnrealRoot 'Engine\Binaries\ThirdParty\Python3\Win64\python.exe'
$build = Join-Path $UnrealRoot 'Engine\Build\BatchFiles\Build.bat'
$source = Join-Path $projectRoot 'Maps\TakamatsuStage1'
$deps = Join-Path $saved 'Python311-Shapely212'
$mutex = New-Object System.Threading.Mutex($false,'Kotoden1086Setup')
$locked = $false
$transcript = $false
try {
    Start-Transcript -Path (Join-Path $run 'install.log') | Out-Null
    $transcript = $true
    try { $locked = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another bus or map installer is running.' }
    if (Get-Process -Name 'UnrealEditor','UnrealEditor-Cmd' -ErrorAction SilentlyContinue) {
        throw 'Save your work and close Unreal Editor first.'
    }
    $v = Get-Content -LiteralPath (Join-Path $UnrealRoot 'Engine\Build\Build.version') -Raw | ConvertFrom-Json
    if ("$($v.MajorVersion).$($v.MinorVersion).$($v.PatchVersion)" -ne '5.5.4') { throw 'UE 5.5.4 is required.' }
    . (Join-Path $PSScriptRoot 'find_1086_level.ps1')
    $busRoot = Join-Path $projectRoot 'Content\Kotoden1086'
    $bus = Find-1086Level $busRoot
    if ($null -eq $bus) {
        # Branch changes can hide Git-ignored .uasset/.umap files. Recover missing
        # files from an old setup snapshot without overwriting anything.
        . (Join-Path $PSScriptRoot 'restore_1086_content.ps1')
        $recoveryLogs = Join-Path $projectRoot 'Saved\Setup1086'
        New-Item -ItemType Directory -Force -Path $recoveryLogs | Out-Null
        Restore-Missing1086Content -ProjectRoot $projectRoot -LogFolder $recoveryLogs
        $bus = Find-1086Level $busRoot
    }
    if ($null -eq $bus) {
        throw '1086 assets are not available. No new bus asset import was attempted. See Recovery_Backup, GitHub Desktop stash history and Saved\Setup1086\LatestRecoveryResult.txt.'
    }
    # One-time safety snapshot: this installer only creates new Stage01 packages.
    # Keep a separate copy of locally generated bus assets and configuration.
    $backupReceipt = Join-Path $saved 'stage1-bus-backup.json'
    $needBackup = $true
    if (Test-Path -LiteralPath $backupReceipt -PathType Leaf) {
        try {
            $oldBackup = Get-Content -LiteralPath $backupReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
            $oldMap = Join-Path (Join-Path $oldBackup.snapshot 'Content\Kotoden1086') ($bus.Directory.Name + '\L_1086_Drive.umap')
            if ($oldBackup.busBuild -eq $bus.Directory.Name -and (Test-Path -LiteralPath $oldMap -PathType Leaf)) {
                $needBackup = $false
                Write-Host "Existing external bus backup: $($oldBackup.snapshot)"
            }
        } catch { Write-Warning "Existing backup receipt is invalid; a new copy will be made." }
    }
    if ($needBackup) {
        $backup = Join-Path (Split-Path $projectRoot -Parent) ("Recovery_Backup\TakamatsuStage1-" + $revision)
        $targetContent = Join-Path $backup 'Content'
        New-Item -ItemType Directory -Force -Path $targetContent | Out-Null
        $copyBus = Join-Path $targetContent 'Kotoden1086'
        Write-Host 'Backing up local 1086 Content and Config before map import...'
        Copy-Item -LiteralPath $busRoot -Destination $copyBus -Recurse -ErrorAction Stop
        $configRoot = Join-Path $projectRoot 'Config'
        if (Test-Path -LiteralPath $configRoot -PathType Container) {
            Copy-Item -LiteralPath $configRoot -Destination (Join-Path $backup 'Config') -Recurse -ErrorAction Stop
        }
        # Verify that the backup is complete before continuing to downloads/build.
        foreach ($src in @(Get-ChildItem -LiteralPath $busRoot -Recurse -File -ErrorAction Stop)) {
            $relative = $src.FullName.Substring($busRoot.Length).TrimStart([char[]]@('\','/'))
            $dest = Join-Path $copyBus $relative
            if (-not (Test-Path -LiteralPath $dest -PathType Leaf) -or
                (Get-FileHash -LiteralPath $src.FullName).Hash -ne (Get-FileHash -LiteralPath $dest).Hash) {
                throw "Bus snapshot verification failed: $relative"
            }
        }
        @{snapshot=$backup;busBuild=$bus.Directory.Name} | ConvertTo-Json |
            Set-Content -LiteralPath $backupReceipt -Encoding UTF8
        Write-Host "Verified external backup: $backup"
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Missing UE bundled Python: $python" }
    # PowerShell 5.1 can strip quotes inside native -c arguments. Use a checked-in Python entry point.
    $runner = Join-Path $source 'windows_python.py'
    & $python -I $runner $deps --probe
    if ($LASTEXITCODE -ne 0) {
        if ($Offline) { throw 'Install the pinned wheels online once before requesting offline mode.' }
        $tempDeps = Join-Path $run 'wheels'
        & $python -I -m pip install --disable-pip-version-check --only-binary=:all: --no-deps --require-hashes --target $tempDeps -r (Join-Path $source 'requirements-win64.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Installing the pinned Windows wheels failed.' }
        if (-not (Test-Path -LiteralPath $deps)) { Move-Item -LiteralPath $tempDeps -Destination $deps }
        else { $deps = $tempDeps }
        & $python -I $runner $deps --probe
        if ($LASTEXITCODE -ne 0) { throw 'Bundled Python cannot load the map dependencies.' }
    }
    $params = @('-I',$runner,$deps,'--saved',$saved)
    if ($Offline) { $params += '--offline' }
    & $python @params
    if ($LASTEXITCODE -ne 0) { throw 'Map source verification failed. See the URL and Inputs filename above.' }
    & $build KotodenBusSimulatorEditor Win64 Development "-Project=$project" -WaitMutex
    if ($LASTEXITCODE -ne 0) { throw 'Editor build failed.' }

    $geometryKey = (Get-Content -LiteralPath (Join-Path $saved 'geometry.sha256') -Raw).Trim()
    $importer = Join-Path $PSScriptRoot 'import_takamatsu_stage1.py'
    $env:KOTODEN_STAGE_BUS = '/Game/Kotoden1086/' + $bus.Directory.Name
    $env:KOTODEN_STAGE_RUN = $run
    $index = Join-Path $saved 'installed.json'
    $key = ($geometryKey + (Get-FileHash -LiteralPath $importer).Hash +
        (Get-FileHash -LiteralPath (Join-Path $projectRoot 'Source\KotodenBusSimulatorEditor\Private\TakamatsuStreetMeshLibrary.cpp')).Hash +
        $env:KOTODEN_STAGE_BUS)
    $level = $null
    if (Test-Path -LiteralPath $index -PathType Leaf) {
        $previous = Get-Content -LiteralPath $index -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($previous.key -eq $key -and $previous.level -match '^/Game/TakamatsuRoute/Stage01/Build_[a-f0-9]{32}/L_TakamatsuStation47$') {
            $disk = Join-Path (Join-Path $projectRoot 'Content') ($previous.level.Substring(6)+'.umap')
            $missing = @($previous.layers | Where-Object {
                -not (Test-Path -LiteralPath (Join-Path (Split-Path $disk -Parent) ("SM_" + $_ + ".uasset")) -PathType Leaf) -or
                -not (Test-Path -LiteralPath (Join-Path (Split-Path $disk -Parent) ("M_" + $_ + ".uasset")) -PathType Leaf)
            })
            if ((Test-Path -LiteralPath $disk -PathType Leaf) -and $missing.Count -eq 0) { $level = $previous.level }
        }
    }
    if (-not $level) {
        $argsEditor = @(('"{0}"' -f $project), ('-ExecutePythonScript="{0}"' -f $importer), '-unattended', '-nosplash', '-log', ('-abslog="{0}"' -f (Join-Path $run 'UnrealImport.log')))
        $proc = Start-Process -FilePath $editor -WorkingDirectory $projectRoot -ArgumentList $argsEditor -Wait -PassThru
        $reportFile = Join-Path $run 'result.json'
        if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $reportFile -PathType Leaf)) { throw "Editor import failed. See $run" }
        $report = Get-Content -LiteralPath $reportFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($report.status -ne 'ok') { throw $report.error }
        if ($report.level -ne "/Game/TakamatsuRoute/Stage01/Build_$revision/L_TakamatsuStation47") { throw 'Unexpected generated level name.' }
        $level = $report.level
        @{key=$key;level=$level;layers=$report.layers} | ConvertTo-Json | Set-Content -LiteralPath $index -Encoding UTF8
    }
    Write-Host "Opening $level. Press Play in Selected Viewport."
    Start-Process -FilePath $editor -WorkingDirectory $projectRoot -ArgumentList @(('"{0}"' -f $project),('"{0}.umap"' -f $level),'-log') | Out-Null
} catch {
    Write-Host "Stage 1 failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log folder: $run"
    exit 1
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
    if ($transcript) { Stop-Transcript | Out-Null }
}
