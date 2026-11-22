#!/usr/bin/env python3
"""Give the board's pads the nets the schematic has now, after a schematic change.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/sync_nets.py

Exports the netlist with kicad-cli, then sets each pad's net from it (adding new nets to the
board).  Unlocked copper on a net whose pads changed is deleted, since it now joins the wrong
pins: reroute it afterwards.  Footprints themselves are not added, removed or swapped
(swap_footprint.py does that).  Planes are refilled.
"""
import os
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.dirname(HERE)
BOARD = os.path.join(PCB, "C128-keyboard-rev3.kicad_pcb")
SCH = os.path.join(PCB, "C128-keyboard-rev3.kicad_sch")
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def parse(text):
    """Minimal s-expression reader: nested lists of strings."""
    out, stack, i, n = [], [], 0, len(text)
    cur = out
    while i < n:
        c = text[i]
        if c == "(":
            stack.append(cur); cur.append([]); cur = cur[-1]; i += 1
        elif c == ")":
            cur = stack.pop(); i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    j += 1
                buf.append(text[j]); j += 1
            cur.append("".join(buf)); i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            cur.append(text[i:j]); i = j
    return out[0]


def netlist_pins():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "n.net")
        subprocess.run([CLI, "sch", "export", "netlist", "-o", path, SCH], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = parse(open(path, encoding="utf-8").read())
    pins = {}
    nets = next(x for x in root if isinstance(x, list) and x[0] == "nets")
    for net in nets[1:]:
        name = next(x[1] for x in net if isinstance(x, list) and x[0] == "name")
        for node in (x for x in net if isinstance(x, list) and x[0] == "node"):
            ref = next(x[1] for x in node if x[0] == "ref")
            pin = next(x[1] for x in node if x[0] == "pin")
            pins[(ref, pin)] = name
    return pins


def main():
    pins = netlist_pins()
    board = pcbnew.LoadBoard(BOARD)
    changed, touched = [], set()
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            num = p.GetNumber()
            if not num:
                continue
            want = pins.get((ref, num), "")
            have = p.GetNetname()
            if want.startswith("unconnected-") and have.startswith("unconnected-"):
                continue
            if want == have:
                continue
            net = board.FindNet(want) if want else board.FindNet("")
            if net is None:
                net = pcbnew.NETINFO_ITEM(board, want)
                board.Add(net)
            p.SetNet(net)
            changed.append(f"{ref}.{num}: {have or '-'} -> {want or '-'}")
            touched.update(n for n in (have, want) if n)
    dead = [t for t in board.GetTracks() if not t.IsLocked() and t.GetNetname() in touched]
    for t in dead:
        board.Delete(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    for c in changed:
        print(" ", c)
    print(f"sync_nets: {len(changed)} pads changed, {len(dead)} tracks and vias on {len(touched)} nets removed")


if __name__ == "__main__":
    sys.exit(main())
