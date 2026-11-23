#!/usr/bin/env python3
"""Build the first rev 3 board, pcb/C128-keyboard-rev3.kicad_pcb, from the schematic.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/gen_pcb.py [--force]

Needs KiCad's own python (the pcbnew module), not the host's or a container's.  It:

  1. exports the schematic netlist with kicad-cli,
  2. loads every footprint from its library and links it to its symbol (sheet path plus
     symbol UUID, as Update PCB from Schematic does), with value, fields and pad nets,
  3. draws the outline from layout/outline.json (the rev 2.3 board's, unchanged),
  4. adds a GND plane on In1.Cu and a 5V_SYS plane on In2.Cu (four layers),
  5. places parts: switches on the centers in layout/switches.json; each switch's LED in its
     pocket (front), its diode and the LED's 100n behind it (back); the electronics on the
     back in the three switch-free pockets of the top row.

This is a starting point for hand layout, not a generator to keep running: once parts are
moved or tracks drawn in pcbnew, the board is the source, and the script refuses to
overwrite it without --force.  Check the result with
`kicad-cli pcb drc --schematic-parity`, which must report no parity issues.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_fp  # noqa: E402  (LED_OFFSET)
import kisym as K  # noqa: E402
import layout  # noqa: E402

import pcbnew  # noqa: E402

KICAD = "/Applications/KiCad/KiCad.app/Contents"
KICAD_CLI = KICAD + "/MacOS/kicad-cli"
KICAD_FP = KICAD + "/SharedSupport/footprints"
NAME = "C128-keyboard-rev3"
SCH = os.path.join(PCB, NAME + ".kicad_sch")
BOARD = os.path.join(PCB, NAME + ".kicad_pcb")
PROJECT = os.path.join(PCB, NAME + ".kicad_pro")

# Rev 2.3 turns 14 top-row switches by 180 degrees.  With an LED in every pocket that would put
# their LEDs at the top of the key and every other key's at the bottom, so rev 3 lines them
# all up (pins north, LED south, as the rev 2.3 lock keys that light).  Keypad Enter keeps -90.
UNIFORM_180 = True

# switch frame offsets (mm, y down) of the parts that belong to each key
DIODE_OFFSET = (0.0, 3.5)      # back, between the center hole and the LED pocket; anode toward pin 2
CAP_OFFSET = (0.0, 6.1)        # back, behind the LED

# Electronics on B.Cu: courtyard center (x, y) and rotation.  The three switch-free pockets of
# the top row (x 182.7-225.3, 297.0-339.6 and 411.3-430.1, y 80.1 to about 112.4) have no
# holes on the back.  Pocket A: MCU (turned so its GND row faces the edge and its signal
# sides face the board), USB-C, LED buffer, and the 3.3 V regulator and buttons west of it so
# the channel under the MCU stays clear.  Pocket B, at rev 2.3's FFC: host connector,
# crosspoint, lock-line and RESTORE FETs, and the keyboard 5 V fuse and diode next to the
# connector's +5 V pin.  Pocket C, by the keypad: the 5 V bulk capacitor.  The 74HC154
# drives columns 0-14 (x 118-385), so it sits mid-board in the channel under the top row (y 97.5-113 on the back is
# clear of holes the whole width: top-row diodes and caps end at 97.1, number-row pins start
# at 113.5).  First pass, packed from the footprints' courtyards; to be refined by hand.
PLACE = {
    # pocket A
    "J1": (189.0, 84.6, 180), "D2": (200.5, 83.0, 0),
    "U7": (189.0, 92.0, 0), "R3": (184.5, 92.0, 90), "R4": (193.5, 92.0, 90),
    "R1": (199.0, 88.0, 0), "C1": (199.0, 90.0, 0), "R2": (199.0, 92.0, 0),
    "C2": (223.2, 84.0, 90), "C3": (225.0, 84.0, 90), "U1": (214.0, 89.0, 180),
    "J4": (190.0, 96.5, 90), "SW93": (188.5, 102.05, 0), "SW94": (199.5, 102.05, 0),
    "U4": (203.5, 95.0, 0), "C9": (198.0, 95.0, 0),
    "U2": (200.0, 109.5, 0), "C6": (189.5, 108.6, 0), "C7": (189.5, 111.6, 0),
    # pocket B
    "J2": (318.25, 85.7, 90), "U3": (318.25, 98.5, 0),
    "Q1": (300.0, 93.6, 0), "JP1": (300.0, 97.0, 0), "Q2": (300.0, 100.5, 0), "Q3": (300.0, 104.5, 0),
    "R5": (306.5, 92.8, 0), "R6": (306.5, 94.8, 0), "C8": (306.5, 97.0, 0), "R7": (306.5, 100.5, 0),
    "R12": (306.5, 104.5, 0), "F1": (301.0, 109.5, 0), "D1": (308.5, 109.5, 0),
    "R10": (328.5, 93.0, 0), "R11": (328.5, 95.0, 0),
    "D3": (330.0, 103.0, 0), "J3": (332.5, 109.5, 90),
    # channel under the top row: decoder and its decoupling
    "U6": (251.0, 105.5, 90), "C11": (262.5, 100.5, 0),
}
PLACE["C5"] = (413.0, 84.5, 0)                       # 5 V bulk, in the top-row gap by the keypad


# --- netlist ------------------------------------------------------------------------------

def netlist():
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "rev3.net")
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "-o", out, SCH], check=True, capture_output=True)
    root = K.parse(open(out, encoding="utf-8").read())
    shutil.rmtree(tmp)
    comps = {}
    for c in K.find_all(K.find(root, "components"), "comp"):
        val = lambda key: K.find(c, key)[1] if K.find(c, key) and len(K.find(c, key)) > 1 else ""
        sp = K.find(c, "sheetpath")
        props = {}
        for p in K.find_all(c, "property"):
            v = K.find(p, "value")
            props[K.find(p, "name")[1]] = v[1] if v and len(v) > 1 else ""
        if val("ref").startswith("#") or not val("footprint"):
            continue
        comps[val("ref")] = dict(value=val("value"), footprint=val("footprint"), uuid=val("tstamps"),
                                 datasheet=val("datasheet"), description=val("description"),
                                 exclude_from_bom="exclude_from_bom" in props, dnp="dnp" in props,
                                 sheet_path=K.find(sp, "tstamps")[1], sheet_name=props.get("Sheetname", ""),
                                 sheet_file=props.get("Sheetfile", ""),
                                 fields={k: v for k, v in props.items()
                                         if k not in ("Sheetname", "Sheetfile") and not k.startswith("ki_")})
    nets = {}
    for n in K.find_all(K.find(root, "nets"), "net"):
        nets[K.find(n, "name")[1]] = [(K.find(nd, "ref")[1], K.find(nd, "pin")[1]) for nd in K.find_all(n, "node")]
    return comps, nets


# --- board --------------------------------------------------------------------------------

def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def rotate(off, deg):
    """A switch-frame offset turned by a KiCad orientation (CCW on screen, y down)."""
    a = math.radians(deg)
    x, y = off
    return (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))


def load_fp(lib_id):
    lib, name = lib_id.split(":", 1)
    path = os.path.join(PCB, lib + ".pretty") if lib == "c128rev3" else os.path.join(KICAD_FP, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        sys.exit(f"footprint {lib_id} not found in {path}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def place(fp, x, y, rot, back):
    fp.SetPosition(pt(x, y))
    if back:
        fp.Flip(pt(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)


def center_courtyard(fp, x, y):
    """Shift a placed footprint so its courtyard (or, without one, its pads) is centered on x, y."""
    fp.BuildCourtyardCaches()
    bb = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
    if bb.GetWidth() == 0:
        bb = fp.GetBoundingBox(False)
    c = bb.GetCenter()
    fp.Move(pcbnew.VECTOR2I(mm(x) - c.x, mm(y) - c.y))


def face_pad(fp, num, s, rot, side):
    """Turn fp by 180 degrees unless pad `num` lies on the `side` (+1 = +x) of the switch frame."""
    px, py = pad_xy(fp, num)
    c = fp.GetPosition()
    ux, uy = rotate((1, 0), rot)
    if ((px - pcbnew.ToMM(c.x)) * ux + (py - pcbnew.ToMM(c.y)) * uy) * side < 0:
        fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)


def pad_xy(fp, num):
    p = next(p for p in fp.Pads() if p.GetNumber() == num).GetPosition()
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


def outline(board):
    for seg in layout.load_outline():
        s = pcbnew.PCB_SHAPE(board)
        if "line" in seg:
            x0, y0, x1, y1 = seg["line"]
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pt(x0, y0)); s.SetEnd(pt(x1, y1))
        else:
            cx, cy, r = seg["circle"]
            s.SetShape(pcbnew.SHAPE_T_CIRCLE)
            s.SetCenter(pt(cx, cy)); s.SetEnd(pt(cx + r, cy))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)


PLANES = ((pcbnew.In1_Cu, "GND"), (pcbnew.In2_Cu, "+5V_SYS"))


def planes(board, netinfo):
    """A full-board zone on each inner layer; KiCad clips it to the outline and the holes."""
    xs, ys = [], []
    for seg in layout.load_outline():
        if "line" in seg:
            xs += seg["line"][0::2]; ys += seg["line"][1::2]
    for layer, net in PLANES:
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netinfo[net])
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))):
            o.Append(mm(x), mm(y))
        board.Add(z)


def build():
    comps, nets = netlist()
    switches = {s["ref"]: s for s in layout.load_switches()}
    _, chain_dir = layout.led_chain()
    board = pcbnew.CreateEmptyBoard()
    # four layers (decided 2026-11-21): signals outside, a GND plane and a 5V_SYS plane inside,
    # so every LED's power vias land on a plane and the outer layers stay free for the matrix
    board.SetCopperLayerCount(4)
    for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu):
        board.SetLayerType(layer, pcbnew.LT_POWER)
    tb = board.GetTitleBlock()
    tb.SetTitle("C128 keyboard, rev 3")
    tb.SetRevision("3")
    outline(board)

    netinfo = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pin_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

    fps = {}
    for ref, c in sorted(comps.items()):
        fp = load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH(c["sheet_path"] + c["uuid"]))
        fp.SetSheetname(c["sheet_name"])
        fp.SetSheetfile(c["sheet_file"])
        fp.SetField("Datasheet", c["datasheet"])
        fp.SetField("Description", c["description"])
        fp.SetExcludedFromBOM(c["exclude_from_bom"])
        fp.SetDNP(c["dnp"])
        for k, v in c["fields"].items():
            if k not in ("Reference", "Value", "Footprint", "Datasheet", "Description"):
                fp.SetField(k, v)
        for pad in fp.Pads():
            n = pin_net.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(netinfo[n])
        board.Add(fp)
        fps[ref] = fp

    planes(board, netinfo)

    unplaced = []
    for ref, fp in fps.items():
        sw_ref = None
        if ref.startswith("SW") and ref in switches:
            sw_ref, kind = ref, "switch"
        elif ref.startswith("LED"):
            sw_ref, kind = "SW" + ref[3:], "led"
        elif ref.startswith("D") and ref[1:].isdigit() and int(ref[1:]) > 100:
            sw_ref, kind = "SW" + str(int(ref[1:]) - 100), "diode"
        elif ref.startswith("C") and ref[1:].isdigit() and int(ref[1:]) > 100:
            sw_ref, kind = "SW" + str(int(ref[1:]) - 100), "cap"
        if sw_ref:
            s = switches[sw_ref]
            rot = 0.0 if (UNIFORM_180 and abs(s["rot"]) == 180) else s["rot"]
            if kind == "switch":
                place(fp, s["x"], s["y"], rot, back=False)
            elif kind == "led":
                # data in (pad 3) on the upstream side of the snake: west in left-to-right rows
                dx, dy = rotate(gen_fp.LED_OFFSET, rot)
                place(fp, s["x"] + dx, s["y"] + dy, rot, back=False)
                face_pad(fp, "3", s, rot, -chain_dir[sw_ref])
            else:
                dx, dy = rotate(DIODE_OFFSET if kind == "diode" else CAP_OFFSET, rot)
                place(fp, s["x"] + dx, s["y"] + dy, rot, back=True)
                # under the plate nobody reads these; keep the reference on the fab layer
                fp.Reference().SetLayer(pcbnew.B_Fab)
                if kind == "diode":
                    face_pad(fp, "2", s, rot, +1)       # anode toward the switch's pin 2 (+x)
                else:
                    # 5 V pad toward the LED's 5 V via: west in left-to-right rows (route_keys.py)
                    face_pad(fp, "1", s, rot, -chain_dir[sw_ref])
        elif ref in PLACE:
            x, y, r = PLACE[ref]
            place(fp, x, y, r, back=True)
            center_courtyard(fp, x, y)
        else:
            unplaced.append(ref)
    # anything without a home is parked in a row below the board, for placing by hand
    for i, ref in enumerate(sorted(unplaced)):
        place(fps[ref], 120 + i * 10, 220, 0, back=True)
    return board, unplaced


# --- project rules ------------------------------------------------------------------------

POWER_NETS = ["GND", "+5V_KB", "+5V_KB_F", "+5V_SYS", "+3V3", "VBUS"]


def project_rules():
    """Net classes and JLCPCB minimums (they hold for its 4-layer boards too) in the project file."""
    p = json.load(open(PROJECT, encoding="utf-8"))
    ns = p["net_settings"]
    default = next(c for c in ns["classes"] if c["name"] == "Default")
    default.update(track_width=0.25, clearance=0.2, via_diameter=0.6, via_drill=0.3)
    power = dict(default, name="Power", track_width=0.5, via_diameter=0.8, via_drill=0.4, priority=0)
    ns["classes"] = [default, power]
    ns["netclass_patterns"] = [{"netclass": "Power", "pattern": n} for n in POWER_NETS]
    rules = p["board"]["design_settings"].setdefault("rules", {})
    rules.update(min_clearance=0.15, min_track_width=0.15, min_via_diameter=0.5, min_via_annular_width=0.1,
                 min_through_hole_diameter=0.3, min_hole_to_hole=0.25, min_copper_edge_clearance=0.3,
                 min_hole_clearance=0.25)
    with open(PROJECT, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)
        f.write("\n")


def main():
    if os.path.exists(BOARD) and "--force" not in sys.argv:
        sys.exit(f"{BOARD} exists; it is the source once hand layout starts.  --force to overwrite.")
    board, unplaced = build()
    # pcbnew's save also writes a project file beside the board; save in a scratch folder and
    # keep only the board, so the real project file is not replaced
    # planes are left unfilled: pcbnew's filler crashes on a board built in memory, and
    # route_keys.py (or pressing B in pcbnew) fills them on a loaded board
    tmp = tempfile.mkdtemp()
    pcbnew.SaveBoard(os.path.join(tmp, NAME + ".kicad_pcb"), board)
    shutil.copy(os.path.join(tmp, NAME + ".kicad_pcb"), BOARD)
    shutil.rmtree(tmp)
    project_rules()
    print("wrote", BOARD, f"({len(board.GetFootprints())} footprints)")
    if unplaced:
        print("parked below the board, place by hand:", " ".join(sorted(unplaced)))


if __name__ == "__main__":
    main()
