#!/usr/bin/env python3
"""Build the keyboard plate as a KiCad board (for aluminum-core PCB fabrication) in the
board's coordinate frame.

Steps:
  1. read the plate's top-face loops from layout/plate.json (extract_layout.py);
  2. find the rigid transform that lays the 88 switch openings onto the switch centers in
     layout/switches.json (tries all eight axis permutations / flips, then a least-squares
     translation);
  3. move the spacebar's stabilizer boxes onto the PCB's stabilizer holes (the stock plate's
     sit at rev 2.3's 125.35 mm) and check them;
  4. write pcb/plate/plate-9u, plate-6.25u and plate-dual.kicad_pcb with every loop on
     Edge.Cuts, and a JSON of the mounting features in PCB coordinates for the layout.

Run:  python3 pcb/tools/gen_plate.py
"""
import json
import math
import os
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout  # noqa: E402
import plate_step as P  # noqa: E402
import gen_fp  # noqa: E402  (SPACEBAR_STABS: the PCB's stabilizer holes)

HEADER = os.path.join(HERE, "plate_header.kicad_pcb")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "plate"))
STABILIZED = {"SW12", "SW22", "SW54", "SW52"}   # Return, Num0, NumEnter, Space: not plain 14 mm openings
SPACEBAR = "SW52"


UUID_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "rev3-plate.the-c128-keyboard-project")


def uid(key):
    """Deterministic UUID so regeneration only changes what actually changed."""
    return str(uuid.uuid5(UUID_NS, key))


# Every loop is written as ONE closed polygon (gr_poly) with arcs flattened to short chords.
# Fab gerber viewers stitch the board outline from the profile layer and need every contour
# to close *exactly*.  Separate gr_line/gr_arc primitives do not guarantee that: KiCad
# recomputes arc endpoints on export and they land a nanometer off the neighboring line,
# the outer contour fails to close, and JLCPCB's viewer then falls back to filling everything
# the strokes enclose, i.e. the switch cutouts render as solid plate.  A closed polyline
# repeats its first vertex verbatim, so it always closes.  Chord error is kept under
# CHORD_ERR, far inside any routing tolerance.
#
# Note on JLCPCB's online gerber viewer: it previews this plate with the switch cutouts
# filled.  That is a limit of the viewer, not of these files.  Bisection on 2026-09-22
# showed it resolves inner cutouts only while the outer contour carries at most ONE edge
# feature (notch or slot); this outline has five, so no flattening of the arcs, however
# coarse, makes the preview right.  Details and how to verify the gerbers instead are in
# the README.
CHORD_ERR = 0.005                    # mm
OUTER_MIN_STEP = 0.0                 # outline arcs flattened like everything else


def arc_points(c, r, a1, sweep, min_step=0.0):
    """Interior points of an arc from angle a1 through `sweep` radians (sign = direction)."""
    if r <= CHORD_ERR:
        return []
    step = max(min_step, min(math.radians(5), 2 * math.acos(1 - CHORD_ERR / r)))
    n = max(1, math.ceil(abs(sweep) / step))
    return [(c[0] + r * math.cos(a1 + sweep * i / n), c[1] + r * math.sin(a1 + sweep * i / n)) for i in range(1, n)]


def loop_vertices(segs, outer=False):
    """Flatten an ordered loop of line/arc segments (or a lone circle) to a closed vertex list."""
    min_step = OUTER_MIN_STEP if outer else 0.0
    if len(segs) == 1 and segs[0]["type"] == "circle":
        c, r = segs[0]["c"], segs[0]["r"]
        return arc_points(c, r, 0, 2 * math.pi, min_step) + [(c[0] + r, c[1])]
    pts = []
    for sg in segs:
        pts.append(sg["a"])
        if sg["type"] == "arc":
            c, r = sg["c"], sg["r"]
            ang = lambda p: math.atan2(p[1] - c[1], p[0] - c[0])
            a1, am, a2 = ang(sg["a"]), ang(sg["mid"]), ang(sg["b"])
            ccw = (a2 - a1) % (2 * math.pi)
            # the mid point tells us which way round the arc goes
            sweep = ccw if (am - a1) % (2 * math.pi) <= ccw else -((a1 - a2) % (2 * math.pi))
            pts += arc_points(c, r, a1, sweep, min_step)
    return pts


def fit_transform(plate_pts, pcb_pts):
    """Try the 8 axis mappings; return (fn, rms) with fn: (u,v) -> (x,y)."""
    best = None
    for perm in ((0, 1), (1, 0)):
        for sx in (1, -1):
            for sy in (1, -1):
                def raw(p, perm=perm, sx=sx, sy=sy):
                    return (sx * p[perm[0]], sy * p[perm[1]])
                q = [raw(p) for p in plate_pts]
                cx = sum(x for x, _ in pcb_pts) / len(pcb_pts) - sum(x for x, _ in q) / len(q)
                cy = sum(y for _, y in pcb_pts) / len(pcb_pts) - sum(y for _, y in q) / len(q)
                moved = [(x + cx, y + cy) for x, y in q]
                # nearest-neighbor residuals
                err = 0
                for m in moved:
                    err += min((m[0] - t[0]) ** 2 + (m[1] - t[1]) ** 2 for t in pcb_pts)
                rms = math.sqrt(err / len(moved))
                if best is None or rms < best[1]:
                    def fn(p, perm=perm, sx=sx, sy=sy, cx=cx, cy=cy):
                        return (round(sx * p[perm[0]] + cx, 4), round(sy * p[perm[1]] + cy, 4))
                    best = (fn, rms, (perm, sx, sy, round(cx, 4), round(cy, 4)))
    return best


def kicad_header():
    """The board's layer stack, setup and plot settings (KiCad's two-layer defaults, 1.5 mm
    thick), kept verbatim in plate_header.kicad_pcb: everything up to the first drawing."""
    return open(HEADER, encoding="utf-8").read()


def edge_poly(segs, T, key, width=0.1, outer=False):
    """One closed polygon on Edge.Cuts for a whole loop, in PCB coordinates."""
    pts, last = [], None
    for p in loop_vertices(segs, outer):
        q = T(p)
        if q != last:
            pts.append(q); last = q
    if len(pts) > 1 and pts[-1] == pts[0]:
        pts.pop()
    xy = " ".join(f"(xy {x} {y})" for x, y in pts)
    return (f'\t(gr_poly (pts {xy}) (stroke (width {width}) (type default)) (fill no)'
            f' (layer "Edge.Cuts") (uuid "{uid(key)}"))')


def copper_pour(segs, T, key, layer="F.Cu"):
    """A zone covering the whole plate on one copper layer.

    Aluminum-core PCBs are ordered as a single copper layer under soldermask, so the copper is
    what carries the plate's finish color; and fab gerber viewers paint the board from copper
    and mask, so without it the cutouts preview as solid plate (JLCPCB does exactly that).
    The fill is computed by KiCad (fill_zones below), which keeps the board's copper-to-edge
    clearance from every Edge.Cuts contour, cutouts included."""
    pts, last = [], None
    for p in loop_vertices(segs):
        q = T(p)
        if q != last:
            pts.append(q); last = q
    xy = " ".join(f"(xy {x} {y})" for x, y in pts)
    return (f'\t(zone (net 0) (net_name "") (layer "{layer}") (uuid "{uid(key)}") (name "plate")'
            f' (hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no)'
            f' (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon (pts {xy})))')


def fill_zones(paths):
    """Let KiCad compute the zone fills (kicad-cli cannot); uses the app bundle's python."""
    py = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
    if not os.path.exists(py):
        print("KiCad python not found: zones left unfilled; open in pcbnew and press B")
        return
    script = ("import pcbnew, sys\n"
              "for p in sys.argv[1:]:\n"
              "    b = pcbnew.LoadBoard(p)\n"
              "    pcbnew.ZONE_FILLER(b).Fill(b.Zones())\n"
              "    b.Save(p)\n")
    r = subprocess.run([py, "-c", script] + list(paths), capture_output=True, text=True)
    if r.returncode:
        print("zone fill failed:", r.stderr.strip()[-400:])
    else:
        print("zones filled by pcbnew")
    for p in paths:                       # pcbnew's Save() drops a project file beside each board
        pro = p[:-len(".kicad_pcb")] + ".kicad_pro"
        if os.path.exists(pro):
            os.remove(pro)


def text(s, at, size=1.5, layer="F.SilkS"):
    return (f'\t(gr_text "{s}" (at {at[0]} {at[1]} 0) (layer "{layer}") (uuid "{uid("text:" + s)}")'
            f' (effects (font (size {size} {size}) (thickness {size/8:.3f})) (justify left)))')


def spacebar_cutout(cls):
    """Index of the spacebar's dumbbell cutout (the only cutout over 100 mm long)."""
    found = [i for i, c in enumerate(cls) if c["kind"] == "cutout" and max(c["w"], c["h"]) > 100]
    assert len(found) == 1, found
    return found[0]


def box_centers(h, c):
    """Long-axis centers of the two stabilizer boxes of a spacebar cutout, as (low, high).

    The stock cutout is a dumbbell: switch square in the middle, a wire channel each side, a
    housing box near each end.  Along the long axis a box runs from its inner edge to its
    outer edge, and the wire notch sticks out 0.8 mm past the outer edge; so a box's center
    is midway between the nearest coordinate to the middle and the second farthest."""
    ax = 0 if c["w"] > c["h"] else 1
    mid = c["cx"] if ax == 0 else c["cy"]
    coords = sorted({round(v[ax], 5) for s in h for k in ("a", "b") for v in (s[k],)})
    out = []
    for side in (-1, 1):
        far = sorted((v for v in coords if (v - mid) * side > 20), key=lambda v: abs(v - mid))
        out.append((far[0] + far[-2]) / 2)
    return tuple(out)


def long_axis(c, T):
    """For a cutout: its long axis and middle in the plate frame, the PCB axis that long axis
    maps to through T, and the sense of that mapping (+1 or -1)."""
    ax = 0 if c["w"] > c["h"] else 1
    mid = c["cx"] if ax == 0 else c["cy"]
    p0, p1 = [c["cx"], c["cy"]], [c["cx"], c["cy"]]
    p1[ax] += 1
    q0, q1 = T(tuple(p0)), T(tuple(p1))
    pax = 0 if abs(q1[0] - q0[0]) > abs(q1[1] - q0[1]) else 1
    return ax, mid, pax, (1 if q1[pax] > q0[pax] else -1)


def spacebar_variant(holes, cls, half, T, sw):
    """A copy of the hole loops with the spacebar's stabilizer boxes centered on the PCB's
    stabilizer holes at `sw` (the spacebar switch center, PCB frame) +/- `half` mm.

    The boxes are placed from the board, not from a spacing assumed for the stock plate: the
    stock plate's boxes sit at 125.35 mm, rev 2.3's spacing, while rev 3 drills 100 and
    133.35 (gen_fp.SPACEBAR_STABS).  Each box, with its end of the wire channel, moves along
    the long axis until its center maps through T onto its hole."""
    i = spacebar_cutout(cls)
    h, c = holes[i], cls[i]
    ax, mid, pax, sense = long_axis(c, T)

    def at(t):                                  # PCB point of long-axis coordinate t
        p = [c["cx"], c["cy"]]
        p[ax] = t
        return T(tuple(p))

    shifts = {}
    for side, t_c in zip((-1, 1), box_centers(h, c)):
        target = sw[pax] + side * sense * half  # this side's hole, PCB frame
        shifts[side] = (target - at(t_c)[pax]) * sense

    def mv(p):
        dlt = p[ax] - mid
        if abs(dlt) > 20:
            q = list(p)
            q[ax] = round(p[ax] + shifts[1 if dlt > 0 else -1], 5)
            return tuple(q)
        return p
    nh = []
    for seg in h:
        ns = dict(seg)
        for k in ("a", "b", "mid", "c"):
            if k in ns:
                ns[k] = mv(ns[k])
        nh.append(ns)
    out = list(holes)
    out[i] = nh
    return out


def check_spacebar(holes, cls, halves, T, sw):
    """Every stabilizer hole pair the PCB drills has a box centered on it (to 0.02 mm)."""
    i = spacebar_cutout(cls)
    c = cls[i]
    ax, _, pax, _ = long_axis(c, T)
    pts = {(round(v[0], 5), round(v[1], 5)) for s in holes[i] for v in (s["a"], s["b"])}
    long_coords = sorted({p[ax] for p in pts})
    # every box: an inner edge, an outer edge 6.75 mm on (the housing's length)
    boxes = []
    for a in long_coords:
        for b in long_coords:
            if abs(b - a - 6.75) < 0.01:
                p = [c["cx"], c["cy"]]; p[ax] = (a + b) / 2
                boxes.append(T(tuple(p)))
    for half in halves:
        for side in (-1, 1):
            want = sw[pax] + side * half
            err = min(abs(bx[pax] - want) for bx in boxes)
            assert err < 0.02, f"no stabilizer box over the hole at {want:.3f} ({err:.3f} mm off)"


def rectilinear_union(loops, snap=0.002):
    """Union of closed loops made only of horizontal and vertical lines, as one loop.

    Coordinate compression: every distinct x and y (values within `snap` merged, since the
    STEP export has a few 1 um slips) cuts the plane into cells; a cell is filled if its
    center is inside any loop; the filled cells' outer boundary, walked with the filled side
    on the left and collinear runs merged, is the result.  Assumes the union is one piece
    without islands, which holds for a spacebar cutout and its shifted copy."""
    def cluster(vals):
        out = []
        for v in sorted(vals):
            if not out or v - out[-1][-1] > snap:
                out.append([v])
            else:
                out[-1].append(v)
        return [sum(g) / len(g) for g in out]

    pts = [p for loop in loops for s in loop for p in (s["a"], s["b"])]
    xs, ys = cluster({p[0] for p in pts}), cluster({p[1] for p in pts})

    def near(v, axis):
        return min(axis, key=lambda a: abs(a - v))

    polys = [[(near(s["a"][0], xs), near(s["a"][1], ys)) for s in loop] for loop in loops]

    def inside(px, py, poly):
        c = False
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        return c

    nx, ny = len(xs) - 1, len(ys) - 1
    fill = [[any(inside((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2, p) for p in polys)
             for j in range(ny)] for i in range(nx)]

    def filled(i, j):
        return 0 <= i < nx and 0 <= j < ny and fill[i][j]

    # directed boundary edges on the grid of corner indices, filled cell on the left (y up)
    nxt = {}
    for i in range(nx):
        for j in range(ny):
            if not fill[i][j]:
                continue
            if not filled(i, j - 1):
                nxt[(i, j)] = (i + 1, j)
            if not filled(i + 1, j):
                nxt[(i + 1, j)] = (i + 1, j + 1)
            if not filled(i, j + 1):
                nxt[(i + 1, j + 1)] = (i, j + 1)
            if not filled(i - 1, j):
                nxt[(i, j + 1)] = (i, j)
    start = min(nxt)
    ring, cur = [start], nxt[start]
    while cur != start:
        ring.append(cur)
        cur = nxt[cur]
    assert len(ring) == len(nxt), "union is not one simple piece"
    # merge collinear runs
    corners = [p for k, p in enumerate(ring)
               if not ((ring[k - 1][0] == p[0] == ring[(k + 1) % len(ring)][0]) or
                       (ring[k - 1][1] == p[1] == ring[(k + 1) % len(ring)][1]))]
    xy = [(round(xs[i], 5), round(ys[j], 5)) for i, j in corners]
    return [{"type": "line", "a": a, "b": b} for a, b in zip(xy, xy[1:] + xy[:1])]


def dual_spacebar(holes, cls, halves, T, sw):
    """A spacebar cutout with a pair of stabilizer boxes for each of `halves`, so either
    spacebar's stabilizers fit: the union of the single-spacebar cutouts."""
    i = spacebar_cutout(cls)
    assert all(seg["type"] == "line" for seg in holes[i]), "spacebar cutout has curves"
    out = list(holes)
    out[i] = rectilinear_union([spacebar_variant(holes, cls, h, T, sw)[i] for h in halves])
    return out


def write_board(name, geo, holes, T, note):
    lines = [kicad_header()]
    lines.append(edge_poly(geo["outer"], T, f"{name}:outer", outer=True))
    for i, h in enumerate(holes):
        lines.append(edge_poly(h, T, f"{name}:hole:{i}"))
    lines.append(copper_pour(geo["outer"], T, f"{name}:pour"))
    bb = P.loop_bbox(geo["outer"])
    corners = [T((bb[0], bb[1])), T((bb[2], bb[3]))]
    x0, y0 = min(c[0] for c in corners), min(c[1] for c in corners)
    x1, y1 = max(c[0] for c in corners), max(c[1] for c in corners)
    # legend inside the outline, in the free strip under the spacebar cutout: anything drawn
    # outside the outline inflates the board size the fab quotes on
    lines.append(text(f"C128 keyboard plate rev 3 ({note}) - 1.5 mm aluminum PCB - c128-led-keyboard",
                      (x0 + 235, y1 - 2.4), size=1.0))
    lines.append("\t(embedded_fonts no)\n)")
    out = os.path.join(OUT_DIR, name)
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("wrote", out, f"outline {x1-x0:.2f} x {y1-y0:.2f} mm at ({x0:.2f},{y0:.2f})")
    return x0, y0, x1, y1


def main():
    geo = layout.load_plate()
    cls = [P.classify(h) for h in geo["holes"]]
    switches = layout.load_switches()
    plate_sw = [(c["cx"], c["cy"]) for c in cls if c["kind"] == "switch"]
    pcb_sw = [(s["x"], s["y"]) for s in switches if s["ref"] not in STABILIZED]
    assert len(plate_sw) == len(pcb_sw) == 88, (len(plate_sw), len(pcb_sw))
    T, rms, params = fit_transform(plate_sw, pcb_sw)
    print(f"transform {params}, switch-center RMS {rms:.3f} mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    # the spacebar's stabilizer boxes go over the PCB's stabilizer holes: 6.25u and 9u sets
    sw = next((s["x"], s["y"]) for s in switches if s["ref"] == SPACEBAR)
    h625, h9 = gen_fp.SPACEBAR_STABS
    variants = [("plate-9u.kicad_pcb", spacebar_variant(geo["holes"], cls, h9, T, sw), (h9,),
                 f"9u spacebar, stabs at {2 * h9:g} mm"),
                ("plate-6.25u.kicad_pcb", spacebar_variant(geo["holes"], cls, h625, T, sw), (h625,),
                 f"6.25u spacebar, stabs at {2 * h625:g} mm"),
                ("plate-dual.kicad_pcb", dual_spacebar(geo["holes"], cls, (h9, h625), T, sw), (h9, h625),
                 f"9u or 6.25u spacebar, stabs at {2 * h9:g} and {2 * h625:g} mm")]
    for name, holes, halves, note in variants:
        check_spacebar(holes, cls, halves, T, sw)
        x0, y0, x1, y1 = write_board(name, geo, holes, T, note)
    print("spacebar stabilizer boxes centered on the PCB's holes in every plate")
    fill_zones([os.path.join(OUT_DIR, n) for n, *_ in variants])

    # feature table in PCB coordinates
    feats = []
    for c in cls:
        if c["kind"] == "switch":
            continue
        x, y = T((c["cx"], c["cy"]))
        f = {"kind": c["kind"], "x": x, "y": y}
        if c["kind"] == "hole":
            f["d"] = c["d"]
        else:
            # width/height swap if the axes were permuted
            f["w"], f["h"] = (c["w"], c["h"]) if params[0] == (0, 1) else (c["h"], c["w"])
        feats.append(f)
    feats.sort(key=lambda f: (f["kind"], f["y"], f["x"]))
    json.dump({"transform": params, "rms": rms, "outline_bbox": [x0, y0, x1, y1], "features": feats},
              open(os.path.join(OUT_DIR, "plate_features.json"), "w"), indent=1)
    print("features (PCB coordinates):")
    for f in feats:
        print("  ", f)


if __name__ == "__main__":
    main()
