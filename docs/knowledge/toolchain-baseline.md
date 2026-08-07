# Stage 1 Toolchain Baseline

Recorded: 2026-08-07

## Finding

The current WSL2 checkout can build HG-Engine and boot its output headlessly with the project-owned Stage 1 wrapper. The base ROM remains a local ignored input. The important host tools are versioned below, but the bootstrap is not yet fully reproducible because several Make downloads and Python requirements resolve unpinned versions.

Confidence: **confirmed by local build and emulator smoke test** for this machine; **confirmed by source inspection** for pin status; a clean-machine bootstrap remains untested.

## Repository baseline

| Component | Revision | Status |
|---|---|---|
| Project checkout | `417f4ff0ccfb8a451d7f2c46f4fc3c8d982a32ac` | Exact Git commit; includes the local devkitARM assembler include-path fix. |
| HG-Engine upstream reference | `c6d63fd8a34f63431214284dc08c3b7942ab0593` | Exact local `upstream/main` reference at the time of recording. |
| NitroGFX submodule | `a8fd94a3e582ded71eda5b9f5f0c69258544bb22` | Pinned by the repository submodule. |

## Host baseline

| Tool/platform | Actual version |
|---|---|
| Host | Ubuntu 26.04 LTS under WSL2, Linux `6.6.87.2-microsoft-standard-WSL2`, x86-64 |
| Python in `.venv` | 3.14.4 |
| GNU Make | 4.4.1 |
| Git | 2.53.0 |
| GCC / G++ | Ubuntu 15.2.0 |
| CMake | 4.2.3 |
| Autoconf | 2.72 |
| Automake | 1.18.1 |
| pkg-config | 2.5.1 |
| `arm-none-eabi-gcc` | 14.2.1 (2024-11-19 build) |
| `arm-none-eabi-ld` / `objcopy` | binutils 2.45.50.20251209 |
| libpng | Detected successfully through `pkg-config --exists libpng` |

The repository does not have a system `python` executable on this machine. Activate `.venv` before using the documented `python -m tools.pokeagent ...` command surface. `python3` is available and remains the interpreter Make uses to bootstrap the virtual environment.

## Python environment

| Distribution | Installed version | Requirement status |
|---|---:|---|
| ndspy | 4.1.0 | Pinned exactly as `ndspy==4.1.0`. |
| pandas | 3.0.5 | Unpinned in `requirements.txt`. |
| Pillow | 12.3.0 | Unpinned in `requirements.txt`. |
| py-desmume | 0.0.9 | Unpinned in `requirements.txt`; bundled emulator reports DeSmuME 0.9.12 at runtime. |

The installed versions above are evidence, not a lock file. Recreating `.venv` later may resolve different pandas, Pillow, or py-desmume versions.

## Downloaded and generated tools

| Tool | Provenance/version | Pin status | Local SHA-256 |
|---|---|---|---|
| `tools/ndstool` | ndstool 2.1.2; Make checks out `fa6b6d01881363eb2cd6e31d794f51440791f336` | Pinned commit | `08f00008cc5eedaab83a0400e3622a36c1667dc38555479be72e43dc81ca9bf7` |
| `tools/nitrogfx` | Submodule `a8fd94a3e582ded71eda5b9f5f0c69258544bb22` | Pinned commit | `e807975bde674a8a66227d3f8776f60c9e620b3602f40ae44935c94fe0937391` |
| `tools/armips` | armips 0.11.0, built 2026-08-07 | **Unpinned branch-tip clone**; source directory is deleted after build, so the resolved commit is unavailable | `49b182e2528388bfa3e1bdc0349f0b9e01e14af050d69d3f261304527a5c4c42` |
| `tools/adpcm-xq` | `dbry/adpcm-xq` default branch | **Unpinned branch-tip clone** | `98292f7d489ea7c53da3c42c39696f15318b3c2ede2bed2d40315cdb50c117e8` |
| `tools/ntrWavTool.py` | `turtleisaac/ntrWavTool` default branch | **Unpinned branch-tip clone** | `61898fb95e54b5c85d6ac68cf6b0792cfd2121d16418ed26dc579b9e4b93aa52` |

Project-hosted tools are tied to the project Git revision at the source level, but their binaries still depend on the host compiler:

| Generated/local tool | Local SHA-256 |
|---|---|
| `tools/msgenc` | `c7c2c9d9e71431788b7a8bb23bfd9ad9ae4e1c95b20949a75f6781848fc5e3a4` |
| `tools/o2narc` | `ae0b0bb9378674f2203bd3850fd76e5431726b06d9b8142480ef343154a2b6aa` |
| `tools/movedatagen` | `be8adfa83ad64124fdb888070794ed8e1ed7d866d5e6111f560b19234cda46fc` |
| `tools/pokedexdatagen` | `9cf12b93ea1c4aca8c54e260189dd9c4e4a4446d16f750bbba25aaf74b5aa67a` |
| `tools/speciesdatagen` | `7146928b9a3ef9c146540e91c547a3d5561ff9534ca6bfb60347abe8fd2faef` |
| `tools/trainerdatagen` | `8f2c76ed0597c4eec41979e53601b31cdee02d50770296a1da07a85f3a2329d4` |
| `tools/btx` | `bbf87e66e99a2d63a0cc0b6a25466e3b2d7c9e13e375244c109262d6f3bfbd65` |
| `tools/ENCODE_IMG` | `1a5b5c9b14082041b217e2cbdbdbbeb53cc2bc5d4a0212bec945fdfebfb70f57` |
| `tools/SDATTool.py` | `9806c62b206c9aafca4e8ea044f6bd627e3f232444df3dd8d4875e9803d0ee15` |
| `tools/narcpy.py` | `a8390787df8112382f2268643a3615611c1d5ce18cb6a07a7488bcd154268e69` |

## Container status

`Dockerfile` uses the mutable `ubuntu:22.04` tag and unpinned Apt repositories. Docker is not available inside this WSL distribution, so the container path was not built. Stage 1 adds `.dockerignore` to prevent ROMs, extracted files, generated ROMs, saves/states, build reports/screenshots, `.git`, `.venv`, and local generated tool binaries from entering the context. Required source PNGs and tool sources remain available to the Docker build.

## Reproduction commands

From the repository root, with a legally supplied US HeartGold ROM at ignored `rom.nds`:

```bash
git submodule update --init --recursive
make venv
. .venv/bin/activate
python -m tools.pokeagent preflight
python -m tools.pokeagent rom build
python -m tools.pokeagent rom smoke
python -m unittest discover -s tests -v
```

Machine-readable CLI output is available by appending `--json`. Full build/smoke logs and compact JSON reports are written under ignored `build/pokeagent/`.

To run the two local-ROM integration tests explicitly:

```bash
POKEAGENT_RUN_INTEGRATION=1 python -m unittest discover -s tests -v
```

## Evidence

- `Makefile`: authoritative build, host prerequisites, tool downloads, and ndstool pin.
- `requirements.txt`: Python dependency constraints.
- `.gitmodules`: NitroGFX source declaration; `git submodule status` supplied the exact revision.
- `Dockerfile` and `.dockerignore`: container baseline and context boundary.
- `build/pokeagent/build-report.json`: ignored local Make command, timing, ROM identity, sizes, and hashes.
- `build/pokeagent/smoke-report.json`: ignored local emulator frames, input, screenshot analysis, timing, and hashes.

## Remaining unknowns and reproducibility risks

- A fresh Ubuntu 22.04 container or clean WSL machine has not run the complete bootstrap.
- Armips, adpcm-xq, and ntrWavTool download branch tips instead of exact commits.
- pandas, Pillow, and py-desmume are not pinned in `requirements.txt`.
- The Docker base image and Apt packages are not digest/version pinned.
- Host-compiled helper binaries are not proven byte-identical across compiler or platform versions.
- DeSmuME screenshots and save behavior may differ across py-desmume/emulator versions; melonDS and hardware compatibility are not covered by Stage 1.
- The existing battle integration suite still needs the ignored `test.sav` fixture, which is absent locally.

No dependency upgrade or broad pinning change was attempted in Stage 1. These risks should be addressed incrementally after the Stage 1 command surface is stable.
