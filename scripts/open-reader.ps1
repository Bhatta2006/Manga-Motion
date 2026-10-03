# Run this yourself to open the reader in its dedicated D-drive Edge profile.
param([int]$Port=5174)
$ErrorActionPreference='Stop'
. "$PSScriptRoot\enter-runtime.ps1"
if($Port -lt 1024 -or $Port -gt 65535){throw 'Port must be 1024–65535'}
$readerProfile=Join-Path $env:MANGAMOTION_RUNTIME 'reader-browser'
$readerCache=Join-Path $env:MANGAMOTION_RUNTIME 'reader-browser-cache'
foreach($folder in @($readerProfile,$readerCache)){if([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($folder)) -ne 'D:\'){throw 'Reader profile/cache must be on D:'};New-Item -ItemType Directory -Force -Path $folder | Out-Null}
$edgeCandidates=@("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe","$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")
$readerBrowser=$edgeCandidates | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
if(!$readerBrowser){throw 'Installed Edge was not found; no browser download was attempted'}
& $readerBrowser "--user-data-dir=$readerProfile" "--disk-cache-dir=$readerCache" '--no-first-run' '--new-window' "http://127.0.0.1:$Port/?offline=enabled"
