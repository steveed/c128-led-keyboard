#!/usr/bin/env python3
"""Autoroute pcb/C128-keyboard-rev3.kicad_pcb with Freerouting, in its Docker container.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/freeroute.py [passes]

1. exports the board to Specctra DSN (pcb/freerouting/out/, not committed),
2. runs `docker compose run --rm freerouting` on it (pcb/freerouting/Dockerfile),
3. imports the routed session back into the board, refills the planes, and saves.

The per-key copper from route_keys.py is locked, so it goes out as protected wiring and
Freerouting routes around it.  Run route_keys.py first.  Commit before running: the import
adds to the board in place, and `git checkout` is the undo.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.dirname(HERE)
REPO = os.path.dirname(PCB)
BOARD = os.path.join(PCB, "C128-keyboard-rev3.kicad_pcb")
OUT = os.path.join(PCB, "freerouting", "out")

import pcbnew  # noqa: E402


def main():
    passes = sys.argv[1] if len(sys.argv) > 1 else "30"
    os.makedirs(OUT, exist_ok=True)
    dsn, ses = os.path.join(OUT, "board.dsn"), os.path.join(OUT, "board.ses")
    for f in (dsn, ses):
        if os.path.exists(f):
            os.remove(f)
    board = pcbnew.LoadBoard(BOARD)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        sys.exit("DSN export failed")
    print("exported", dsn)
    # paths inside the container: ./pcb is mounted at /work
    rel = lambda p: "/work/" + os.path.relpath(p, PCB)
    cmd = ["docker", "compose", "-f", os.path.join(REPO, "docker-compose.yml"), "run", "--rm", "freerouting",
           "-de", rel(dsn), "-do", rel(ses), "-mp", passes]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    if not os.path.exists(ses):
        sys.exit("Freerouting wrote no session file")
    board = pcbnew.LoadBoard(BOARD)
    if not pcbnew.ImportSpecctraSES(board, ses):
        sys.exit("SES import failed")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print("imported", ses, "into", BOARD)


if __name__ == "__main__":
    main()
