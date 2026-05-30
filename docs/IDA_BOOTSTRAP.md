# Phase 0 — IDA-Seeded Function Discovery

How the MechWarrior 3 function table was produced, and why.

## Disc → binary
The source is an Alcohol-format disc image (`MW3.mdf` / `.mds`, 2448-byte sectors with
subchannel data). Converted to a plain ISO with the toolkit's `mdf2iso.py`
(auto-detects sector layout via the ISO9660 `CD001` descriptor), then the game exe
was extracted. The main executable is **`HSBR.exe`** (the GOS engine is statically
linked — there is no separate engine DLL on disc).

## Triage
`HSBR.exe` was probed with `pe_probe.py`:
- **No SafeDisc markers** — clean `.text`/`.rdata`/`.data`/`.idata`; analyzes directly
  (no runtime memory dump needed, unlike Crimson Skies / X-Wing Alliance).
- **VC6 / MFC42** — confirmed by FLIRT matches (`CDocument`, `CRectTracker`,
  `CDockablePane`, `ios_base`, `std::locale::facet`, …).

## Discovery
`mw3_bootstrap.py` runs IDA auto-analysis + VC6/MFC FLIRT signatures, then emits:

- **`config/functions.json`** — 2,814 functions `{address, address_int, name,
  num_instructions}` (same schema as the Crimson Skies / X-Wing Alliance recomps).
- **`config/ida_names.txt`** — 1,629 library names recovered by FLIRT.
- **`analysis/vtables.json`** — 168 vtables, 950 virtual methods.

## Why IDA instead of a call-graph sweep
The sister project **Crimson Skies** discovered functions by recursive call-graph
traversal. On a C++/MFC binary that **misses every virtual method reached only through
a vtable** — IDA cross-validation found **~770** such missing virtuals there, a likely
source of its runtime-bringup instability.

IDA's analysis scans `.rdata` for vtables and treats their entries as function entries,
so MechWarrior 3's **950 virtual methods are all in `functions.json` from day one**.
Starting Phase 1 codegen from this list avoids inheriting the Crimson Skies gap.

## Cross-project note
Because the GOS engine is shared, the same vtable layouts and many engine functions
should recur in **Recoil** and **Crimson Skies**. Diffing the three function tables is
a promising way to label engine code across all three.
