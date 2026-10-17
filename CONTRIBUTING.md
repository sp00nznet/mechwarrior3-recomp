# Contributing

This is a recompilation project, which changes what a useful contribution looks
like. Three rules matter more than the rest.

## No game files, ever

Nothing from MechWarrior 3 goes in the repository, in any form. That means no
executable, DLL, `.zbd` archive, video or disc image, and nothing regenerated
from one: no lifted source, disassembly listing, function catalog, vtable or
address list, reconstructed header or format dump, and no test file with a
lifted function in it.

The tool ships; the game does not. Everyone brings their own disc, and
`Setup.cmd` points the tools at it. `.gitignore` covers `game/`, `work/`,
`analysis/` and `src/recomp/gen/`. If something slips past it, that is a bug
worth reporting on its own.

Screenshots and recordings of the game running are fine, and belong in
`docs/`.

## Where your code comes from

Contributions have to be your own work or under a licence compatible with MIT.
The live risk is a fix ported from a GPL or LGPL project, which would
relicense it by accident and is very hard to untangle later. The ones most
likely to be open next to this are **Wine** (LGPL), whose `ddraw`, `dsound`
and `dinput` cover the same ground as this game's DirectX 6 calls, and
**DxWnd** (GPL), which wraps old DirectDraw games in a window. Reading such
code to understand a behaviour is not the same as copying it, but if you have
it open while writing the fix, the fix is derived from it. If something in
your PR came from somewhere, say where.

## Claims are measured, not assumed

`py -3 tools\conformance.py` has to pass before and after your change, and
`--run` too if the change touches what happens after the game starts. A change
to the lifter or the runtime it shares belongs in
[pcrecomp](https://github.com/sp00nznet/pcrecomp), as a PR there.

## The usual

- Imperative commit subjects; the body explains *why* when it is not obvious.
- Community pull requests are merged with a merge commit, never squashed or
  rebased, so your commits stay yours. Anything the maintainer adds goes in
  separate commits on top.
- Comments explain the reasoning, not the syntax.
- AI-assisted contributions are welcome, provided a human understood and
  verified the change: ran it, and can say what it does.
