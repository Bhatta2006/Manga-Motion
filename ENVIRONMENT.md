# Environment baseline — 2026-09-30

Read-only checks on the target laptop. This is an installation baseline, **not** an M0 model benchmark. Values such as free memory change with running programs.

| Item | Observed result | Evidence / interpretation |
|---|---|---|
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU, compute capability 8.9 | `nvidia-smi --query-gpu=name,compute_cap --format=csv` |
| VRAM | 6,141 MiB total; 5,920 MiB free; 221 MiB reserved, 0 MiB used at check | `nvidia-smi --query-gpu=memory.total,memory.free --format=csv`; this is less than a full 6 GiB available to a model |
| Driver / CUDA | NVIDIA driver/KMD 610.74; CUDA driver API reported 13.3; `nvcc` absent from PATH | `nvidia-smi --query`, `Get-Command nvcc`; PyTorch/CUDA runtime compatibility remains to be verified at install |
| GPU power | About 60 W default/current limit, 75 W reported maximum | `nvidia-smi --query`; throughput will depend on laptop power and thermals |
| System RAM | 15.65 GiB total, 2.56 GiB free at check | Node `os.totalmem()` and `os.freemem()`; close memory-heavy apps before benchmarks |
| OS | Windows 11 Home Single Language x64, release/build 10.0.26200 (25H2, build 26200.9550) | Node `os.version()` plus registry; legacy registry `ProductName` says Windows 10, so the OS API was preferred |
| WSL2 | `wsl.exe` exists, but `wsl --version` and `wsl --list --quiet` both failed with “The system cannot find the file specified.” No usable distro or WSL2 runtime confirmed | Do not assume WSL2 is ready; M0 uses native Windows first unless a verified dependency requires WSL2 |
| Python | `python`, `py`, and `nvcc` not found on PATH | Python 3.11 must be provisioned on D: before M0; no install performed in Step 1 |
| Node / npm | Node v24.21.0; npm 11.19.0 | `node --version`, `npm --version`; project versions will be pinned after compatibility checks |
| FFmpeg | FFmpeg 8.1 essentials build; `ffprobe` present, both under `D:\tools\ffmpeg` | `ffmpeg -version`, `Get-Command ffmpeg,ffprobe` |
| Storage | D: about 77.61 GiB free; C: about 13.79 GiB free | `Get-PSDrive`; all project downloads, virtual environments, package/model caches, logs and temporary artifacts must be on D: |
| Repository | Only the supplied PRD existed; no `.git` directory, tests, data, or code | `rg --files`, `git status`; Git initialization belongs to M0a, after plan approval |

## Reproducibility note

The PRD was supplied as `mangamotion-prd(1).md`; an exact SHA-256-identical copy now lives at `docs/PRD.md`, the requested canonical path. Both hashes are `A007D3F5CAB446C26FC3FDB74BC3A19C616260E10FC3FE05AE78B61A745E6C5D`.

No model, package, or repository was downloaded or run during Step 1. Peak model VRAM and seconds per page are therefore **not measured yet**; M0a records them on the real pages.
