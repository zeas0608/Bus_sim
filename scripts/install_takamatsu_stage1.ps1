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
$oldPythonPath = $env:PYTHONPATH
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
    $bus = Find-1086Level (Join-Path $projectRoot 'Content\Kotoden1086')
    if ($null -eq $bus) { throw 'No complete local 1086 installation. Restore your existing Content or run UPGRADE_KOTODEN1086.cmd once.' }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Missing UE bundled Python: $python" }
    $env:PYTHONPATH = $deps
    & $python -c "import sys, shapely, numpy; assert sys.version_info[:2]==(3,11) and shapely.__version__=='2.1.2' and numpy.__version__=='1.26.4'" 2>$null
    if ($LASTEXITCODE -ne 0) {
        if ($Offline) { throw "Install Python wheels online once before requesting offline mode." }
        # Publish dependencies only after pip succeeds. Failed downloads never poison a working installation.
        $tempDeps = Join-Path $run 'wheels'
        & $python -m pip install --disable-pip-version-check --only-binary=:all: --no-deps --require-hashes --target $tempDeps -r (Join-Path $source 'requirements-win64.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Installing the pinned Windows wheels failed.' }
        if (-not (Test-Path -LiteralPath $deps)) { Move-Item -LiteralPath $tempDeps -Destination $deps }
        else { $env:PYTHONPATH = $tempDeps }
    }
    $params = @((Join-Path $source 'prepare.py'),'--saved',$saved)
    if ($Offline) { $params += '--offline' }
    & $python @params
    if ($LASTEXITCODE -ne 0) { throw 'Map source verification failed. See the URL and Inputs filename above.' }
    $env:PYTHONPATH = $oldPythonPath
    & $build KotodenBusSimulatorEditor Win64 Development "-Project=$project" -WaitMutex
    if ($LASTEXITCODE -ne 0) { throw 'Editor build failed.' }

    $plan = Join-Path $saved 'plan.json'
    $importer = Join-Path $PSScriptRoot 'import_takamatsu_stage1.py'
    $env:KOTODEN_STAGE_BUS = '/Game/Kotoden1086/' + $bus.Directory.Name
    $env:KOTODEN_STAGE_RUN = $run
    $index = Join-Path $saved 'installed.json'
    $key = ((Get-FileHash -LiteralPath $plan).Hash + (Get-FileHash -LiteralPath $importer).Hash +
        (Get-FileHash -LiteralPath (Join-Path $projectRoot 'Source\KotodenBusSimulatorEditor\Private\TakamatsuStreetMeshLibrary.cpp')).Hash +
        $env:KOTODEN_STAGE_BUS)
    $level = $null
    if (Test-Path -LiteralPath $index -PathType Leaf) {
        $previous = Get-Content -LiteralPath $index -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($previous.key -eq $key -and $previous.level -match '^/Game/TakamatsuRoute/Stage01/Build_[a-f0-9]{32}/L_TakamatsuStation47$') {
            $disk = Join-Path (Join-Path $projectRoot 'Content') ($previous.level.Substring(6)+'.umap')
            if (Test-Path -LiteralPath $disk -PathType Leaf) { $level = $previous.level }
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
        @{key=$key;level=$level} | ConvertTo-Json | Set-Content -LiteralPath $index -Encoding UTF8
    }
    Write-Host "Opening $level. Press Play in Selected Viewport."
    Start-Process -FilePath $editor -WorkingDirectory $projectRoot -ArgumentList @(('"{0}"' -f $project),('"{0}.umap"' -f $level),'-log') | Out-Null
} catch {
    Write-Host "Stage 1 failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log folder: $run"
    exit 1
} finally {
    $env:PYTHONPATH = $oldPythonPath
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
    if ($transcript) { Stop-Transcript | Out-Null }
}
