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
OUTLINE = os.path.join(LAYOUT_DIR, "outline.json")


def load_switches():
    """Every switch footprint: ref, key legend (val), center x/y in KiCad board coordinates
    (mm, y down), rotation in degrees, and the row/col nets on pads 1 and 2."""
    return json.load(open(SWITCHES, encoding="utf-8"))["switches"]


def load_plate():
    """The plate's top face as loops of line/arc/circle segments in the plate's own frame:
    {"outer": [...], "holes": [[...], ...]}.  gen_plate.py fits it onto the switches."""
    d = json.load(open(PLATE, encoding="utf-8"))
    return {"outer": d["outer"], "holes": d["holes"]}


def load_outline():
    """The board outline as {"line": [x0, y0, x1, y1]} and {"circle": [cx, cy, r]} segments,
    in KiCad board coordinates."""
    return json.load(open(OUTLINE, encoding="utf-8"))["segments"]


# --- rev 3 physical matrix ------------------------------------------------------------------
#
# Rev 3 scans its own matrix and the CH446Q presents the C128's, so the scanned rows and
# columns follow the board instead of the C128 assignment: 6 rows (the five key rows, plus
# the spacebar on its own) by 20 columns (one per key of the number row, the only row with a
# key in every column).  Every other key takes the column whose number-row key is nearest in
# x.  Keypad Enter, which sits between two rows, goes in the upper one (column 19 is free
# there).  RESTORE is hard-wired to the host and is not scanned.
PHYS_ROWS = 6
PHYS_COLS = 20
_ROW_OF = {"Space": 5, "NumEnter": 3}


def physical_matrix(switches=None):
    """{switch ref: (row, col)} of the rev 3 scanned matrix, for every key but RESTORE."""
    sw = [s for s in (switches or load_switches()) if s["val"] != "Restore"]
    ys = sorted({round(s["y"], 1) for s in sw})
    rows = []                                    # key-row centers: y clusters of more than one key
    for y in ys:
        group = [s for s in sw if abs(s["y"] - y) < 3]
        if len(group) > 1 and not any(abs(r - y) < 3 for r in rows):
            rows.append(y)
    number_row = max(rows, key=lambda y: sum(abs(s["y"] - y) < 3 for s in sw))
    col_x = sorted(s["x"] for s in sw if abs(s["y"] - number_row) < 3)
    assert len(rows) == PHYS_ROWS - 1 and len(col_x) == PHYS_COLS, (rows, len(col_x))
    out, used = {}, set()
    for s in sw:
        r = _ROW_OF.get(s["val"], min(range(len(rows)), key=lambda i: abs(rows[i] - s["y"])))
        c = min(range(PHYS_COLS), key=lambda i: abs(col_x[i] - s["x"]))
        if (r, c) in used:
            raise ValueError(f"{s['ref']} ({s['val']}) collides at row {r} column {c}")
        used.add((r, c))
        out[s["ref"]] = (r, c)
    return out
