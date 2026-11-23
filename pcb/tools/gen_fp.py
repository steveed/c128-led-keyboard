#!/usr/bin/env python3
"""Write the rev 3 project footprint library, pcb/c128rev3.pretty, and pcb/fp-lib-table.

    python3 pcb/tools/gen_fp.py

Footprints (origin at the switch center, the frame layout/switches.json uses):

  SW_MX_1u, SW_MX_1.5u     MX PCB-mount switch, no stabilizer
  SW_MX_2u                 2u with Cherry PCB stabilizer holes (Return, keypad 0, and keypad
                           Enter placed at -90 as on rev 2.3)
  SW_MX_Spacebar           spacebar switch with the stabilizer hole sets in SPACEBAR_STABS
  LED_SK6812MINI_MX        SK6812 MINI (top mount) for the switch's LED pocket; no courtyard,
                           because it sits inside the switch's by design

Switch geometry is the rev 2.3 board's MX pattern with the Alps pads dropped: pin 1 at
(-3.81, -2.54), pin 2 at (2.54, -5.08), 3.9878 mm center hole, 1.75 mm pegs at +/-5.08 for
5-pin switches.  The LED goes opposite the pins, where rev 2.3 had its lock-key LED holes:
LED_OFFSET in the switch frame, rotating with the switch.  The placement script imports it.

Every UUID is derived from footprint name plus item key, so regeneration is byte-identical.
"""
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.dirname(HERE)
LIB = "c128rev3"
OUT = os.path.join(PCB, LIB + ".pretty")

VERSION = "20260206"           # KiCad 10.0 footprint format
UUID_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "rev3-fp.the-c128-keyboard-project")
U = 19.05

# LED pocket center in the switch frame (mm, y down).  Rev 2.3's lock-key LED holes were at
# (+/-1.27, 5.08).  PROVISIONAL until the Outemu pocket is measured
# (pcb/bench/before-parts-arrive.md section 5.2).
LED_OFFSET = (0.0, 5.08)

# Cherry PCB-mount stabilizer: 3.048 mm hole above, 3.988 mm below the switch row, per side.
STAB_2U = 11.938
STAB_SMALL = (3.048, -6.985)
STAB_LARGE = (3.9878, 8.255)
# Spacebar: half-spacings of the stabilizer sets.  Rev 2.3 mounts its stabilizer "reversed"
# (large hole above, small below), kept here.  Cherry 6.25u is 100 mm, Cherry 9u 133.35 mm;
# the rev 2.3 board as fabricated has 99.77 and 125.35 mm instead.  Holes 4 mm apart overlap,
# so 125.35 and 133.35 cannot both be drilled.
SPACEBAR_STABS = (50.0, 66.675)


def uid(fp, key):
    return str(uuid.uuid5(UUID_NS, f"{fp}/{key}"))


def num(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Fp:
    def __init__(self, name, descr, tags, attr):
        self.name, self.items = name, []
        self.head = [f'(footprint "{name}"', f'\t(version {VERSION})', '\t(generator "gen_fp")',
                     '\t(generator_version "10.0")', '\t(layer "F.Cu")', f'\t(descr "{descr}")',
                     f'\t(tags "{tags}")']
        self.attr = attr

    def prop(self, key, value, at, layer, size=1.0, hide=False):
        h = "\n\t\t(hide yes)" if hide else ""
        self.items.append(
            f'\t(property "{key}" "{value}"\n\t\t(at {num(at[0])} {num(at[1])} 0)\n\t\t(layer "{layer}"){h}\n'
            f'\t\t(uuid "{uid(self.name, "prop/" + key)}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {num(size)} {num(size)})\n\t\t\t\t(thickness {num(size * 0.15)})\n\t\t\t)\n\t\t)\n\t)')

    def rect(self, x0, y0, x1, y1, layer, width):
        self.items.append(
            f'\t(fp_rect\n\t\t(start {num(x0)} {num(y0)})\n\t\t(end {num(x1)} {num(y1)})\n'
            f'\t\t(stroke\n\t\t\t(width {num(width)})\n\t\t\t(type solid)\n\t\t)\n\t\t(fill no)\n'
            f'\t\t(layer "{layer}")\n\t\t(uuid "{uid(self.name, f"rect/{layer}/{x0}/{y0}/{x1}/{y1}")}")\n\t)')

    def line(self, x0, y0, x1, y1, layer, width):
        self.items.append(
            f'\t(fp_line\n\t\t(start {num(x0)} {num(y0)})\n\t\t(end {num(x1)} {num(y1)})\n'
            f'\t\t(stroke\n\t\t\t(width {num(width)})\n\t\t\t(type solid)\n\t\t)\n'
            f'\t\t(layer "{layer}")\n\t\t(uuid "{uid(self.name, f"line/{layer}/{x0}/{y0}/{x1}/{y1}")}")\n\t)')

    def circle(self, x, y, r, layer, width, fill=False):
        self.items.append(
            f'\t(fp_circle\n\t\t(center {num(x)} {num(y)})\n\t\t(end {num(x + r)} {num(y)})\n'
            f'\t\t(stroke\n\t\t\t(width {num(width)})\n\t\t\t(type solid)\n\t\t)\n\t\t(fill {"yes" if fill else "no"})\n'
            f'\t\t(layer "{layer}")\n\t\t(uuid "{uid(self.name, f"circle/{layer}/{x}/{y}/{r}")}")\n\t)')

    def text(self, s, x, y, layer, size):
        self.items.append(
            f'\t(fp_text user "{s}"\n\t\t(at {num(x)} {num(y)} 0)\n\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{uid(self.name, f"text/{layer}/{s}")}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {num(size)} {num(size)})\n\t\t\t\t(thickness {num(size * 0.15)})\n\t\t\t)\n\t\t)\n\t)')

    def npth(self, x, y, d):
        self.items.append(
            f'\t(pad "" np_thru_hole circle\n\t\t(at {num(x)} {num(y)})\n\t\t(size {num(d)} {num(d)})\n'
            f'\t\t(drill {num(d)})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(uuid "{uid(self.name, f"npth/{x}/{y}")}")\n\t)')

    def tht(self, n, x, y, size, drill):
        self.items.append(
            f'\t(pad "{n}" thru_hole circle\n\t\t(at {num(x)} {num(y)})\n\t\t(size {num(size)} {num(size)})\n'
            f'\t\t(drill {num(drill)})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n'
            f'\t\t(uuid "{uid(self.name, f"pad/{n}")}")\n\t)')

    def slot(self, n, x, y, w, h, dw, dh):
        """Plated oval slot, w x h pad around a dw x dh drill (h along y)."""
        self.items.append(
            f'\t(pad "{n}" thru_hole oval\n\t\t(at {num(x)} {num(y)})\n\t\t(size {num(w)} {num(h)})\n'
            f'\t\t(drill oval {num(dw)} {num(dh)})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n'
            f'\t\t(uuid "{uid(self.name, f"slot/{n}/{x}/{y}")}")\n\t)')

    def smd(self, n, x, y, w, h):
        self.items.append(
            f'\t(pad "{n}" smd rect\n\t\t(at {num(x)} {num(y)})\n\t\t(size {num(w)} {num(h)})\n'
            f'\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n\t\t(uuid "{uid(self.name, f"pad/{n}")}")\n\t)')

    def model(self, path, offset):
        self.items.append(
            f'\t(model "{path}"\n\t\t(offset\n\t\t\t(xyz {num(offset[0])} {num(offset[1])} 0)\n\t\t)\n'
            f'\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n\t\t(rotate\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t)')

    def write(self):
        body = self.head[:]
        props, rest = [i for i in self.items if i.startswith("\t(property")], \
            [i for i in self.items if not i.startswith("\t(property") and not i.startswith("\t(model")]
        models = [i for i in self.items if i.startswith("\t(model")]
        # KiCad's save order (graphics by kind, then pads), so a save from the footprint editor
        # leaves the file unchanged
        rank = ("\t(fp_line", "\t(fp_rect", "\t(fp_circle", "\t(fp_text", "\t(pad")
        rest.sort(key=lambda i: next(n for n, r in enumerate(rank) if i.startswith(r)))
        body += props + [f"\t(attr {self.attr})", "\t(duplicate_pad_numbers_are_jumpers no)"] + rest
        body += ["\t(embedded_fonts no)"] + models + [")"]
        with open(os.path.join(OUT, self.name + ".kicad_mod"), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")


def switch(name, width, stabs=(), reversed_stabs=False, descr=""):
    fp = Fp(name, f"MX PCB-mount keyswitch, {descr}; SK6812 MINI pocket at {num(LED_OFFSET[0])},{num(LED_OFFSET[1])} "
                  "(LED is a separate footprint, LED_SK6812MINI_MX)",
            f"Cherry MX keyswitch {num(width)}u c128 rev3", "through_hole")
    fp.prop("Reference", "REF**", (-4.6, -5.9), "F.SilkS", 0.8)
    fp.prop("Value", name, (0, 7.9), "F.Fab", 0.8)
    fp.prop("Datasheet", "", (0, 0), "F.Fab", hide=True)
    fp.prop("Description", "", (0, 0), "F.Fab", hide=True)
    # pads and holes
    fp.npth(0, 0, 3.9878)
    fp.npth(-5.08, 0, 1.75)
    fp.npth(5.08, 0, 1.75)
    fp.tht("1", -3.81, -2.54, 2.2, 1.5)
    fp.tht("2", 2.54, -5.08, 2.2, 1.5)
    # switch body: courtyard on the 14 mm housing, fab outline of body and keycap
    fp.rect(-7.25, -7.25, 7.25, 7.25, "F.CrtYd", 0.05)
    fp.rect(-7, -7, 7, 7, "F.Fab", 0.1)
    fp.rect(-width * U / 2, -U / 2, width * U / 2, U / 2, "Dwgs.User", 0.1)
    # silk: switch corners only (the plate hides the rest), and the LED pocket on F.Fab
    for sx in (-1, 1):
        for sy in (-1, 1):
            fp.line(sx * 7, sy * 7, sx * 5.5, sy * 7, "F.SilkS", 0.12)
            fp.line(sx * 7, sy * 7, sx * 7, sy * 5.5, "F.SilkS", 0.12)
    lx, ly = LED_OFFSET
    fp.rect(lx - 1.75, ly - 1.75, lx + 1.75, ly + 1.75, "F.Fab", 0.1)
    # stabilizers: holes, plus a courtyard for the housing that sits between PCB and plate
    for half in stabs:
        for sx in (-1, 1):
            x = sx * half
            (ds, ys), (dl, yl) = STAB_SMALL, STAB_LARGE
            if reversed_stabs:
                ys, yl = -ys, -yl
            fp.npth(x, ys, ds)
            fp.npth(x, yl, dl)
            y0, y1 = min(ys - ds / 2, yl - dl / 2) - 0.5, max(ys + ds / 2, yl + dl / 2) + 0.5
            fp.rect(x - 3.5, y0, x + 3.5, y1, "F.CrtYd", 0.05)
            fp.rect(x - 3.25, y0 + 0.25, x + 3.25, y1 - 0.25, "F.Fab", 0.1)
    fp.text("${REFERENCE}", 0, -2.2 if not stabs else 3, "F.Fab", 0.8)
    # stock KiCad MX model has its origin at pin 2 of our numbering; offset y is up in 3D
    fp.model("${KICAD10_3DMODEL_DIR}/Button_Switch_Keyboard.3dshapes/SW_Cherry_MX_1.00u_PCB.step", (2.54, 5.08))
    fp.write()


def led():
    name = "LED_SK6812MINI_MX"
    fp = Fp(name, "SK6812 MINI 3.5x3.5 mm top-mount RGB LED for an MX switch LED pocket; pads as KiCad "
                  "LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm, no courtyard (sits inside the switch's by design)",
            "LED RGB SK6812MINI 3535 MX pocket c128 rev3", "smd allow_missing_courtyard")
    fp.prop("Reference", "REF**", (0, -2.5), "F.Fab", 0.5)
    fp.prop("Value", name, (0, 2.5), "F.Fab", 0.5)
    fp.prop("Datasheet", "https://cdn-shop.adafruit.com/product-files/2686/SK6812MINI_REV.01-1-2.pdf", (0, 0), "F.Fab", hide=True)
    fp.prop("Description", "", (0, 0), "F.Fab", hide=True)
    # numbering as KiCad's LED:SK6812MINI symbol.  The part fitted (OPSCO SK6812MINI-012, LCSC
    # C2886570, pcb/datasheets/C2886570.pdf; the -B-012, C5183448, has the same pins and lands)
    # numbers its pins differently (1 DIN, 2 VDD, 3 DOUT, 4 GND) but puts each in the same
    # place, so the pads hold; its pin 1 and chamfered corner are our pad 3, DIN.
    fp.smd("1", -1.75, -0.875, 1.6, 0.85)    # DOUT
    fp.smd("2", -1.75, 0.875, 1.6, 0.85)     # VSS
    fp.smd("3", 1.75, 0.875, 1.6, 0.85)      # DIN
    fp.smd("4", 1.75, -0.875, 1.6, 0.85)     # VDD
    fp.rect(-1.75, -1.75, 1.75, 1.75, "F.Fab", 0.1)
    fp.line(1.75, 0.75, 0.75, 1.75, "F.Fab", 0.1)
    # the dot marks the part's pin 1 (DIN, pad 3), not pad 1: at the fab, a part's pin-1 mark
    # lined up with a dot on pad 1 would put every LED in turned 180 degrees
    fp.circle(2.95, 0.875, 0.15, "F.SilkS", 0.12, fill=True)
    fp.text("${REFERENCE}", 0, 0, "F.Fab", 0.5)
    fp.model("${KICAD10_3DMODEL_DIR}/LED_SMD.3dshapes/LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm.step", (0, 0))
    fp.write()


# SHOU HAN TYPE-C 16P 3MD 040 (LCSC C41417453), pcb/datasheets/C41417453.pdf: the recommended
# layout on sheet 2, measured from the pad row's outer edge (y 0) toward the PCB edge (7.89).
# Pad pairs that share a land (A1/B12, A4/B9, B4/A9, B1/A12) get two pads at one spot.
USBC_PADS = [(("A1", "B12"), -3.20, 0.60), (("A4", "B9"), -2.40, 0.60), (("B8",), -1.75, 0.30),
             (("A5",), -1.25, 0.30), (("B7",), -0.75, 0.30), (("A6",), -0.25, 0.30),
             (("A7",), 0.25, 0.30), (("B6",), 0.75, 0.30), (("A8",), 1.25, 0.30),
             (("B5",), 1.75, 0.30), (("B4", "A9"), 2.40, 0.60), (("B1", "A12"), 3.20, 0.60)]
USBC_EDGE = 1.64 + 6.25        # pad row edge to PCB edge: locating holes at 1.64, edge 6.25 past them


def usb_c():
    name = "USB_C_Receptacle_ShouHan_TYPE-C-16P-3MD-040"
    fp = Fp(name, "USB 2.0 Type-C receptacle, 16 pins, SMD right angle on the board surface, 3.26 mm tall, "
                  "shell legs in four plated slots; SHOU HAN TYPE-C 16P 3MD 040, LCSC C41417453.  Origin on the "
                  "PCB edge line, opening toward +y, front flush with the edge",
            "USB C Type-C receptacle USB2.0 16P ShouHan C41417453", "through_hole")
    y = lambda v: v - USBC_EDGE                    # datasheet y (from the pad row) to footprint y
    fp.prop("Reference", "REF**", (0, y(-1.2)), "F.SilkS")
    fp.prop("Value", name, (0, 1.5), "F.Fab", 0.6)
    fp.prop("Datasheet", "pcb/datasheets/C41417453.pdf", (0, 0), "F.Fab", hide=True)
    fp.prop("Description", "", (0, 0), "F.Fab", hide=True)
    for nums, x, w in USBC_PADS:
        for n in nums:
            fp.smd(n, x, y(1.15 / 2), w, 1.15)
    for sx in (-2.89, 2.89):                       # locating posts, 5.78 apart
        fp.npth(sx, y(1.64), 0.65)
    for sx in (-4.32, 4.32):                       # shell legs, 8.64 apart
        fp.slot("SH", sx, y(1.11), 0.90, 2.00, 0.60, 1.70)    # rear pair, 4.18 behind the front pair
        fp.slot("SH", sx, y(1.64 + 3.65), 0.90, 1.70, 0.60, 1.40)
    fp.rect(-4.47, -7.30, 4.47, 0, "F.Fab", 0.1)   # body 8.94 x 7.30, front on the edge
    fp.line(-5.5, 0, 5.5, 0, "Dwgs.User", 0.1)
    fp.text("PCB edge", 0, 0.8, "Dwgs.User", 0.5)
    fp.line(-4.95, y(2.3), -4.95, y(4.2), "F.SilkS", 0.12)
    fp.line(4.95, y(2.3), 4.95, y(4.2), "F.SilkS", 0.12)
    fp.line(-4.95, y(6.3), -4.95, -0.3, "F.SilkS", 0.12)
    fp.line(4.95, y(6.3), 4.95, -0.3, "F.SilkS", 0.12)
    fp.rect(-5.2, y(-0.5), 5.2, 0.0, "F.CrtYd", 0.05)
    fp.text("${REFERENCE}", 0, -3.5, "F.Fab", 0.8)
    fp.write()


def main():
    os.makedirs(OUT, exist_ok=True)
    switch("SW_MX_1u", 1, descr="1u")
    switch("SW_MX_1.5u", 1.5, descr="1.5u")
    switch("SW_MX_2u", 2, stabs=(STAB_2U,), descr="2u, Cherry PCB stabilizer holes (screw-in)")
    switch("SW_MX_Spacebar", 9, stabs=SPACEBAR_STABS, reversed_stabs=True,
           descr="spacebar, stabilizer sets at " + ", ".join(f"{num(2 * h)} mm" for h in SPACEBAR_STABS))
    led()
    usb_c()
    with open(os.path.join(PCB, "fp-lib-table"), "w", encoding="utf-8") as f:
        f.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.pretty")'
                f'(options "")(descr "rev 3 project footprints"))\n)\n')
    print("wrote", OUT)


if __name__ == "__main__":
    main()
