#!/usr/bin/env python3
"""Tap the inner planes from the SMD pads that cannot reach them yet.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/plane_taps.py

GND is In1.Cu and +5V_SYS In2.Cu, and an SMD pad reaches its plane only through a via or a
through-hole pad.  For each GND or +5V_SYS SMD pad whose copper (the pad and the tracks
joined to it) holds neither, this drops a via next to the pad, joined by a short track, at
the first spot that clears everything else on every copper layer.  Big pads (the module's
center ground) take the via inside the pad instead.

What it adds is locked, so the autorouter keeps it, and goes in the group "plane_taps",
which the next run deletes first.  Run it after
the autorouter, then run DRC: it checks clearances itself, but DRC has the last word.
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
GROUP = "plane_taps"
PLANE_NETS = ("GND", "+5V_SYS")

VIA_D, VIA_DRILL = 0.6, 0.3
TRACK_W = 0.4
CLEARANCE = 0.2          # Default and Power net classes
HOLE_TO_HOLE = 0.25
HOLE_CLEARANCE = 0.25     # copper to a hole of another net, or to an unplated hole
EDGE = 0.3
IN_PAD = 1.6             # pads at least this big on both sides take the via inside
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)

mm, to_mm = pcbnew.FromMM, pcbnew.ToMM


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def is_smd(pad):
    return pad.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN)


def has_hole(pad):
    return pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)


def reaches_plane(board, pad, by_net):
    """Walk the pad's copper: tracks touching it, pads and vias they touch, and on."""
    net = pad.GetNetname()
    tracks, pads = by_net[net]
    seen_pads, seen_tracks = {id(pad)}, set()
    frontier = [pad]
    while frontier:
        item = frontier.pop()
        for t in tracks:
            if id(t) in seen_tracks:
                continue
            if isinstance(item, pcbnew.PCB_TRACK):
                ends = (item.GetStart(), item.GetEnd())
                hit = any(t.HitTest(e, 1) for e in ends) or \
                    any(item.HitTest(e, 1) for e in (t.GetStart(), t.GetEnd()))
            else:
                hit = any(item.HitTest(e) for e in (t.GetStart(), t.GetEnd()))
            if hit:
                if t.Type() == pcbnew.PCB_VIA_T:
                    return True
                seen_tracks.add(id(t))
                frontier.append(t)
        if isinstance(item, pcbnew.PCB_TRACK):
            for p in pads:
                if id(p) not in seen_pads and any(p.HitTest(e) for e in (item.GetStart(), item.GetEnd())):
                    if has_hole(p):
                        return True
                    seen_pads.add(id(p))
                    frontier.append(p)
    return False


class Obstacles:
    def __init__(self, board):
        self.items = []                   # (net, layer, shape, bbox)
        self.drills = []                  # (hole shape, bbox): every hole, against any copper
        self.holes = []                   # (x, y, r)
        for t in board.GetTracks():
            layers = COPPER if t.Type() == pcbnew.PCB_VIA_T else (t.GetLayer(),)
            for L in layers:
                self.items.append((t.GetNetname(), L, t.GetEffectiveShape(L), t.GetBoundingBox()))
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                self.holes.append((to_mm(p.x), to_mm(p.y), to_mm(t.GetDrillValue()) / 2))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                for L in COPPER:
                    if p.IsOnLayer(L) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                        self.items.append((p.GetNetname(), L, p.GetEffectiveShape(L), p.GetBoundingBox()))
                if has_hole(p):
                    self.drills.append((p.GetEffectiveHoleShape(), p.GetBoundingBox()))
                    q = p.GetPosition()
                    d = p.GetDrillSize()
                    self.holes.append((to_mm(q.x), to_mm(q.y), to_mm(max(d.x, d.y)) / 2))
        self.edge = board.GetBoardEdgesBoundingBox()
        self.edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]

    def add(self, net, layers, shape, bbox):
        for L in layers:
            self.items.append((net, L, shape, bbox))

    def clear(self, net, layers, shape, bbox, margin):
        grow = bbox.GetInflated(mm(margin + 1))
        for n, L, s, bb in self.items:
            if n == net or L not in layers or not grow.Intersects(bb):
                continue
            if s.Collide(shape, mm(margin)):
                return False
        for s, bb in self.drills:
            if grow.Intersects(bb) and s.Collide(shape, mm(HOLE_CLEARANCE)):
                return False
        return True

    def hole_ok(self, x, y):
        r = VIA_DRILL / 2
        return all(math.hypot(x - hx, y - hy) >= r + hr + HOLE_TO_HOLE for hx, hy, hr in self.holes)

    def edge_ok(self, via):
        shape = via.GetEffectiveShape(pcbnew.F_Cu)
        for d in self.edges:
            if d.GetEffectiveShape().Collide(shape, mm(EDGE)):
                return False
        return True


def candidates(pad):
    """Spots for the via: inside a big pad; under the package, for a pin of an IC (the
    space inside its ring of pins is free); then rings around the pad, nearest first."""
    c = pad.GetPosition()
    cx, cy = to_mm(c.x), to_mm(c.y)
    size = pad.GetBoundingBox()
    w, h = to_mm(size.GetWidth()), to_mm(size.GetHeight())
    if w >= IN_PAD and h >= IN_PAD:
        yield cx, cy, True
    reach = max(w, h) / 2
    fp = pad.GetParentFootprint()
    if len(fp.Pads()) >= 8:
        o = fp.GetBoundingBox(False).GetCenter()
        dx, dy = to_mm(o.x) - cx, to_mm(o.y) - cy
        n = math.hypot(dx, dy)
        if n > 1:
            # straight in along the pin's own axis (the pad's long side), then toward the center
            ax = (1, 0) if w > h else (0, 1)
            ax = (ax[0] * (1 if ax[0] * dx >= 0 else -1), ax[1] * (1 if ax[1] * dy >= 0 else -1))
            for u in (ax, (dx / n, dy / n)):
                d = reach + VIA_D / 2 + CLEARANCE + 0.05
                while d < min(n, 6.0):
                    yield cx + u[0] * d, cy + u[1] * d, False
                    d += 0.2
    for ring in range(0, 12):
        r = reach + VIA_D / 2 + CLEARANCE + 0.05 + 0.25 * ring
        for k in range(16):
            a = math.pi * 2 * k / 16
            yield cx + r * math.cos(a), cy + r * math.sin(a), False


def tap(board, obs, pad, group):
    net = pad.GetNet()
    name = pad.GetNetname()
    layer = pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
    c = pad.GetPosition()
    for x, y, inside in candidates(pad):
        if not obs.hole_ok(x, y):
            continue
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(x, y)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net)
        v.SetLocked(True)                          # fixed for the autorouter
        if not obs.clear(name, COPPER, v.GetEffectiveShape(pcbnew.F_Cu), v.GetBoundingBox(), CLEARANCE):
            continue
        if not obs.edge_ok(v):
            continue
        t = None
        if not inside:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(c); t.SetEnd(pt(x, y)); t.SetLayer(layer); t.SetWidth(mm(TRACK_W)); t.SetNet(net)
            t.SetLocked(True)
            if not obs.clear(name, (layer,), t.GetEffectiveShape(layer), t.GetBoundingBox(), CLEARANCE):
                continue
        board.Add(v); group.AddItem(v)
        obs.add(name, COPPER, v.GetEffectiveShape(pcbnew.F_Cu), v.GetBoundingBox())
        obs.holes.append((x, y, VIA_DRILL / 2))
        if t:
            board.Add(t); group.AddItem(t)
            obs.add(name, (layer,), t.GetEffectiveShape(layer), t.GetBoundingBox())
        return [v] + ([t] if t else [])
    return None


def clear_previous(board):
    for t in list(board.GetTracks()):
        g = t.GetParentGroup()
        if g is not None and g.GetName() == GROUP:
            g.RemoveItem(t)
            board.Delete(t)
    for g in list(board.Groups()):
        if g.GetName() == GROUP:
            board.Delete(g)


def main():
    board = pcbnew.LoadBoard(BOARD)
    clear_previous(board)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)

    by_net = {n: ([], []) for n in PLANE_NETS}
    for t in board.GetTracks():
        if t.GetNetname() in by_net:
            by_net[t.GetNetname()][0].append(t)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() in by_net:
                by_net[p.GetNetname()][1].append(p)

    obs = Obstacles(board)
    added, failed = 0, []
    done = set()
    for net in PLANE_NETS:
        for p in by_net[net][1]:
            if not is_smd(p) or id(p) in done:
                continue
            if reaches_plane(board, p, by_net):
                continue
            new = tap(board, obs, p, group)
            if new:
                added += 1
                by_net[net][0].extend(new)       # pads joined to this one now reach the plane
            else:
                failed.append(f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()} [{net}]")
            done.add(id(p))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"plane_taps: {added} vias")
    for f in failed:
        print("  no room:", f)


if __name__ == "__main__":
    main()
