"""The keyboard layout every generator works from: layout/switches.json and layout/plate.json.

Both are written by extract_layout.py.  They currently hold the original measurements (the
rev 2.3 board's switches and the original plate.step); once the new board is laid out,
re-extract switches.json from it and everything downstream follows.
"""
import json
import os

LAYOUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "layout"))
SWITCHES = os.path.join(LAYOUT_DIR, "switches.json")
PLATE = os.path.join(LAYOUT_DIR, "plate.json")


def load_switches():
    """Every switch footprint: ref, key legend (val), center x/y in KiCad board coordinates
    (mm, y down), and the row/col nets on pads 1 and 2."""
    return json.load(open(SWITCHES, encoding="utf-8"))["switches"]


def load_plate():
    """The plate's top face as loops of line/arc/circle segments in the plate's own frame:
    {"outer": [...], "holes": [[...], ...]}.  gen_plate.py fits it onto the switches."""
    d = json.load(open(PLATE, encoding="utf-8"))
    return {"outer": d["outer"], "holes": d["holes"]}
