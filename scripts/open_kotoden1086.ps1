# Open an ALREADY imported Kotoden 1086 map in the normal Unreal Editor.
# This does NOT use -ExecutePythonScript and NEVER reimports or modifies assets.
[CmdletBinding()]
param([string] $UnrealRoot = 'C:\Program Files\Epic Games\UE_5.5')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$project=Join-Path $root 'KotodenBusSimulator.uproject'
$editor=Join-Path $UnrealRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$mapsRoot=Join-Path $root 'Content\Kotoden1086'
try {
    if (-not (Test-Path -LiteralPath $project -PathType Leaf)) { throw "Project missing: $project" }
    if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) { throw "UnrealEditor.exe missing: $editor" }
    if (-not (Test-Path -LiteralPath $mapsRoot -PathType Container)) { throw 'No imported 1086 bus folder found. Run START_KOTODEN1086.cmd for first-time setup.' }
    if (Get-Process -Name 'UnrealEditor' -ErrorAction SilentlyContinue) {
        throw 'Unreal Editor is already running. Please use its Content Browser to open the map, or close it before retrying.'
    }
    $maps=@(Get-ChildItem -LiteralPath $mapsRoot -Filter 'L_1086_Drive.umap' -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object @{Expression={$_.Directory.Name}; Descending=$true}, @{Expression={$_.LastWriteTime};Descending=$true})
    if ($maps.Count -eq 0) {throw 'No L_1086_Drive.umap found under Content\Kotoden1086. Run START_KOTODEN1086.cmd for first-time import.'}
    # Choose newest numbered Build_### with both Blueprint classes and map saved.
    $selected=$null
    foreach($map in $maps){
        $folder=$map.Directory.FullName
        if ((Test-Path -LiteralPath (Join-Path $folder 'BP_Kotoden1086.uasset') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $folder 'BP_KotodenDriveMode.uasset') -PathType Leaf)) {
            $selected=$map
            break
        }
    }
    if($null -eq $selected){throw 'Bus maps found, but required Blueprints are missing. Stop and share diagnostics; do not reimport over them.'}
    $contentPrefix=(Join-Path $root 'Content') + [IO.Path]::DirectorySeparatorChar
    $relative=$selected.FullName.Substring($contentPrefix.Length)
    # Epic's command-line docs require the .umap extension for maps outside the Maps folder.
    $map='/Game/' + $relative.Replace('\','/')
    Write-Host 'Opening the previously imported Kotoden 1086, without Python or build steps.'
    Write-Host "Map: $map"
    Write-Host 'If the Editor closes unexpectedly, run CHECK_1086_ERROR.cmd and send its report.'
    Start-Process -FilePath $editor -WorkingDirectory $root -ArgumentList @(
        ('"{0}"' -f $project),
        ('"{0}"' -f $map),
        '-log'
    ) | Out-Null
    Write-Host 'Editor launch requested. No assets were overwritten.'
} catch {
    Write-Host "OPEN FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
