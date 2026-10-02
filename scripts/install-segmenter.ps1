$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'enter-runtime.ps1')
$taskProject=Split-Path $PSScriptRoot -Parent
Push-Location $taskProject
try {
    & .\.venv\Scripts\python.exe scripts\prepare-segmenter.py
    if($LASTEXITCODE -ne 0){throw 'Pinned source/checkpoint verification failed'}
    & .\.venv\Scripts\python.exe -m pip install --no-deps wheel==0.45.1
    if($LASTEXITCODE -ne 0){throw 'Wheel setup failed'}
    & .\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation hydra-core==1.3.2 omegaconf==2.3.0 antlr4-python3-runtime==4.9.3 iopath==0.1.10 portalocker==3.2.0 pywin32==311
    if($LASTEXITCODE -ne 0){throw 'Segmentation dependencies failed'}
    & .\.venv\Scripts\python.exe -m pip check
    if($LASTEXITCODE -ne 0){throw 'Dependency consistency check failed'}
} finally {Pop-Location}
