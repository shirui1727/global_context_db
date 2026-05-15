param(
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $OutputDir) {
    $OutputDir = Join-Path (Split-Path $RepoRoot -Parent) "release"
}

$YamlPath = Join-Path $RepoRoot "docker-compose.yaml"
$YmlPath = Join-Path $RepoRoot "docker-compose.yml"
if (Test-Path $YmlPath) {
    throw "Do not ship docker-compose.yml. This NAS project uses docker-compose.yaml only."
}
if (-not (Test-Path $YamlPath)) {
    throw "Missing docker-compose.yaml."
}

$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$StageRoot = Join-Path $OutputDir "nas_overlay_bundle"
$ProjectRoot = Join-Path $StageRoot "global_context_db"
$ZipPath = Join-Path $OutputDir "global_context_db.zip"

if (Test-Path $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Path $ProjectRoot -Force | Out-Null

$Items = @(
    ".dockerignore",
    ".gitignore",
    "app",
    "desktop\extension",
    "docs",
    "docker-compose.yaml",
    "Dockerfile",
    "pyproject.toml",
    "README.md"
)

foreach ($Item in $Items) {
    $From = Join-Path $RepoRoot $Item
    if (Test-Path $From) {
        $To = Join-Path $ProjectRoot $Item
        $Parent = Split-Path $To -Parent
        if (-not (Test-Path $Parent)) {
            New-Item -ItemType Directory -Path $Parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $From -Destination $To -Recurse -Force
    }
}

$BlockedDirs = @("__pycache__", "node_modules", "dist", "release", ".git", "data")
Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force |
    Where-Object { $_.PSIsContainer -and ($BlockedDirs -contains $_.Name) } |
    Sort-Object FullName -Descending |
    Remove-Item -Recurse -Force

Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force |
    Where-Object { -not $_.PSIsContainer -and ($_.Extension -in @(".pyc", ".pyo")) } |
    Remove-Item -Force

Compress-Archive -Path (Join-Path $StageRoot "global_context_db") -DestinationPath $ZipPath -Force

Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $Entries = $Zip.Entries
    $BadEntries = $Entries | Where-Object {
        $_.FullName -like "global_context_db/data/*" -or
        $_.FullName -like "global_context_db/.git/*" -or
        $_.FullName -like "*node_modules*" -or
        $_.FullName -like "*docker-compose.yml"
    }
    if ($BadEntries) {
        $Names = ($BadEntries | Select-Object -First 10 -ExpandProperty FullName) -join ", "
        throw "Package contains blocked entries: $Names"
    }

    $RequiredEntries = @(
        "global_context_db/app/api.py",
        "global_context_db/app/core/config.py",
        "global_context_db/docker-compose.yaml"
    )
    foreach ($Required in $RequiredEntries) {
        if (-not ($Entries | Where-Object { $_.FullName -replace "\\", "/" -eq $Required })) {
            throw "Package is missing required entry: $Required"
        }
    }
}
finally {
    $Zip.Dispose()
}

if (Test-Path $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}

Get-Item $ZipPath | Select-Object FullName, Length, LastWriteTime
