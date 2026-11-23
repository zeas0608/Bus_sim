# Return the latest complete generated driving level. File system checks are read-only.
function Find-1086Level([string] $ContentRoot) {
    if (-not (Test-Path -LiteralPath $ContentRoot -PathType Container)) { return }
    $folders = @(Get-ChildItem -LiteralPath $ContentRoot -Directory |
        Where-Object { $_.Name -match '^Build_[0-9]{3}$' } | Sort-Object Name -Descending)
    foreach ($folder in $folders) {
        $map = Join-Path $folder.FullName 'L_1086_Drive.umap'
        if ((Test-Path -LiteralPath $map -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $folder.FullName 'BP_Kotoden1086.uasset') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $folder.FullName 'BP_KotodenDriveMode.uasset') -PathType Leaf)) {
            return Get-Item -LiteralPath $map
        }
    }
}
