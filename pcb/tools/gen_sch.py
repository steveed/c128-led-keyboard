#!/usr/bin/env python3
"""Generate the rev 3 KiCad schematic (root + four sheets) from a description in code.

Run from anywhere:  python3 pcb/tools/gen_sch.py
Writes pcb/C128-keyboard-rev3.kicad_sch and the sheet files next to it.

The switch matrix and LED chain are derived from layout/switches.json (the rev 2.3 board's
switches, see extract_layout.py) so the key positions and the C128 matrix assignments stay
identical.  Everything else (MCU, power,
crosspoint, host connector) is described in build_* functions below.  Net connectivity is
made with global labels and power symbols placed on short stubs off every pin, which
KiCad treats exactly like wires; the result passes ERC and is meant as the starting point
for hand-tidying in eeschema, not as a finished drawing.

Regenerating overwrites the sheet files, so once hand edits start, stop running this.
"""
import json
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kisym as K  # noqa: E402
import layout  # noqa: E402

OUT_DIR = os.path.normpath(os.path.join(HERE, ".."))
PROJECT = "C128-keyboard-rev3"
# File-format versions written by KiCad 10.0 (eeschema and the symbol editor).  Emitting
# the current version keeps eeschema from asking to resave every sheet on open; kicad-cli
# `sch upgrade --force` of these files changes whitespace only.  Bump when KiCad does.
VERSION = "20260306"
GENERATOR_VERSION = "10.0"
LIB_VERSION = "20251024"

R_FP = "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder"
C_FP = "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"
C_FP_1206 = "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder"
# switch and LED footprints come from the project library, pcb/c128rev3.pretty (tools/gen_fp.py)
SW_FP = "c128rev3:SW_MX_1u"
SW_FP_BY_REF = {   # the wider keys, as on the rev 2.3 board; keypad Enter is a 2u placed at -90
    "SW79": "c128rev3:SW_MX_1.5u", "SW90": "c128rev3:SW_MX_1.5u",
    "SW12": "c128rev3:SW_MX_2u", "SW22": "c128rev3:SW_MX_2u", "SW54": "c128rev3:SW_MX_2u",
    "SW52": "c128rev3:SW_MX_Spacebar",
}
LED_FP = "c128rev3:LED_SK6812MINI_MX"   # top-mount, sits in the switch's SMD LED pocket


# Every UUID is derived from what the object *is*, not from when it was generated, so a
# regeneration leaves unchanged objects with unchanged UUIDs.  That keeps git diffs to the
# real change and, once a board exists, keeps every footprint linked to its symbol (KiCad
# ties footprints to symbol UUIDs).  Symbols and pins key on the sheet file and reference
# designator; wires, labels and text key on type, text and position.
UUID_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "rev3.the-c128-keyboard-project")


def uid(key):
    return str(uuid.uuid5(UUID_NS, key))


# JLCPCB/LCSC part numbers for the parts that are stock "basic" or common "extended" items.
# Verify each against the LCSC site before ordering; blanks are to be filled in at layout time.
LCSC = {
    ("Device:R", "10k"): "C25804", ("Device:R", "1k"): "C21190", ("Device:R", "100k"): "C25803",
    ("Device:R", "5k1"): "C23186", ("Device:R", "20k"): "C4184",
    ("Device:C", "100n"): "C14663", ("Device:C", "10u"): "C19702",
    ("Diode:SS34", None): "C8678", ("Diode:1N4148W", None): "C81598", ("Transistor_FET:2N7002", None): "C8545",
    ("Power_Protection:USBLC6-2SC6", None): "C7519",
}


def mm(v):
    """Round to the 1.27 mm grid so pins and labels coincide exactly."""
    return round(round(v / 1.27) * 1.27, 4)


# --- CH446Q custom symbol ---------------------------------------------------------------

# WCH CH446Q, 8x16 analog switch array, LQFP-44 (datasheet CH446DS1, v1D).  Functionally the
# MT8816 at a fraction of the price: VDD 4..13.2 V, RON 120/185 ohm at 5 V, VIH 2.0 V at a 5 V
# supply (so 3.3 V logic drives it directly), linear address map ADDR = AY*16 + AX, and a
# serial address mode (P/S low) that needs only DAT, CS/CK, STB and RST.
CH446Q_LQFP = {
    "VDD": 38, "GND": 12, "VEE": 16, "RST": 41, "P/S": 10, "DAT": 36, "STB": 14, "CS/CK": 34,
    "AX0": 43, "AX1": 18, "AX2": 19, "AX3": 42, "AY0": 20, "AY1": 21, "AY2": 40,
    "X0": 31, "X1": 30, "X2": 29, "X3": 28, "X4": 27, "X5": 26, "X6": 3, "X7": 4,
    "X8": 5, "X9": 6, "X10": 7, "X11": 8, "X12": 25, "X13": 24, "X14": 1, "X15": 2,
    "Y0": 33, "Y1": 35, "Y2": 37, "Y3": 39, "Y4": 17, "Y5": 15, "Y6": 13, "Y7": 11,
    # NC: 9, 22, 23, 32, 44 (leave unconnected; not drawn)
}


def ch446q_symbol():
    """Build a flattened lib symbol for the CH446Q (LQFP-44 numbering)."""
    S = K.Sym
    body_w = 15.24  # half width
    top, bot = 22.86, -22.86
    pins = []

    def pin(name, num, x, y, ang, typ):
        pins.append([S("pin"), S(typ), S("line"), [S("at"), x, y, ang], [S("length"), 5.08],
                     [S("name"), name, [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]],
                     [S("number"), str(num), [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]]])

    for i in range(16):
        pin(f"X{i}", CH446Q_LQFP[f"X{i}"], -body_w - 5.08, 20.32 - 2.54 * i, 0, "bidirectional")
    for i in range(8):
        pin(f"Y{i}", CH446Q_LQFP[f"Y{i}"], body_w + 5.08, 20.32 - 2.54 * i, 180, "bidirectional")
    ctrl = ["AX0", "AX1", "AX2", "AX3", "AY0", "AY1", "AY2", "P/S", "DAT", "CS/CK", "STB", "RST"]
    for i, n in enumerate(ctrl):
        pin(n, CH446Q_LQFP[n], -13.97 + 2.54 * i, bot - 5.08, 90, "input")
    pin("VEE", CH446Q_LQFP["VEE"], -5.08, top + 5.08, 270, "power_in")
    pin("VDD", CH446Q_LQFP["VDD"], 0, top + 5.08, 270, "power_in")
    pin("GND", CH446Q_LQFP["GND"], 5.08, top + 5.08, 270, "power_in")

    def prop(name, val, hide=True, at=(0, 0)):
        eff = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
        if hide:
            eff.append([S("hide"), S("yes")])
        return [S("property"), name, val, [S("at"), at[0], at[1], 0], eff]

    sym = [S("symbol"), "c128rev3:CH446Q",
           [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
           prop("Reference", "U", False, (-body_w, top + 2.54)),
           prop("Value", "CH446Q", False, (body_w - 7.62, top + 2.54)),
           prop("Footprint", "Package_QFP:LQFP-44_10x10mm_P0.8mm"),
           prop("Datasheet", "https://www.wch-ic.com/downloads/CH446DS1_PDF.html"),
           prop("Description", "WCH 8x16 analog crosspoint switch array, LQFP-44"),
           [S("symbol"), "CH446Q_0_1",
            [S("rectangle"), [S("start"), -body_w, top], [S("end"), body_w, bot],
             [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]],
             [S("fill"), [S("type"), S("background")]]]],
           [S("symbol"), "CH446Q_1_1"] + pins,
           [S("embedded_fonts"), S("no")]]
    return sym


# --- schematic sheet builder ------------------------------------------------------------

class Sheet:
    def __init__(self, filename, title, root_uuid=None, page=1, paper="A3"):
        self.paper = paper
        self.filename = filename
        self.title = title
        self.uuid = uid(f"sheet:{filename}")
        self.root_uuid = root_uuid or self.uuid
        self.page = page
        self.items = []          # serialized s-expr nodes
        self._uid_seen = {}      # key -> count, keeps identical geometry keys unique
        self.lib_symbols = {}    # lib_id -> flattened symbol node
        self.pins_cache = {}
        self.refs = {}

    def uid(self, kind, *parts):
        """Deterministic UUID for an item of this sheet; repeats of one key get a suffix."""
        key = f"{self.filename}:{kind}:" + ":".join(str(p) for p in parts)
        n = self._uid_seen.get(key, 0)
        self._uid_seen[key] = n + 1
        return uid(key if n == 0 else f"{key}#{n}")

    # -- symbols
    def libsym(self, lib_id):
        if lib_id not in self.lib_symbols:
            self.lib_symbols[lib_id] = ch446q_symbol() if lib_id == "c128rev3:CH446Q" else K.get_symbol(lib_id)
            self.pins_cache[lib_id] = K.pins(self.lib_symbols[lib_id])
        return self.lib_symbols[lib_id]

    def symbol(self, lib_id, ref, value, at, rot=0, mirror=None, unit=1, footprint=None,
               fields=None, dnp=False, hide_value=False):
        self.libsym(lib_id)
        S = K.Sym
        x, y = mm(at[0]), mm(at[1])
        sym = Placed(self, lib_id, ref, x, y, rot, mirror, unit)
        props = []

        tang = (360 - rot) % 360  # field text is drawn in the symbol's frame; keep it horizontal

        def prop(name, val, hide, dx=0, dy=0, justify="left"):
            eff = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("justify"), S(justify)]]
            if hide:
                eff.append([S("hide"), S("yes")])
            props.append([S("property"), name, val, [S("at"), mm(x + dx), mm(y + dy), tang], eff])

        ps = [p for p in self.pins_cache[lib_id] if p["unit"] in (0, unit) and not p["hidden"]]
        bx = self.body_extent(lib_id)
        by = max([abs(p["y"]) for p in ps] or [2.54])
        ic_style = len(ps) > 2
        if ref.startswith("#"):
            # power symbols: reference hidden, value where the library puts it
            lv = next((q for q in K.find_all(self.lib_symbols[lib_id], "property") if q[1] == "Value"), None)
            lat = K.find(lv, "at") if lv else None
            ox, oy = (float(lat[1]), float(lat[2])) if lat else (0, 2.54)
            vx, vy = sym._xf(ox, oy)
            prop("Reference", ref, True)
            prop("Value", value, hide_value, vx, vy)
        elif ic_style:
            # both fields off the top-left corner, right-justified so they never reach the top pin
            prop("Reference", ref, False, -bx - 1.27, -by - 5.08, justify="right")
            prop("Value", value, hide_value, -bx - 1.27, -by - 2.54, justify="right")
        else:
            # two-pin part: is it lying horizontally or standing vertically after rotation?
            pts = [sym._xf(p["x"], p["y"]) for p in ps[:2]]
            horizontal = len(pts) == 2 and abs(pts[0][0] - pts[1][0]) > abs(pts[0][1] - pts[1][1])
            if horizontal:
                prop("Reference", ref, False, -3.81, -2.54)
                prop("Value", value, hide_value, -3.81, 2.54)
            else:
                # beside the body: reference above center, value below, clear of C plates and SW graphics
                prop("Reference", ref, False, 2.54, -2.54)
                prop("Value", value, hide_value, 2.54, 2.54)
        prop("Footprint", footprint or self.default_footprint(lib_id), True)
        prop("Datasheet", self.default_prop(lib_id, "Datasheet") or "~", True)
        prop("Description", self.default_prop(lib_id, "Description") or "", True)
        fields = dict(fields or {})
        fields.setdefault("LCSC", LCSC.get((lib_id, value), LCSC.get((lib_id, None), "")))
        for k, v in fields.items():
            prop(k, v, True)
        node = [S("symbol"), [S("lib_id"), lib_id], [S("at"), x, y, rot]]
        if mirror:
            node.append([S("mirror"), S(mirror)])
        node += [[S("unit"), unit], [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")],
                 [S("on_board"), S("yes")], [S("dnp"), S("yes" if dnp else "no")],
                 [S("uuid"), self.uid("sym", ref, unit)]] + props
        for p in self.pins_cache[lib_id]:
            if p["unit"] in (0, unit):
                node.append([S("pin"), p["number"], [S("uuid"), self.uid("pin", ref, unit, p["number"])]])
        node.append([S("instances"), [S("project"), PROJECT,
                     [S("path"), self.path(), [S("reference"), ref], [S("unit"), unit]]]])
        self.items.append(node)
        self.refs[ref] = sym
        return sym

    def path(self):
        return "/" + self.root_uuid if self.uuid == self.root_uuid else f"/{self.root_uuid}/{self.uuid}"

    def default_prop(self, lib_id, name):
        for p in K.find_all(self.lib_symbols[lib_id], "property"):
            if p[1] == name:
                return p[2]
        return None

    def default_footprint(self, lib_id):
        return self.default_prop(lib_id, "Footprint") or ""

    def body_extent(self, lib_id):
        """Right-hand x extent of the symbol (pins included), library units."""
        xs = [abs(p["x"]) for p in self.pins_cache[lib_id]] or [2.54]
        return max(xs)

    # -- graphics / connectivity
    def wire(self, a, b):
        S = K.Sym
        self.items.append([S("wire"), [S("pts"), [S("xy"), mm(a[0]), mm(a[1])], [S("xy"), mm(b[0]), mm(b[1])]],
                           [S("stroke"), [S("width"), 0], [S("type"), S("default")]],
                           [S("uuid"), self.uid("wire", mm(a[0]), mm(a[1]), mm(b[0]), mm(b[1]))]])

    def junction(self, at):
        S = K.Sym
        self.items.append([S("junction"), [S("at"), mm(at[0]), mm(at[1])], [S("diameter"), 0], [S("color"), 0, 0, 0, 0],
                           [S("uuid"), self.uid("junction", mm(at[0]), mm(at[1]))]])

    def path(self, *pts):
        """Wires through consecutive points."""
        for a, b in zip(pts, pts[1:]):
            if (mm(a[0]), mm(a[1])) != (mm(b[0]), mm(b[1])):
                self.wire(a, b)

    def label(self, text, at, rot=0):
        """Local (sheet-scoped) net label."""
        S = K.Sym
        self.items.append([S("label"), text, [S("at"), mm(at[0]), mm(at[1]), rot],
                           [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("justify"), S("left"), S("bottom")]],
                           [S("uuid"), self.uid("label", text, mm(at[0]), mm(at[1]))]])

    def glabel(self, text, at, direction, shape="passive"):
        """Global label at `at`; `direction` is where the text extends: R, L, U, D."""
        S = K.Sym
        rot = {"R": 0, "L": 180, "U": 90, "D": 270}[direction]
        just = "left" if direction in ("R", "U") else "right"
        self.items.append([S("global_label"), text, [S("shape"), S(shape)], [S("at"), mm(at[0]), mm(at[1]), rot],
                           [S("fields_autoplaced"), S("yes")],
                           [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("justify"), S(just)]],
                           [S("uuid"), self.uid("glabel", text, mm(at[0]), mm(at[1]))],
                           [S("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [S("at"), mm(at[0]), mm(at[1]), 0],
                            [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("hide"), S("yes")]]]])

    def power(self, net, at, rot=0):
        lib = {"GND": "power:GND", "+5V": "power:+5V", "+3V3": "power:+3V3", "PWR_FLAG": "power:PWR_FLAG"}
        lib_id = lib.get(net, "power:+5V")
        ref = "#PWR" if net != "PWR_FLAG" else "#FLG"
        n = sum(1 for r in self.refs if r.startswith(ref)) + 1
        self.symbol(lib_id, f"{ref}{n:03d}", net, at, rot=rot, hide_value=(net == "PWR_FLAG"))

    def no_connect(self, at):
        S = K.Sym
        self.items.append([S("no_connect"), [S("at"), mm(at[0]), mm(at[1])],
                           [S("uuid"), self.uid("nc", mm(at[0]), mm(at[1]))]])

    def text(self, s, at, size=1.27):
        S = K.Sym
        self.items.append([S("text"), s, [S("exclude_from_sim"), S("no")], [S("at"), mm(at[0]), mm(at[1]), 0],
                           [S("effects"), [S("font"), [S("size"), size, size]], [S("justify"), S("left"), S("top")]],
                           [S("uuid"), self.uid("text", mm(at[0]), mm(at[1]))]])

    def sheet_ref(self, sub, at, size):
        S = K.Sym
        x, y = mm(at[0]), mm(at[1])
        self.items.append([S("sheet"), [S("at"), x, y], [S("size"), size[0], size[1]],
                           [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
                           [S("dnp"), S("no")], [S("fields_autoplaced"), S("yes")],
                           [S("stroke"), [S("width"), 0.1524], [S("type"), S("solid")]],
                           [S("fill"), [S("color"), 0, 0, 0, 0.0]], [S("uuid"), sub.uuid],
                           [S("property"), "Sheetname", sub.title, [S("at"), x, y - 0.7, 0],
                            [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("justify"), S("left"), S("bottom")]]],
                           [S("property"), "Sheetfile", sub.filename, [S("at"), x, y + size[1] + 0.6, 0],
                            [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], [S("justify"), S("left"), S("top")]]],
                           [S("instances"), [S("project"), PROJECT, [S("path"), "/" + self.root_uuid, [S("page"), str(sub.page)]]]]])

    def connect(self, sym, pin, net, stub=5.08, kind=None):
        """Stub wire out of `pin` and terminate it on `net`.

        kind: 'power' forces a power symbol (GND/+5V/+3V3 style), 'label' forces a global
        label, None picks a power symbol for GND/+3V3/+5V* when the stub points the natural
        way (down for GND, up for supplies) and a label otherwise.  net None = no-connect.
        """
        p, d = sym.pin_end(pin)
        if net is None:
            self.no_connect(p)
            return
        e = (p[0] + d[0] * stub, p[1] + d[1] * stub)
        self.wire(p, e)
        is_pwr = net == "GND" or net.startswith("+")
        if kind == "power" or (kind is None and is_pwr and ((net == "GND" and d == (0, 1)) or (net != "GND" and d == (0, -1)))):
            self.power_symbol(net, e, d)
        else:
            direction = {(-1, 0): "L", (1, 0): "R", (0, -1): "U", (0, 1): "D"}[d]
            self.glabel(net, e, direction)

    def power_symbol(self, net, at, d):
        # GND graphic hangs below its pin, supplies stand above; rotate for sideways stubs
        if net == "GND":
            rot = {(0, 1): 0, (0, -1): 180, (-1, 0): 90, (1, 0): 270}[d]
            self.power("GND", at, rot)
        else:
            rot = {(0, -1): 0, (0, 1): 180, (-1, 0): 270, (1, 0): 90}[d]
            lib = "+3V3" if net == "+3V3" else "+5V"
            self.symbol({"+3V3": "power:+3V3", "+5V": "power:+5V"}[lib], self._pwr_ref(), net, at, rot=rot)

    def _pwr_ref(self):
        n = sum(1 for r in self.refs if r.startswith("#PWR")) + 1
        return f"#PWR{n:03d}"

    # -- output
    def emit(self, is_root=False):
        S = K.Sym
        doc = [S("kicad_sch"), [S("version"), S(VERSION)], [S("generator"), "eeschema"],
               [S("generator_version"), GENERATOR_VERSION], [S("uuid"), self.uuid], [S("paper"), self.paper],
               [S("title_block"), [S("title"), self.title], [S("rev"), "3.0-draft"], [S("company"), "c128-led-keyboard"]],
               [S("lib_symbols")] + [self.lib_symbols[k] for k in sorted(self.lib_symbols)]]
        doc += self.items
        if is_root:
            doc.append([S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]])
        doc.append([S("embedded_fonts"), S("no")])
        with open(os.path.join(OUT_DIR, self.filename), "w", encoding="utf-8") as f:
            f.write(K.dump(doc) + "\n")


class Placed:
    def __init__(self, sheet, lib_id, ref, x, y, rot, mirror, unit):
        self.sheet, self.lib_id, self.ref, self.x, self.y, self.rot, self.mirror, self.unit = sheet, lib_id, ref, x, y, rot, mirror, unit

    def _xf(self, px, py):
        x, y = px, -py
        if self.mirror == "x":
            y = -y
        if self.mirror == "y":
            x = -x
        r = self.rot % 360
        if r == 90:
            x, y = y, -x
        elif r == 180:
            x, y = -x, -y
        elif r == 270:
            x, y = -y, x
        return x, y

    def pin(self, number):
        for p in self.sheet.pins_cache[self.lib_id]:
            if p["number"] == str(number) and p["unit"] in (0, self.unit):
                return p
        raise KeyError(f"{self.ref}: no pin {number}")

    def pin_end(self, number):
        """Connection point of a pin in sheet coords and the outward unit vector."""
        p = self.pin(number)
        x, y = self._xf(p["x"], p["y"])
        a = (p["angle"] + 180) % 360  # outward direction in library frame
        dx, dy = round(__import__("math").cos(__import__("math").radians(a))), round(__import__("math").sin(__import__("math").radians(a)))
        ox, oy = self._xf(dx, dy)
        return (mm(self.x + x), mm(self.y + y)), (int(round(ox)), int(round(oy)))

    def pins_named(self):
        return {p["name"]: p["number"] for p in self.sheet.pins_cache[self.lib_id] if p["unit"] in (0, self.unit)}


# --- GPIO plan ---------------------------------------------------------------------------

# ESP32-S3-MINI-1U-N8 (2.4 mm tall, U.FL antenna: the whole PCB sits under the plate, so an
# on-board antenna would be under metal).  Strapping pins (IO0, IO3, IO45, IO46) are left
# free.  The scanned matrix is 6 rows x 20 columns: 15 columns through the 74HC154, five
# straight from GPIO.
#
# The pins are chosen for the layout, the way the CH446Q's are.  The module sits on the back
# turned 180 degrees, so its GND row faces the rear edge and the other three sides face the
# board.  Everything bound east (the five GPIO columns at the keypad, the lock-line gates, the
# crosspoint, the decoder address) is on the east side, top to bottom, then along the south
# side from its east end: that order runs out into the channel under the top row without a
# crossing.  The matrix rows leave the south side west of USB and drop straight into the main
# block; the LED data and ROW0 (top row, westward) leave the west side.  USB, UART0, EN and
# IO0 keep their fixed pins.  The bench rig is wired to its own, older plan (firmware pins.h).
# Spare: IO21, IO37-42.
GPIO = {
    # east side, top to bottom
    "IO1": "P_COL15", "IO2": "P_COL16", "IO4": "P_COL17", "IO5": "P_COL18", "IO6": "P_COL19",
    "IO7": "MCU_4080_GATE", "IO8": "MCU_CAPLK_GATE", "IO9": "MCU_RESTORE_GATE",
    "IO10": "MCU_XP_STB", "IO11": "MCU_XP_CK",
    # south side, east to west
    "IO12": "MCU_XP_DAT", "IO13": "MCU_XP_RST", "IO14": "MCU_RESTORE_SENSE",
    "IO15": "MCU_COLSEL3", "IO16": "MCU_COLSEL2", "IO17": "MCU_COLSEL1", "IO18": "MCU_COLSEL0",
    "USB_D-": "USB_DN", "USB_D+": "USB_DP",
    "IO21": None,
    "IO26": "P_ROW1", "IO47": "P_ROW2", "IO33": "P_ROW3", "IO34": "P_ROW4", "IO48": "P_ROW5",
    # west side, bottom to top
    "IO35": "MCU_LED_DATA", "IO36": "P_ROW0",
    "IO37": None, "IO38": None, "IO39": None, "IO40": None, "IO41": None, "IO42": None,
    "TXD0": "MCU_TXD0", "RXD0": "MCU_RXD0", "EN": "MCU_EN",
    # fixed
    "IO0": "MCU_BOOT",
    "IO3": None, "IO45": None, "IO46": None,
}

# host connector (2x13 in D-sub IDC order): header pin -> net
HOST_PINS = {
    1: "GND", 2: "H_COL6", 3: None, 4: "H_COL5", 5: "H_RESTORE", 6: "H_COL4", 7: "+5V_KB", 8: "H_COL3",
    9: "H_ROW3", 10: "H_COL2", 11: "H_ROW6", 12: "H_COL1", 13: "H_ROW5", 14: "H_COL7", 15: "H_ROW4",
    16: "H_COL8", 17: "H_ROW7", 18: "H_COL9", 19: "H_ROW2", 20: "H_COL10", 21: "H_ROW1", 22: "H_4080",
    23: "H_ROW0", 24: "H_CAPLK", 25: "H_COL0", 26: None,
}


# --- sheets -----------------------------------------------------------------------------

def build_mcu(sh):
    sh.text("MCU, USB-C and power.  +5V_KB is the raw keyboard rail from the host connector; +5V_SYS is the\n"
            "OR of the fused keyboard rail and USB VBUS; +3V3 feeds the ESP32, the 74HC154 and the physical matrix.",
            (15, 15), 1.5)
    u1 = sh.symbol("RF_Module:ESP32-S3-MINI-1U", "U1", "ESP32-S3-MINI-1U-N8", (135, 125),
                   footprint="RF_Module:ESP32-S2-MINI-1U")   # KiCad's S3-MINI-1U symbol uses this; same land pattern
    for p in sh.pins_cache[u1.lib_id]:
        name, num = p["name"], p["number"]
        if p["hidden"]:
            continue
        if name == "3V3":
            sh.connect(u1, num, "+3V3")
        elif name == "GND":
            sh.connect(u1, num, "GND")
        elif name in GPIO:
            sh.connect(u1, num, GPIO[name], stub=7.62)
        else:
            raise SystemExit(f"unmapped ESP32 pin {num} {name}")
    # EN / BOOT: pull-up, (cap,) button, one node with one label
    def pull_button(x, rname, cname, swname, swval, net):
        r = sh.symbol("Device:R", rname, "10k", (x, 70), footprint=R_FP)
        sh.connect(r, 1, "+3V3")
        node = (x, 80)
        sh.path(r.pin_end(2)[0], node)
        sw = sh.symbol("Switch:SW_Push", swname, swval, (x, 92), rot=90,
                       footprint="Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92")
        sh.path(sw.pin_end(2)[0], node)   # rot 90 puts pin 2 on top
        sh.connect(sw, 1, "GND")
        if cname:
            c = sh.symbol("Device:C", cname, "100n", (x + 10, 86), footprint=C_FP)
            top = c.pin_end(1)[0]
            sh.path(top, (top[0], node[1]), node)
            sh.connect(c, 2, "GND")
        sh.junction(node)
        sh.wire(node, (x - 5.08, node[1])); sh.glabel(net, (x - 5.08, node[1]), "L")
    pull_button(45, "R1", "C1", "SW93", "RESET", "MCU_EN")
    pull_button(75, "R2", None, "SW94", "BOOT", "MCU_BOOT")
    # 3V3 decoupling
    for i, x in enumerate((85, 95)):
        c = sh.symbol("Device:C", f"C{2 + i}", "100n" if i == 0 else "10u", (x, 60), footprint=C_FP)
        sh.connect(c, 1, "+3V3"); sh.connect(c, 2, "GND")
    # debug UART header
    j4 = sh.symbol("Connector_Generic:Conn_01x03", "J4", "UART0", (190, 60),
                   footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
    sh.connect(j4, 1, "MCU_TXD0"); sh.connect(j4, 2, "MCU_RXD0"); sh.connect(j4, 3, "GND", kind="label")

    # USB-C
    j1 = sh.symbol("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C", (260, 120),
                   footprint="c128rev3:USB_C_Receptacle_ShouHan_TYPE-C-16P-3MD-040",
                   fields={"LCSC": "C41417453"})
    sh.connect(j1, "A4", "VBUS"); sh.connect(j1, "A5", "CC1"); sh.connect(j1, "B5", "CC2")
    sh.connect(j1, "A6", "USB_DP_C"); sh.connect(j1, "B6", "USB_DP_C")
    sh.connect(j1, "A7", "USB_DN_C"); sh.connect(j1, "B7", "USB_DN_C")
    sh.connect(j1, "A8", None); sh.connect(j1, "B8", None)
    sh.connect(j1, "A1", "GND"); sh.connect(j1, "SH", "GND", kind="label")
    r3 = sh.symbol("Device:R", "R3", "5k1", (300, 100), footprint=R_FP)
    sh.connect(r3, 1, "CC1", stub=2.54); sh.connect(r3, 2, "GND")
    r4 = sh.symbol("Device:R", "R4", "5k1", (315, 100), footprint=R_FP)
    sh.connect(r4, 1, "CC2", stub=2.54); sh.connect(r4, 2, "GND")
    u7 = sh.symbol("Power_Protection:USBLC6-2SC6", "U7", "USBLC6-2SC6", (300, 140), footprint="Package_TO_SOT_SMD:SOT-23-6")
    sh.connect(u7, 1, "USB_DP_C"); sh.connect(u7, 3, "USB_DN_C"); sh.connect(u7, 6, "USB_DP"); sh.connect(u7, 4, "USB_DN")
    sh.connect(u7, 5, "VBUS"); sh.connect(u7, 2, "GND")

    # power path: +5V_KB -> F1 -> D1 -> +5V_SYS <- D2 <- VBUS ; LDO -> +3V3
    sh.text("Power path", (200, 165), 1.5)
    f1 = sh.symbol("Device:Polyfuse", "F1", "1.1A", (210, 185), footprint="Fuse:Fuse_1812_4532Metric")
    sh.connect(f1, 1, "+5V_KB"); sh.connect(f1, 2, "+5V_KB_F", stub=2.54)
    d1 = sh.symbol("Diode:SS34", "D1", "SS34", (240, 195), footprint="Diode_SMD:D_SMA")
    sh.connect(d1, 2, "+5V_KB_F"); sh.connect(d1, 1, "+5V_SYS")
    d2 = sh.symbol("Diode:SS34", "D2", "SS34", (240, 210), footprint="Diode_SMD:D_SMA")
    sh.connect(d2, 2, "VBUS"); sh.connect(d2, 1, "+5V_SYS")
    c4 = sh.symbol("Device:C_Polarized", "C5", "220u", (265, 210), footprint="Capacitor_SMD:CP_Elec_6.3x7.7")
    sh.connect(c4, 1, "+5V_SYS"); sh.connect(c4, 2, "GND")
    u2 = sh.symbol("Regulator_Linear:AP7361C-33E", "U2", "AP7361C-33E", (315, 190), footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
                   fields={"LCSC": "C500795"})
    n2 = u2.pins_named()
    sh.connect(u2, n2["VI"], "+5V_SYS"); sh.connect(u2, n2["VO"], "+3V3"); sh.connect(u2, n2["GND"], "GND")
    c6 = sh.symbol("Device:C", "C6", "10u", (285, 210), footprint=C_FP_1206, fields={"LCSC": ""})
    sh.connect(c6, 1, "+5V_SYS"); sh.connect(c6, 2, "GND")
    c7 = sh.symbol("Device:C", "C7", "10u", (345, 210), footprint=C_FP_1206, fields={"LCSC": ""})
    sh.connect(c7, 1, "+3V3"); sh.connect(c7, 2, "GND")
    # power flags
    for i, (net, x) in enumerate((("+5V_KB", 150), ("+5V_SYS", 180), ("GND", 210), ("VBUS", 240))):
        sh.power("PWR_FLAG", (x, 250))
        sh.glabel(net, (x, 250), "D")
    sh.text("GPIO map: rows IO4-7,15,16; column select IO8-11 (columns 0-14); columns 15-19 IO17,18,14,21,35; CH446Q serial: CK IO12,\n"
            "DAT IO38, STB IO39, RST IO40; LED IO41; 40/80 gate IO42; CAPS gate IO2; RESTORE sense IO1, gate IO13.  Spare: IO36,37.  IO0/IO3/IO45/IO46 strapping.",
            (15, 280), 1.27)


# Which crosspoint X pin carries each host column, and which Y pin each host row.  The C128
# sees the same matrix whatever the order (the firmware addresses the switch by pin number
# through this table), so the order is chosen for the board: host connector J2's pins, which
# follow the C128's own connector, then reach their CH446Q pins without crossing.  Columns
# run on the back into the package's sides, nested so the line nearest the chip takes the
# pin nearest J2: COL0-2 and COL7-10 the left side (seven lanes fit there, beside R5-R7),
# COL3-6 the top of the right side (R10/R11 and U4 leave room for four).  Rows run on the top
# straight down from J2 and drop through vias inside the ring of pins, so their order is
# J2's, left to right, against the Y pins inside the ring, left to right (route_host.py).
XP_X_OF_COL = {0: 15, 10: 6, 9: 7, 8: 8, 7: 9, 1: 10, 2: 11, 3: 13, 4: 12, 5: 5, 6: 4}
XP_Y_OF_ROW = {0: 7, 1: 6, 2: 5, 7: 4, 4: 3, 5: 2, 6: 1, 3: 0}
assert sorted(XP_X_OF_COL) == list(range(11)) and len(set(XP_X_OF_COL.values())) == 11
assert sorted(XP_Y_OF_ROW) == list(range(8)) and sorted(XP_Y_OF_ROW.values()) == list(range(8))


def build_crosspoint(sh):
    sh.text("Host side: CH446Q crosspoint mirrors the physical matrix onto the C128 ROW/COL lines.  X = host columns, Y = host rows,\n"
            "in the order that routes cleanly from J2 (XP_X_OF_COL / XP_Y_OF_ROW in gen_sch.py); the firmware addresses through the same table.\n"
            "Serial address mode (P/S low): DAT, CS/CK, STB, RST straight from the ESP32 (VIH is 2.0 V at a 5 V supply).\n"
            "Lock lines are open-drain FETs; 40/80 asserts at power-on when JP1 is closed, before the MCU boots.\n"
            "RESTORE is hard-wired to the host; D3 lets the MCU see it, Q3 lets the MCU press it.", (15, 15), 1.5)
    u3 = sh.symbol("c128rev3:CH446Q", "U3", "CH446Q", (110, 110))
    names = u3.pins_named()
    col_of_x = {x: c for c, x in XP_X_OF_COL.items()}
    row_of_y = {y: r for r, y in XP_Y_OF_ROW.items()}
    for i in range(16):
        sh.connect(u3, names[f"X{i}"], f"H_COL{col_of_x[i]}" if i in col_of_x else None, stub=7.62)
    for i in range(8):
        sh.connect(u3, names[f"Y{i}"], f"H_ROW{row_of_y[i]}", stub=7.62)
    for n in ("AX0", "AX1", "AX2", "AX3", "AY0", "AY1", "AY2", "P/S"):
        sh.connect(u3, names[n], "GND", stub=7.62, kind="label")   # serial mode: unused address pins to GND
    for n, net in (("DAT", "MCU_XP_DAT"), ("CS/CK", "MCU_XP_CK"), ("STB", "MCU_XP_STB"), ("RST", "MCU_XP_RST")):
        sh.connect(u3, names[n], net, stub=7.62)
    sh.connect(u3, names["VDD"], "+5V_KB", stub=2.54)
    sh.connect(u3, names["VEE"], "GND", stub=10.16, kind="label"); sh.connect(u3, names["GND"], "GND", stub=10.16, kind="label")
    c8 = sh.symbol("Device:C", "C8", "100n", (150, 70), footprint=C_FP)
    sh.connect(c8, 1, "+5V_KB"); sh.connect(c8, 2, "GND")
    r10 = sh.symbol("Device:R", "R10", "10k", (190, 90), footprint=R_FP)   # RST high until the MCU drives it
    sh.connect(r10, 1, "+3V3"); sh.connect(r10, 2, "MCU_XP_RST", stub=2.54)
    r11 = sh.symbol("Device:R", "R11", "10k", (215, 90), footprint=R_FP)   # STB idles low
    sh.connect(r11, 1, "MCU_XP_STB", stub=2.54); sh.connect(r11, 2, "GND")

    # single-gate 3.3 -> 5 V buffer for the LED data line (the only 5 V logic input left)
    u4 = sh.symbol("74xGxx:74AHCT1G125", "U4", "74AHCT1G125", (250, 130), footprint="Package_TO_SOT_SMD:SOT-23-5")
    sh.connect(u4, 2, "MCU_LED_DATA", stub=7.62); sh.connect(u4, 4, "LED_DATA_5V", stub=7.62)
    sh.connect(u4, 1, "GND", stub=10.16, kind="label"); sh.connect(u4, 5, "+5V_SYS", stub=2.54); sh.connect(u4, 3, "GND")
    c9 = sh.symbol("Device:C", "C9", "100n", (305, 110), footprint=C_FP)
    sh.connect(c9, 1, "+5V_SYS"); sh.connect(c9, 2, "GND")

    # lock drivers
    sh.text("Lock lines", (15, 195), 1.5)
    def lock_driver(x, qname, rd_name, host_net, gate_net, pull_up=None):
        q = sh.symbol("Transistor_FET:2N7002", qname, "2N7002", (x, 230), footprint="Package_TO_SOT_SMD:SOT-23")
        sh.connect(q, 3, host_net); sh.connect(q, 2, "GND")
        gate, _ = q.pin_end(1)
        node = (x - 22.86, gate[1])
        sh.path(gate, node)
        rd = sh.symbol("Device:R", rd_name, "100k", (node[0], node[1] + 12.7), footprint=R_FP)
        sh.path(rd.pin_end(1)[0], node); sh.connect(rd, 2, "GND")
        if pull_up:
            ru = sh.symbol("Device:R", pull_up, "10k", (node[0], node[1] - 12.7), footprint=R_FP)
            sh.path(ru.pin_end(2)[0], node)
            jp = sh.symbol("Jumper:SolderJumper_2_Open", "JP1", "80col default", (node[0], node[1] - 27.94), rot=90,
                           footprint="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm")
            sh.path(jp.pin_end(1)[0], ru.pin_end(1)[0])   # pin 1 is the lower pad after rot 90
            sh.label("JP1_B", (node[0], node[1] - 16.51), rot=90)
            sh.connect(jp, 2, "+3V3")
        sh.junction(node)
        sh.wire(node, (node[0] - 7.62, node[1])); sh.glabel(gate_net, (node[0] - 7.62, node[1]), "L")
    lock_driver(60, "Q1", "R5", "H_4080", "MCU_4080_GATE", pull_up="R6")
    lock_driver(130, "Q2", "R7", "H_CAPLK", "MCU_CAPLK_GATE")
    # RESTORE driver: lets the firmware press RESTORE (RUN/STOP+RESTORE from the network
    # keyboard, macros).  The physical RESTORE switch stays hard-wired in parallel.
    lock_driver(250, "Q3", "R12", "H_RESTORE", "MCU_RESTORE_GATE")
    # RESTORE sense: diode from the MCU pin (internal pull-up) to the host line.  Pressed, the
    # line is grounded and pulls the pin low through the diode; released, the line sits at the
    # C128's 5 V or floats (USB mode, no C128) and the diode blocks either way.  The pin never
    # sees 5 V and the board never drives the C128's line.
    d3 = sh.symbol("Diode:1N4148W", "D3", "1N4148W", (180, 228), rot=270, footprint="Diode_SMD:D_SOD-123")
    sh.connect(d3, 1, "H_RESTORE", stub=5.08)             # cathode (top) to the host line
    sh.connect(d3, 2, "MCU_RESTORE_SENSE", stub=5.08)     # anode (bottom) to the ESP32

    # host connector and external LED header
    j2 = sh.symbol("Connector_Generic:Conn_02x13_Odd_Even", "J2", "C128 keyboard (D-sub IDC order)", (330, 205),
                   footprint="Connector_IDC:IDC-Header_2x13_P2.54mm_Vertical")
    for pin, net in HOST_PINS.items():
        sh.connect(j2, pin, net, stub=7.62, kind="label" if net else None)
    sh.text("J2 pin n = ribbon conductor n.  Odd pins -> D-sub 1..13, even pins -> D-sub 14..25.\n"
            "Fit an IDC box header, or solder the ribbon straight into the pads on a flat.", (200, 268), 1.27)
    j3 = sh.symbol("Connector_Generic:Conn_01x03", "J3", "Ext LED", (330, 150),
                   footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
    sh.connect(j3, 1, "+5V_SYS"); sh.connect(j3, 2, "LED_OUT"); sh.connect(j3, 3, "GND", kind="label")


def build_matrix(sh, switches):
    sh.text("Physical matrix, scanned by the MCU at 3.3 V: 6 rows x 20 columns following the board (pcb/tools/layout.py\n"
            "physical_matrix), not the C128's assignment; the firmware maps each position to its host position.  One diode per\n"
            "key (row -> switch -> diode -> column) so any chord reads without ghosting: needed for USB keyboard mode.  RESTORE\n"
            "bypasses the MCU entirely.  Columns 0-14 straight from the 74HC154 (3.3 V; output 15 is the idle park), 15-19\n"
            "straight from GPIO.  No series resistors: a column held high reverse-biases its diodes, so two keys in one row\n"
            "cannot connect two outputs.", (15, 15), 1.5)
    u6 = sh.symbol("74xx:74LS154", "U6", "74HC154", (60, 80), footprint="Package_SO:SOIC-24W_7.5x15.4mm_P1.27mm")
    n6 = u6.pins_named()
    for i in range(4):
        sh.connect(u6, n6[f"A{i}"], f"MCU_COLSEL{i}", stub=7.62)
    sh.connect(u6, n6["E0"], "GND", kind="label"); sh.connect(u6, n6["E1"], "GND", kind="label")
    sh.connect(u6, n6["VCC"], "+3V3"); sh.connect(u6, n6["GND"], "GND")
    for i in range(16):
        sh.connect(u6, n6[f"S{i}"], f"P_COL{i}" if i <= 14 else None, stub=7.62)
    c11 = sh.symbol("Device:C", "C11", "100n", (100, 40), footprint=C_FP)
    sh.connect(c11, 1, "+3V3"); sh.connect(c11, 2, "GND")

    # switches laid out by physical position; rev 2.3 rows of y are ~19 mm apart
    # physical rows are ~19 mm apart; keypad Enter sits between two rows, so cluster with a tolerance
    centers = []
    for y in sorted(set(s["y"] for s in switches)):
        if not centers or y - centers[-1] > 12:
            centers.append(y)
    def row_of(y):
        return min(range(len(centers)), key=lambda i: abs(centers[i] - y))
    phys = layout.physical_matrix(switches)
    x0 = min(s["x"] for s in switches)
    for s in switches:
        xs = 165 + (s["x"] - x0) * 1.0
        ys = 55 + row_of(s["y"]) * 52
        sw = sh.symbol("Switch:SW_Push", s["ref"], s["val"], (xs, ys), rot=90, footprint=SW_FP_BY_REF.get(s["ref"], SW_FP),
                       fields={"Key": s["val"]})
        if s["val"] == "Restore":
            # hard-wired to the host NMI line, no diode: it must work with the firmware dead
            sh.connect(sw, 1, "H_RESTORE", stub=2.54, kind="label")
            sh.connect(sw, 2, "GND", stub=2.54, kind="label")
            continue
        pr, pc = phys[s["ref"]]
        row, col = f"P_ROW{pr}", f"P_COL{pc}"
        # row (pulled up) -> switch -> diode anode ... cathode -> column (driven low)
        sh.connect(sw, 1, row, stub=2.54, kind="label")
        top, _ = sw.pin_end(2)
        # anode pin end lands exactly on the switch's top pin end (pin-to-pin, no wire needed)
        d = sh.symbol("Diode:1N4148W", "D" + str(100 + int(s["ref"][2:])), "1N4148W", (xs, top[1] - 3.81), rot=270,
                      footprint="Diode_SMD:D_SOD-123")
        assert d.pin_end(2)[0] == top, (d.pin_end(2)[0], top)   # pin 2 = anode, bottom after rot 270
        # pins that merely touch are not connected in the netlist; a label on the point is
        sh.label(f"KEY{s['ref'][2:]}", top)
        sh.connect(d, 1, col, stub=2.54, kind="label")          # pin 1 = cathode, top


def led_chain_order(switches):
    """Lock keys first, then a snake through the rows (layout.led_chain)."""
    order, _ = layout.led_chain(switches)
    by = {s["ref"]: s for s in switches}
    return [by[r] for r in order]


def build_leds(sh, chain):
    sh.text("Per-key RGB: SK6812 MINI (3.5 x 3.5 top mount, in the switch's SMD LED pocket), one per switch, 100n each.  Chain starts at the three lock keys\n"
            "(SHIFT LOCK, CAPS LOCK, 40/80) so a minimal build with three LEDs still has indicators, then snakes through the rows.\n"
            "LED refs match switch refs (LED89 sits under SW89).  Data in from U5 (5 V), data out to J3.", (15, 15), 1.5)
    per_row = 12
    pitch_x, pitch_y = 40, 46
    prev_out = None
    for i, s in enumerate(chain):
        r, c = divmod(i, per_row)
        x = 40 + c * pitch_x
        y = 42 + r * pitch_y
        led = sh.symbol("LED:SK6812MINI", "LED" + s["ref"][2:], "SK6812MINI", (x, y), footprint=LED_FP,
                        fields={"Key": s["val"]})
        sh.connect(led, 4, "+5V_SYS", stub=2.54); sh.connect(led, 2, "GND", stub=2.54)
        cap = sh.symbol("Device:C", "C" + str(100 + int(s["ref"][2:])), "100n", (x + 17.78, y + 19.05), footprint=C_FP)
        sh.connect(cap, 1, "+5V_SYS", stub=2.54); sh.connect(cap, 2, "GND", stub=2.54)
        din, _ = led.pin_end(3)
        dout, _ = led.pin_end(1)
        if i == 0:
            sh.wire(din, (din[0] - 5.08, din[1])); sh.glabel("LED_DATA_5V", (din[0] - 5.08, din[1]), "L")
        elif c == 0:
            sh.wire(din, (din[0] - 5.08, din[1])); sh.glabel(f"LED_D{i}", (din[0] - 5.08, din[1]), "L")
        else:
            sh.wire(prev_out, din)
            sh.label(f"LED_D{i}", ((prev_out[0] + din[0]) / 2 - 3.81, din[1]))
        if i == len(chain) - 1:
            sh.wire(dout, (dout[0] + 5.08, dout[1])); sh.glabel("LED_OUT", (dout[0] + 5.08, dout[1]), "R")
        elif c == per_row - 1:
            sh.wire(dout, (dout[0] + 5.08, dout[1])); sh.glabel(f"LED_D{i + 1}", (dout[0] + 5.08, dout[1]), "R")
        prev_out = dout


def build_root(root, sheets):
    root.text("C128 mechanical keyboard, PCB rev 3 (draft).  MCU + CH446Q crosspoint, per-key RGB, saved lock state,\n"
              "rear-exit host connector in stock C128 order.  See docs/rev3-plan.md.  Generated by pcb/tools/gen_sch.py;\n"
              "hand edits are fine, just stop regenerating afterwards.", (20, 20), 1.8)
    x = 20
    for sub in sheets:
        root.sheet_ref(sub, (x, 50), (70, 30))
        x += 90
    root.text("Nets between sheets are global labels:\n"
              "  P_ROW0-5, P_COL0-19      physical matrix (3.3 V), MCU <-> matrix sheet\n"
              "  MCU_COLSEL0-3            74HC154 address\n"
              "  MCU_XP_DAT/CK/STB/RST    CH446Q serial control, driven directly at 3.3 V\n"
              "  H_ROW0-7, H_COL0-10, H_RESTORE, H_4080, H_CAPLK   host (C128) lines\n"
              "  MCU_LED_DATA -> LED_DATA_5V -> LED_D1..LED_D91 -> LED_OUT   LED chain\n"
              "  +5V_KB (raw keyboard rail), +5V_SYS (OR'd with USB), +3V3, GND", (20, 100), 1.27)


def main():
    switches = layout.load_switches()
    assert len(switches) == 92, len(switches)
    root = Sheet(f"{PROJECT}.kicad_sch", "C128 keyboard rev 3", page=1)
    mcu = Sheet("mcu.kicad_sch", "MCU and power", root.uuid, 2)
    xp = Sheet("crosspoint.kicad_sch", "Crosspoint and host", root.uuid, 3)
    mx = Sheet("matrix.kicad_sch", "Physical matrix", root.uuid, 4, paper="A2")
    leds = Sheet("leds.kicad_sch", "LEDs", root.uuid, 5, paper="A2")
    build_mcu(mcu)
    build_crosspoint(xp)
    build_matrix(mx, switches)
    build_leds(leds, led_chain_order(switches))
    build_root(root, [mcu, xp, mx, leds])
    for sh in (mcu, xp, mx, leds):
        sh.emit()
    root.emit(is_root=True)
    # bench notes want the DIP numbering
    json.dump({"ch446q_lqfp44": CH446Q_LQFP, "gpio": GPIO, "host_pins": HOST_PINS,
               "crosspoint_rev3": {"x_of_col": [XP_X_OF_COL[c] for c in range(11)],
                                   "y_of_row": [XP_Y_OF_ROW[r] for r in range(8)]}},
              open(os.path.join(OUT_DIR, "tools", "pinmaps.json"), "w"), indent=1)
    # project symbol library holding the custom CH446Q, plus the table that registers it
    S = K.Sym
    lib = [S("kicad_symbol_lib"), [S("version"), S(LIB_VERSION)], [S("generator"), "gen_sch"], [S("generator_version"), GENERATOR_VERSION]]
    m = ch446q_symbol(); m[1] = "CH446Q"
    lib.append(m)
    with open(os.path.join(OUT_DIR, "c128rev3.kicad_sym"), "w", encoding="utf-8") as f:
        f.write(K.dump(lib) + "\n")
    with open(os.path.join(OUT_DIR, "sym-lib-table"), "w", encoding="utf-8") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "c128rev3")(type "KiCad")(uri "${KIPRJMOD}/c128rev3.kicad_sym")(options "")(descr "rev 3 project symbols"))\n)\n')
    print("wrote", root.filename, "and 4 sheets in", OUT_DIR)


if __name__ == "__main__":
    main()
