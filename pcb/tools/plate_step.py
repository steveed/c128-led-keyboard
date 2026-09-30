#!/usr/bin/env python3
"""Pull the 2-D plate geometry out of a plate STEP model (plate.step).

The plate is a flat extrusion, so one planar face carries everything: the outer outline and
one inner loop per cutout (switch openings, stabilizer clearance, mounting holes, slots).
This reads the STEP B-rep directly (no CAD kernel needed): ADVANCED_FACE -> FACE_BOUND ->
EDGE_LOOP -> ORIENTED_EDGE -> EDGE_CURVE -> LINE / CIRCLE, and returns each loop as a list of
segments in the plane of the plate.

Usage:
    python3 plate_step.py plate.step            # summary
    python3 plate_step.py plate.step --json out.json

extract_layout.py uses it to write layout/plate.json.
"""
import json
import math
import re
import sys

TOL = 1e-4


# --- STEP part 21 parsing ----------------------------------------------------------------

def load_entities(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    data = text[text.index("DATA;") + 5:text.rindex("ENDSEC;")]
    ents = {}
    # entities end with ';' at end of a statement; strings can contain ';' but Fusion's do not
    for stmt in re.split(r";\s*\n", data):
        stmt = stmt.strip()
        if not stmt.startswith("#"):
            continue
        m = re.match(r"#(\d+)\s*=\s*(.*)$", stmt, re.S)
        if not m:
            continue
        eid = int(m.group(1))
        body = m.group(2).strip()
        typ_m = re.match(r"([A-Z_0-9]+)\s*\(", body)
        if typ_m:
            typ = typ_m.group(1)
            args = parse_args(body[typ_m.end() - 1:])
        else:
            typ, args = "COMPLEX", body   # e.g. ( A() B() ) complex entities; not needed here
        ents[eid] = (typ, args)
    return ents


def parse_args(s):
    """Parse a parenthesised STEP argument list into nested Python lists.
    Refs -> ('#', id); strings -> str; enums -> ('.', name); numbers -> float; '*'/'$' -> None."""
    tokens = re.findall(r"#\d+|'(?:[^']|'')*'|\.[A-Z_0-9]+\.|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?|\(|\)|,|\*|\$", s)
    pos = [0]

    def parse_list():
        assert tokens[pos[0]] == "("
        pos[0] += 1
        out = []
        while tokens[pos[0]] != ")":
            t = tokens[pos[0]]
            if t == "(":
                out.append(parse_list())
                continue
            elif t == ",":
                pos[0] += 1
                continue
            elif t.startswith("#"):
                out.append(("#", int(t[1:])))
            elif t.startswith("'"):
                out.append(t[1:-1])
            elif t.startswith("."):
                out.append((".", t[1:-1]))
            elif t in ("*", "$"):
                out.append(None)
            else:
                out.append(float(t))
            pos[0] += 1
        pos[0] += 1
        return out
    return parse_list()


class Step:
    def __init__(self, path):
        self.e = load_entities(path)

    def get(self, ref):
        return self.e[ref[1] if isinstance(ref, tuple) else ref]

    def point(self, ref):
        typ, a = self.get(ref)
        assert typ == "CARTESIAN_POINT", typ
        return tuple(a[1])

    def direction(self, ref):
        typ, a = self.get(ref)
        assert typ == "DIRECTION", typ
        return tuple(a[1])

    def placement(self, ref):
        typ, a = self.get(ref)
        assert typ == "AXIS2_PLACEMENT_3D", typ
        loc = self.point(a[1])
        axis = self.direction(a[2]) if a[2] else (0, 0, 1)
        return loc, axis

    def faces(self):
        return [eid for eid, (t, _) in self.e.items() if t == "ADVANCED_FACE"]


# --- geometry -----------------------------------------------------------------------------

def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def plate_face(step):
    """Return (face_id, plane_origin, plane_normal, u_axis, v_axis) of the planar face with
    the most boundary loops on the side facing +normal (the 'top')."""
    best = None
    for fid in step.faces():
        _, a = step.get(fid)
        bounds, surf = a[1], a[2]
        st, sa = step.get(surf)
        if st != "PLANE":
            continue
        loc, axis = step.placement(sa[1])
        key = (len(bounds), dot(loc, axis))
        if best is None or key > best[0]:
            best = (key, fid, loc, axis)
    _, fid, loc, axis = best
    # in-plane axes: pick the world axis least aligned with the normal as 'up' helper
    n = axis
    helper = min([(1, 0, 0), (0, 1, 0), (0, 0, 1)], key=lambda w: abs(dot(w, n)))
    u = cross(helper, n)
    u = norm(u)
    v = cross(n, u)
    return fid, loc, n, u, v


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    l = math.sqrt(dot(a, a))
    return tuple(x / l for x in a)


def face_loops(step, fid, origin, n, u, v):
    """Yield (is_outer, [segments]) where a segment is
    {'type': 'line', 'a': (x,y), 'b': (x,y)} or
    {'type': 'arc', 'a': .., 'b': .., 'mid': .., 'c': (x,y), 'r': r} or
    {'type': 'circle', 'c': (x,y), 'r': r}."""
    def to2d(p):
        d = sub(p, origin)
        return (round(dot(d, u), 5), round(dot(d, v), 5))

    _, a = step.get(fid)
    for bref in a[1]:
        bt, ba = step.get(bref)
        is_outer = bt == "FACE_OUTER_BOUND"
        lt, la = step.get(ba[1])
        assert lt == "EDGE_LOOP", lt
        segs = []
        for oeref in la[1]:
            _, oa = step.get(oeref)
            edge_ref, orient = oa[3], oa[4][1] == "T"
            et, ea = step.get(edge_ref)
            assert et == "EDGE_CURVE", et
            v1 = step.point(step.get(ea[1])[1][1])
            v2 = step.point(step.get(ea[2])[1][1])
            ct, ca = step.get(ea[3])
            same_sense = ea[4][1] == "T"
            if not orient:
                v1, v2 = v2, v1
            p1, p2 = to2d(v1), to2d(v2)
            if ct == "LINE":
                segs.append({"type": "line", "a": p1, "b": p2})
            elif ct == "CIRCLE":
                loc, axis = step.placement(ca[1])
                r = ca[2]
                c = to2d(loc)
                # direction of travel about the plate normal
                ccw = (dot(axis, n) > 0) == same_sense
                if not orient:
                    ccw = not ccw
                if math.dist(p1, p2) < TOL:
                    segs.append({"type": "circle", "c": c, "r": r})
                    continue
                a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
                a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
                sweep = (a2 - a1) % (2 * math.pi) if ccw else -((a1 - a2) % (2 * math.pi))
                am = a1 + sweep / 2
                mid = (round(c[0] + r * math.cos(am), 5), round(c[1] + r * math.sin(am), 5))
                segs.append({"type": "arc", "a": p1, "b": p2, "mid": mid, "c": c, "r": r})
            else:
                raise SystemExit(f"unsupported curve {ct} in edge #{edge_ref[1]}")
        yield is_outer, clean_loop(segs)


def clean_loop(segs, tiny=0.005):
    """Drop sub-micron sliver segments (tangent artifacts of the CAD export) and stitch the
    neighbors back together so the loop stays closed."""
    keep = [s for s in segs if s["type"] == "circle" or math.dist(s["a"], s["b"]) >= tiny]
    for prev, cur in zip(keep, keep[1:] + keep[:1]):
        if prev["type"] != "circle" and cur["type"] != "circle" and math.dist(prev["b"], cur["a"]) < tiny:
            cur["a"] = prev["b"]
    return keep


def loop_bbox(segs):
    xs, ys = [], []
    for s in segs:
        if s["type"] == "circle":
            xs += [s["c"][0] - s["r"], s["c"][0] + s["r"]]
            ys += [s["c"][1] - s["r"], s["c"][1] + s["r"]]
        else:
            for k in ("a", "b") + (("mid",) if s["type"] == "arc" else ()):
                xs.append(s[k][0]); ys.append(s[k][1])
    return min(xs), min(ys), max(xs), max(ys)


def classify(segs):
    x0, y0, x1, y1 = loop_bbox(segs)
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    kinds = {s["type"] for s in segs}
    if kinds == {"circle"} or (kinds <= {"arc"} and abs(w - h) < 0.05):
        return {"kind": "hole", "d": round(w, 3), "cx": round(cx, 3), "cy": round(cy, 3)}
    if abs(w - h) < 0.6 and 13.5 <= w <= 16.5:
        return {"kind": "switch", "w": round(w, 3), "h": round(h, 3), "cx": round(cx, 3), "cy": round(cy, 3)}
    if kinds == {"line"} and len(segs) == 8 and w < 12:
        # U-shaped slot around a tongue that carries a screw hole (front-corner tabs)
        return {"kind": "tab_slot", "w": round(w, 3), "h": round(h, 3), "cx": round(cx, 3), "cy": round(cy, 3)}
    return {"kind": "cutout", "w": round(w, 3), "h": round(h, 3), "cx": round(cx, 3), "cy": round(cy, 3),
            "segments": len(segs)}


def extract(path):
    step = Step(path)
    fid, origin, n, u, v = plate_face(step)
    outer, holes = None, []
    for is_outer, segs in face_loops(step, fid, origin, n, u, v):
        if is_outer:
            outer = segs
        else:
            holes.append(segs)
    return {"face": fid, "normal": n, "u": u, "v": v, "origin": origin, "outer": outer, "holes": holes}


def main():
    path = sys.argv[1]
    geo = extract(path)
    bb = loop_bbox(geo["outer"])
    print(f"plate face #{geo['face']}, normal {tuple(round(x, 3) for x in geo['normal'])}")
    print(f"outline bbox {bb[0]:.2f}..{bb[2]:.2f} x {bb[1]:.2f}..{bb[3]:.2f}  ->  {bb[2]-bb[0]:.2f} x {bb[3]-bb[1]:.2f} mm, {len(geo['outer'])} segments")
    cls = [classify(h) for h in geo["holes"]]
    from collections import Counter
    print("inner loops:", len(cls), Counter(c["kind"] for c in cls))
    for kind in ("hole", "cutout", "tab_slot", "switch"):
        items = [c for c in cls if c["kind"] == kind]
        if kind == "switch":
            sizes = Counter((c["w"], c["h"]) for c in items)
            print(f"  switch cutouts: sizes {dict(sizes)}")
            continue
        for c in sorted(items, key=lambda c: (c["cy"], c["cx"])):
            print("  ", c)
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump({"outer": geo["outer"], "holes": geo["holes"], "classified": cls,
                   "normal": geo["normal"], "u": geo["u"], "v": geo["v"], "origin": geo["origin"]},
                  open(out, "w"), indent=0)
        print("wrote", out)


if __name__ == "__main__":
    main()
