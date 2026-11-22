# Read-only source inventory. Run against your installed Unreal Engine 5.5.4 directory.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $UnrealRoot
)

$ErrorActionPreference = 'Stop'
$versionFile = Join-Path $UnrealRoot 'Engine/Build/Build.version'
$version = Get-Content -LiteralPath $versionFile -Raw | ConvertFrom-Json
$actualVersion = '{0}.{1}.{2}' -f $version.MajorVersion, $version.MinorVersion, $version.PatchVersion
Write-Output "Engine version: $actualVersion (CL $($version.Changelist))"
if ($actualVersion -ne '5.5.4') {
    Write-Error 'This check requires the UE 5.5.4 installation.'
}

$plugin = 'Engine/Plugins/Experimental/ChaosVehiclesPlugin/Source/ChaosVehicles'
$core = 'Engine/Source/Runtime/Experimental/ChaosVehicles/ChaosVehiclesCore'
$checks = [ordered]@{
    "$plugin/Public/ChaosWheeledVehicleMovementComponent.h" = @(
        'SetDriveTorque', 'SetBrakeTorque', 'SetTorqueCombineMethod', 'bMechanicalSimEnabled', 'GetWheelState'
    )
    "$plugin/Public/ChaosVehicleWheel.h" = @(
        'ETorqueCombineMethod', 'ExternalTorqueCombineMethod'
    )
    "$plugin/Private/ChaosWheeledVehicleMovementComponent.cpp" = @(
        '::SetupVehicle(', 'if (bMechanicalSimEnabled)', '::ProcessMechanicalSimulation(',
        '::ApplyInput(', '::SetDriveTorque(', '::SetBrakeTorque(', '::SetTorqueCombineMethod(',
        'TorqueMToCm(', '::FillWheelOutputState(', '::ParallelUpdate('
    )
    "$core/Private/WheelSystem.cpp" = @(
        '::Simulate(', 'ExternalDriveTorque', 'ExternalBrakeTorque'
    )
}

$missing = 0
foreach ($relativePath in $checks.Keys) {
    $path = Join-Path $UnrealRoot $relativePath
    Write-Output $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-Output '  FILE NOT FOUND'
        $missing++
        continue
    }

    foreach ($marker in $checks[$relativePath]) {
        $matchesForMarker = @(Select-String -LiteralPath $path -Pattern $marker -SimpleMatch -CaseSensitive)
        if ($matchesForMarker.Count -eq 0) {
            Write-Output "  NOT FOUND: $marker"
            $missing++
            continue
        }

        foreach ($match in $matchesForMarker) {
            Write-Output ('  {0}: {1}' -f $match.LineNumber, $match.Line.Trim())
        }
    }
}

if ($missing -gt 0) {
    Write-Output 'INCOMPLETE: some paths or markers are missing. Check the source installation and file names.'
    exit 2
}

Write-Output 'Source markers found. Review the surrounding code for behavior; this is not a compile or runtime test.'
