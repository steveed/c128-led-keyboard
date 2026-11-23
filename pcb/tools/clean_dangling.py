#!/usr/bin/env python3
"""Delete unlocked track stubs that end on nothing, on pcb/C128-keyboard-rev3.kicad_pcb.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/clean_dangling.py

A track end is anchored when it lands on a pad, a via or another track of its net on its
layer.  Tracks with a loose end are deleted, and the check repeats until nothing changes, so
a whole dead branch goes.  Vias left joined to fewer than two things on any layer go too
(a via on a plane net counts its plane).  Locked copper is never touched.  Planes are refilled.
"""
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
PLANE_NETS = ("GND", "+5V_SYS")


def main():
    board = pcbnew.LoadBoard(BOARD)
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(p.GetNetCode(), []).append(p)
    removed = 0
    while True:
        tracks = list(board.GetTracks())
        by_net = {}
        for t in tracks:
            by_net.setdefault(t.GetNetCode(), []).append(t)
        dead = []
        for t in tracks:
            if t.IsLocked():
                continue
            net = t.GetNetCode()
            if t.Type() == pcbnew.PCB_VIA_T:
                if t.GetNetname() in PLANE_NETS:
                    continue
                pos = t.GetPosition()
                links = sum(1 for o in by_net[net] if o is not t and o.Type() != pcbnew.PCB_VIA_T
                            and (o.GetStart() == pos or o.GetEnd() == pos))
                links += sum(1 for p in pads.get(net, []) if p.HitTest(pos))
                if links < 2:
                    dead.append(t)
                continue
            L = t.GetLayer()
            for e in (t.GetStart(), t.GetEnd()):
                ok = any(p.IsOnLayer(L) and p.HitTest(e) for p in pads.get(net, []))
                for o in by_net[net]:
                    if ok:
                        break
                    if o is t:
                        continue
                    if o.Type() == pcbnew.PCB_VIA_T:
                        ok = o.GetPosition() == e or o.HitTest(e)
                    elif o.GetLayer() == L:
                        ok = o.HitTest(e, 1)
                if not ok:
                    dead.append(t)
                    break
        if not dead:
            break
        for t in dead:
            board.Delete(t)
        removed += len(dead)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"clean_dangling: {removed} tracks and vias removed")


if __name__ == "__main__":
    main()
