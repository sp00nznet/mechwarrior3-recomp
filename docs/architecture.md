# Architecture

How MechWarrior 3 gets from your disc to a native program, what each part
owns, and why it is built this way. The code it describes:
[tools/gamefiles.py](../tools/gamefiles.py), [tools/catalog.py](../tools/catalog.py),
[run_lift.py](../run_lift.py), [src/runtime/host.c](../src/runtime/host.c).

## The pipeline

```
your disc / ISO / MDF
   │  tools/gamefiles.py   (pcrecomp iso_peek + isextract)
   ▼
game/                      Mech3.exe, MFC42.DLL, MSVCP50.DLL, IFORCE2.dll, zbd\, video\
   │  tools/catalog.py     (pcrecomp disasm32)
   ▼
work/functions.json        15,923 functions, 94.7% of the code bytes
   │  run_lift.py          (pcrecomp generate + lift32)
   ▼
src/recomp/gen/*.c         15,930 lifted functions + the dispatch table
   │  build.cmd            (MSVC x86, CMake, Ninja)
   ▼
build/mw3.exe              host.c + pcrecomp native32 + the lifted C
```

`game/`, `work/` and `src/recomp/gen/` are gitignored. Everything in them is
the game or derived from it, so it is rebuilt on each machine from the user's
own copy and never committed.

## Which binary is the game

**`Mech3.exe`, not `HSBR.exe`.** The disc's root holds `HSBR.exe` beside
`Setup.exe`, and the first version of this project (May 2026) catalogued and
lifted that file. It is the Hasbro launcher: 320 KB of code, 1.8 MB of
resources (the autorun screens), and imports only KERNEL32, USER32, GDI32,
SHELL32, COMCTL32, MSVFW32, WINSPOOL and comdlg32. No DirectX at all.

The game is inside `data1.cab`, which only the installer unpacks:

| | `HSBR.exe` (launcher) | `Mech3.exe` (game) |
|---|---|---|
| `.text` | 0x4F0E5 (316 KB) | 0x1B3D58 (1.70 MB) |
| `.rsrc` | 0x1BB7B0 (1.7 MB) | 0x52590 |
| Imports | no DirectX | DDRAW, DSOUND, DINPUT, DPLAYX, IFORCE2, MFC42, MSVCP50, AVIFIL32, MSVFW32, WINMM |
| Entry | 0x00417C60 | 0x005A6520 |

That is why the old IDA catalog (2,814 functions) and its lift were thrown
away rather than carried forward.

## The disc

The disc is an InstallShield 5 setup. `data1.hdr`/`data1.cab` hold the
program, its runtime DLLs and the `zbd\` archives (about 520 MB). `video\`
sits loose on the disc, and the installer copies it. `REDIST\` is DirectX 6
for Windows 98, which is not needed.

`gamefiles.py` reads a drive, a folder, a 2048-byte ISO or a raw image. The
original dump here is an Alcohol 120% MDF with **2448-byte sectors**: 2352
raw plus 96 bytes of subchannel. It hands the installer files to pcrecomp's
`isextract.py`, which lays the install out exactly as `Setup.exe` would. It
does not run setup and does not write to the registry. From the MDF and from
the ISO, the result is byte-identical.

## The catalog: no IDA

`disasm32` runs recursive descent from the entry point, then prologue
detection, then a data scan for pointers into code. Mech3.exe was built
without RTTI (`cpp/rtti.py` finds one class), so its virtual methods are
found only by that data scan: 5,203 functions are reachable only through a
data pointer (vtables, MFC message maps, callback tables). The whole run takes
about 2 minutes.

The old catalog came from IDA. Section 10 of the house rules keeps IDA and
Ghidra out of the default build path, so it is not used here. It would only
be useful as a reference for `score_recovery.py`.

## The host: native32

`build/mw3.exe` is a 32-bit process linked at 0x60000000, so Mech3.exe's
range (0x00400000-0x009EE000) is free. pcrecomp's `native32`:

- maps Mech3.exe at its own base, with its code pages non-executable;
- binds its imports to the real DLLs: Windows, DirectX and the game's own
  `MFC42.DLL` and `MSVCP50.DLL`, loaded from `game\` through
  `SetDllDirectoryA`;
- runs every guest function as lifted C. A call into a real DLL goes through
  the native bridge. A call back into the guest (a WndProc, an MFC virtual
  such as `CWinApp::InitInstance`) faults on the non-executable page and is
  redirected to the lifted body.

`host.c` adds only what is specific to the game. `GetModuleHandleA(NULL)`,
`GetModuleFileNameA` and `GetCommandLineA` answer for Mech3.exe instead of
the host, because the CRT startup hands that module to MFC's `AfxWinMain`,
which loads its dialogs and strings from it. `ExitProcess` is logged. A fault
report and a `--watchdog` complete the host.

Without `--run`, the host only maps and binds the image. That opens no
window, so it is safe over RDP and on a test VM.
