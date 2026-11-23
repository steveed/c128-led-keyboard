#!/usr/bin/env python3
"""Center pcb/C128-keyboard-rev3.kicad_pcb on its drawing sheet.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/to_sheet.py [PAPER]

The board (395 x 126 mm) overflows the A4 sheet gen_pcb.py gave it, so this sets the paper
(A3 landscape by default) and moves everything -- parts, copper, zones, drawings, the outline
and the origins -- by one offset so the outline's box sits in the middle of the page.  The
shift is rounded to 0.025 mm and printed; rerunning on a centered board moves nothing.

The board's coordinates then differ from rev 2.3's (and from layout.py, gen_pcb.py PLACE and
coordinates written down before the move) by that offset.
"""
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
PAPERS = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0)}
STEP = 0.025


def snap(v):
    return round(v / STEP) * STEP


def main():
    paper = sys.argv[1] if len(sys.argv) > 1 else "A3"
    w, h = PAPERS[paper]
    board = pcbnew.LoadBoard(BOARD)

    e = board.GetBoardEdgesBoundingBox()
    to = pcbnew.ToMM
    cx, cy = to(e.GetCenter().x), to(e.GetCenter().y)
    dx, dy = snap(w / 2 - cx), snap(h / 2 - cy)
    if dx or dy:
        d = pcbnew.VECTOR2I(pcbnew.FromMM(dx), pcbnew.FromMM(dy))
        for fp in board.GetFootprints():
            fp.Move(d)
        for t in board.GetTracks():
            t.Move(d)
        for z in board.Zones():
            z.Move(d)
        for g in board.GetDrawings():
            g.Move(d)
        ds = board.GetDesignSettings()
        ds.SetAuxOrigin(ds.GetAuxOrigin() + d)
        ds.SetGridOrigin(ds.GetGridOrigin() + d)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    # the Python bindings don't wrap PAGE_INFO: set the paper in the file
    text = open(BOARD, encoding="utf-8").read()
    text = re.sub(r'\(paper "[^"]*"[^)]*\)', f'(paper "{paper}")', text, count=1)
    open(BOARD, "w", encoding="utf-8").write(text)
    e = board.GetBoardEdgesBoundingBox()
    print(f"to_sheet: {paper} landscape; moved by ({dx:+.3f}, {dy:+.3f}) mm; outline now "
          f"({to(e.GetLeft()):.2f},{to(e.GetTop()):.2f})-({to(e.GetRight()):.2f},{to(e.GetBottom()):.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
