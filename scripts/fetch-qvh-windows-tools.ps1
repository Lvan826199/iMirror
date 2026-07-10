param(
    [string]$Destination = "tools"
)

$ErrorActionPreference = "Stop"
$repoZip = "https://github.com/chotgpt/quicktime_video_hack_windows/archive/refs/heads/main.zip"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dest = Join-Path $root $Destination
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("imirror_qvh_tools_" + [System.Guid]::NewGuid().ToString("N"))
$zip = Join-Path $tmp "qvh.zip"

New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
    Write-Host "Downloading quicktime_video_hack_windows tools..."
    Invoke-WebRequest -Uri $repoZip -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $src = Get-ChildItem -Path $tmp -Directory | Where-Object { $_.Name -like "quicktime_video_hack_windows-*" } | Select-Object -First 1
    if (-not $src) {
        throw "Cannot find extracted quicktime_video_hack_windows directory"
    }
    $toolSrc = Join-Path $src.FullName "tool"
    if (-not (Test-Path $toolSrc)) {
        throw "Cannot find tool directory in downloaded archive"
    }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $toolSrc "*") -Destination $dest -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $src.FullName "LICENSE") -Destination (Join-Path $dest "LICENSE") -Force
    Copy-Item -LiteralPath (Join-Path $src.FullName "README.md") -Destination (Join-Path $dest "README.md") -Force
    Write-Host "Done. Tools installed to: $dest"
    Write-Host "Next: .venv\Scripts\python.exe -m imirror windows-poc-check"
} finally {
    if (Test-Path $tmp) {
        Remove-Item -LiteralPath $tmp -Recurse -Force
    }
}
