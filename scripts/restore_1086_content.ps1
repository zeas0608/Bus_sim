# Restore missing, locally generated Content assets from a prior setup snapshot.
# Called only with Unreal Editor CLOSED. Never removes or overwrites existing assets.
# Does NOT run git checkout/stash/clean/reset, import FBX, or write to backups.
function Restore-Missing1086Content {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)] [string] $ProjectRoot,
        [Parameter(Mandatory=$true)] [string] $LogFolder
    )

    $targetContent = Join-Path $ProjectRoot 'Content'
    $targetBus = Join-Path $targetContent 'Kotoden1086'
    $snapshotRoot = Join-Path (Split-Path $ProjectRoot -Parent) 'Recovery_Backup'

    # If a usable map is present, keep the existing Content entirely untouched.
    $existingMaps = @()
    if (Test-Path -LiteralPath $targetBus -PathType Container) {
        $existingMaps = @(Get-ChildItem -LiteralPath $targetBus -Filter 'L_1086_Drive.umap' -File -Recurse -ErrorAction SilentlyContinue)
    }
    if ($existingMaps.Count -gt 0) {
        Write-Host "Kotoden 1086 map exists; no asset recovery needed."
        return
    }

    if (-not (Test-Path -LiteralPath $snapshotRoot -PathType Container)) {
        Write-Warning "No Recovery_Backup folder found. Will not modify existing Content."
        return
    }

    $candidates = @()
    foreach ($snapshot in @(Get-ChildItem -LiteralPath $snapshotRoot -Directory -ErrorAction SilentlyContinue)) {
        $candidateContent = Join-Path $snapshot.FullName 'Content'
        $candidateBus = Join-Path $candidateContent 'Kotoden1086'
        if (-not (Test-Path -LiteralPath $candidateBus -PathType Container)) { continue }
        foreach ($build in @(Get-ChildItem -LiteralPath $candidateBus -Directory -ErrorAction SilentlyContinue)) {
            if ($build.Name -notmatch '^Build_[0-9]{3}$') { continue }
            $map = Join-Path $build.FullName 'L_1086_Drive.umap'
            $pawn = Join-Path $build.FullName 'BP_Kotoden1086.uasset'
            $mode = Join-Path $build.FullName 'BP_KotodenDriveMode.uasset'
            $mesh = Join-Path $build.FullName 'SK_Kotoden1086.uasset'
            $physics = Join-Path $build.FullName 'PA_Kotoden1086.uasset'
            if (@($map, $pawn, $mode, $mesh, $physics) | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }) { continue }
            $candidates += [pscustomobject]@{
                Content = $candidateContent
                Snapshot = $snapshot.FullName
                Build = $build.Name
                LastWrite = $snapshot.LastWriteTimeUtc
            }
        }
    }

    $best = $candidates | Sort-Object @{Expression='Build';Descending=$true},
        @{Expression='LastWrite';Descending=$true} | Select-Object -First 1
    if ($null -eq $best) {
        Write-Warning "No complete 1086 backup snapshot found; no recovery performed."
        return
    }

    # Restore missing files from one consistent snapshot. Skips ALL existing files,
    # including project-specific other Blueprint maps/assets. Config/Source untouched.
    Write-Host "Recovering missing Content assets from $($best.Snapshot) (best bus $($best.Build))."
    $copied = 0
    $skipped = 0
    foreach ($file in @(Get-ChildItem -LiteralPath $best.Content -File -Recurse -ErrorAction Stop)) {
        $relative = $file.FullName.Substring($best.Content.Length).TrimStart([char[]]@('\','/'))
        $destination = Join-Path $targetContent $relative
        if (Test-Path -LiteralPath $destination) { $skipped++; continue }
        $directory = Split-Path -Path $destination -Parent
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            New-Item -ItemType Directory -Force -Path $directory | Out-Null
        }
        # Do not use -Force: an unexpected concurrent file creation must stop recovery.
        Copy-Item -LiteralPath $file.FullName -Destination $destination -ErrorAction Stop
        $copied++
    }

    $report = Join-Path $LogFolder 'LatestRecoveryResult.txt'
    @(
        'RECOVERED'
        "Snapshot: $($best.Snapshot)"
        "BusBuild: $($best.Build)"
        "CopiedMissing: $copied"
        "ExistingSkipped: $skipped"
        'No existing file was overwritten; Config and Source untouched.'
    ) | Set-Content -LiteralPath $report -Encoding UTF8

    Write-Host "Recovery copied $copied missing assets; skipped $skipped existing files."
    Write-Host "Recovery details: $report"
}
