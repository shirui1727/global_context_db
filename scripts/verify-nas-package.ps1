param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath
)

$ErrorActionPreference = "Stop"

$ZipPath = (Resolve-Path $ZipPath).Path
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $Entries = $Zip.Entries
    $Names = $Entries | ForEach-Object { $_.FullName -replace "\\", "/" }

    $Required = @(
        "global_context_db/app/api.py",
        "global_context_db/app/core/config.py",
        "global_context_db/docker-compose.yaml"
    )
    foreach ($Item in $Required) {
        if ($Names -notcontains $Item) {
            throw "Missing required entry: $Item"
        }
    }

    $Blocked = $Names | Where-Object {
        $_ -like "global_context_db/data/*" -or
        $_ -like "global_context_db/.git/*" -or
        $_ -like "*node_modules*" -or
        $_ -like "*docker-compose.yml"
    }
    if ($Blocked) {
        throw "Blocked entries found: $(($Blocked | Select-Object -First 10) -join ', ')"
    }

    [pscustomobject]@{
        Ok = $true
        ZipPath = $ZipPath
        Entries = $Entries.Count
        Compose = "global_context_db/docker-compose.yaml"
        ProjectRoot = "global_context_db/"
    }
}
finally {
    $Zip.Dispose()
}
