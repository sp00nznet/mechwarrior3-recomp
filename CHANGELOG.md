# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [SemVer](https://semver.org/).

## [Unreleased]

The project starts over on the right binary and today's pcrecomp.

### Added
- The whole of `Mech3.exe` recompiled to C with pcrecomp `main`
  (`disasm32`, `generate`, `lift32`): 15,930 functions, 0 lift errors,
  2.53M lines. No toolkit change was needed.
- A 32-bit host on pcrecomp `native32` (`src/runtime/host.c`) that maps
  Mech3.exe, binds its imports to the real Windows, DirectX and MFC42 DLLs
  and runs only lifted code. `--run`, `--game`, `--watchdog`,
  `--native-trace`, `--callbacks`.
- `tools/gamefiles.py`: the game from a CD, a folder, an ISO or a raw
  MDF/BIN (2352 or 2448-byte sectors), unpacked from the InstallShield cab
  with no installer and no registry.
- `tools/catalog.py`: the function catalog from pcrecomp `disasm32` alone.
- `Setup.cmd` / `tools/setup.ps1`: checks and offers to install the
  prerequisites, unpacks the disc, catalogs, lifts, builds and leaves a
  shortcut.
- `tools/conformance.py` and `conformance.json`: boot milestones and lift
  health against a committed baseline. A regression fails the run.
- CI (build checks without the game), a recomp-netlab recipe,
  `docs/architecture.md`, ROADMAP, CONTRIBUTING and NOTICE.

- First `--run`: the lift boots through the CRT, MFC's `AfxWinMain` and the
  game's `InitInstance`, reads its options, opens its window, enumerates
  Direct3D and every subsystem init passes. It stops in the first
  DirectDraw surface `Unlock`, inside NVIDIA's driver, under Windows'
  16-bit DirectDraw emulation (ROADMAP).
- Host fixes found on the way: MFC42's own `GetModuleFileNameA` answers for
  the guest's handle; the game folder is the CD drive; the installer's
  `InstallOptions` key comes from HKCU; the Indeo 5 codec is installed for
  the process; the guest gets its own `lpCmdLine`; stderr is unbuffered and
  a fault names its module.

### Changed
- **The game is `Mech3.exe`, not `HSBR.exe`.** v0.1 catalogued and lifted
  `HSBR.exe` from the disc root, which is the Hasbro launcher (no DirectX
  imports, mostly resources). The game is inside `data1.cab`
  ([docs/architecture.md](docs/architecture.md)).
- pcrecomp is a sibling checkout (`..\tools`, or `PCRECOMP`), as in every
  other port, instead of a vendored copy in `tools/pcrecomp`.

### Removed
- IDA from the build path: `config/functions.json`, `config/ida_names.txt`,
  `docs/IDA_BOOTSTRAP.md`.
- Everything derived from the game binary that was committed:
  `config/`, `analysis/pe_analysis.json`, `analysis/vtables.json`,
  `analysis/phase1_codegen.json`. These are now gitignored. They stay in
  earlier history, which was not rewritten.
- The old `run_pipeline.py`, `CMakeLists.txt` and `src/recomp/recomp_types.h`.

## 0.1.0 - 2026-05-31 (never tagged)

### Added
- First scaffold: IDA-seeded function discovery, a lift of `HSBR.exe` (2,805
  functions) that compiled as a static library. Superseded by the above.
