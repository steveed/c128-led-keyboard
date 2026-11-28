#!/usr/bin/env python3
"""Generate the C128D wireless dongle's schematic (dongle/pcb/).

    docker compose run --rm -e KICAD_SYMBOLS=/usr/share/kicad/symbols kicad \\
        python3 dongle/pcb/tools/gen_sch.py

The plan is docs/wireless-128d.md.  The host side is the keyboard's own circuit: this script
imports pcb/tools/gen_sch.py and calls its crosspoint_core(), so the CH446Q, the lock-line and
RESTORE FETs, the RESTORE sense diode and the LED data buffer are the same parts, values,
references and nets on both boards, and the firmware drives them the same way.  What is the
dongle's own: the two DB25s (male to the 128D, female for the keyboard, every pin straight
through), the ESP32-S3-MINI-1, the 5 V entry, the USB-C (device: the Mac and flashing) and USB-A
(host: a USB keyboard) behind a CH442E switch, the status LED and the two buttons.

Like the keyboard's generator it is deterministic (UUIDs keyed on sheet file and reference) and
writes every sheet afresh, so schematic changes are made here, not in eeschema.
"""
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "pcb", "tools"))

import gen_sch as G  # noqa: E402  the keyboard's generator: sheet builder, CH446Q, crosspoint core
import kisym as K  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, ".."))
PROJECT = "c128-dongle"

# the keyboard generator's module globals, pointed at this project
G.PROJECT = PROJECT
G.OUT_DIR = OUT
G.UUID_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "dongle.the-c128-keyboard-project")

R_FP, C_FP, C_FP_1206 = G.R_FP, G.C_FP, G.C_FP_1206
DB25_PINS_FP = "dongle:DB25_Pins_EdgeStraddle_1.6mm"      # male, to the 128D (gen_fp.py)
DB25_SOCKET_FP = "dongle:DB25_Socket_EdgeStraddle_1.6mm"  # female, for the keyboard cable
USB_A_FP = "dongle:USB_A_Jing_904-131A2032S10100"         # right-angle, lies flat
LED_FP = "LED_SMD:LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm"

# LCSC numbers for the parts this board adds (the shared ones are in G.LCSC).  Verify each on
# lcsc.com before ordering.  The two DB25s are solder-cup parts soldered by hand: no number.
G.LCSC.update({
    ("RF_Module:ESP32-S3-MINI-1", None): "C2913206",       # ESP32-S3-MINI-1-N8, PCB antenna
    ("c128rev3:CH442E", None): "C150097",                  # WCH CH442E, USB 2.0 2:1 switch, MSOP-10
    ("c128rev3:SY6280AAC", None): "C55136",                # Silergy SY6280AAC, USB-A power switch
    ("Connector:USB_A", None): "C8328",                    # Jing Extension 904-131A2032S10100
    ("Device:R", "12k"): "C22790",                         # UNI-ROYAL 0603 12k 1 %, the SY6280's Rset
})


# --- the two project symbols this board adds ------------------------------------------

def box_symbol(name, value, footprint, datasheet, description, left, right, top=(), bottom=(), half_w=10.16):
    """A rectangular symbol: pins as (name, number, type) on each side, 2.54 mm apart."""
    S = K.Sym
    n_side = max(len(left), len(right), 1)
    top_y = 2.54 * ((n_side + 1) // 2) + 1.27
    bot_y = -top_y
    pins = []

    def pin(nm, num, x, y, ang, typ):
        pins.append([S("pin"), S(typ), S("line"), [S("at"), x, y, ang], [S("length"), 5.08],
                     [S("name"), nm, [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]],
                     [S("number"), str(num), [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]]])

    y0 = 2.54 * ((n_side - 1) // 2)
    for i, (nm, num, typ) in enumerate(left):
        pin(nm, num, -half_w - 5.08, y0 - 2.54 * i, 0, typ)
    for i, (nm, num, typ) in enumerate(right):
        pin(nm, num, half_w + 5.08, y0 - 2.54 * i, 180, typ)
    for i, (nm, num, typ) in enumerate(top):
        pin(nm, num, -2.54 * (len(top) - 1) / 2 + 2.54 * i, top_y + 5.08, 270, typ)
    for i, (nm, num, typ) in enumerate(bottom):
        pin(nm, num, -2.54 * (len(bottom) - 1) / 2 + 2.54 * i, bot_y - 5.08, 90, typ)

    def prop(pname, val, hide=True, at=(0, 0)):
        eff = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
        if hide:
            eff.append([S("hide"), S("yes")])
        return [S("property"), pname, val, [S("at"), at[0], at[1], 0], eff]

    return [S("symbol"), f"c128rev3:{name}",
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            prop("Reference", "U", False, (-half_w, top_y + 2.54)),
            prop("Value", value, False, (half_w - 5.08, top_y + 2.54)),
            prop("Footprint", footprint), prop("Datasheet", datasheet), prop("Description", description),
            [S("symbol"), f"{name}_0_1",
             [S("rectangle"), [S("start"), -half_w, top_y], [S("end"), half_w, bot_y],
              [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]],
              [S("fill"), [S("type"), S("background")]]]],
            [S("symbol"), f"{name}_1_1"] + pins,
            [S("embedded_fonts"), S("no")]]


def ch442e_symbol():
    # WCH CH440/CH442 datasheet v3B, section 4.2 (pcb/datasheets/C150097.pdf): IN low connects
    # the commons DB/DC to S1B/S1C, IN high to S2B/S2C; EN# is active low.
    return box_symbol("CH442E", "CH442E", "Package_SO:MSOP-10_3x3mm_P0.5mm",
                      "https://www.wch-ic.com/downloads/CH440DS1_PDF.html",
                      "WCH dual 2:1 analog switch for USB 2.0, MSOP-10",
                      left=[("DB", 4, "bidirectional"), ("DC", 6, "bidirectional"),
                            ("IN", 1, "input"), ("EN#", 9, "input")],
                      right=[("S1B", 2, "bidirectional"), ("S1C", 8, "bidirectional"),
                             ("S2B", 3, "bidirectional"), ("S2C", 7, "bidirectional")],
                      top=[("VCC", 10, "power_in")], bottom=[("GND", 5, "power_in")])


def sy6280_symbol():
    # Silergy SY6280 preliminary spec rev 0.3 (pcb/datasheets/C55136.pdf): Ilim (A) = 6800 / Rset (ohm),
    # EN active high and not to be left floating, no fault output.
    return box_symbol("SY6280AAC", "SY6280AAC", "Package_TO_SOT_SMD:SOT-23-5",
                      "https://www.silergy.com/", "Silergy current-limited power distribution switch, SOT-23-5",
                      left=[("IN", 5, "power_in"), ("EN", 4, "input")],
                      right=[("OUT", 1, "power_out"), ("ISET", 3, "passive")],
                      bottom=[("GND", 2, "power_in")], half_w=7.62)


G.PROJECT_SYMBOLS["c128rev3:CH442E"] = ch442e_symbol
G.PROJECT_SYMBOLS["c128rev3:SY6280AAC"] = sy6280_symbol


# --- the dongle's ESP32 pins -----------------------------------------------------------

# The host side keeps the keyboard's pins (pcb/tools/gen_sch.py GPIO), so one firmware module
# drives the crosspoint on both boards.  The rest is the dongle's.
GPIO = {
    "IO0": "MCU_BOOT",          # BOOT at reset; the pairing button while running
    "IO1": "MCU_MODE",          # mode button: USB-C (Mac) or USB-A (keyboard)
    "IO2": "MCU_USB_SEL",       # CH442E IN: low = USB-C, high = USB-A
    "IO4": "MCU_USBA_EN",       # SY6280 EN: USB-A power, host mode only
    "IO7": "MCU_4080_GATE", "IO8": "MCU_CAPLK_GATE", "IO9": "MCU_RESTORE_GATE",
    "IO10": "MCU_XP_STB", "IO11": "MCU_XP_CK", "IO12": "MCU_XP_DAT", "IO13": "MCU_XP_RST",
    "IO14": "MCU_RESTORE_SENSE",
    "IO35": "MCU_LED_DATA",     # status LED, through U4
    "USB_D-": "USB_DN", "USB_D+": "USB_DP",
    "TXD0": "MCU_TXD0", "RXD0": "MCU_RXD0", "EN": "MCU_EN",
    # IO0, IO3, IO45 and IO46 are strapping pins; the rest are spare
    "IO3": None, "IO5": None, "IO6": None, "IO15": None, "IO16": None, "IO17": None, "IO18": None,
    "IO21": None, "IO26": None, "IO33": None, "IO34": None, "IO36": None, "IO37": None, "IO38": None,
    "IO39": None, "IO40": None, "IO41": None, "IO42": None, "IO45": None, "IO46": None,
    "IO47": None, "IO48": None,
}


def dsub_pins():
    """D-sub pin -> net, from the keyboard's 2x13 header table: header pin n is ribbon conductor
    n, and the IDC D-sub puts odd conductors on D-sub 1..13 and even ones on 14..25."""
    out = {}
    for hdr, net in G.HOST_PINS.items():
        d = (hdr + 1) // 2 if hdr % 2 else 13 + hdr // 2
        if d <= 25:
            out[d] = net
    assert sorted(out) == list(range(1, 26)), sorted(out)
    return out


# --- sheets ----------------------------------------------------------------------------

def build_mcu(sh):
    sh.text("C128D dongle: ESP32-S3, USB and power.  +5V_KB is the 128D's 5 V on DB25 pin 4; +5V_SYS is its OR with\n"
            "the USB-C's VBUS; +3V3 feeds the ESP32 and the CH442E.  The CH442E routes the S3's one USB port to the\n"
            "USB-C (device: the Mac app and flashing) or the USB-A (host: a USB keyboard).  See docs/wireless-128d.md.",
            (15, 15), 1.5)

    # ESP32-S3-MINI-1, PCB antenna (the keyboard has the -1U); same land pattern as the S2-MINI-1
    u1 = sh.symbol("RF_Module:ESP32-S3-MINI-1", "U1", "ESP32-S3-MINI-1-N8", (75, 130),
                   footprint="RF_Module:ESP32-S2-MINI-1")
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
    for i, (x, val) in enumerate(((30, "100n"), (40, "10u"))):
        c = sh.symbol("Device:C", f"C{2 + i}", val, (x, 60), footprint=C_FP)
        sh.connect(c, 1, "+3V3"); sh.connect(c, 2, "GND")

    # EN: RC reset at power-up (no reset button; USB-Serial/JTAG resets it for flashing)
    r1 = sh.symbol("Device:R", "R1", "10k", (55, 60), footprint=R_FP)
    sh.connect(r1, 1, "+3V3"); sh.connect(r1, 2, "MCU_EN", stub=2.54)
    c1 = sh.symbol("Device:C", "C1", "100n", (65, 60), footprint=C_FP)
    sh.connect(c1, 1, "MCU_EN", stub=2.54); sh.connect(c1, 2, "GND")

    # UART0 test pads: the console when the S3's USB is hosting a keyboard
    for i, (net, x) in enumerate((("MCU_TXD0", 100), ("MCU_RXD0", 112), ("GND", 124))):
        tp = sh.symbol("Connector:TestPoint", f"TP{i + 1}", net.replace("MCU_", ""), (x, 245),
                       footprint="TestPoint:TestPoint_Pad_1.0x1.0mm")
        sh.connect(tp, 1, net, stub=2.54, kind="label" if net == "GND" else None)

    # buttons: BOOT/pairing on IO0, mode on IO1, each with a pull-up
    def button(x, rname, swname, swval, net):
        r = sh.symbol("Device:R", rname, "10k", (x, 205), footprint=R_FP)
        sh.connect(r, 1, "+3V3"); sh.connect(r, 2, net, stub=2.54)
        sw = sh.symbol("Switch:SW_Push", swname, swval, (x + 12, 215), rot=90,
                       footprint="Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92", fields={"LCSC": G.TACT_LCSC})
        sh.connect(sw, 2, net, stub=2.54); sh.connect(sw, 1, "GND")
    button(20, "R2", "SW1", "BOOT / PAIR", "MCU_BOOT")
    button(50, "R8", "SW2", "MODE", "MCU_MODE")

    # status LED: one SK6812 MINI behind the clamshell's light pipe, data through U4 (host sheet)
    led = sh.symbol("LED:SK6812MINI", "LED1", "SK6812MINI", (95, 215), footprint=LED_FP)
    sh.connect(led, 3, "LED_DATA_5V", stub=5.08); sh.connect(led, 1, None)
    sh.connect(led, 4, "+5V_SYS", stub=2.54); sh.connect(led, 2, "GND", stub=2.54)
    c10 = sh.symbol("Device:C", "C10", "100n", (115, 215), footprint=C_FP)
    sh.connect(c10, 1, "+5V_SYS"); sh.connect(c10, 2, "GND")

    # USB-C: device port (Mac app, flashing).  Only ever a sink: plain 5.1 k pull-downs.
    sh.text("USB", (150, 40), 1.5)
    j1 = sh.symbol("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C", (175, 85),
                   footprint="c128rev3:USB_C_Receptacle_ShouHan_TYPE-C-16P-3MD-040", fields={"LCSC": "C41417453"})
    sh.connect(j1, "A4", "VBUS"); sh.connect(j1, "A5", "CC1"); sh.connect(j1, "B5", "CC2")
    sh.connect(j1, "A6", "USBC_DP"); sh.connect(j1, "B6", "USBC_DP")
    sh.connect(j1, "A7", "USBC_DN"); sh.connect(j1, "B7", "USBC_DN")
    sh.connect(j1, "A8", None); sh.connect(j1, "B8", None)
    sh.connect(j1, "A1", "GND"); sh.connect(j1, "SH", "GND", kind="label")
    r3 = sh.symbol("Device:R", "R3", "5k1", (215, 60), footprint=R_FP)
    sh.connect(r3, 1, "CC1", stub=2.54); sh.connect(r3, 2, "GND")
    r4 = sh.symbol("Device:R", "R4", "5k1", (230, 60), footprint=R_FP)
    sh.connect(r4, 1, "CC2", stub=2.54); sh.connect(r4, 2, "GND")
    u7 = sh.symbol("Power_Protection:USBLC6-2SC6", "U7", "USBLC6-2SC6", (215, 105), footprint="Package_TO_SOT_SMD:SOT-23-6")
    sh.connect(u7, 1, "USBC_DP"); sh.connect(u7, 3, "USBC_DN"); sh.connect(u7, 6, "USBC_DP"); sh.connect(u7, 4, "USBC_DN")
    sh.connect(u7, 5, "VBUS"); sh.connect(u7, 2, "GND")

    # USB-A: host port (a USB keyboard), powered only in host mode
    j4 = sh.symbol("Connector:USB_A", "J4", "USB-A", (175, 165), footprint=USB_A_FP)
    sh.connect(j4, 1, "USBA_VBUS"); sh.connect(j4, 2, "USBA_DN"); sh.connect(j4, 3, "USBA_DP")
    sh.connect(j4, 4, "GND"); sh.connect(j4, "SH", "GND", kind="label")
    u8 = sh.symbol("Power_Protection:USBLC6-2SC6", "U8", "USBLC6-2SC6", (230, 182), footprint="Package_TO_SOT_SMD:SOT-23-6")
    sh.connect(u8, 1, "USBA_DP"); sh.connect(u8, 3, "USBA_DN"); sh.connect(u8, 6, "USBA_DP"); sh.connect(u8, 4, "USBA_DN")
    sh.connect(u8, 5, "USBA_VBUS"); sh.connect(u8, 2, "GND")
    # SY6280AAC: Ilim = 6800 / 12k = 0.57 A (0.75-1.25 x at 6.8 k in the datasheet's table)
    u6 = sh.symbol("c128rev3:SY6280AAC", "U6", "SY6280AAC", (260, 210))
    n6 = u6.pins_named()
    sh.connect(u6, n6["IN"], "+5V_SYS", stub=5.08); sh.connect(u6, n6["EN"], "MCU_USBA_EN", stub=5.08)
    sh.connect(u6, n6["OUT"], "USBA_VBUS", stub=5.08); sh.connect(u6, n6["ISET"], "USBA_ISET", stub=5.08)
    sh.connect(u6, n6["GND"], "GND")
    r9 = sh.symbol("Device:R", "R9", "12k", (300, 225), footprint=R_FP)
    sh.connect(r9, 1, "USBA_ISET", stub=2.54); sh.connect(r9, 2, "GND")
    r13 = sh.symbol("Device:R", "R13", "100k", (215, 232), footprint=R_FP)   # USB-A off while the S3 resets
    sh.connect(r13, 1, "MCU_USBA_EN", stub=2.54); sh.connect(r13, 2, "GND")
    c11 = sh.symbol("Device:C", "C11", "10u", (315, 225), footprint=C_FP_1206, fields={"LCSC": G.C_10U_1206_LCSC})
    sh.connect(c11, 1, "USBA_VBUS"); sh.connect(c11, 2, "GND")

    # CH442E: the S3's USB to one port or the other.  Run from +3V3, so the S3's 3.3 V drives IN.
    u5 = sh.symbol("c128rev3:CH442E", "U5", "CH442E", (290, 120))
    n5 = u5.pins_named()
    sh.connect(u5, n5["DB"], "USB_DP", stub=5.08); sh.connect(u5, n5["DC"], "USB_DN", stub=5.08)
    sh.connect(u5, n5["IN"], "MCU_USB_SEL", stub=5.08); sh.connect(u5, n5["EN#"], "GND", stub=5.08, kind="label")
    sh.connect(u5, n5["S1B"], "USBC_DP", stub=5.08); sh.connect(u5, n5["S1C"], "USBC_DN", stub=5.08)
    sh.connect(u5, n5["S2B"], "USBA_DP", stub=5.08); sh.connect(u5, n5["S2C"], "USBA_DN", stub=5.08)
    sh.connect(u5, n5["VCC"], "+3V3"); sh.connect(u5, n5["GND"], "GND")
    c4 = sh.symbol("Device:C", "C4", "100n", (345, 112), footprint=C_FP)
    sh.connect(c4, 1, "+3V3"); sh.connect(c4, 2, "GND")
    r14 = sh.symbol("Device:R", "R14", "100k", (245, 152), footprint=R_FP)   # USB-C selected at reset
    sh.connect(r14, 1, "MCU_USB_SEL", stub=2.54); sh.connect(r14, 2, "GND")

    # power path: +5V_KB -> F1 -> D1 -> +5V_SYS <- D2 <- VBUS ; LDO -> +3V3
    sh.text("Power path", (250, 22), 1.5)
    f1 = sh.symbol("Device:Polyfuse", "F1", "1.1A", (255, 40), footprint="Fuse:Fuse_1812_4532Metric")
    sh.connect(f1, 1, "+5V_KB"); sh.connect(f1, 2, "+5V_KB_F", stub=2.54)
    d1 = sh.symbol("Diode:SS34", "D1", "SS34", (280, 45), footprint="Diode_SMD:D_SMA")
    sh.connect(d1, 2, "+5V_KB_F"); sh.connect(d1, 1, "+5V_SYS")
    d2 = sh.symbol("Diode:SS34", "D2", "SS34", (280, 60), footprint="Diode_SMD:D_SMA")
    sh.connect(d2, 2, "VBUS"); sh.connect(d2, 1, "+5V_SYS")
    c5 = sh.symbol("Device:C", "C5", "10u", (305, 55), footprint=C_FP_1206, fields={"LCSC": G.C_10U_1206_LCSC})
    sh.connect(c5, 1, "+5V_SYS"); sh.connect(c5, 2, "GND")
    u2 = sh.symbol("Regulator_Linear:AP7361C-33E", "U2", "AP7361C-33E", (350, 45),
                   footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2", fields={"LCSC": "C500795"})
    n2 = u2.pins_named()
    sh.connect(u2, n2["VI"], "+5V_SYS"); sh.connect(u2, n2["VO"], "+3V3"); sh.connect(u2, n2["GND"], "GND")
    c6 = sh.symbol("Device:C", "C6", "10u", (322, 60), footprint=C_FP_1206, fields={"LCSC": G.C_10U_1206_LCSC})
    sh.connect(c6, 1, "+5V_SYS"); sh.connect(c6, 2, "GND")
    c7 = sh.symbol("Device:C", "C7", "10u", (385, 60), footprint=C_FP_1206, fields={"LCSC": G.C_10U_1206_LCSC})
    sh.connect(c7, 1, "+3V3"); sh.connect(c7, 2, "GND")
    for net, x in (("+5V_KB", 330), ("+5V_SYS", 345), ("GND", 360), ("VBUS", 375)):
        sh.power("PWR_FLAG", (x, 82))
        sh.glabel(net, (x, 82), "D")
    used = [f"{io} {net}" for io, net in GPIO.items() if net and io.startswith("IO")]
    spare = [io for io, net in GPIO.items() if net is None]
    lines = ["GPIO: " + ", ".join(used[:5]), "      " + ", ".join(used[5:10]), "      " + ", ".join(used[10:]),
             "Spare: " + ", ".join(spare[:11]), "       " + ", ".join(spare[11:]) + " (IO0, IO3, IO45, IO46 strap)"]
    sh.text("\n".join(lines), (150, 262), 1.27)


def build_host(sh):
    G.crosspoint_core(sh)
    sh.text("Host connectors: J2 (male) plugs into the 128D's female keyboard socket, on its right side; J3 (female) takes\n"
            "the keyboard's cable.  Every pin runs straight through, so a wired keyboard works as normal, and the\n"
            "CH446Q and the FETs sit on the same lines in parallel.  Both are solder-cup DB25s straddling 1.6 mm board edges.",
            (200, 160), 1.27)
    pins = dsub_pins()
    for ref, lib, value, fp, x in (("J2", "Connector:DB25_Pins", "DB25 male, to the 128D", DB25_PINS_FP, 320),
                                   ("J3", "Connector:DB25_Socket", "DB25 female, for the keyboard", DB25_SOCKET_FP, 375)):
        j = sh.symbol(lib, ref, value, (x, 205), footprint=fp)
        for d, net in pins.items():
            sh.connect(j, d, net, stub=7.62, kind="label" if net else None)


def build_root(root, sheets):
    root.text("C128D wireless dongle (draft).  Plugs into the 128D's keyboard socket and passes the keyboard through;\n"
              "an ESP32-S3 drives a CH446Q crosspoint on the host lines from the radio keyboard, a Mac app or a USB keyboard.\n"
              "See docs/wireless-128d.md.  Generated by dongle/pcb/tools/gen_sch.py: change the script, not the sheets.",
              (20, 20), 1.8)
    x = 20
    for sub in sheets:
        root.sheet_ref(sub, (x, 50), (70, 30))
        x += 90
    root.text("Nets between sheets are global labels:\n"
              "  H_ROW0-7, H_COL0-10, H_RESTORE, H_4080, H_CAPLK   host (C128) lines, both DB25s\n"
              "  MCU_XP_DAT/CK/STB/RST, MCU_*_GATE, MCU_RESTORE_SENSE   crosspoint and FETs, as on the keyboard\n"
              "  MCU_LED_DATA -> LED_DATA_5V   status LED through U4\n"
              "  +5V_KB (the 128D's 5 V), +5V_SYS (OR'd with USB-C VBUS), +3V3, GND", (20, 100), 1.27)


def main():
    root = G.Sheet(f"{PROJECT}.kicad_sch", "C128D wireless dongle", page=1)
    mcu = G.Sheet("mcu.kicad_sch", "ESP32, USB and power", root.uuid, 2)
    host = G.Sheet("host.kicad_sch", "Crosspoint and host", root.uuid, 3)
    build_mcu(mcu)
    build_host(host)
    build_root(root, [mcu, host])
    for sh in (mcu, host):
        sh.emit()
    root.emit(is_root=True)
    S = K.Sym
    lib = [S("kicad_symbol_lib"), [S("version"), S(G.LIB_VERSION)], [S("generator"), "gen_sch"],
           [S("generator_version"), G.GENERATOR_VERSION]]
    for lib_id in ("c128rev3:CH446Q", "c128rev3:CH442E", "c128rev3:SY6280AAC"):
        m = G.PROJECT_SYMBOLS[lib_id]()
        m[1] = lib_id.split(":")[1]
        lib.append(m)
    with open(os.path.join(OUT, "c128rev3.kicad_sym"), "w", encoding="utf-8") as f:
        f.write(K.dump(lib) + "\n")
    with open(os.path.join(OUT, "sym-lib-table"), "w", encoding="utf-8") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "c128rev3")(type "KiCad")(uri "${KIPRJMOD}/c128rev3.kicad_sym")'
                '(options "")(descr "dongle project symbols: CH446Q, CH442E, SY6280AAC"))\n)\n')
    with open(os.path.join(OUT, "fp-lib-table"), "w", encoding="utf-8") as f:
        f.write('(fp_lib_table\n  (version 7)\n'
                '  (lib (name "c128rev3")(type "KiCad")(uri "${KIPRJMOD}/../../pcb/c128rev3.pretty")(options "")(descr "the keyboard\'s footprints: USB-C"))\n'
                '  (lib (name "dongle")(type "KiCad")(uri "${KIPRJMOD}/dongle.pretty")(options "")(descr "edge-straddle DB25s, USB-A"))\n)\n')
    print("wrote", root.filename, "and 2 sheets in", OUT)


if __name__ == "__main__":
    main()
