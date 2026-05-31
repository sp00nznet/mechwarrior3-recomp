# MechWarrior 3 — Static Recompilation

A static recompilation of **MechWarrior 3** (1999, Zipper Interactive / Hasbro
Interactive / MicroProse), targeting modern Windows with native x86 execution.

This is a game-preservation project. MechWarrior 3 runs on the Zipper Interactive
**GameZ/GOS engine** — the same engine as **Crimson Skies** (2000) and **Recoil**
(1999). Tooling and findings carry across all three.

> *"Pilot. The 'Mech is ready."*

## Why this game

- **Shared GOS engine.** Cross-validation tooling, the function-discovery approach,
  and even some engine structures are common with Crimson Skies and Recoil.
- **Clean binary.** Unlike Crimson Skies and X-Wing Alliance (both SafeDisc, needing
  runtime memory dumps), MW3's `HSBR.exe` is **not encrypted** — it analyzes directly.
- **VC6 / MFC.** Visual C++ 6.0 with MFC42 + DirectX 6, so IDA's FLIRT signatures name
  a large fraction of the library surface for free.

## Project status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0** | **Complete** | Disc extraction (MDF→ISO), binary triage, **IDA-seeded function discovery** |
| **Phase 1** | **Complete** | x86→C code generation — **2,805 functions, 0 lift errors**, 158K lines |
| **Phase 2** | **Complete** | Compilation — **all 7 translation units compile** (MSVC x86, 0 errors) as a static lib |
| Phase 3 | Pending | Executable link: Win32/MFC42 runtime, register/memory model, import bridges |
| Phase 3 | Pending | Runtime bringup — CRT init, MFC42 bridges, imports |
| Phase 4 | Pending | Win32/DirectX 6 HAL (DDraw/D3D/DInput/DSound COM mocks) |
| Phase 5 | Pending | GOS engine abstraction — rendering, audio, input |
| Phase 6 | Pending | Asset loading |
| Phase 7+ | Pending | Mission/sim logic, modern rendering backend |

## Binary

| Property | Value |
|----------|-------|
| **Target** | `HSBR.exe` (2.26 MB) |
| **Compiler** | Visual C++ 6.0 + MFC42, DirectX 6 |
| **Architecture** | x86-32, PE32, image base `0x00400000` |
| **Code (.text)** | `0x00401000` – `0x00451000` (~320 KB) |
| **Entry point** | `0x00417C60` |
| **DRM** | none on `HSBR.exe` (clean) |

## Phase 0: IDA-seeded discovery

Function discovery was bootstrapped with **IDA Pro 9.1** rather than a call-graph
sweep. This matters: IDA follows **vtables**, so virtual methods reached only through
a vtable pointer are captured from the start. (On the sister project Crimson Skies,
call-graph discovery missed ~770 such virtual methods — this scaffold avoids that gap.)

| Artifact | Value |
|----------|-------|
| `config/functions.json` | **2,814** functions |
| `config/ida_names.txt` | **1,629** FLIRT-identified names (MFC42 / VC6 CRT / std) |
| `analysis/vtables.json` | **168** vtables → **950** virtual methods (**all 950** in functions.json) |
| `analysis/pe_analysis.json` | sections / entry / base |

Regenerate with the [ida-recomp-toolkit](https://github.com/sp00nznet/ida-recomp-toolkit):
```
py -3.11 tools/mw3_bootstrap.py HSBR.exe config/ analysis/
```

## Phase 1: x86 → C code generation

`run_pipeline.py` lifts every function in `config/functions.json` to C using the
shared `pcrecomp` lifter (Capstone-based), **seeding entries from the IDA list** so
all 950 virtual methods are lifted from the start:

| Result | Value |
|--------|-------|
| Functions lifted | **2,805** |
| Lift errors | **0** |
| Output | 158,645 lines of C, 7.2 MB, 6 files |

```
py -3.11 run_pipeline.py            # -> src/recomp/gen/recomp_*.c
```

The generated `src/recomp/gen/` is **not committed** (regenerable from `HSBR.exe` +
the function list). Phase 2 will add a CMake C build + the Win32/MFC42 runtime
bridges (the lifter and `recomp_types.h` are the same ones Crimson Skies already
compiles cleanly).

## Layout

```
config/     functions.json, ida_names.txt    (the recomp's function table — committed)
analysis/   pe_analysis.json, vtables.json    (derived binary metadata — committed)
src/        recompiled / HAL / engine sources (to be generated)
tools/      project-specific scripts
docs/       analysis notes & handoffs
```

> **Game data is not in this repo.** `HSBR.exe`, the disc image (`.mdf`/`.iso`), and
> any extracted assets are `.gitignore`d. Supply your own legally-obtained copy.
