param([string]$ModelSpec='pipeline/director/local-runtime.json')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\enter-runtime.ps1"
$ProgressPreference = 'SilentlyContinue'
$projectRoot = Split-Path $PSScriptRoot -Parent
$binaryRoot = Join-Path $projectRoot '.runtime\llama-b11323'
$modelSpecPath=[IO.Path]::GetFullPath((Join-Path $projectRoot $ModelSpec))
if ($modelSpecPath -notlike 'D:\Motion Manga\*') { throw 'Model specification must be in the D-drive workspace' }
$modelDefinition=Get-Content -LiteralPath $modelSpecPath -Raw | ConvertFrom-Json
$weightRoot = Join-Path $projectRoot $modelDefinition.model_root
function Assert-PlainPath([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Installation path contains a link: $cursor" }
        }
        $cursor=Split-Path $cursor -Parent
    }
}
foreach ($targetRoot in @($binaryRoot,$weightRoot)) {
    if ([IO.Path]::GetFullPath($targetRoot) -notlike 'D:\Motion Manga\*') { throw 'Director installation must remain in the D-drive workspace' }
    Assert-PlainPath $targetRoot
    New-Item -ItemType Directory -Force $targetRoot | Out-Null
}
$downloads = @(
    @{Name='llama.zip';Root=$binaryRoot;URL='https://github.com/ggml-org/llama.cpp/releases/download/b11323/llama-b11323-bin-win-cuda-12.4-x64.zip';SHA='17f676bde0ddeb365506310c8a20e2a26b314aca3dfd3cd3f8af87d80401d1b2'},
    @{Name='cudart.zip';Root=$binaryRoot;URL='https://github.com/ggml-org/llama.cpp/releases/download/b11323/cudart-llama-bin-win-cuda-12.4-x64.zip';SHA='8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6'}
)
foreach ($weight in $modelDefinition.weights) {
    if ([IO.Path]::GetFileName($weight.file) -ne $weight.file) { throw 'Invalid weight filename' }
    $downloads += @{Name=$weight.file;Root=$weightRoot;URL="https://huggingface.co/$($modelDefinition.model_id)/resolve/$($modelDefinition.revision)/$($weight.file)";SHA=$weight.sha256}
}
foreach ($item in $downloads) {
    $destination = Join-Path $item.Root $item.Name
    Assert-PlainPath $destination
    Assert-PlainPath "$destination.part"
    if (-not (Test-Path -LiteralPath $destination) -or (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLower() -ne $item.SHA) {
        Write-Output "Downloading $($item.Name) to D:"
        Invoke-WebRequest $item.URL -OutFile "$destination.part"
        if ((Get-FileHash -LiteralPath "$destination.part" -Algorithm SHA256).Hash.ToLower() -ne $item.SHA) { throw "Checksum mismatch: $($item.Name)" }
        Move-Item -LiteralPath "$destination.part" -Destination $destination -Force
    }
    if ($item.Name.EndsWith('.zip')) { Expand-Archive -LiteralPath $destination -DestinationPath $binaryRoot -Force }
    Write-Output "Verified $($item.Name)"
}
Get-ChildItem -LiteralPath $binaryRoot -Filter 'llama-server.exe' -Recurse | Select-Object FullName
