#!/usr/bin/env python3
"""Tidy the routed copper on pcb/C128-keyboard-rev3.kicad_pcb.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/tidy.py [--report] [--no-straighten] [--mark]

Only unlocked copper is touched; locked groups (route_keys, plane_taps, route_host) and their
ends are fixed anchors.  In order:

  1. split segments wherever another same-net track ends on their middle (a T), so every
     junction is a shared endpoint;
  2. delete copper that carries nothing: segments wholly inside one pad, duplicate vias,
     and tracks and signal vias KiCad calls dangling, repeatedly (plane nets keep their
     vias: they tap In1/In2);
  3. straighten: each chain of segments between anchors (pads, vias, junctions, layer or
     width changes, locked copper) is string-pulled: from each anchor take the farthest bend
     still reachable by a one- or two-segment 0/45/90-degree path that clears every other
     net's copper, the board edge and the holes, and replace the bends in between.  This
     merges collinear runs and removes the router's zigzags and odd angles.

--report prints the counts and the worst chains (most segments, longest detour) without
saving;  --mark also draws a circle on Eco1.User at each one, in the group "tidy_marks".
Every change is checked against KiCad's connectivity and undone if the unconnected count
rises.  After a run, check with DRC (parity and copper) as usual.
"""
import argparse
import collections
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
PLANE_NETS = {"GND", "+5V_SYS"}
KEEP_NETS = {"USB_DP", "USB_DN", "USB_DP_C", "USB_DN_C"}   # a pair: straighten by hand, together
MARGIN = pcbnew.FromMM(0.01)          # on top of the rule clearance
CELL = pcbnew.FromMM(2.0)             # spatial index cell
MARK_GROUP = "tidy_marks"


def mm(v):
    return pcbnew.FromMM(v)


def key(p):
    return (p.x, p.y)


def uid(item):
    # SWIG hands out a new wrapper on every call, so `is` and id() don't identify items
    return item.m_Uuid.AsString()


def is_seg(t):
    return t.GetClass() == "PCB_TRACK"


def is_via(t):
    return t.GetClass() == "PCB_VIA"


def seg_len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def octilinear(a, b, tol=1000):
    """0, 45 or 90 degrees, to within 1 um (the router's rounding)."""
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    return dx <= tol or dy <= tol or abs(dx - dy) <= tol


def paths(a, b):
    """One- or two-segment 0/45/90 paths from a to b, shortest first (all equal length)."""
    if octilinear(a, b, 0):
        return [[a, b]]
    dx, dy = b[0] - a[0], b[1] - a[1]
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    d = min(abs(dx), abs(dy))
    diag_first = (a[0] + sx * d, a[1] + sy * d)
    diag_last = (b[0] - sx * d, b[1] - sy * d)
    return [[a, diag_first, b], [a, diag_last, b]]


class Index:
    """Grid index of copper items per layer, for clearance checks."""

    def __init__(self, board):
        self.board = board
        self.cells = collections.defaultdict(list)
        self.edge = board.GetBoardEdgesBoundingBox()
        for t in board.GetTracks():
            self.add(t)
        for fp in board.GetFootprints():
            for p in fp.Pads():
                self.add(p)

    def _cells(self, bb):
        for cx in range(bb.GetLeft() // CELL, bb.GetRight() // CELL + 1):
            for cy in range(bb.GetTop() // CELL, bb.GetBottom() // CELL + 1):
                yield (cx, cy)

    def add(self, item):
        for c in self._cells(item.GetBoundingBox()):
            self.cells[c].append(item)

    def remove(self, item):
        for c in self._cells(item.GetBoundingBox()):
            u = uid(item)
            self.cells[c] = [i for i in self.cells.get(c, ()) if uid(i) != u]

    def near(self, bb):
        seen = set()
        for c in self._cells(bb):
            for it in self.cells.get(c, ()):
                if uid(it) not in seen:
                    seen.add(uid(it))
                    yield it

    def clear(self, pts, net, layer, width, own_clearance, ignore):
        """True if a track of `width` along pts on `layer` keeps clearance from other nets."""
        edge_in = pcbnew.BOX2I(self.edge.GetPosition(), self.edge.GetSize())
        edge_in.Inflate(-(self.board.GetDesignSettings().m_CopperEdgeClearance + width // 2))
        for a, b in zip(pts, pts[1:]):
            va, vb = pcbnew.VECTOR2I(*a), pcbnew.VECTOR2I(*b)
            if not (edge_in.Contains(va) and edge_in.Contains(vb)):
                return False
            shape = pcbnew.SHAPE_SEGMENT(va, vb, width)
            bb = pcbnew.BOX2I(pcbnew.VECTOR2I(min(a[0], b[0]), min(a[1], b[1])),
                              pcbnew.VECTOR2L(abs(b[0] - a[0]), abs(b[1] - a[1])))
            bb.Inflate(width + mm(1.0))
            for it in self.near(bb):
                if uid(it) in ignore:
                    continue
                if not it.IsOnLayer(layer) and not (it.GetClass() == "PAD" and it.HasHole()):
                    continue
                same = it.GetNetCode() == net and net != 0
                if same:
                    continue
                clr = max(own_clearance, it.GetOwnClearance(layer)) + MARGIN
                if it.IsOnLayer(layer) and it.GetEffectiveShape(layer).Collide(shape, clr):
                    return False
                if it.GetClass() in ("PAD", "PCB_VIA") and it.HasHole():
                    hole = it.GetEffectiveHoleShape()
                    hc = self.board.GetDesignSettings().m_HoleClearance + MARGIN
                    if hole.Collide(shape, hc):
                        return False
        return True


def on_segment(p, t):
    """p lies strictly inside segment t (not at an end)."""
    a, b = t.GetStart(), t.GetEnd()
    if min(seg_len(key(p), key(a)), seg_len(key(p), key(b))) < 1000:
        return False
    ab = b - a
    ap = p - a
    cross = ab.x * ap.y - ab.y * ap.x
    L = math.hypot(ab.x, ab.y)
    if L == 0 or abs(cross) / L > 1000:          # within 1 um of the line
        return False
    dot = ab.x * ap.x + ab.y * ap.y
    return 0 < dot < ab.x * ab.x + ab.y * ab.y


class Copper:
    def __init__(self, board):
        self.board = board
        self.pads = [p for fp in board.GetFootprints() for p in fp.Pads()]

    def segs(self):
        return [t for t in self.board.GetTracks() if is_seg(t)]

    def vias(self):
        return [t for t in self.board.GetTracks() if is_via(t)]

    def pad_at(self, p, layer, net):
        v = pcbnew.VECTOR2I(*p)
        for pad in self.pads:
            if pad.GetNetCode() == net and pad.IsOnLayer(layer) and pad.HitTest(v):
                return pad
        return None

    def ends(self, segs=None):
        """(layer, point) -> segments ending there; point -> vias."""
        ends = collections.defaultdict(list)
        for t in segs if segs is not None else self.segs():
            ends[(t.GetLayer(), key(t.GetStart()))].append(t)
            ends[(t.GetLayer(), key(t.GetEnd()))].append(t)
        vias = collections.defaultdict(list)
        for v in self.vias():
            vias[key(v.GetPosition())].append(v)
        return ends, vias


def split_tees(board):
    segs = [t for t in board.GetTracks() if is_seg(t)]
    by_net = collections.defaultdict(list)
    for t in segs:
        by_net[(t.GetNetCode(), t.GetLayer())].append(t)
    points = collections.defaultdict(set)
    for t in segs:
        for p in (t.GetStart(), t.GetEnd()):
            points[(t.GetNetCode(), t.GetLayer())].add(key(p))
    for v in board.GetTracks():
        if is_via(v):
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                points[(v.GetNetCode(), layer)].add(key(v.GetPosition()))
    n = 0
    for k, ts in by_net.items():
        for t in list(ts):
            if t.IsLocked():
                continue
            cuts = [p for p in points[k] if on_segment(pcbnew.VECTOR2I(*p), t)]
            if not cuts:
                continue
            a = t.GetStart()
            cuts.sort(key=lambda p: seg_len(key(a), p))
            prev = key(a)
            end = key(t.GetEnd())
            for p in cuts + [end]:
                nt = pcbnew.PCB_TRACK(board)
                nt.SetStart(pcbnew.VECTOR2I(*prev)); nt.SetEnd(pcbnew.VECTOR2I(*p))
                nt.SetLayer(t.GetLayer()); nt.SetWidth(t.GetWidth()); nt.SetNet(t.GetNet())
                board.Add(nt)
                prev = p
            board.Delete(t)
            n += 1
    return n


class Guard:
    """KiCad's own connectivity: the unconnected count must never rise.

    Endpoints are not enough to judge connection by: a hand-drawn track often ends on a via's
    ring or a pad's edge rather than its center, and KiCad counts that as connected.
    """

    def __init__(self, board):
        self.board = board
        self.base = self.count()
        self.grave = []        # items off the board: hold them so Python never frees one in use


    def count(self):
        self.board.BuildConnectivity()
        return self.board.GetConnectivity().GetUnconnectedCount(True)

    def dangling(self, item):
        return self.board.GetConnectivity().TestTrackEndpointDangling(item, False)

    def try_remove(self, items, add=()):
        """Take items off the board (and put `add` on); keep the change only if nothing
        comes apart.  Returns True if kept."""
        for t in items:
            self.board.Remove(t)
        for t in add:
            self.board.Add(t)
            t.thisown = 0
        self.grave.extend(items)
        self.grave.extend(add)
        if self.count() <= self.base:
            return True
        for t in add:
            self.board.Remove(t)
        for t in items:
            self.board.Add(t)
        self.count()
        return False


def prune(board, cu, guard):
    """Delete copper that carries nothing, until nothing changes."""
    removed_s = removed_v = 0
    # zero-length segments, segments wholly inside one pad of their net, duplicate vias
    for t in cu.segs():
        if t.IsLocked():
            continue
        if key(t.GetStart()) != key(t.GetEnd()):
            pa = cu.pad_at(key(t.GetStart()), t.GetLayer(), t.GetNetCode())
            pb = cu.pad_at(key(t.GetEnd()), t.GetLayer(), t.GetNetCode())
            if pa is None or pb is None or uid(pa) != uid(pb):
                continue
        if guard.try_remove([t]):
            removed_s += 1
    seen = {}
    for v in cu.vias():
        k = (key(v.GetPosition()), v.GetNetCode())
        if k in seen and not v.IsLocked():
            if guard.try_remove([v]):
                removed_v += 1
        else:
            seen[k] = v
    # dangling tracks and vias, as KiCad's DRC sees them, repeatedly
    while True:
        guard.count()
        dead = [t for t in board.GetTracks()
                if not t.IsLocked() and guard.dangling(t)
                and not (is_via(t) and t.GetNetname() in PLANE_NETS)]
        if not dead or not guard.try_remove(dead):
            break
        removed_s += sum(1 for t in dead if is_seg(t))
        removed_v += sum(1 for t in dead if is_via(t))
    return removed_s, removed_v


def chains(board, cu):
    """Maximal runs of unlocked segments (same net, layer, width) through degree-2 bends."""
    all_segs = cu.segs()
    ends, vias = cu.ends(all_segs)
    segs = [t for t in all_segs if not t.IsLocked()]

    def other(here, t):
        return here[0] if uid(here[1]) == uid(t) else here[1]

    def anchor(layer, p, t):
        here = ends[(layer, p)]
        if len(here) != 2 or vias.get(p):
            return True
        o = other(here, t)
        if o.IsLocked() or o.GetWidth() != t.GetWidth() or o.GetNetCode() != t.GetNetCode():
            return True
        return cu.pad_at(p, layer, t.GetNetCode()) is not None

    done, out = set(), []
    for t in segs:
        if uid(t) in done:
            continue
        layer = t.GetLayer()
        # walk back to an anchor
        cur, p = t, key(t.GetStart())
        guard = 0
        while not anchor(layer, p, cur) and guard < 10000:
            here = ends[(layer, p)]
            nxt = other(here, cur)
            if uid(nxt) == uid(t):
                break                                   # a loop: start anywhere
            p = key(nxt.GetEnd()) if key(nxt.GetStart()) == p else key(nxt.GetStart())
            cur = nxt
            guard += 1
        # walk forward from p along cur
        pts, run = [p], []
        while True:
            done.add(uid(cur))
            run.append(cur)
            q = key(cur.GetEnd()) if key(cur.GetStart()) == p else key(cur.GetStart())
            pts.append(q)
            if anchor(layer, q, cur):
                break
            here = ends[(layer, q)]
            nxt = other(here, cur)
            if uid(nxt) in done:
                break
            cur, p = nxt, q
        out.append((pts, run))
    return out


def detour(pts):
    L = sum(seg_len(a, b) for a, b in zip(pts, pts[1:]))
    dx, dy = abs(pts[-1][0] - pts[0][0]), abs(pts[-1][1] - pts[0][1])
    ideal = max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
    return L, (L / ideal if ideal else float("inf"))


def ugly(pts):
    odd = sum(1 for a, b in zip(pts, pts[1:]) if not octilinear(a, b))
    short = sum(1 for a, b in zip(pts, pts[1:]) if seg_len(a, b) < mm(0.3))
    return odd, short


def straighten(board, cu, idx, guard):
    replaced = before = after = 0
    for pts, run in chains(board, cu):
        if len(run) < 2 and all(octilinear(a, b) for a, b in zip(pts, pts[1:])):
            continue
        t0 = run[0]
        net, layer, width = t0.GetNetCode(), t0.GetLayer(), t0.GetWidth()
        netinfo = t0.GetNet()
        own = t0.GetOwnClearance(layer)
        if pts[0] == pts[-1] or t0.GetNetname() in KEEP_NETS:
            continue                                     # a loop: leave it for a human
        ignore = {uid(t) for t in run}
        new = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            best = None
            for j in range(len(pts) - 1, i, -1):
                for cand in paths(pts[i], pts[j]):
                    if j == i + 1 and len(cand) == 2 and cand == [pts[i], pts[j]]:
                        best = (j, cand)                 # the existing segment: always fine
                        break
                    if idx.clear(cand, net, layer, width, own, ignore):
                        best = (j, cand)
                        break
                if best:
                    break
            if best is None:                             # odd-angle original segment, keep it
                best = (i + 1, [pts[i], pts[i + 1]])
            j, cand = best
            new.extend(cand[1:])
            i = j
        # drop collinear interior points
        simp = [new[0]]
        for p in new[1:]:
            if len(simp) >= 2:
                a, b = simp[-2], simp[-1]
                if (b[0] - a[0]) * (p[1] - b[1]) - (b[1] - a[1]) * (p[0] - b[0]) == 0 and \
                        (b[0] - a[0]) * (p[0] - b[0]) + (b[1] - a[1]) * (p[1] - b[1]) >= 0:
                    simp[-1] = p
                    continue
            simp.append(p)
        if len(simp) - 1 >= len(run) and simp == pts:
            continue
        new_tracks = []
        for a, b in zip(simp, simp[1:]):
            nt = pcbnew.PCB_TRACK(board)
            nt.SetStart(pcbnew.VECTOR2I(*a)); nt.SetEnd(pcbnew.VECTOR2I(*b))
            nt.SetLayer(layer); nt.SetWidth(width); nt.SetNet(netinfo)
            new_tracks.append(nt)
        # something may join the old run off its bends (a track ending on its side): if the
        # new run leaves it behind, keep the old one
        if not guard.try_remove(run, add=new_tracks):
            continue
        for t in run:
            idx.remove(t)
        for nt in new_tracks:
            idx.add(nt)
        before += len(run)
        after += len(simp) - 1
        replaced += 1
    return replaced, before, after


def report(board, cu, mark):
    cs = chains(board, cu)
    rows = []
    for pts, run in cs:
        L, ratio = detour(pts)
        odd, short = ugly(pts)
        score = (len(run) - 1) + 3 * odd + 2 * short + 10 * max(0, ratio - 1.2)
        if score >= 4:
            rows.append((score, run[0].GetNetname(), board.GetLayerName(run[0].GetLayer()),
                         len(run), odd, short, ratio, pts[len(pts) // 2]))
    rows.sort(reverse=True)
    segs = [t for t in cu.segs() if not t.IsLocked()]
    print(f"unlocked segments {len(segs)}, chains {len(cs)}, "
          f"short (<0.3 mm) {sum(1 for t in segs if t.GetLength() < mm(0.3))}, "
          f"odd-angle {sum(1 for t in segs if not octilinear(key(t.GetStart()), key(t.GetEnd())))}")
    print(f"{len(rows)} messy chains; worst 25:")
    for s, net, layer, n, odd, short, ratio, at in rows[:25]:
        print(f"  {net:18s} {layer:5s} {n:3d} segs  odd {odd:2d}  short {short:2d}  "
              f"detour {ratio:4.2f}  @({pcbnew.ToMM(at[0]):.1f},{pcbnew.ToMM(at[1]):.1f})")
    if mark:
        for g in list(board.Groups()):
            if g.GetName() == MARK_GROUP:
                for it in list(g.GetItems()):
                    board.Delete(it)
                board.Delete(g)
        g = pcbnew.PCB_GROUP(board); g.SetName(MARK_GROUP); board.Add(g)
        for *_, at in rows:
            c = pcbnew.PCB_SHAPE(board); c.SetShape(pcbnew.SHAPE_T_CIRCLE)
            c.SetCenter(pcbnew.VECTOR2I(*at)); c.SetEnd(pcbnew.VECTOR2I(at[0] + mm(1.5), at[1]))
            c.SetLayer(pcbnew.Eco1_User); c.SetWidth(mm(0.15))
            board.Add(c); g.AddItem(c)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="only report, don't change copper")
    ap.add_argument("--no-straighten", action="store_true")
    ap.add_argument("--mark", action="store_true", help="circle messy chains on Eco1.User")
    a = ap.parse_args()
    board = pcbnew.LoadBoard(BOARD)
    cu = Copper(board)
    if a.report:
        report(board, cu, a.mark)
        if a.mark:
            board.Save(BOARD)
        return 0
    guard = Guard(board)
    n = split_tees(board)
    s, v = prune(board, cu, guard)
    print(f"tidy: split {n} segments at tees; removed {s} dangling segments, {v} vias")
    if not a.no_straighten:
        idx = Index(board)
        for rnd in range(3):
            r, b4, af = straighten(board, cu, idx, guard)
            print(f"tidy: pass {rnd + 1}: {r} chains straightened, {b4} -> {af} segments")
            if not r:
                break
        s, v = prune(board, cu, guard)
        if s or v:
            print(f"tidy: removed {s} more dangling segments, {v} vias")
    report(board, cu, a.mark)
    if guard.count() > guard.base:
        print(f"tidy: unconnected went {guard.base} -> {guard.count()}; not saved")
        return 1
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
