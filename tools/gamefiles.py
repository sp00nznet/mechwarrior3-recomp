#!/usr/bin/env python3
r"""Put your copy of MechWarrior 3 in game/, from wherever it is.

    py -3 tools/gamefiles.py E:\                  # the CD in a drive
    py -3 tools/gamefiles.py MW3.iso              # a 2048-byte ISO
    py -3 tools/gamefiles.py MW3.mdf              # a raw image (2352 or 2448-byte sectors)
    py -3 tools/gamefiles.py "C:\Games\MechWarrior 3"   # an installed copy (has Mech3.exe)
    py -3 tools/gamefiles.py                      # look in every drive

The disc is an InstallShield 5 installer: the game is inside data1.cab, and
the videos sit loose in video\. A disc source is unpacked with pcrecomp's
isextract.py, which lays the install out exactly as setup would (Mech3.exe,
MFC42.DLL, zbd\, video\), without running setup or touching the registry.
Disc images are read with pcrecomp's ISO9660 walker, so nothing is mounted.

The game is Mech3.exe. HSBR.exe on the disc root is the Hasbro launcher; it is
copied along but never lifted (docs/architecture.md).

It supplies your own copy to the local build; nothing is downloaded, and none
of it is ever committed.
"""
import os
import shutil
import string
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'game')
STAGE = os.path.join(ROOT, 'work', 'disc')
TOOLS = os.path.join(os.environ.get('PCRECOMP', os.path.join(ROOT, '..', 'tools')), 'tools', 'assets')
NEEDED = ('Mech3.exe', 'MFC42.DLL', 'zbd/mechlib.zbd', 'zbd/c1/gamez.zbd')


def complete(d):
    return all(os.path.isfile(os.path.join(d, *n.split('/'))) for n in NEEDED)


def from_disc(d):
    """A folder holding data1.hdr/data1.cab: unpack the installer into game/."""
    print('unpacking the installer in %s' % d)
    subprocess.run([sys.executable, os.path.join(TOOLS, 'isextract.py'), '-o', OUT,
                    os.path.join(d, 'data1.hdr'), os.path.join(d, 'data1.cab')], check=True)


def from_image(path):
    sys.path.insert(0, TOOLS)
    import iso_peek

    size = os.path.getsize(path)
    # 2048 is a plain ISO. A raw image keeps each sector's 2048 bytes 16 bytes
    # into a 2352-byte sector (12 sync + 4 header); an MDF adds 96 bytes of
    # subchannel after that, 2448 in all.
    raw = next((n for n in (2448, 2352) if size % n == 0 and size % 2048), None)

    class RawReader(iso_peek.Reader):
        def read(self, off, n):
            out = bytearray()
            while n > 0:
                sec, within = divmod(off, 2048)
                take = min(n, 2048 - within)
                self.fh.seek(sec * raw + 16 + within)
                out += self.fh.read(take)
                off += take
                n -= take
            return bytes(out)

    reader = (RawReader if raw else iso_peek.Reader)(path)
    files = iso_peek.walk(reader)
    if not any(p.lower() == 'data1.cab' for p, _, _ in files):
        return False
    shutil.rmtree(STAGE, ignore_errors=True)
    print('reading %d files (%d MB) from %s' % (len(files), sum(n for _, _, n in files) >> 20, path))
    for p, off, n in files:
        if p.upper().startswith('REDIST/'):             # DirectX 6 for Windows 98: not needed
            continue
        dst = os.path.join(STAGE, *p.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            for o in range(0, n, 1 << 24):              # 16 MB at a time: the videos are 80 MB
                f.write(reader.read(off + o, min(1 << 24, n - o)))
    from_disc(STAGE)
    return True


def main():
    src = sys.argv[1].strip('"') if len(sys.argv) > 1 else ''
    os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)
    if not src:
        src = next(('%s:\\' % c for c in string.ascii_uppercase
                    if os.path.isfile('%s:\\data1.hdr' % c) and os.path.isfile('%s:\\Setup.exe' % c)), '')
        if not src:
            sys.exit('no drive holds the MechWarrior 3 CD; pass a drive, folder or disc image')
    if os.path.isfile(os.path.join(src, 'data1.hdr')):
        from_disc(src)
    elif os.path.isfile(os.path.join(src, 'Mech3.exe')):
        print('copying %s' % src)
        shutil.copytree(src, OUT, dirs_exist_ok=True)
    elif os.path.isfile(src):
        if not from_image(src):
            sys.exit('%s is not a disc image holding MechWarrior 3 (no data1.cab on it)' % src)
    else:
        sys.exit('%s holds neither the MechWarrior 3 disc (data1.hdr) nor an install (Mech3.exe)' % src)
    if not complete(OUT):
        sys.exit('copied, but %s is still missing a file the game needs (%s)' % (OUT, ', '.join(NEEDED)))
    print('done: %s' % OUT)


if __name__ == '__main__':
    main()
