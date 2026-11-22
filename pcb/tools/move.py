#!/usr/bin/env python3
"""Move or turn footprints on pcb/C128-keyboard-rev3.kicad_pcb, keeping them on their side.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/move.py [--check] REF=X,Y,ROT [REF=X,Y,ROT]...

X, Y is the footprint's courtyard center (as in gen_pcb.py PLACE) and ROT its orientation.
Each moved courtyard is checked against the other parts' courtyards on its side, every
through-hole pad and hole on the board (switch pins, stabilizer holes) and the board edge;
clashes are printed, and with --check nothing is saved.  Otherwise unlocked tracks and vias
on the moved pads, or crossing a moved courtyard, are deleted (reroute them afterwards) and
the planes are refilled.  Locked copper in the way is reported, not touched.
"""
import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
GAP = 0.25          # courtyard to a through-hole pad or hole
EDGE = 0.3


def mm(v):
    return pcbnew.FromMM(v)


def courtyard(fp):
    fp.BuildCourtyardCaches()
    bb = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
    if bb.GetWidth() == 0:
        bb = fp.GetBoundingBox(False)
    return bb


def grown(bb, d):
    b = pcbnew.BOX2I(bb.GetPosition(), bb.GetSize())
    b.Inflate(mm(d))
    return b


def fmt(bb):
    to = pcbnew.ToMM
    return f"({to(bb.GetLeft()):.2f},{to(bb.GetTop()):.2f})-({to(bb.GetRight()):.2f},{to(bb.GetBottom()):.2f})"


def clashes(board, fp, moving):
    out = []
    cy = courtyard(fp)
    edge = board.GetBoardEdgesBoundingBox()
    if not grown(edge, -EDGE).Contains(cy):
        out.append(f"edge: courtyard {fmt(cy)} within {EDGE} mm of the board edge")
    for o in board.GetFootprints():
        if o.GetReference() in moving:
            continue
        if o.IsFlipped() == fp.IsFlipped() and courtyard(o).Intersects(cy):
            out.append(f"courtyard {o.GetReference()}")
        for p in o.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) and \
                    grown(cy, GAP).Intersects(p.GetBoundingBox()):
                out.append(f"hole {o.GetReference()}.{p.GetNumber() or 'NPTH'}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("moves", nargs="+", metavar="REF=X,Y,ROT")
    a = ap.parse_args()
    board = pcbnew.LoadBoard(BOARD)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    moves = {}
    for m in a.moves:
        ref, spec = m.split("=")
        x, y, rot = map(float, spec.split(","))
        moves[ref] = (x, y, rot)

    old_pads = {}
    for ref, (x, y, rot) in moves.items():
        fp = fps[ref]
        old_pads[ref] = [(p.GetNetCode(), p.GetBoundingBox()) for p in fp.Pads()]
        fp.SetOrientationDegrees(rot)
        c = courtyard(fp).GetCenter()
        fp.Move(pcbnew.VECTOR2I(mm(x) - c.x, mm(y) - c.y))

    bad = False
    for ref in moves:
        for c in clashes(board, fps[ref], moves):
            print(f"{ref}: {c}")
            bad = True
    if a.check:
        print("move: clear" if not bad else "move: clashes above (not saved)")
        return 1 if bad else 0

    dead, kept = [], set()
    for t in board.GetTracks():
        hit = False
        for ref in moves:
            fp = fps[ref]
            box = courtyard(fp)
            if t.GetBoundingBox().Intersects(box):
                hit = True
            for net, bb in old_pads[ref]:
                if t.GetNetCode() == net and t.GetBoundingBox().Intersects(bb):
                    hit = True
        if not hit:
            continue
        if t.IsLocked():
            g = t.GetParentGroup()
            kept.add(g.GetName() if g else "locked")
        else:
            dead.append(t)
    for t in dead:
        board.Delete(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"move: {len(moves)} parts, {len(dead)} tracks and vias removed"
          + (f"; locked copper in the way from {', '.join(sorted(kept))}" if kept else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
