#!/usr/bin/env python3
"""Start the dongle's board: project file, design rules and an empty 4-layer board with its outline.

    docker compose run --rm kicad python3 dongle/pcb/tools/gen_board.py [--force]

Run gen_sch.py first.  This writes:

- c128-dongle.kicad_pro: the keyboard's project settings (pcb/C128-keyboard-rev3.kicad_pro:
  net classes, JLCPCB minimums, DRC severities), with this project's name, its sheets (read from
  the generated root sheet) and its power nets in the Power class;
- c128-dongle.kicad_dru: the keyboard's J1 rule (the same USB-C footprint, also J1 here), and
  the dongle's own: U5's MSOP-10 pad gap;
- c128-dongle.kicad_pcb: 4 copper layers and the board outline, nothing else.  Parts come in
  with Update PCB from Schematic (F8) and are placed by hand.

It refuses to overwrite an existing board (--force to start over): from here the board is
hand-edited.  The project and rules files are rewritten each run.

Outline: 65 x 45 mm, 1 mm corner radius (widened from 60 for the USB-C pair to U5).  The west and east edges carry the DB25s (J2 and J3
straddle them, footprint origin on the edge, 45 mm leaving room for the 41 mm connector bodies;
the 52.65 mm flanges overhang and are captured by the clamshell).  The north edge takes the
USB-C and the USB-A side by side, the south edge the status light pipe, the buttons and the
ESP32's antenna corner (docs/wireless-128d.md).
"""
import json
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, ".."))
REPO = os.path.normpath(os.path.join(PCB, "..", ".."))
NAME = "c128-dongle"
KB_PRO = os.path.join(REPO, "pcb", "C128-keyboard-rev3.kicad_pro")
KB_DRU = os.path.join(REPO, "pcb", "C128-keyboard-rev3.kicad_dru")

W, H, R = 65.0, 45.0, 1.0          # outline, mm (60 -> 65 on 2026-11-27: room for the USB-C pair)
X0, Y0 = 100.0, 80.0               # its top-left corner on the sheet
# the dongle's own rules, after the keyboard's
DONGLE_RULES = """
# U5, the CH442E: an MSOP-10 at 0.5 mm pitch with 0.35 mm pads leaves 0.15 mm between its own
# pads, under the board's 0.2 mm default (and at its 0.15 mm floor, inside JLCPCB's limits).
(rule "U5 MSOP-10 pad to pad"
	(constraint clearance (min 0.15mm))
	(condition "A.memberOfFootprint('U5') && B.memberOfFootprint('U5')"))
"""
POWER_NETS = ["GND", "+5V_KB", "+5V_KB_F", "+5V_SYS", "+3V3", "VBUS", "USBA_VBUS"]


def sheets():
    """[uuid, name] for the root and each sub-sheet, as eeschema writes them into the project."""
    root = open(os.path.join(PCB, f"{NAME}.kicad_sch"), encoding="utf-8").read()
    root_uuid = re.search(r'\(uuid "([^"]+)"\)', root).group(1)
    out = [[root_uuid, NAME]]
    for m in re.finditer(r'\(sheet\b.*?\(uuid "([^"]+)"\).*?\(property "Sheetname" "([^"]+)"', root, re.S):
        out.append([m.group(1), m.group(2)])
    return out


def write_project():
    pro = json.load(open(KB_PRO, encoding="utf-8"))
    pro["meta"]["filename"] = f"{NAME}.kicad_pro"
    pro["sheets"] = sheets()
    pro["boards"] = []
    pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": n} for n in POWER_NETS]
    pro["board"]["design_settings"]["drc_exclusions"] = []
    pro.pop("kicad_routing_tools", None)
    with open(os.path.join(PCB, f"{NAME}.kicad_pro"), "w", encoding="utf-8") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")
    with open(KB_DRU, encoding="utf-8") as src, open(os.path.join(PCB, f"{NAME}.kicad_dru"), "w", encoding="utf-8") as dst:
        dst.write(src.read())
        dst.write(DONGLE_RULES)


def mm(v):
    return pcbnew.FromMM(v)


def outline(board):
    """Rounded rectangle on Edge.Cuts: four lines and four quarter arcs."""
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); s.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)

    def arc(c, start, mid, end):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(*(pcbnew.VECTOR2I(mm(p[0]), mm(p[1])) for p in (start, mid, end)))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)

    x0, y0, x1, y1 = X0, Y0, X0 + W, Y0 + H
    k = R * (1 - 2 ** -0.5)
    seg((x0 + R, y0), (x1 - R, y0)); seg((x1, y0 + R), (x1, y1 - R))
    seg((x1 - R, y1), (x0 + R, y1)); seg((x0, y1 - R), (x0, y0 + R))
    arc((x1 - R, y0 + R), (x1 - R, y0), (x1 - k, y0 + k), (x1, y0 + R))
    arc((x1 - R, y1 - R), (x1, y1 - R), (x1 - k, y1 - k), (x1 - R, y1))
    arc((x0 + R, y1 - R), (x0 + R, y1), (x0 + k, y1 - k), (x0, y1 - R))
    arc((x0 + R, y0 + R), (x0, y0 + R), (x0 + k, y0 + k), (x0 + R, y0))


def note(board, text, at, layer=pcbnew.Cmts_User, size=1.0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text); t.SetPosition(pcbnew.VECTOR2I(mm(at[0]), mm(at[1])))
    t.SetLayer(layer); t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.12))
    board.Add(t)


def main():
    write_project()
    path = os.path.join(PCB, f"{NAME}.kicad_pcb")
    if os.path.exists(path) and "--force" not in sys.argv:
        print("gen_board: project and rules rewritten; board exists, not touched (--force to start over)")
        return
    board = pcbnew.NewBoard(path)
    board.SetCopperLayerCount(4)
    outline(board)
    cx, cy = X0 + W / 2, Y0 + H / 2
    note(board, "north: USB-C, USB-A (toward the 128D's rear)", (cx, Y0 - 3))
    note(board, "south: status light pipe, buttons, antenna corner", (cx, Y0 + H + 3))
    note(board, "west: J2 DB25 male, to the 128D", (X0 - 12, cy))
    note(board, "east: J3 DB25 female, for the keyboard", (X0 + W + 14, cy))
    board.Save(path)
    print(f"gen_board: wrote {NAME}.kicad_pro, .kicad_dru and a {W:g} x {H:g} mm 4-layer board")


if __name__ == "__main__":
    main()
