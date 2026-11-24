# Run in PowerShell on Linux with bash. Native UE/Python invocations use isolated test executables.
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('stage smoke '+[guid]::NewGuid().ToString('N'))
function Write-Fixture($name,$contents) {
    $path=Join-Path $fixture $name
    New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force | Out-Null
    [IO.File]::WriteAllText($path,$contents)
    return $path
}
$engine=Join-Path $fixture 'engine'
$projectDir=Join-Path $fixture 'project'
$projectScripts=Join-Path $projectDir 'scripts'
New-Item -ItemType Directory -Path $projectScripts -Force | Out-Null
foreach ($script in @('install_takamatsu_stage1.ps1','find_1086_level.ps1','import_takamatsu_stage1.py')) {
    Copy-Item (Join-Path $repository "scripts/$script") $projectScripts
}
$null=Write-Fixture 'project/Source/KotodenBusSimulatorEditor/Private/TakamatsuStreetMeshLibrary.cpp' 'fixture'
$null=Write-Fixture 'engine/Engine/Build/Build.version' '{"MajorVersion":5,"MinorVersion":5,"PatchVersion":4}'
$buildBat=Write-Fixture 'engine/Engine/Build/BatchFiles/Build.bat' "#!/bin/sh`nexit 0`n"
$pythonExe=Write-Fixture 'engine/Engine/Binaries/ThirdParty/Python3/Win64/python.exe' "#!/bin/sh`nexit 0`n"
chmod +x $buildBat $pythonExe
$null=Write-Fixture 'project/Saved/TakamatsuStage1/geometry.sha256' 'test-plan'
$original=@{}
foreach ($name in @('BP_Kotoden1086.uasset','BP_KotodenDriveMode.uasset','L_1086_Drive.umap')) {
    $path=Write-Fixture "project/Content/Kotoden1086/Build_001/$name" "protected-$name"
    $original[$path]=(Get-FileHash $path).Hash
}
function Get-Process { param($Name,$ErrorAction) }
$calls=@{Imports=0;Opens=0;Fail=$false}
function Start-Process {
    param($FilePath,$WorkingDirectory,$ArgumentList,[switch]$Wait,[switch]$PassThru)
    if ($ArgumentList -match '^-ExecutePythonScript=') {
        if (-not $Wait -or $env:KOTODEN_STAGE_BUS -ne '/Game/Kotoden1086/Build_001') { throw 'Wrong bus or asynchronous import' }
        $calls.Imports++
        $result=Join-Path $env:KOTODEN_STAGE_RUN 'result.json'
        if ($calls.Fail) { '{"status":"failed","error":"simulated import failure"}' | Set-Content $result }
        else {
            $rev=Split-Path $env:KOTODEN_STAGE_RUN -Leaf
            $level="/Game/TakamatsuRoute/Stage01/Build_$rev/L_TakamatsuStation47"
            @{status='ok';level=$level;layers=@('Asphalt');textures=@('T_Asphalt_BC')} |ConvertTo-Json| Set-Content $result
            foreach ($file in @('L_TakamatsuStation47.umap','SM_Asphalt.uasset','M_Asphalt.uasset','T_Asphalt_BC.uasset')) {
                $null=Write-Fixture "project/Content/TakamatsuRoute/Stage01/Build_$rev/$file" 'new'
            }
        }
        return [pscustomobject]@{ExitCode=0}
    }
    if ($Wait -or -not ($ArgumentList -match 'L_TakamatsuStation47.umap')) { throw 'Wrong map launch' }
    $calls.Opens++
}
$installer=Join-Path $projectScripts 'install_takamatsu_stage1.ps1'
& $installer -UnrealRoot $engine
& $installer -UnrealRoot $engine
if ($calls.Imports -ne 1 -or $calls.Opens -ne 2) { throw 'Identical rerun failed to reuse stage' }
# A partial cached build must result in a new directory. Other map assets may be local work.
$stageRoot=Join-Path $projectDir 'Content/TakamatsuRoute/Stage01'
$first=@(Get-ChildItem -LiteralPath $stageRoot -Directory)[0]
$priorMap=Join-Path $first.FullName 'L_TakamatsuStation47.umap'
$original[$priorMap]=(Get-FileHash $priorMap).Hash
Move-Item -LiteralPath (Join-Path $first.FullName 'T_Asphalt_BC.uasset') -Destination (Join-Path $fixture 'held-texture.uasset')
& $installer -UnrealRoot $engine
if ($calls.Imports -ne 2 -or $calls.Opens -ne 3 -or @(Get-ChildItem -LiteralPath $stageRoot -Directory).Count -ne 2) {
    throw 'Partial map build did not cause isolated regeneration'
}
$calls.Fail=$true
$null=Write-Fixture 'project/Saved/TakamatsuStage1/geometry.sha256' 'different'
& $installer -UnrealRoot $engine
if ($LASTEXITCODE -ne 1 -or $calls.Opens -ne 3) { throw 'Failed import launched the normal editor' }
foreach ($path in $original.Keys) {
    if ((Get-FileHash $path).Hash -ne $original[$path]) { throw 'Protected asset changed' }
}
Write-Host 'PASS new stage, unchanged rerun, missing texture recovery, failed import and protected asset hashes'
