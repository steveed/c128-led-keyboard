#!/usr/bin/env python3
"""Build the bottom liner: a die-cut Formex sheet held off the PCB's back by a few long foam tape strips.

The liner keeps the switch pins, solder joints and back-side parts off the flat 128's RF
shield, a bench or a hand (docs/rev3-plan.md, *Bottom cover*).  It hangs 2.3 mm below the
board on double-sided foam tape, which clears the 1.7 mm of switch pins, so the tape is the
only thing touching the PCB.  Everything is taken from the board, so a layout change only
needs a rerun:

  - outline: the board's width less a margin, from the rear edge to just past the lane
    between the ASDF and Z rows (the 128's main board does not reach further forward);
  - windows: every back-side part taller than the tape clears (the module, USB-C, cable
    header, electrolytic, tact switches ...), merged where they crowd and opened to the
    rear edge where they reach it;
  - tape: a few long strips on bare board, as on the Amiga 1000 keyboard: two in the rear
    band, one full width behind the number row, one in the last lane before the front edge
    and, where the stabilizers break that lane, a short one a lane back for the front-right
    corner.  Each is clear of every pin, pad and back-side part.

It writes pcb/liner/liner.kicad_pcb in the board's coordinates: the die line on Edge.Cuts,
the tape strips on User.1, the PCB's outline and back-side parts for reference on User.2, and
the notes and dimensions on User.Drawings, and pcb/liner/liner.dxf for the cutter (CUT and
TAPE layers, closed polylines).  `make liner` plots the PDF drawings from the board.

Run:  python3 pcb/tools/gen_liner.py   (KiCad's bundled python: it needs pcbnew)
"""
import math
import os
import re

import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.normpath(os.path.join(HERE, "..", "C128-keyboard-rev3.kicad_pcb"))
OUT = os.path.normpath(os.path.join(HERE, "..", "liner", "liner.kicad_pcb"))
DXF = os.path.normpath(os.path.join(HERE, "..", "liner", "liner.dxf"))

LINER_T = 0.43          # Formex GK-17
TAPE_T = 2.3            # double-sided foam tape, e.g. 3M VHB 4991
PIN_PROTRUSION = 1.7    # switch pins below the PCB
CLEAR = 0.4             # a part this close to the liner's face gets a window instead
SIDE_MARGIN = 1.0       # liner edge inside the board edge
WINDOW_MARGIN = 1.0     # around a windowed part's courtyard
MERGE = 6.0             # windows (or a window and an edge) closer than this become one opening
R_OUTER = 3.0           # die-line corner radii (R_OUTER also drops any bridge under 2x)
R_INNER = 1.0
TAPE_KEEPOUT = 0.6      # tape edge to any pad, hole or part courtyard
TAPE_EDGE = 1.5         # tape edge to the liner's edge or a window
TAPE_W = 4.0            # strip width
TAPE_MIN = 40.0         # shortest strip worth laying
GRID = 0.1              # raster for the tape search, mm

# Tallest point of each back-side footprint above the PCB, mm (datasheet maxima, rounded up).
HEIGHT = {
    "USB_C_Receptacle_ShouHan_TYPE-C-16P-3MD-040": 3.3,
    "ESP32-S2-MINI-1U": 4.5,              # S3-MINI-1U footprint; 2.4 mm plus the mated U.FL
    "IDC-Header_2x13_P2.54mm_Vertical": 9.0,
    "CP_Elec_6.3x7.7": 7.7,
    "PinHeader_1x03_P2.54mm_Vertical": 8.5,
    "SW_SPST_PTS645Sx43SMTR92": 4.3,
    "SOIC-24W_7.5x15.4mm_P1.27mm": 2.65,
    "D_SMA": 2.45,
    "Fuse_1812_4532Metric": 1.9,
    "SOT-223-3_TabPin2": 1.8,
    "C_1206_3216Metric_Pad1.33x1.80mm_HandSolder": 1.8,
    "LQFP-44_10x10mm_P0.8mm": 1.6,
}
LOW = 1.2               # everything else on the back: 0603s, SOT-23s, SOD-123 diodes, jumper

LIMIT = TAPE_T - CLEAR  # taller than this: window

mm = pcbnew.ToMM
iu = pcbnew.FromMM


def rect_poly(x0, y0, x1, y1):
    s = pcbnew.SHAPE_POLY_SET()
    s.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        s.Append(iu(x), iu(y))
    return s


def grow(s, d):
    s = pcbnew.SHAPE_POLY_SET(s)
    if d > 0:
        s.Inflate(iu(d), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, iu(0.005))
    elif d < 0:
        s.Deflate(iu(-d), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, iu(0.005))
    return s


def chains(s):
    """Every outline and hole of a polygon set as a list of (x, y) mm points."""
    out = []
    for i in range(s.OutlineCount()):
        out.append(s.Outline(i))
        out.extend(s.Hole(i, h) for h in range(s.HoleCount(i)))
    return [[(mm(c.CPoint(k).x), mm(c.CPoint(k).y)) for k in range(c.PointCount())] for c in out]


def bbox(box):
    return mm(box.GetX()), mm(box.GetY()), mm(box.GetRight()), mm(box.GetBottom())


def courtyard(f):
    return bbox(f.GetCourtyard(pcbnew.B_CrtYd).BBox())


def read_board():
    b = pcbnew.LoadBoard(BOARD)
    edge = bbox(b.GetBoardEdgesBoundingBox())
    ys = [round(mm(f.GetY()), 2) for f in b.GetFootprints()
          if f.GetReference().startswith("SW") and not f.IsFlipped()]
    rows = sorted({y for y in ys if ys.count(y) >= 3})   # the key rows (not the upright 2u)
    back, obstacles = [], []
    for f in b.GetFootprints():
        name = str(f.GetFPID().GetLibItemName())
        if f.IsFlipped():
            back.append((f.GetReference(), name, HEIGHT.get(name, LOW), courtyard(f)))
            obstacles.append(courtyard(f))
        for p in f.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and not f.IsFlipped():
                continue                          # front-side SMD (the LEDs): not under the liner
            obstacles.append(bbox(p.GetBoundingBox()))
    return b, edge, rows, back, obstacles


def liner_outline(edge, rows, back):
    x0, y0, x1, _ = edge
    z_row = rows[-1]                              # the Z row (the spacebar row has one key)
    front = z_row - 3.0                           # past the Z row's first pins: the liner floats
    rear = y0 + SIDE_MARGIN
    outer = rect_poly(x0 + SIDE_MARGIN, rear, x1 - SIDE_MARGIN, front)

    tall = [(r, n, h, c) for r, n, h, c in back if h > LIMIT and c[1] < front]
    holes = pcbnew.SHAPE_POLY_SET()
    for _, _, _, (a, b, c, d) in tall:
        a, b, c, d = a - WINDOW_MARGIN, b - WINDOW_MARGIN, c + WINDOW_MARGIN, d + WINDOW_MARGIN
        if b - rear < MERGE:                      # reaches the rear edge: a notch, not a sliver
            b = rear - 2
        holes.BooleanAdd(rect_poly(a, b, c, d))
    holes = grow(grow(holes, MERGE / 2), -MERGE / 2)  # close the gaps between crowded windows
    liner = pcbnew.SHAPE_POLY_SET(outer)
    liner.BooleanSubtract(holes)
    liner = grow(grow(liner, -R_OUTER), R_OUTER)  # round the convex corners, drop thin bridges
    liner = grow(grow(liner, R_INNER), -R_INNER)  # round the window corners
    liner.Simplify()
    # an island of sheet boxed in between windows would fall out of the die: cut it away too
    areas = [liner.Outline(i).Area() for i in range(liner.OutlineCount())]
    for i in sorted(range(len(areas)), reverse=True):
        if areas[i] < max(areas):
            liner.DeletePolygon(i)
    return liner, tall, front


class Raster:
    """Boolean grid over the board: True where a tape pad may not cover."""

    def __init__(self, edge):
        self.x0, self.y0 = edge[0], edge[1]
        self.nx = int(math.ceil((edge[2] - edge[0]) / GRID)) + 1
        self.ny = int(math.ceil((edge[3] - edge[1]) / GRID)) + 1
        self.blocked = np.zeros((self.ny, self.nx), dtype=bool)

    def ij(self, x, y):
        return int(round((y - self.y0) / GRID)), int(round((x - self.x0) / GRID))

    def block(self, a, b, c, d):
        i0, j0 = self.ij(a, b)
        i1, j1 = self.ij(c, d)
        self.blocked[max(i0, 0):max(i1 + 1, 0), max(j0, 0):max(j1 + 1, 0)] = True

    def fill(self, loops):
        """Even-odd scanline fill of closed loops (outlines and holes alike)."""
        inside = np.zeros_like(self.blocked)
        edges = [(p, q) for pts in loops for p, q in zip(pts, pts[1:] + pts[:1]) if p[1] != q[1]]
        e = np.array([(p[0], p[1], q[0], q[1]) for p, q in edges])
        xs = self.x0 + GRID * np.arange(self.nx)
        for i in range(self.ny):
            y = self.y0 + GRID * i + 1e-6
            hit = (np.minimum(e[:, 1], e[:, 3]) <= y) & (np.maximum(e[:, 1], e[:, 3]) > y)
            h = e[hit]
            cut = np.sort(h[:, 0] + (y - h[:, 1]) * (h[:, 2] - h[:, 0]) / (h[:, 3] - h[:, 1]))
            for a, b in zip(cut[0::2], cut[1::2]):
                inside[i, (xs >= a) & (xs <= b)] = True
        return inside


def free_runs(r, y, h):
    """(x0, x1) of every stretch where a strip h tall centred on y covers no blocked cell."""
    i, k = r.ij(r.x0, y)[0], int(math.ceil(h / 2 / GRID))
    if i - k < 0 or i + k >= r.ny:
        return []
    free = ~r.blocked[i - k:i + k + 1].any(0)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], free.view(np.int8), [0]))))
    return [(r.x0 + GRID * s + 0.5, r.x0 + GRID * (e - 1) - 0.5) for s, e in zip(edges[0::2], edges[1::2])]


def place_tape(edge, rows, liner, obstacles):
    """A few long strips, as Commodore did.  In each band, the height with the most strip
    length in its `n` longest runs, keeping only runs of TAPE_MIN or more."""
    r = Raster(edge)
    for a, b, c, d in obstacles:
        r.block(a - TAPE_KEEPOUT, b - TAPE_KEEPOUT, c + TAPE_KEEPOUT, d + TAPE_KEEPOUT)
    r.blocked |= ~r.fill(chains(grow(liner, -TAPE_EDGE)))    # TAPE_EDGE inside the sheet

    lanes = [(a, b) for a, b in zip(rows, rows[1:]) if b - a < 25]
    strips = []

    def lay(row_a, row_b, n, xmin=-1e9):
        best = (0, [], 0)
        for y in np.arange(row_a + 6.0, row_b - 5.0, GRID):
            runs = sorted((x for x in free_runs(r, y, TAPE_W) if x[1] - x[0] >= TAPE_MIN and x[0] >= xmin),
                          key=lambda x: x[0] - x[1])[:n]
            total = sum(x1 - x0 for x0, x1 in runs)
            if total > best[0] + 0.5:
                best = (total, runs, float(y))
        for x0, x1 in best[1]:
            strips.append((float(x0), best[2] - TAPE_W / 2, float(x1), best[2] + TAPE_W / 2))
        return best[1]

    lay(rows[0], rows[1], 2)                      # the rear band: two strips, either side of J2
    lay(*lanes[0], 1)                             # behind the number row: full width
    front = lay(*lanes[2], 1)                     # the last lane before the front edge
    if front and front[0][1] < bbox(liner.BBox())[2] - 60:
        # the Return and keypad stabilizers break that lane up: carry the front-right corner
        # on a strip one lane back
        lay(*lanes[1], 1, xmin=front[0][1] + 5)
    return sorted(strips, key=lambda p: (round(p[1]), p[0]))


def add_poly(board, pts, layer, width=0.1, fill=False):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    s.SetLayer(layer)
    s.SetWidth(iu(width))
    s.SetFilled(fill)
    s.SetPolyPoints([pcbnew.VECTOR2I(iu(x), iu(y)) for x, y in pts])
    board.Add(s)


def add_rect(board, r, layer, width=0.1):
    a, b, c, d = r
    add_poly(board, [(a, b), (c, b), (c, d), (a, d)], layer, width)


def add_text(board, s, x, y, size=2.0, layer=pcbnew.Dwgs_User, left=True):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(iu(x), iu(y)))
    t.SetTextSize(pcbnew.VECTOR2I(iu(size), iu(size)))
    t.SetTextThickness(iu(size * 0.12))
    if left:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
    board.Add(t)


def add_dim(board, a, b, offset):
    d = pcbnew.PCB_DIM_ALIGNED(board)
    d.SetLayer(pcbnew.Dwgs_User)
    d.SetStart(pcbnew.VECTOR2I(iu(a[0]), iu(a[1])))
    d.SetEnd(pcbnew.VECTOR2I(iu(b[0]), iu(b[1])))
    d.SetHeight(iu(offset))
    d.SetUnits(pcbnew.EDA_UNITS_MM)
    d.SetPrecision(pcbnew.DIM_PRECISION_X_X)
    d.SetLineThickness(iu(0.15))
    d.SetTextSize(pcbnew.VECTOR2I(iu(2.0), iu(2.0)))
    board.Add(d)


def write_dxf(liner, strips):
    """DXF in mm: one closed LWPOLYLINE per contour, die line on CUT and the tape on TAPE.
    Origin at the liner's front left corner, Y up, viewed from the tape side."""
    lx0, _, _, ly1 = bbox(liner.BBox())
    out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
           "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "2"]
    for name, colour in (("CUT", 7), ("TAPE", 3)):
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(colour), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def poly(layer, pts):
        nonlocal out
        out += ["0", "LWPOLYLINE", "8", layer, "90", str(len(pts)), "70", "1"]
        for x, y in pts:
            out += ["10", f"{x - lx0:.4f}", "20", f"{ly1 - y:.4f}"]

    for ch in chains(liner):
        poly("CUT", ch)
    for a, b, c, d in strips:
        poly("TAPE", [(a, b), (c, b), (c, d), (a, d)])
    out += ["0", "ENDSEC", "0", "EOF"]
    with open(DXF, "w") as fh:
        fh.write("\n".join(out) + "\n")


def write(src, edge, liner, tall, strips, back, front):
    out = pcbnew.CreateEmptyBoard()
    for ch in chains(liner):
        add_poly(out, ch, pcbnew.Edge_Cuts, 0.25)
    for p in strips:
        a, b, c, d = p
        add_poly(out, [(a, b), (c, b), (c, d), (a, d)], pcbnew.User_1, 0.1, fill=True)
    # reference: the PCB outline and its back-side parts (looking through the board from the front)
    for d in src.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            s = d.Duplicate()
            s.SetLayer(pcbnew.User_2)
            out.Add(s)
    for ref, _, h, c in back:
        if c[1] < front:
            add_rect(out, c, pcbnew.User_2, 0.05)
    for f in src.GetFootprints():                 # the switch pins and holes
        for p in f.Pads():
            if p.GetDrillSizeX() and mm(p.GetY()) < front + 3:
                c = pcbnew.PCB_SHAPE(out, pcbnew.SHAPE_T_CIRCLE)
                c.SetLayer(pcbnew.User_2)
                c.SetWidth(iu(0.05))
                c.SetCenter(p.GetPosition())
                c.SetEnd(p.GetPosition() + pcbnew.VECTOR2I(int(max(p.GetSizeX(), p.GetDrillSizeX()) / 2), 0))
                out.Add(c)
    for ref, _, h, c in tall:
        add_text(out, f"{ref} {h:g}", c[0], c[3] + 0.3, 1.2, pcbnew.User_2)

    lx0, ly0, lx1, ly1 = bbox(liner.BBox())
    add_dim(out, (lx0, ly1), (lx1, ly1), -12)
    add_dim(out, (lx1, ly0), (lx1, ly1), -8)
    add_dim(out, (edge[0], edge[1]), (lx0, edge[1]), 6)
    tape_len = sum(c - a for a, _, c, _ in strips)
    notes = [
        "C128 LED keyboard rev 3 - bottom liner",
        f"Material: Formex GK-17 ({LINER_T} mm polypropylene), or fish paper 0.4 mm.  Die line: liner.dxf layer CUT.",
        f"Tape: {len(strips)} strips, {TAPE_W:g} mm wide, {tape_len:.0f} mm in all, double-sided foam {TAPE_T} mm (3M VHB 4991 or equal),",
        "   laminated to this face of the liner (liner.dxf layer TAPE); release liner left on.",
        "View: from the PCB side (the tape side), in the PCB's coordinates.  Mirror for the view from below.",
        f"Windows clear every back-side part taller than {LIMIT:.1f} mm (heights in mm beside each).  Corners R{R_OUTER:g} / R{R_INNER:g}.",
        "Tolerance +/-0.3 mm.  Thin gray lines are the PCB and its back-side parts, for reference only.",
    ]
    for i, s in enumerate(notes):
        add_text(out, s, edge[0], edge[3] + 18 + 3.2 * i, 2.0 if i == 0 else 1.6)
    tb = out.GetTitleBlock()
    tb.SetTitle("Bottom liner")
    tb.SetCompany("C128 LED keyboard")
    tb.SetRevision("3")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pcbnew.SaveBoard(OUT, out)
    with open(OUT) as fh:
        text = fh.read()
    text = re.sub(r'\(paper "[^"]*"[^)]*\)', '(paper "A3")', text, count=1)
    with open(OUT, "w") as fh:
        fh.write(text)
    for junk in (".kicad_pro", ".kicad_prl"):         # SaveBoard's project files: not needed
        path = OUT.replace(".kicad_pcb", junk)
        if os.path.exists(path):
            os.remove(path)
    return lx1 - lx0, ly1 - ly0, tape_len


def check(liner, strips, obstacles):
    """Independent of the raster: every pad clear of every obstacle and inside the sheet."""
    k = TAPE_KEEPOUT - GRID
    for a, b, c, d in strips:
        for e, f, g, h in obstacles:
            assert c <= e - k or a >= g + k or d <= f - k or b >= h + k, ((a, b, c, d), (e, f, g, h))
        for x, y in ((a, b), (c, b), (c, d), (a, d)):
            assert liner.Contains(pcbnew.VECTOR2I(iu(x), iu(y))), ("tape off the liner", (a, b, c, d))


def main():
    src, edge, rows, back, obstacles = read_board()
    liner, tall, front = liner_outline(edge, rows, back)
    strips = place_tape(edge, rows, liner, obstacles)
    w, h, tape_len = write(src, edge, liner, tall, strips, back, front)
    write_dxf(liner, strips)
    check(liner, strips, obstacles)
    print(f"gen_liner: {w:.1f} x {h:.1f} mm, {liner.HoleCount(0)} windows, "
          f"{len(strips)} tape strips ({tape_len:.0f} mm of {TAPE_W:g} mm tape)")
    print("  windows for: " + ", ".join(f"{r} ({h:g} mm)" for r, _, h, _ in tall))
    for p in strips:
        print(f"  tape {p[2] - p[0]:4.0f} x {p[3] - p[1]:.0f} at ({(p[0] + p[2]) / 2:6.1f}, {(p[1] + p[3]) / 2:6.1f})")
    print(f"  wrote {os.path.relpath(OUT)} and {os.path.relpath(DXF)}")


if __name__ == "__main__":
    main()
