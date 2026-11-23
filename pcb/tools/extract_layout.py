#!/usr/bin/env python3
"""Write layout/switches.json and layout/plate.json, the measurements every generator uses.

    python3 pcb/tools/extract_layout.py switches BOARD.kicad_pcb
    python3 pcb/tools/extract_layout.py outline BOARD.kicad_pcb
    python3 pcb/tools/extract_layout.py plate PLATE.step

switches: every SW* footprint on a KiCad board, with its key legend (Value), center, and the
nets on pads 1 (row) and 2 (column).  The committed file came from the rev 2.3 board
(pcb/C128-keyboard.kicad_pcb in the-c128-keyboard-project); run it on the new board once
that is laid out.

outline: the board's Edge.Cuts lines and circles, in board coordinates; gen_pcb.py draws the
rev 3 outline from it.

plate: the plate's top-face loops from a STEP model, in the model's own frame (plate_step.py
does the parsing).  The committed file came from that project's plate/plate.step.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout  # noqa: E402
import plate_step as P  # noqa: E402


def board_switches(path):
    s = open(path, encoding="utf-8").read()
    out = []
    for b in re.split(r"\n\t\(footprint ", s)[1:]:
        ref = re.search(r'\(property "Reference" "([^"]+)"', b)
        val = re.search(r'\(property "Value" "([^"]+)"', b)
        at = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", b)
        if not ref or not ref.group(1).startswith("SW"):
            continue
        nets = {}
        for p in re.split(r"\n\t\t\(pad ", b)[1:]:
            name = re.match(r'"([^"]*)"', p).group(1)
            net = re.search(r'\(net "([^"]*)"', p)
            if name in ("1", "2") and net:
                nets[name] = net.group(1)
        out.append(dict(ref=ref.group(1), val=val.group(1), x=float(at.group(1)), y=float(at.group(2)),
                        rot=float(at.group(3) or 0), row=nets.get("1"), col=nets.get("2")))
    return out


def board_outline(path):
    """Top-level Edge.Cuts lines and circles (the rev 2.3 outline has nothing else)."""
    s = open(path, encoding="utf-8").read()
    out = []
    for kind, body in re.findall(r"\n\t\((gr_line|gr_circle|gr_arc|gr_rect|gr_poly)\n(.*?)\n\t\)", s, re.S):
        if '(layer "Edge.Cuts")' not in body:
            continue
        p = {k: (float(a), float(b)) for k, a, b in re.findall(r"\((start|end|center|mid) ([-\d.]+) ([-\d.]+)\)", body)}
        if kind == "gr_line":
            out.append({"line": [*p["start"], *p["end"]]})
        elif kind == "gr_circle":
            r = ((p["end"][0] - p["center"][0]) ** 2 + (p["end"][1] - p["center"][1]) ** 2) ** 0.5
            out.append({"circle": [*p["center"], round(r, 6)]})
        else:
            sys.exit(f"outline: {kind} not handled")
    return out


def write(path, source, key, items):
    """One list item per line, so a changed switch or loop shows up as a one-line diff."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("{\n" + f' "source": {json.dumps(source)},\n')
        for i, (k, v) in enumerate(items.items()):
            if k == key:
                f.write(f' "{k}": [\n' + ",\n".join("  " + json.dumps(x) for x in v) + "\n ]")
            else:
                f.write(f' "{k}": {json.dumps(v)}')
            f.write(",\n" if i < len(items) - 1 else "\n")
        f.write("}\n")
    print("wrote", path)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("switches", "outline", "plate"):
        sys.exit(__doc__)
    what, src = sys.argv[1], sys.argv[2]
    name = os.path.basename(src)
    if what == "switches":
        sw = board_switches(src)
        write(layout.SWITCHES, f"{name}: SW* footprints, KiCad board coordinates (mm, y down)",
              "switches", {"switches": sw})
        print(len(sw), "switches")
    elif what == "outline":
        seg = board_outline(src)
        write(layout.OUTLINE, f"{name}: Edge.Cuts lines and circles, KiCad board coordinates (mm, y down)",
              "segments", {"segments": seg})
        print(len(seg), "outline segments")
    else:
        geo = P.extract(src)
        write(layout.PLATE, f"{name}: top-face loops in the model's frame (mm)",
              "holes", {"outer": geo["outer"], "holes": geo["holes"]})
        print(len(geo["holes"]), "inner loops")


if __name__ == "__main__":
    main()
