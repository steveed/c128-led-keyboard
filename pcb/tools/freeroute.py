#!/usr/bin/env python3
"""Autoroute pcb/C128-keyboard-rev3.kicad_pcb with Freerouting, in its Docker container.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/freeroute.py [passes] [job timeout HH:MM:SS]

1. exports the board to Specctra DSN (pcb/freerouting/out/, not committed),
2. runs `docker compose run --rm freerouting` on it (pcb/freerouting/Dockerfile),
3. imports the routed session back into the board, refills the planes, and saves.

Freerouting's fanout pre-pass is off: it tries to put a via stub on every SMD pad (978 here),
stalls after a few passes, and a keyboard's pads want short tracks to their neighbours, not
vias.  GND and 5V_SYS are declared plane nets, so their pads get a via to the inner plane
instead of a track.  It can be rerun on a routed board: unlocked copper goes out as ordinary
wiring and the router carries on from it.  The optimizer is capped at a few passes and the whole job has a time budget.

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
    timeout = sys.argv[2] if len(sys.argv) > 2 else "01:30:00"
    os.makedirs(OUT, exist_ok=True)
    dsn, ses = os.path.join(OUT, "board.dsn"), os.path.join(OUT, "board.ses")
    result = os.path.join(OUT, "result.json")
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
           "-de", rel(dsn), "-do", rel(ses),
           "--router.fanout.enabled=false",
           "--router.plane_nets=GND,+5V_SYS",        # reach the inner planes with a via
           f"--router.autorouter.max_passes={passes}",
           "--router.optimizer.max_passes=5",
           f"--router.job_timeout={timeout}",
           f"--router.result_json={rel(result)}"]
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
