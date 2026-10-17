# MechWarrior 3 — Static Recompilation

Static recompilation of **MechWarrior 3** (Zipper Interactive / MicroProse /
Hasbro Interactive, 1999), from its shipping Win32 executable to native C that
builds on Windows 10 and 11.

Built on the [pcrecomp](https://github.com/sp00nznet/pcrecomp) toolchain and
following its shared house style (layout, CLI, conformance harness). Generated
source is **not** distributed: you bring your own disc and the pipeline
rebuilds everything locally.

## Status: **v0.2.0-dev, early bring-up. The whole game lifts and builds; it has not been run yet.**

| Stage | State |
|---|---|
| Identify the binary | `Mech3.exe` (VC6 + MFC42, DirectX 6, no protection). `HSBR.exe`, which v0.1 lifted, turned out to be the Hasbro launcher ([docs/architecture.md](docs/architecture.md)) |
| Game files | unpacked from your disc, ISO or MDF by `tools/gamefiles.py`, with no installer and no registry |
| Function catalog (`disasm32`, no IDA) | 15,923 functions, 94.7% of the code bytes, about 2 minutes |
| Lift (`run_lift.py`) | **whole program**: 15,930 functions, 0 lift errors, 2.53M lines of C. pcrecomp `main`, no toolkit change |
| Host (`build/mw3.exe`, 32-bit, pcrecomp `native32`) | builds (netlab clang-cl, 4.5 min cold). Maps Mech3.exe and binds all 472 imports: 461 to the real Windows, DirectX and MFC42 DLLs, 11 shimmed, 0 unresolved |
| Running the game | not tried yet: see [ROADMAP.md](ROADMAP.md) |

Conformance (`tools/conformance.py`, figures in `conformance.json`):
**2/4 milestones** (the two a dry run can reach; the other two need `--run` on a display). Lift health: 0 errors, 63 functions with no terminator, 1 unresolvable ITAIL target, 12 UNIMPLEMENTED instructions.

## Screenshots

None yet: the game has not been run. The first ones will come from a recorded
run (`offstage run --record`) and go in `docs/screenshots/`.

## What is not in this repo

The game, and anything made from it. `game/` (your install), `work/` (the
catalog and the lift statistics) and `src/recomp/gen/` (the lifted C) are
built on your machine and gitignored. See [NOTICE](NOTICE).

## Getting Started

You need your **MechWarrior 3 CD** (in a drive, or as an `.iso` or `.mdf`
image), Windows 10 or 11, and about 3 GB free.

### Quick start

1. Download this repository and [pcrecomp](https://github.com/sp00nznet/pcrecomp)
   side by side, with pcrecomp in a folder named `tools`:
   ```
   somewhere\mechwarrior3-recomp\
   somewhere\tools\              <- pcrecomp
   ```
   (If `tools` is missing, Setup offers to fetch it with git.)
2. Double-click **`Setup.cmd`**. It checks for Python, the Python packages,
   Visual Studio, CMake and Ninja, and asks before installing anything
   missing. It then finds your disc, or asks for its path, unpacks it into
   `game\`, catalogs, lifts and builds. Expect 20 to 40 minutes the first
   time. A rerun skips what is done.
3. When it says **Done**, `MechWarrior 3 (recomp).cmd` is in the folder.
   Expect early bring-up: see Status.

If it stops, it says why in one line, and the full log is `setup.log`.

### Step by step

Prerequisites: **Python 3.10+** with `pefile` and `capstone`, **Visual Studio
2022** (or its Build Tools) with *Desktop development with C++*, **CMake
3.20+** and **Ninja**. These are exactly the commands Setup runs.

```bat
:: 0. the toolkit, beside this repo
git clone https://github.com/sp00nznet/pcrecomp ..\tools
py -3 -m pip install --user pefile capstone

:: 1. your disc -> game\   (a drive, a folder, an .iso or an .mdf)
py -3 tools\gamefiles.py D:\path\to\MW3.mdf
::   reading 303 files (519 MB) from D:\path\to\MW3.mdf
::   ...
::   done: ...\game

:: 2. the function catalog -> work\functions.json
py -3 tools\catalog.py
::   [*] Functions: 15923  (thunks=275, leaves=6368)
::   [*] Byte coverage: 1,690,437 / 1,785,344 (94.7% of code range)

:: 3. the lift -> src\recomp\gen\
py -3 run_lift.py
::   lifted 15930   errors 0   no terminator 63
::   2,529,059 lines of C in 40 files

:: 4. the host -> build\mw3.exe
build.cmd

:: 5. map and bind Mech3.exe (no window)
build\mw3.exe
```

The usual trip-ups:

- **`python` opens the Microsoft Store.** That is the Store's placeholder.
  Use `py -3`, or turn off the alias under *Settings > Apps > Advanced app
  settings > App execution aliases*.
- **A tool installed but "not found".** PATH changes reach new windows only:
  open a new terminal.
- **pcrecomp somewhere else.** Set `PCRECOMP` to its folder before steps 1-3,
  and run `set CMAKE_ARGS=-DPCRECOMP=<folder>` before step 4.
- **`build.cmd` uses the 64-bit-hosted x86 compiler** (`amd64_x86`): the
  32-bit `cl.exe` runs out of heap on a 400-function chunk.

## Usage

```
build\mw3.exe                       map Mech3.exe and bind its imports, then stop
build\mw3.exe --run                 run the game (opens its window)
build\mw3.exe --run --watchdog 30   ...and stop after 30 s with a report of where it is
build\mw3.exe --game D:\mw3         use an install somewhere other than game\
build\mw3.exe --native-trace        one line per call into Windows or DirectX
build\mw3.exe --callbacks           one line per call from Windows back into the game
py -3 tools\conformance.py [--run]  the conformance harness
```

A fault prints the lifted function it happened in, the last native call, the
registers and the last indirect calls.

`--headless --record out.mp4`, the house style's headless mode, is not in
yet ([ROADMAP.md](ROADMAP.md)).

## Building from source

Steps 2 to 4 above are the whole build. On a machine with
[recomp-netlab](https://github.com/sp00nznet/recomp-netlab), `netlab build
mechwarrior3-recomp` compiles on the farm instead (recipe
`projects/mechwarrior3-recomp.env`). The lifted C goes over, and the game does
not.

[docs/architecture.md](docs/architecture.md) explains how the parts fit.

## Contributors

See [CONTRIBUTING.md](CONTRIBUTING.md). No outside contributions yet.

## License

MIT for what is ours (the host, the tools, the docs): [LICENSE](LICENSE).
MechWarrior 3 itself is not covered, and lifted code carries the original's
licence, not this one: [NOTICE](NOTICE).
