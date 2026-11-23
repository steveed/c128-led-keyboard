#!/usr/bin/env python3
"""Make the JLCPCB order files for the rev 3 board: gerbers + drills (zipped), BOM and CPL.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/fab.py

Writes pcb/fab/ (not tracked):
  C128-keyboard-rev3-gerbers.zip   copper (4 layers), mask, paste, silk, outline, drills
  C128-keyboard-rev3-bom.csv       Comment, Designator, Footprint, LCSC Part #
  C128-keyboard-rev3-cpl.csv       Designator, Mid X, Mid Y, Layer, Rotation

Settings follow JLCPCB's KiCad guide: Protel extensions, no X2 or netlist attributes, solder
mask subtracted from silk, Excellon drills in mm with PTH and NPTH in separate files, absolute
origin for gerbers, drills and positions alike.  The planes are refilled on a copy first.

The BOM comes from the schematic's LCSC fields.  A part with no LCSC number is not placed by
the fab (the key switches and J2-J4, which the builder solders, and JP1, which is copper only)
and is left out of both the BOM and the CPL; the script lists them, and refuses to write if an
SMD footprint on the board has no number, or if DRC finds an error or anything unconnected.

Rotations are KiCad's.  JLCPCB's part models don't all share KiCad's zero orientation, so
check every part in the placement preview after upload and fix any that are turned there
(or add a correction to ROT_FIX and rerun).
"""
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.dirname(HERE)
NAME = "C128-keyboard-rev3"
BOARD = os.path.join(PCB, NAME + ".kicad_pcb")
SCH = os.path.join(PCB, NAME + ".kicad_sch")
OUT = os.path.join(PCB, "fab")
KC = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
ROT_FIX = {}        # footprint name -> degrees added to KiCad's rotation, once checked at JLCPCB


def run(*args):
    r = subprocess.run([KC, *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"fab: kicad-cli {args[0]} {args[1]} failed:\n{r.stdout}{r.stderr}")
    return r.stdout


def copy_project(tmp):
    """The board, project and schematic in a scratch folder, planes refilled."""
    for f in glob.glob(os.path.join(PCB, NAME + ".kicad_p*")) + glob.glob(os.path.join(PCB, "*.kicad_sch")):
        shutil.copy(f, tmp)
    b = os.path.join(tmp, NAME + ".kicad_pcb")
    board = pcbnew.LoadBoard(b)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(b)
    return b, board


def drc(b, tmp):
    rpt = os.path.join(tmp, "drc.json")
    run("pcb", "drc", "--schematic-parity", "--format", "json", "-o", rpt, b)
    d = json.load(open(rpt))
    errors = [v for v in d["violations"] if v["severity"] == "error"]
    bad = len(d["unconnected_items"]) + len(d.get("schematic_parity", [])) + len(errors)
    if bad:
        for v in errors[:20]:
            print("  ", v["type"], v["description"])
        sys.exit(f"fab: DRC: {len(errors)} errors, {len(d['unconnected_items'])} unconnected, "
                 f"{len(d.get('schematic_parity', []))} parity; fix first")


def bom(tmp):
    raw = os.path.join(tmp, "bom-raw.csv")
    run("sch", "export", "bom", "-o", raw, "--fields", "Reference,Value,Footprint,LCSC",
        "--group-by", "Value,Footprint,LCSC", "--ref-range-delimiter", "", SCH)
    rows, skipped, lcsc_of = [], [], {}
    by_lcsc = {}
    for r in csv.DictReader(open(raw, encoding="utf-8")):
        refs = [x.strip() for x in r["Reference"].split(",") if x.strip()]
        lcsc = r["LCSC"].strip()
        if not lcsc:
            skipped.extend(refs)
            continue
        fp = r["Footprint"].split(":", 1)[-1]
        # one line per LCSC number: JLCPCB rejects a BOM where two lines name the same part
        # (SW93 RESET and SW94 BOOT are both the PTS645)
        row = by_lcsc.get(lcsc)
        if row is None:
            row = by_lcsc[lcsc] = {"Comment": [], "Designator": [], "Footprint": fp, "LCSC Part #": lcsc}
            rows.append(row)
        elif row["Footprint"] != fp:
            sys.exit(f"fab: {lcsc} is on two footprints, {row['Footprint']} and {fp}")
        if r["Value"] not in row["Comment"]:
            row["Comment"].append(r["Value"])
        row["Designator"].extend(refs)
        for ref in refs:
            lcsc_of[ref] = lcsc
    for row in rows:
        row["Comment"] = "/".join(row["Comment"])
        row["Designator"] = ",".join(row["Designator"])
    return rows, skipped, lcsc_of


def cpl(b, tmp, placed, board):
    raw = os.path.join(tmp, "pos-raw.csv")
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", raw, b)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    rows = []
    for r in csv.DictReader(open(raw, encoding="utf-8")):
        ref = r["Ref"]
        if ref not in placed:
            continue
        name = fps[ref].GetFPID().GetLibItemName().wx_str() if ref in fps else ""
        rot = (float(r["Rot"]) + ROT_FIX.get(name, 0)) % 360
        rows.append({"Designator": ref, "Mid X": f"{float(r['PosX']):.4f}mm",
                     "Mid Y": f"{float(r['PosY']):.4f}mm",
                     "Layer": "Top" if r["Side"] == "top" else "Bottom", "Rotation": f"{rot:g}"})
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    tmp = tempfile.mkdtemp()
    try:
        b, board = copy_project(tmp)
        drc(b, tmp)
        bom_rows, skipped, lcsc_of = bom(tmp)

        # every SMD part must have a number: the fab places them all
        missing = sorted(f.GetReference() for f in board.GetFootprints()
                         if f.GetAttributes() & pcbnew.FP_SMD and f.GetReference() not in lcsc_of
                         and f.GetReference() not in ("JP1",))
        if missing:
            sys.exit(f"fab: SMD footprints with no LCSC number: {', '.join(missing)}")
        on_board = {f.GetReference() for f in board.GetFootprints()}
        lost = sorted(set(lcsc_of) - on_board)
        if lost:
            sys.exit(f"fab: in the BOM but not on the board: {', '.join(lost)}")

        cpl_rows = cpl(b, tmp, set(lcsc_of), board)
        if len(cpl_rows) != len(lcsc_of):
            sys.exit(f"fab: CPL has {len(cpl_rows)} parts, BOM {len(lcsc_of)}")

        if os.path.isdir(OUT):
            shutil.rmtree(OUT)
        ger = os.path.join(tmp, "gerbers")
        os.makedirs(ger)
        run("pcb", "export", "gerbers", "-o", ger + "/", "--layers", LAYERS, "--no-x2", "--no-netlist",
            "--subtract-soldermask", b)
        run("pcb", "export", "drill", "-o", ger + "/", "--format", "excellon", "--excellon-units", "mm",
            "--excellon-zeros-format", "decimal", "--excellon-oval-format", "alternate",
            "--excellon-separate-th", "--drill-origin", "absolute", b)
        os.makedirs(OUT)
        files = sorted(os.listdir(ger))
        z = os.path.join(OUT, NAME + "-gerbers.zip")
        # zip -X: no macOS extended attributes; a Finder zip's __MACOSX twins confuse uploaders
        subprocess.run(["zip", "-X", "-j", "-q", z, *[os.path.join(ger, f) for f in files]], check=True)
        write_csv(os.path.join(OUT, NAME + "-bom.csv"), bom_rows,
                  ["Comment", "Designator", "Footprint", "LCSC Part #"])
        write_csv(os.path.join(OUT, NAME + "-cpl.csv"), cpl_rows,
                  ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    top = sum(1 for r in cpl_rows if r["Layer"] == "Top")
    print(f"fab: {len(files)} gerber/drill files -> {os.path.relpath(z)}")
    print(f"fab: BOM {len(bom_rows)} lines, {len(lcsc_of)} parts; CPL {top} top, {len(cpl_rows) - top} bottom")
    print(f"fab: not placed by the fab ({len(skipped)}): "
          + ", ".join(sorted(skipped, key=lambda s: (s.rstrip('0123456789'), int('0' + s[len(s.rstrip('0123456789')):]))))
          [:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
