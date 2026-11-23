#!/usr/bin/env python3
"""Tidy the silkscreen on pcb/C128-keyboard-rev3.kicad_pcb.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/silk.py

  1. hide the fields the schematic hands every footprint: LCSC (the part number, for the BOM)
     and Key (the legend, under a keycap and the plate where nobody reads it);
  2. move each reference that overlaps other silk, a pad's mask opening, a hole or the board
     edge to the first clear spot around its part (above, below, left, right, along the side);
     a reference with no clear spot goes to the fab layer.

Safe to rerun; copper is not touched.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
HIDE = ("LCSC", "Key")
GAP = 0.15          # silk to silk, to a mask opening, to a hole
EDGE = 0.3


def mm(v):
    return pcbnew.FromMM(v)


def grown(bb, d):
    b = pcbnew.BOX2I(bb.GetPosition(), bb.GetSize())
    b.Inflate(mm(d))
    return b


def silk_layer(back):
    return pcbnew.B_SilkS if back else pcbnew.F_SilkS


def obstacles(board, side_layer, skip_text):
    """Boxes a reference on side_layer must keep clear of (other than skip_text itself)."""
    mask = pcbnew.B_Mask if side_layer == pcbnew.B_SilkS else pcbnew.F_Mask
    out = []
    for fp in board.GetFootprints():
        for it in fp.GraphicalItems():
            if it.GetLayer() == side_layer:
                out.append(it.GetBoundingBox())
        for fld in fp.GetFields():
            if fld.IsVisible() and fld.GetLayer() == side_layer and fld.m_Uuid.AsString() != skip_text:
                out.append(fld.GetBoundingBox())
        for p in fp.Pads():
            if p.IsOnLayer(mask) or p.HasHole():
                out.append(p.GetBoundingBox())
    for d in board.GetDrawings():
        if d.GetLayer() == side_layer:
            out.append(d.GetBoundingBox())
    return out


def clear(bb, obs, inner_edge):
    if not inner_edge.Contains(bb):
        return False
    g = grown(bb, GAP)
    return not any(g.Intersects(o) for o in obs)


def candidates(fp, ref):
    """Reference positions around the part's courtyard, nearest first."""
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
    if cy.GetWidth() == 0:
        cy = fp.GetBoundingBox(False)
    tb = ref.GetBoundingBox()
    hw, hh = tb.GetWidth() // 2, tb.GetHeight() // 2
    c = cy.GetCenter()
    g = mm(GAP)
    spots = [
        (c.x, cy.GetTop() - hh - g), (c.x, cy.GetBottom() + hh + g),
        (cy.GetLeft() - hw - g, c.y), (cy.GetRight() + hw + g, c.y),
    ]
    for dx in (-0.5, 0.5, -1.0, 1.0):
        for y in (cy.GetTop() - hh - g, cy.GetBottom() + hh + g):
            spots.append((c.x + int(dx * cy.GetWidth()), y))
    for dy in (-0.5, 0.5):
        for x in (cy.GetLeft() - hw - g, cy.GetRight() + hw + g):
            spots.append((x, c.y + int(dy * cy.GetHeight())))
    return spots


def main():
    board = pcbnew.LoadBoard(BOARD)
    hidden = 0
    for fp in board.GetFootprints():
        for fld in fp.GetFields():
            if fld.GetName() in HIDE and fld.IsVisible():
                fld.SetVisible(False)
                hidden += 1
    inner = grown(board.GetBoardEdgesBoundingBox(), -EDGE)

    moved, to_fab = [], []
    for fp in board.GetFootprints():
        ref = fp.Reference()
        if not ref.IsVisible() or ref.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        layer = ref.GetLayer()
        obs = obstacles(board, layer, ref.m_Uuid.AsString())
        if clear(ref.GetBoundingBox(), obs, inner):
            continue
        ref.SetTextAngleDegrees(0)
        for x, y in candidates(fp, ref):
            ref.SetTextPos(pcbnew.VECTOR2I(int(x), int(y)))
            if clear(ref.GetBoundingBox(), obs, inner):
                moved.append(fp.GetReference())
                break
        else:
            ref.SetLayer(pcbnew.B_Fab if layer == pcbnew.B_SilkS else pcbnew.F_Fab)
            to_fab.append(fp.GetReference())
    board.Save(BOARD)
    print(f"silk: hid {hidden} fields; moved {len(moved)} references"
          + (f" ({', '.join(moved)})" if moved else "")
          + (f"; to fab: {', '.join(to_fab)}" if to_fab else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
