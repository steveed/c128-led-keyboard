#!/usr/bin/env python3
"""Lay the regular per-key copper on pcb/C128-keyboard-rev3.kicad_pcb.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/route_keys.py

Every key gets the same pattern, in its switch's frame (mm, y down, pins north, LED south):

  - switch pin 2 to the diode's anode on B.Cu, down the east side of the center hole
    (between it and the peg)
  - the LED's two power pads each get a via: the bottom-left pad straight below it at
    (-1.75, 7.25), the top-right pad east of it at (3.3, 4.205).  In left-to-right rows those
    are 5 V and GND, in right-to-left rows (LED turned 180) GND and 5 V; the LED's 100n on
    B.Cu is turned to match (gen_pcb.py) and joins both vias
  - the data hop to the next LED of the chain on F.Cu, when the two keys are neighbours in
    the same row with no key between them: out of DOUT, along y = LED center (5.08), into the
    next DIN.  Other hops (around the lock keys, across rows, the row ends) are left to the
    router

What this lays is kept in one group, "route_keys", which the next run deletes first, so the
script can be rerun after a footprint or offset change without touching anything else.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout  # noqa: E402

import pcbnew  # noqa: E402

BOARD = os.path.join(os.path.dirname(HERE), "C128-keyboard-rev3.kicad_pcb")
GROUP = "route_keys"

SIGNAL_W = 0.25
POWER_W = 0.4
VIA_D, VIA_DRILL = 0.6, 0.3

ANODE_PATH = [(2.54, -5.08), (3.3, -4.32), (3.3, 2.85), (2.65, 3.5), (1.65, 3.5)]
VIA_S = (-1.75, 7.25)            # below the LED's bottom-left pad
VIA_E = (3.3, 4.205)             # east of the LED's top-right pad
CAP_W_PAD, CAP_E_PAD = (-0.863, 6.1), (0.863, 6.1)
VIA_S_TO_CAP = [VIA_S, (-0.863, 6.363), CAP_W_PAD]
VIA_E_TO_CAP = [VIA_E, (3.3, 4.66), (1.86, 6.1), CAP_E_PAD]
DATA_Y = 5.08                    # LED center line
JOG = 0.875                      # 45-degree jog between the pad rows and DATA_Y


def mm(v):
    return pcbnew.FromMM(v)


def pt(xy):
    return pcbnew.VECTOR2I(mm(xy[0]), mm(xy[1]))


class Key:
    """A switch's frame: offsets in, board coordinates out."""

    def __init__(self, fp):
        p = fp.GetPosition()
        self.x, self.y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        self.a = math.radians(fp.GetOrientationDegrees())

    def __call__(self, off):
        x, y = off
        return (self.x + x * math.cos(self.a) + y * math.sin(self.a),
                self.y - x * math.sin(self.a) + y * math.cos(self.a))


def pad_at(fp, xy, tol=0.05):
    for p in fp.Pads():
        q = p.GetPosition()
        if abs(pcbnew.ToMM(q.x) - xy[0]) < tol and abs(pcbnew.ToMM(q.y) - xy[1]) < tol:
            return p
    raise LookupError(f"{fp.GetReference()}: no pad at {xy}")


class Layer:
    def __init__(self, board, group):
        self.board, self.group = board, group

    def track(self, pts, net, layer, width):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(pt(a)); t.SetEnd(pt(b))
            t.SetLayer(layer); t.SetWidth(mm(width)); t.SetNet(net)
            self.board.Add(t); self.group.AddItem(t)

    def via(self, xy, net):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(pt(xy)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net)
        self.board.Add(v); self.group.AddItem(v)


def clear_previous(board):
    for g in list(board.Groups()):
        if g.GetName() == GROUP:
            for item in list(g.GetItems()):
                board.Remove(item)
            board.Remove(g)


def main():
    board = pcbnew.LoadBoard(BOARD)
    clear_previous(board)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)
    cu = Layer(board, group)
    f = board.FindFootprintByReference
    switches = layout.load_switches()
    order, direction = layout.led_chain(switches)
    rows = {ref: rc[0] for ref, rc in layout.physical_matrix(switches).items()}
    counts = dict(anode=0, led=0, hop=0)

    for s in switches:
        n = s["ref"][2:]
        sw, led, cap, diode = f("SW" + n), f("LED" + n), f("C" + str(100 + int(n))), f("D" + str(100 + int(n)))
        k = Key(sw)
        if diode:
            cu.track([k(p) for p in ANODE_PATH], pad_at(sw, k(ANODE_PATH[0])).GetNet(), pcbnew.B_Cu, SIGNAL_W)
            counts["anode"] += 1
        # LED power pads to their vias, and the vias to the 100n behind
        for pad_off, via, to_cap in (((-1.75, 5.955), VIA_S, VIA_S_TO_CAP), ((1.75, 4.205), VIA_E, VIA_E_TO_CAP)):
            net = pad_at(led, k(pad_off)).GetNet()
            cap_pad = pad_at(cap, k(to_cap[-1]))
            assert cap_pad.GetNetname() == net.GetNetname(), (s["ref"], cap_pad.GetNetname(), net.GetNetname())
            cu.track([k(pad_off), k(via)], net, pcbnew.F_Cu, POWER_W)
            cu.via(k(via), net)
            cu.track([k(p) for p in to_cap], net, pcbnew.B_Cu, POWER_W)
        counts["led"] += 1

    # data hops between neighbours in a row
    by_ref = {s["ref"]: s for s in switches}
    for a, b in zip(order, order[1:]):
        sa, sb = by_ref[a], by_ref[b]
        if a in layout.LOCK_LEDS or rows.get(a) != rows.get(b) or abs(sa["y"] - sb["y"]) > 0.1:
            continue
        if f(a).GetOrientationDegrees() != 0 or f(b).GetOrientationDegrees() != 0:
            continue
        lo, hi = sorted((sa["x"], sb["x"]))
        if any(abs(s["y"] - sa["y"]) < 1 and lo < s["x"] < hi for s in switches):
            continue                              # a key in between (a lock key): router's job
        d = direction[a]
        ka, kb = Key(f(a)), Key(f(b))
        dout = (1.75 * d, 5.08 + JOG * d)        # pad 1 of LED a, in its switch frame
        din = (-1.75 * d, 5.08 - JOG * d)        # pad 3 of LED b
        net = pad_at(f("LED" + a[2:]), ka(dout)).GetNet()
        assert pad_at(f("LED" + b[2:]), kb(din)).GetNetname() == net.GetNetname(), (a, b)
        pts = [ka(dout), ka((dout[0] + JOG * d, DATA_Y)), kb((din[0] - JOG * d, DATA_Y)), kb(din)]
        cu.track(pts, net, pcbnew.F_Cu, SIGNAL_W)
        counts["hop"] += 1

    # the new vias change what the inner planes connect to
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"route_keys: {counts['anode']} switch-to-diode links, {counts['led']} LED power pairs, "
          f"{counts['hop']} data hops")


if __name__ == "__main__":
    main()
