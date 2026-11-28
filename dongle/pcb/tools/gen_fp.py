#!/usr/bin/env python3
"""Write the dongle's edge-straddle DB25 footprints into dongle/pcb/dongle.pretty/.

    docker compose run --rm kicad python3 dongle/pcb/tools/gen_fp.py

A straight solder-cup DB25 slides over the board edge: its 13-cup row (pins 1-13) lies on one
face of the 1.6 mm board and its 12-cup row (pins 14-25) on the other, and each cup is soldered
flat to its pad.  Dimensions from FCI drawing C-DSUB-0064 (pcb/datasheets/FCI-C-DSUB-0064.pdf),
size 25: contact pitch 2.76 mm, 2.84 mm between the cup rows (the board sits between them),
cups about 7.4 mm behind the insulator.

Frame: the board edge is y = 0, the board is y > 0, the connector hangs off the edge at y < 0.
F.Cu carries pins 1-13, B.Cu pins 14-25.  Seen from the solder side with the 13-pin row on top,
a plug (male, pins) has pin 1 on the right and a socket (female) has pin 1 on the left, so the
two footprints are mirror images in x.  The footprint is always viewed from above the board,
looking at the solder side with the connector away from the viewer, which is the solder-side
view: plug pin 1 at +x, socket pin 1 at -x.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "dongle.pretty"))

PITCH = 2.76
PAD_W, PAD_L = 1.5, 4.5        # a cup is about 1.1 mm across; 1.26 mm between pads
PAD_Y0 = 0.4                   # pads start this far in from the board edge, clear of the copper-to-edge rule
# body outline off the edge (FCI C-DSUB-0064, size 25): insulator 41.02 wide; flange 52.65 wide,
# 1.0 (plug) / 0.8 (socket) thick, 47.04 between its holes; D shell 38.84 / 38.25 wide,
# 8.23 / 7.77 deep; G 5.85 / 6.05 from the cup end of the insulator to the flange
BODY = {
    "Pins":   dict(G=5.85, L=1.0, B=38.84, D=8.23),
    "Socket": dict(G=6.05, L=0.8, B=38.25, D=7.77),
}
H_W, A_W, C_HOLES = 41.02, 52.65, 47.04


def f(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def footprint(kind):
    sign = 1 if kind == "Pins" else -1          # where pin 1 sits: plug +x, socket -x
    name = f"DB25_{kind}_EdgeStraddle_1.6mm"
    b = BODY[kind]
    gender = "male (plug)" if kind == "Pins" else "female (socket)"
    out = [f'(footprint "{name}"',
           '  (version 20240108) (generator "gen_fp")',
           '  (layer "F.Cu")',
           f'  (descr "Straight solder-cup DB25 {gender} straddling a 1.6 mm board edge: pins 1-13 on F.Cu, 14-25 on B.Cu. '
           f'FCI C-DSUB-0064, size 25, pitch {PITCH} mm. Board edge at y = 0; the connector hangs off the edge at y < 0.")',
           '  (attr smd)',
           f'  (property "Reference" "REF**" (at 0 {f(PAD_Y0 + PAD_L + 2)} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
           f'  (property "Value" "{name}" (at 0 {f(-(b["G"] + b["L"] + b["D"]) - 1.5)} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))']
    cy = PAD_Y0 + PAD_L / 2
    for i in range(13):                          # pins 1..13 on top
        x = sign * (6 - i) * PITCH
        out.append(f'  (pad "{i + 1}" smd rect (at {f(x)} {f(cy)}) (size {f(PAD_W)} {f(PAD_L)}) (layers "F.Cu" "F.Mask"))')
    for k in range(12):                          # pins 14..25 underneath, offset half a pitch
        x = sign * (5.5 - k) * PITCH
        out.append(f'  (pad "{14 + k}" smd rect (at {f(x)} {f(cy)}) (size {f(PAD_W)} {f(PAD_L)}) (layers "B.Cu" "B.Mask"))')

    def rect(layer, x0, y0, x1, y1, w=0.1):
        return f'  (fp_rect (start {f(x0)} {f(y0)}) (end {f(x1)} {f(y1)}) (stroke (width {w}) (type solid)) (fill no) (layer "{layer}"))'

    g, l, d = b["G"], b["L"], b["D"]
    # Fab: insulator behind the flange, the flange, the D shell beyond it
    out.append(rect("F.Fab", -H_W / 2, -g, H_W / 2, 0))
    out.append(rect("F.Fab", -A_W / 2, -g - l, A_W / 2, -g))
    out.append(rect("F.Fab", -b["B"] / 2, -g - l - d, b["B"] / 2, -g - l))
    for hx in (-C_HOLES / 2, C_HOLES / 2):
        out.append(f'  (fp_circle (center {f(hx)} {f(-g - l / 2)}) (end {f(hx + 1.55)} {f(-g - l / 2)}) '
                   f'(stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))')
    # where the board edge must be, and the pin-1 end
    out.append(f'  (fp_line (start {f(-A_W / 2)} 0) (end {f(A_W / 2)} 0) (stroke (width 0.1) (type dash)) (layer "Dwgs.User"))')
    out.append(f'  (fp_text user "board edge" (at 0 -0.8 0) (layer "Dwgs.User") (effects (font (size 0.8 0.8) (thickness 0.1))))')
    out.append(f'  (fp_text user "1" (at {f(sign * 6 * PITCH)} {f(PAD_Y0 + PAD_L + 1)} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    out.append(f'  (fp_text user "14" (at {f(sign * 5.5 * PITCH)} {f(PAD_Y0 + PAD_L + 1)} 0) (layer "B.SilkS") '
               f'(effects (font (size 1 1) (thickness 0.15)) (justify mirror)))')
    # courtyard: the pads on both faces, and the body out to the flange and shell
    for layer in ("F.CrtYd", "B.CrtYd"):
        out.append(rect(layer, -A_W / 2 - 0.25, -g - l - d - 0.25, A_W / 2 + 0.25, PAD_Y0 + PAD_L + 0.5, 0.05))
    out.append(")")
    path = os.path.join(OUT, name + ".kicad_mod")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    for kind in ("Pins", "Socket"):
        print("wrote", footprint(kind))


if __name__ == "__main__":
    main()
