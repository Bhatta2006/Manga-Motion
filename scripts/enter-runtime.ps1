# Dot-source this file before running pipeline commands.
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $projectRoot '.runtime'
$cacheRoot = Join-Path $runtimeRoot 'cache'
$env:TEMP = Join-Path $runtimeRoot 'tmp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
$env:HF_HOME = Join-Path $cacheRoot 'huggingface'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:HF_MODULES_CACHE = Join-Path $env:HF_HOME 'modules'
$env:HF_XET_CACHE = Join-Path $env:HF_HOME 'xet'
$env:HF_ASSETS_CACHE = Join-Path $env:HF_HOME 'assets'
$env:HF_TOKEN_PATH = Join-Path $env:HF_HOME 'token'
$env:TORCH_HOME = Join-Path $cacheRoot 'torch'
$env:XDG_CACHE_HOME = Join-Path $cacheRoot 'xdg'
$env:UV_CACHE_DIR = Join-Path $cacheRoot 'uv'
$env:npm_config_cache = Join-Path $cacheRoot 'npm'
$env:PYTHONPYCACHEPREFIX = Join-Path $cacheRoot 'pycache'
$env:PYTHONUSERBASE = Join-Path $runtimeRoot 'python-user'
$env:MPLCONFIGDIR = Join-Path $cacheRoot 'matplotlib'
$env:MANGAMOTION_RUNTIME = $runtimeRoot
@($env:TEMP, $env:PIP_CACHE_DIR, $env:HF_HOME, $env:HF_HUB_CACHE,
  $env:HF_MODULES_CACHE, $env:HF_XET_CACHE, $env:HF_ASSETS_CACHE,
  $env:TORCH_HOME, $env:XDG_CACHE_HOME, $env:UV_CACHE_DIR,
  $env:npm_config_cache, $env:PYTHONPYCACHEPREFIX, $env:PYTHONUSERBASE,
  $env:MPLCONFIGDIR) |
  ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
