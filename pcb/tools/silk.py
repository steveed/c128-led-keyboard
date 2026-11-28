#!/usr/bin/env python3
"""Tidy the silkscreen on pcb/C128-keyboard-rev3.kicad_pcb, or on the board given.

    docker compose run --rm kicad python3 pcb/tools/silk.py [BOARD]

  1. hide the fields the schematic hands every footprint: LCSC (the part number, for the BOM)
     and Key (the legend, under a keycap and the plate where nobody reads it);
  2. run KiCad's DRC and take its silkscreen findings (silk over a mask opening, silk too
     close to the board edge, silk on silk); only those items are touched:
  3. a flagged reference moves to the first clear spot around its part (above, below, left,
     right, along the side), or to the fab layer when there is none; another flagged
     footprint text (a pin-1 "1") moves the same way if a spot within 1 mm of its own is
     clear (further off it would mark the wrong pin), or goes to the fab layer;
  4. a flagged footprint line is trimmed to the pieces clear of mask openings and of the
     board edge (a part that overhangs the edge, like a connector's flange or a module's
     antenna, has outline past it).

Safe to rerun; copper is not touched.  Check with DRC afterwards: a moved text is placed by
its bounding box, which is stricter than DRC's test of the glyphs.
"""
import json
import os
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
KICAD_CLI = os.environ.get("KICAD_CLI", "kicad-cli")
HIDE = ("LCSC", "Key")
GAP = 0.15          # a moved text to other silk, a mask opening or a hole
EDGE = 0.3          # silk to the board edge
PIN_MARK_REACH = 1.0  # a footprint text (a pin-1 "1") moves no further than this
SILK = ("silk_over_copper", "silk_edge_clearance", "silk_overlap")


def mm(v):
    return pcbnew.FromMM(v)


def grown(bb, d):
    b = pcbnew.BOX2I(bb.GetPosition(), bb.GetSize())
    b.Inflate(mm(d))
    return b


def edge_box(board):
    """The outline's bounding box, from the Edge.Cuts drawings (KiCad 10's
    GetBoardEdgesBoundingBox() can come back wrong for a board with arcs)."""
    box = None
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            bb = d.GetBoundingBox()
            if box is None:
                box = pcbnew.BOX2I(bb.GetPosition(), bb.GetSize())
            else:
                box.Merge(bb)
    return box


def drc_silk(path):
    """{uuid: set of silk violation types} from kicad-cli's DRC of the saved board."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "drc.json")
        subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "-o", out, path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        report = json.load(open(out, encoding="utf-8"))
    flagged = {}
    for v in report["violations"]:
        if v["type"] in SILK:
            for it in v["items"]:
                flagged.setdefault(it["uuid"], set()).add(v["type"])
    return flagged


def obstacles(board, side_layer, skip_text):
    """Boxes a text on side_layer must keep clear of (other than skip_text itself)."""
    mask = pcbnew.B_Mask if side_layer == pcbnew.B_SilkS else pcbnew.F_Mask
    out = []
    for fp in board.GetFootprints():
        for it in fp.GraphicalItems():
            if it.GetLayer() == side_layer and it.m_Uuid.AsString() != skip_text:
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


def candidates(fp, text):
    """Text positions around the part's courtyard, nearest first."""
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
    if cy.GetWidth() == 0:
        cy = fp.GetBoundingBox(False)
    tb = text.GetBoundingBox()
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


def place(board, fp, text, inner, reach=None):
    """Move text to the first clear spot around fp, within reach (mm) of where it was if
    given; False, with the text put back, if there is none."""
    obs = obstacles(board, text.GetLayer(), text.m_Uuid.AsString())
    was, angle = text.GetPosition(), text.GetTextAngleDegrees()
    text.SetTextAngleDegrees(0)
    for x, y in candidates(fp, text):
        p = pcbnew.VECTOR2I(int(x), int(y))
        if reach is not None and pcbnew.ToMM((p - was).EuclideanNorm()) > reach:
            continue
        text.SetTextPos(p)
        if clear(text.GetBoundingBox(), obs, inner):
            return True
    text.SetTextAngleDegrees(angle); text.SetPosition(was)
    return False


def trim(board, fp, line, inner):
    """Replace a silk segment by its pieces clear of mask openings, holes and the edge."""
    L = line.GetLayer()
    mask = pcbnew.B_Mask if L == pcbnew.B_SilkS else pcbnew.F_Mask
    hw = line.GetWidth() // 2 + mm(0.02)
    obs = [p.GetBoundingBox() for f in board.GetFootprints() for p in f.Pads() if p.IsOnLayer(mask) or p.HasHole()]
    a, b = line.GetStart(), line.GetEnd()
    n = max(2, int(pcbnew.ToMM((b - a).EuclideanNorm()) / 0.02))
    at = lambda t: pcbnew.VECTOR2I(int(a.x + (b.x - a.x) * t), int(a.y + (b.y - a.y) * t))

    def ok(t):
        p = at(t)
        dot = pcbnew.BOX2I(pcbnew.VECTOR2I(p.x - hw, p.y - hw), pcbnew.VECTOR2I(2 * hw, 2 * hw))
        return inner.Contains(dot) and not any(o.Intersects(dot) for o in obs)
    flags = [ok(i / n) for i in range(n + 1)] + [False]
    pieces, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if pcbnew.ToMM((at((i - 1) / n) - at(start / n)).EuclideanNorm()) >= 0.2:
                pieces.append((at(start / n), at((i - 1) / n)))
            start = None
    for p0, p1 in pieces:
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(L); s.SetStroke(line.GetStroke()); s.SetStart(p0); s.SetEnd(p1)
        fp.Add(s)
    fp.Remove(line)


def main():
    flagged = drc_silk(BOARD)
    board = pcbnew.LoadBoard(BOARD)
    hidden = 0
    for fp in board.GetFootprints():
        for fld in fp.GetFields():
            if fld.GetName() in HIDE and fld.IsVisible():
                fld.SetVisible(False)
                hidden += 1
    inner = grown(edge_box(board), -EDGE)

    moved, to_fab, hid, lines = [], [], [], []
    trims = []
    for fp in list(board.GetFootprints()):
        ref = fp.Reference()
        if ref.IsVisible() and ref.m_Uuid.AsString() in flagged:
            if place(board, fp, ref, inner):
                moved.append(fp.GetReference())
            else:
                ref.SetLayer(pcbnew.B_Fab if ref.GetLayer() == pcbnew.B_SilkS else pcbnew.F_Fab)
                to_fab.append(fp.GetReference())
        for it in list(fp.GraphicalItems()):
            why = flagged.get(it.m_Uuid.AsString())
            if not why:
                continue
            if it.GetClass() == "PCB_TEXT" and it.IsVisible():
                if place(board, fp, it, inner, reach=PIN_MARK_REACH):
                    moved.append(f"{fp.GetReference()} '{it.GetText()}'")
                else:
                    it.SetLayer(pcbnew.B_Fab if it.GetLayer() == pcbnew.B_SilkS else pcbnew.F_Fab)
                    hid.append(f"{fp.GetReference()} '{it.GetText()}'")
            elif (it.GetClass() == "PCB_SHAPE" and it.GetShape() == pcbnew.SHAPE_T_SEGMENT
                  and why & {"silk_over_copper", "silk_edge_clearance"}):
                trims.append((fp, it))
    for fp, it in trims:                # last: the SWIG lists go stale once footprints change
        trim(board, fp, it, inner)
        lines.append(fp.GetReference())
    board.Save(BOARD)
    print(f"silk: hid {hidden} fields; moved {len(moved)} texts"
          + (f" ({', '.join(moved)})" if moved else "")
          + (f"; to fab: {', '.join(to_fab)}" if to_fab else "")
          + (f"; texts to fab: {', '.join(hid)}" if hid else "")
          + (f"; trimmed {len(lines)} lines on {', '.join(sorted(set(lines)))}" if lines else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
