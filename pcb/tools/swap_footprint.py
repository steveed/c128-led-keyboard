#!/usr/bin/env python3
"""Swap one footprint on pcb/C128-keyboard-rev3.kicad_pcb for another, keeping its link to the schematic.

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \\
        pcb/tools/swap_footprint.py REF LIB:NAME X Y ROT [back]

The new footprint comes from the project library (fp-lib-table), takes the old one's
reference, fields, schematic link and pad nets, and goes on at (X, Y, ROT) by its origin, on
the back with "back".  Unlocked tracks and vias that touched the old footprint's pads, or
that cross the new one's courtyard, are deleted: reroute them afterwards.  Planes are refilled.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.dirname(HERE)
BOARD = os.path.join(PCB, "C128-keyboard-rev3.kicad_pcb")
LIBS = {"c128rev3": os.path.join(PCB, "c128rev3.pretty")}


def main():
    ref, fpid, x, y, rot = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:6])
    back = len(sys.argv) > 6 and sys.argv[6] == "back"
    lib, name = fpid.split(":")
    board = pcbnew.LoadBoard(BOARD)
    old = {f.GetReference(): f for f in board.GetFootprints()}[ref]
    new = pcbnew.FootprintLoad(LIBS[lib], name)
    if new is None:
        sys.exit(f"no footprint {fpid}")

    # tracks and vias on the old pads
    stale = []
    for t in board.GetTracks():
        if t.IsLocked():
            continue
        for p in old.Pads():
            if p.GetNetCode() != t.GetNetCode():
                continue
            ends = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
            if any(p.HitTest(e) for e in ends):
                stale.append(t)
                break

    nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
    new.SetFPID(pcbnew.LIB_ID(lib, name))
    new.SetReference(old.GetReference())
    new.SetValue(old.GetValue())
    for f in old.GetFields():
        if not f.IsReference() and not f.IsValue() and f.GetName() != "Footprint":
            new.SetField(f.GetName(), f.GetText())
    new.SetPath(old.GetPath())
    new.SetSheetname(old.GetSheetname())
    new.SetSheetfile(old.GetSheetfile())
    kind = pcbnew.FP_THROUGH_HOLE | pcbnew.FP_SMD      # the new footprint's own; the rest (DNP, BOM) the old one's
    new.SetAttributes((new.GetAttributes() & kind) | (old.GetAttributes() & ~kind))
    for p in new.Pads():
        if p.GetNumber() in nets:
            p.SetNet(nets[p.GetNumber()])
    board.Add(new)
    new.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    if back:
        new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    new.SetOrientationDegrees(rot)
    for f in new.GetFields():
        if f.GetName() in ("Datasheet", "Description") or f.IsValue():
            f.SetVisible(False)
    board.Delete(old)
    # and whatever crosses the new courtyard
    layer = pcbnew.B_CrtYd if back else pcbnew.F_CrtYd
    yard = new.GetCourtyard(layer)
    seen = {id(t) for t in stale}
    for t in board.GetTracks():
        if t.IsLocked() or id(t) in seen:
            continue
        if yard.Collide(t.GetEffectiveShape(t.GetLayer() if t.Type() != pcbnew.PCB_VIA_T else pcbnew.F_Cu), 0):
            stale.append(t)
            seen.add(id(t))
    for t in stale:
        board.Delete(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"{ref}: now {fpid} at ({x}, {y}, {rot}){' on the back' if back else ''}; {len(stale)} stale tracks and vias removed")


if __name__ == "__main__":
    main()
