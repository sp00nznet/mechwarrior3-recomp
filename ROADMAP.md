# Roadmap

What is next, what is deferred, and what is out of scope. What is true today
is in the README's Status section and in `docs/`.

## Next

- **First `--run`.** Enter the CRT startup on a display (at the console under
  offstage), and record how far MFC's `AfxWinMain` and the game's
  `InitInstance` get. Each new stage becomes a conformance milestone.
- **Headless mode** (`--headless --record out.mp4`), required of every recomp
  by the house style. MechWarrior 3 draws through DirectDraw and Direct3D 6,
  so this needs a host-side DirectDraw like Virtual Springfield's
  (`src/runtime/ddraw.c` there), extended to Direct3D's `IDirect3DDevice3`.
- **The display.** The game asks for an exclusive fullscreen mode. A window,
  scaled by the presenter other ports share, comes before anything else
  visual.
- **Netlab QA on a test VM.** The recipe builds on the farm. A test VM has
  no game data, so QA there reports SKIP, and that is what it should do.

## Deferred

- **Scoring the catalog** against an IDA export with `score_recovery.py`, as
  a reference only. Worth doing if a lift bug traces back to a missed or split
  function.
- **Force feedback** (`IFORCE2.dll`, Immersion). It is bound to the real DLL
  and left alone until a run shows it matters.
- **Multiplayer** (DirectPlay, `DPLAYX`).
- **Linux on win32hle**, as Tiberian Sun does. It depends on headless mode and
  the display work first.

## Out of scope

- The Pirate's Moon expansion. It is not on this disc, and nothing here has
  looked at it.
- Crimson Skies and Recoil, the other Zipper GOS-engine games. They are their
  own repos. What carries across is a pcrecomp concern.
- Any game data in this repository, ever (CONTRIBUTING.md).
