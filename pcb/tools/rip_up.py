#!/usr/bin/env python3
"""Rip up unlocked copper on pcb/C128-keyboard-rev3.kicad_pcb, for a cleaner reroute.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/rip_up.py [--rect X0 Y0 X1 Y1]... [--pad REF.PAD]... [--radius MM]

--rect   every unlocked track or via that enters the rectangle, whole (a long track that
         only passes through goes too, and is rerouted with the rest)
--pad    unlocked tracks and vias of other nets within --radius (default 1.5 mm) of the pad:
         room for that pad's plane via

Locked copper (route_keys, plane_taps) stays.  Planes are refilled.  Reroute afterwards.
"""
import argparse
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")


def shape(t):
    return t.GetEffectiveShape(pcbnew.F_Cu if t.Type() == pcbnew.PCB_VIA_T else t.GetLayer())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rect", nargs=4, type=float, action="append", default=[])
    ap.add_argument("--pad", action="append", default=[])
    ap.add_argument("--radius", type=float, default=1.5)
    a = ap.parse_args()
    board = pcbnew.LoadBoard(BOARD)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    mm = pcbnew.FromMM
    rects = [pcbnew.SHAPE_RECT(pcbnew.VECTOR2I(mm(x0), mm(y0)), mm(x1 - x0), mm(y1 - y0))
             for x0, y0, x1, y1 in a.rect]
    pads = []
    for rp in a.pad:
        ref, num = rp.split(".")
        pads += [p for p in fps[ref].Pads() if p.GetNumber() == num]
    dead = []
    for t in board.GetTracks():
        if t.IsLocked():
            continue
        s = shape(t)
        if any(r.Collide(s, 0) for r in rects):
            dead.append(t)
            continue
        for p in pads:
            if t.GetNetCode() == p.GetNetCode():
                continue
            layers = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if t.Type() == pcbnew.PCB_VIA_T \
                else (t.GetLayer(),)
            q = p.GetPosition()
            if any(L in (pcbnew.F_Cu, pcbnew.B_Cu) for L in layers) and \
                    s.Collide(pcbnew.SHAPE_CIRCLE(q, 1), mm(a.radius)):
                dead.append(t)
                break
    nets = sorted({t.GetNetname() for t in dead})
    for t in dead:
        board.Delete(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"rip_up: {len(dead)} tracks and vias on {len(nets)} nets")


if __name__ == "__main__":
    main()
