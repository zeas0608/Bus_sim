# Exercise the real upgrade orchestration on isolated fixtures, without launching UE.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$suite = Join-Path ([IO.Path]::GetTempPath()) ("1086 upgrade " + [guid]::NewGuid())
$engine = Join-Path $suite 'Fake UE'
function PutFile($path, $value) {
    New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
    [IO.File]::WriteAllText($path, $value)
}
function MakeLevel($dir) {
    foreach ($name in @('L_1086_Drive.umap','BP_Kotoden1086.uasset','BP_KotodenDriveMode.uasset')) {
        PutFile (Join-Path $dir $name) "fixture $name"
    }
}
$build = Join-Path $engine 'Engine/Build/BatchFiles/Build.bat'
if ($env:OS -eq 'Windows_NT') {
    PutFile $build "@echo off`r`necho invoked >> `"%KOTODEN_TEST_BUILD_RECORD%`"`r`nexit /b 0`r`n"
} else {
    PutFile $build "#!/bin/sh`necho invoked >> `"`$KOTODEN_TEST_BUILD_RECORD`"`n"
    chmod +x $build
}
PutFile (Join-Path $engine 'Engine/Build/Build.version') '{"MajorVersion":5,"MinorVersion":5,"PatchVersion":4}'
PutFile (Join-Path $engine 'Engine/Binaries/Win64/UnrealEditor.exe') 'fixture'
function Get-Process { param($Name,$ErrorAction) } # no real editor is involved
function Start-Process {
    param($FilePath,$WorkingDirectory,$ArgumentList,[switch]$Wait,[switch]$PassThru)
    if ($ArgumentList -match '^-ExecutePythonScript=') {
        if (-not $Wait) { throw 'Preparation must finish before opening the level' }
        if ($stageFails) {
            PutFile $env:KOTODEN_UPGRADE_RESULT '{"status":"failed","error":"fixture failure"}'
        } else {
            MakeLevel (Join-Path $WorkingDirectory 'Content/Kotoden1086/Build_003')
            PutFile $env:KOTODEN_UPGRADE_RESULT '{"status":"ok","level":"/Game/Kotoden1086/Build_003/L_1086_Drive"}'
        }
        return [pscustomobject]@{ExitCode=0}
    }
    if ($Wait -or -not ($ArgumentList -match 'L_1086_Drive.umap')) { throw 'Expected a normal map launch' }
    PutFile (Join-Path $WorkingDirectory 'opened.txt') ($ArgumentList -join ' ')
}
foreach ($case in @('existing','fresh','failure')) {
    $project = Join-Path $suite $case
    $stageFails = $case -eq 'failure'
    New-Item -ItemType Directory -Force -Path $project | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo 'scripts') -Destination $project -Recurse
    foreach ($relative in @('KotodenBusSimulator.uproject','Config/DefaultGame.ini','Content/P0/Test.umap',
        'Art/Bus1086/Bus1086.fbx','Art/Bus1086/Bus1086.json',
        'Source/KotodenBusSimulatorEditor/KotodenBusSimulatorEditor.Build.cs')) {
        PutFile (Join-Path $project $relative) 'original fixture'
    }
    $levels = Join-Path $project 'Content/Kotoden1086'
    if ($case -eq 'existing') {
        MakeLevel (Join-Path $levels 'Build_001')
        MakeLevel (Join-Path $levels 'Build_002')
        PutFile (Join-Path $levels 'Build_003/L_1086_Drive.umap') 'incomplete'
    }
    $before = @{}
    Get-ChildItem (Join-Path $project 'Content') -File -Recurse | ForEach-Object { $before[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName).Hash }
    $env:KOTODEN_TEST_BUILD_RECORD = Join-Path $project 'built.txt'
    & (Join-Path $project 'scripts/setup_kotoden1086.ps1') -Upgrade -UnrealRoot $engine
    $rc = $LASTEXITCODE
    if (($rc -eq 0) -eq $stageFails) { throw "Unexpected result for $case ($rc)" }
    if (-not (Test-Path $env:KOTODEN_TEST_BUILD_RECORD)) { throw 'Build skipped' }
    $opened = Join-Path $project 'opened.txt'
    if ((Test-Path $opened) -eq $stageFails) { throw "Bad launch for $case" }
    if ($case -eq 'existing' -and (Get-Content $opened) -notmatch 'Build_002') { throw 'Wrong existing map opened' }
    $backup = Get-ChildItem (Join-Path $suite 'Recovery_Backup') -Directory | Sort-Object CreationTimeUtc -Descending | Select-Object -First 1
    foreach ($file in $before.Keys) {
        $copy = Join-Path $backup.FullName $file.Substring($project.Length+1)
        if ((Get-FileHash -LiteralPath $file).Hash -ne $before[$file] -or (Get-FileHash -LiteralPath $copy).Hash -ne $before[$file]) {
            throw 'Existing asset or backup changed'
        }
    }
}
Write-Host "PASS existing / fresh / failed upgrade in isolated fixtures"
