#!/usr/bin/env python3
"""Route the host lines between J2 (the C128 keyboard connector) and U3 (the CH446Q).

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/route_host.py

The crosspoint's pin order (gen_sch.py XP_X_OF_COL / XP_Y_OF_ROW) is chosen so these lines
route without crossing; this lays them, locked, in the group "route_host" (replaced on each
run).  Positions come from the pads, so a small move of U3 or J2 only needs a rerun.

  columns, on B.Cu: out of J2's top row with a 45-degree jog between two bottom-row pins,
      down to the line's own level, across to its own lane beside the package, down the
      lane and straight into the pin.  Levels and lanes nest (the line nearest the chip
      takes the innermost lane and the pin nearest J2), so nothing crosses.  COL0, which is
      on J2's bottom row, runs straight down to its level.
  rows, on F.Cu: straight down from J2's bottom row, a staircase across to a via inside the
      package's ring of pins, and a short B.Cu stub out to the pin.  Leftmost source turns
      lowest, so the steps nest too.  ROW3 runs over the right-hand pins and comes in from
      the side, which keeps the top-right corner free for a GND via.
  GND: pin 12 to a via off the top-left corner; pins 18-21 (tied-low address pins) joined
      by a bar above them to a via off the top-right corner.  The other GND pins are left to
      plane_taps.py, which runs after this.
  STB: a via inside the ring under pin 14, and an F.Cu escape to the left for the router.

Rip up the pocket first (rip_up.py --rect), then run this, plane_taps.py and freeroute.py.
"""
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
GROUP = "route_host"
W = 0.25                       # signal track
GND_W = 0.3
VIA_D, VIA_DRILL = 0.6, 0.3
PITCH = 1.27                   # half J2's pitch: the jog between two bottom-row pins

# columns: (net, level y) per side, innermost lane first
LEFT = [("H_COL2", 90.7), ("H_COL1", 90.2), ("H_COL7", 89.7), ("H_COL8", 89.2),
        ("H_COL9", 88.7), ("H_COL10", 88.2), ("H_COL0", 88.2)]
RIGHT = [("H_COL3", 88.2), ("H_COL4", 88.2), ("H_COL5", 88.7), ("H_COL6", 89.2)]
LANE_GAP = 0.2 + W / 2         # pad end to lane center: clearance plus half a track
LANE_PITCH = 0.5
# rows: net -> level y on F.Cu
ROW_LEVEL = {"H_ROW6": 88.2, "H_ROW5": 88.7, "H_ROW4": 89.2, "H_ROW7": 89.7, "H_ROW2": 90.2,
             "H_ROW1": 90.7, "H_ROW0": 91.2, "H_ROW3": 88.2}
VIA_IN = 0.5                   # pad's inner end to the via center, inside the ring
BOTTOM_VIA_IN = 0.8            # bottom-side vias sit a little deeper, clear of the next pad


def mm(v):
    return pcbnew.FromMM(v)


def xy(p):
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


class Cu:
    def __init__(self, board, group):
        self.board, self.group = board, group

    def track(self, pts, net, layer, width=W):
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
            t.SetLayer(layer); t.SetWidth(mm(width)); t.SetNet(net); t.SetLocked(True)
            self.board.Add(t); self.group.AddItem(t)

    def via(self, p, net):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(pcbnew.VECTOR2I(mm(p[0]), mm(p[1])))
        v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net); v.SetLocked(True)
        self.board.Add(v); self.group.AddItem(v)


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
    cu = Cu(board, group)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    u3, j2 = fps["U3"], fps["J2"]

    # U3's ring: pad extents per side
    pads = list(u3.Pads())
    bb = [(p, p.GetBoundingBox()) for p in pads]
    to = pcbnew.ToMM
    left_x0 = min(to(b.GetLeft()) for _, b in bb)          # outer end of the left pads
    right_x1 = max(to(b.GetRight()) for _, b in bb)
    top_y0 = min(to(b.GetTop()) for _, b in bb)
    bottom_y1 = max(to(b.GetBottom()) for _, b in bb)

    def side(p):
        x, y = xy(p.GetPosition())
        b = p.GetBoundingBox()
        if abs(to(b.GetLeft()) - left_x0) < 0.01:
            return "L", to(b.GetRight())                     # inner end x
        if abs(to(b.GetRight()) - right_x1) < 0.01:
            return "R", to(b.GetLeft())
        if abs(to(b.GetTop()) - top_y0) < 0.01:
            return "T", to(b.GetBottom())                    # inner end y
        return "B", to(b.GetTop())

    u3_by_net = {}
    for p in pads:
        u3_by_net.setdefault(p.GetNetname(), []).append(p)
    j2_by_net = {p.GetNetname(): p for p in j2.Pads()}
    j2_rows = sorted({round(xy(p.GetPosition())[1], 2) for p in j2.Pads()})
    j2_top, j2_bottom = j2_rows[0], j2_rows[-1]

    # columns on B.Cu
    for lanes, sign, x_edge in ((LEFT, -1, left_x0), (RIGHT, +1, right_x1)):
        for k, (net, level) in enumerate(lanes):
            src = j2_by_net[net]
            dst = u3_by_net[net][0]
            sx, sy = xy(src.GetPosition())
            dx, dy = xy(dst.GetPosition())
            lane = x_edge + sign * (LANE_GAP + LANE_PITCH * k)
            if abs(sy - j2_top) < 0.01:                     # top row: jog between bottom-row pins
                jx = sx - PITCH
                pts = [(sx, sy), (jx, sy + PITCH), (jx, level)]
            else:
                pts = [(sx, sy), (sx, level)]
            pts += [(lane, level), (lane, dy), (dx, dy)]
            cu.track(pts, src.GetNet(), pcbnew.B_Cu)

    # rows on F.Cu, through a via inside the ring
    for net, level in ROW_LEVEL.items():
        src = j2_by_net[net]
        dst = u3_by_net[net][0]
        sx, sy = xy(src.GetPosition())
        px, py = xy(dst.GetPosition())
        s, inner = side(dst)
        n = src.GetNet()
        if s == "T":
            via = (px, inner + VIA_IN + VIA_D / 2)
            stub = [via, (px, py)]
            fpath = [(sx, sy), (sx, level), (via[0], level), via]
        elif s == "L":
            via = (inner + VIA_IN + VIA_D / 2, py)
            stub = [via, (px, py)]
            fpath = [(sx, sy), (sx, level), (via[0], level), via]
        elif s == "B":
            vy = inner - BOTTOM_VIA_IN - VIA_D / 2
            # clear of a top-side via above it: shift right, and come back in at 45 degrees
            top_vias = [xy(q.GetPosition())[0] for nm in ROW_LEVEL for q in u3_by_net[nm][:1]
                        if side(q)[0] == "T"]
            vx = px
            if any(abs(vx - t) < 0.65 for t in top_vias):
                vx = px + 0.7
            via = (vx, vy)
            knee = (px, vy + abs(vx - px))
            stub = [via, knee, (px, py)]
            fpath = [(sx, sy), (sx, level), (vx, level), via]
        else:                                                # right side: over the pins, in from the side
            via = (inner - VIA_IN - VIA_D / 2, py)
            over = right_x1 - 0.75
            drop = py - (over - via[0])
            stub = [via, (px, py)]
            fpath = [(sx, sy), (sx, level), (over, level), (over, drop), via]
        cu.track(fpath, n, pcbnew.F_Cu)
        cu.via(via, n)
        cu.track(stub, n, pcbnew.B_Cu)

    # GND: pin 12 to a via off the top-left corner
    gnd_pads = {p.GetNumber(): p for p in u3_by_net["GND"]}
    p12 = gnd_pads["12"]
    gnd = p12.GetNet()
    x12, y12 = xy(p12.GetPosition())
    corner = (left_x0 + 1.05, top_y0 + 1.0)
    cu.track([(x12, y12), corner], gnd, pcbnew.B_Cu, GND_W)
    cu.via(corner, gnd)
    # pins 18-21: a bar above them to a via off the top-right corner
    bar_y = top_y0 - 0.4
    xs = sorted(xy(gnd_pads[n].GetPosition())[0] for n in ("18", "19", "20", "21"))
    for x in xs:
        cu.track([(x, y12), (x, bar_y)], gnd, pcbnew.B_Cu, GND_W)
    via_tr = (right_x1 - 1.45, top_y0 + 0.2)
    cu.track([(xs[0], bar_y), (via_tr[0], bar_y), via_tr], gnd, pcbnew.B_Cu, GND_W)
    cu.via(via_tr, gnd)

    # STB: via inside the ring under pin 14, F.Cu escape to the left
    stb = u3_by_net["MCU_XP_STB"][0]
    sx, sy = xy(stb.GetPosition())
    _, inner = side(stb)
    via = (sx, inner + 1.7)
    cu.track([(sx, sy), via], stb.GetNet(), pcbnew.B_Cu)
    cu.via(via, stb.GetNet())
    cu.track([via, (via[0] - 0.8, via[1] + 0.8), (left_x0 - 2.0, via[1] + 0.8)], stb.GetNet(), pcbnew.F_Cu)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"route_host: {len(LEFT) + len(RIGHT)} columns, {len(ROW_LEVEL)} rows, GND and STB laid")


if __name__ == "__main__":
    main()
