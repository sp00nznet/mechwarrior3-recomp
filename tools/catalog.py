#!/usr/bin/env python3
"""Function catalog for Mech3.exe: pcrecomp disasm32, no IDA.

    py -3 tools/catalog.py            # -> work/functions.json

The entry point is the seed; the rest is recursive descent, prologues and a
data scan for pointers (vtables, MFC message maps). Mech3.exe was built
without RTTI, so the data scan is what finds virtual methods. The catalog is
derived from the game binary, so it lives in work/ and is never committed.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(os.environ.get('PCRECOMP', os.path.join(ROOT, '..', 'tools')), 'tools')

os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)     # gitignored, so absent in a fresh copy
subprocess.run([sys.executable, os.path.join(TOOLS, 'disasm', 'disasm32.py'),
                os.path.join(ROOT, 'game', 'Mech3.exe'), '-o',
                os.path.join(ROOT, 'work', 'functions.json')], check=True)
