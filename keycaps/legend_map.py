#!/usr/bin/env python3
"""Generate the C128 keycap legend map: legend_map.csv, legend_map.md and SVG artwork for the
front-face legends (fronts/*.svg plus front_legends_sheet.svg).

Key positions come from the rev 2.3 board (see layout/switches.json); legends were checked against a
Commodore 128 keyboard photo; PETSCII glyphs follow the Unicode 13 mapping (Wikipedia/KreativeKorp).
Run:  python3 legend_map.py
"""
import csv, os, html

# --------------------------------------------------------------------- PETSCII glyphs
# code -> (unicode char, codepoint, description, drawing)
# drawing: list of primitives on an 8x8 grid (x right, y down):
#   ("r", x, y, w, h)  rectangle   ("p", [(x,y),...])  polygon   ("c", cx, cy, r, filled)
#   ("a", kind)  rounded corner   ("chk", x0, y0, x1, y1) 1-px checkerboard   ("t", text)  fallback text
def R(*a): return ("r",) + a
H = lambda row: R(0, row, 8, 1)      # full-width horizontal line at pixel row
V = lambda col: R(col, 0, 1, 8)      # full-height vertical line at pixel column
GLYPHS = {
    0xA1: ("▌", "U+258C", "left half block",            [R(0,0,4,8)]),
    0xA2: ("▄", "U+2584", "lower half block",           [R(0,4,8,4)]),
    0xA3: ("▔", "U+2594", "top edge line",              [H(0)]),
    0xA4: ("▁", "U+2581", "bottom edge line",           [H(7)]),
    0xA5: ("▏", "U+258F", "left edge line",             [V(0)]),
    0xA6: ("▒", "U+2592", "checkerboard",               [("chk",0,0,8,8)]),
    0xA7: ("▕", "U+2595", "right edge line",            [V(7)]),
    0xA8: ("🮏", "U+1FB8F", "lower half checkerboard",   [("chk",0,4,8,8)]),
    0xA9: ("◤", "U+25E4", "upper-left filled triangle", [("p",[(0,0),(8,0),(0,8)])]),
    0xAA: ("🮇", "U+1FB87", "right quarter block",       [R(6,0,2,8)]),
    0xAB: ("├", "U+251C", "T pointing right",           [V(4), R(4,3,4,1)]),
    0xAC: ("▗", "U+2597", "lower-right quadrant",       [R(4,4,4,4)]),
    0xAD: ("└", "U+2514", "corner: up and right",       [R(4,0,1,4), R(4,3,4,1)]),
    0xAE: ("┐", "U+2510", "corner: left and down",      [R(0,3,5,1), R(4,3,1,5)]),
    0xAF: ("▂", "U+2582", "lower quarter block",        [R(0,6,8,2)]),
    0xB0: ("┌", "U+250C", "corner: right and down",     [R(4,3,4,1), R(4,3,1,5)]),
    0xB1: ("┴", "U+2534", "T pointing up",              [H(3), R(4,0,1,4)]),
    0xB2: ("┬", "U+252C", "T pointing down",            [H(3), R(4,3,1,5)]),
    0xB3: ("┤", "U+2524", "T pointing left",            [V(4), R(0,3,5,1)]),
    0xB4: ("▎", "U+258E", "left quarter block",         [R(0,0,2,8)]),
    0xB5: ("▍", "U+258D", "left 3/8 block",             [R(0,0,3,8)]),
    0xB6: ("🮈", "U+1FB88", "right 3/8 block",           [R(5,0,3,8)]),
    0xB7: ("🮂", "U+1FB82", "upper quarter block",       [R(0,0,8,2)]),
    0xB8: ("🮃", "U+1FB83", "upper 3/8 block",           [R(0,0,8,3)]),
    0xB9: ("▃", "U+2583", "lower 3/8 block",            [R(0,5,8,3)]),
    0xBA: ("🭿", "U+1FB7F", "bottom + right edge lines", [H(7), V(7)]),
    0xBB: ("▖", "U+2596", "lower-left quadrant",        [R(0,4,4,4)]),
    0xBC: ("▝", "U+259D", "upper-right quadrant",       [R(4,0,4,4)]),
    0xBD: ("┘", "U+2518", "corner: left and up",        [R(0,3,5,1), R(4,0,1,4)]),
    0xBE: ("▘", "U+2598", "upper-left quadrant",        [R(0,0,4,4)]),
    0xBF: ("▚", "U+259A", "diagonal quadrants",         [R(0,0,4,4), R(4,4,4,4)]),
    0xC0: ("─", "U+2500", "horizontal line, row 4",     [H(4)]),
    0xC1: ("♠", "U+2660", "spade",                      [("t","♠")]),
    0xC2: ("🭲", "U+1FB72", "vertical line, col 3",      [V(3)]),
    0xC3: ("🭸", "U+1FB78", "horizontal line, row 3",    [H(3)]),
    0xC4: ("🭷", "U+1FB77", "horizontal line, row 2",    [H(2)]),
    0xC5: ("🭶", "U+1FB76", "horizontal line, row 1",    [H(1)]),
    0xC6: ("🭺", "U+1FB7A", "horizontal line, row 5",    [H(5)]),
    0xC7: ("🭱", "U+1FB71", "vertical line, col 2",      [V(2)]),
    0xC8: ("🭴", "U+1FB74", "vertical line, col 5",      [V(5)]),
    0xC9: ("╮", "U+256E", "rounded corner: left and down", [("a","ld")]),
    0xCA: ("╰", "U+2570", "rounded corner: up and right",  [("a","ur")]),
    0xCB: ("╯", "U+256F", "rounded corner: left and up",   [("a","lu")]),
    0xCC: ("🭼", "U+1FB7C", "left + bottom edge lines",  [V(0), H(7)]),
    0xCD: ("╲", "U+2572", "diagonal, top-left to bottom-right", [("p",[(0,0),(1,0),(8,7),(8,8),(7,8),(0,1)])]),
    0xCE: ("╱", "U+2571", "diagonal, bottom-left to top-right", [("p",[(7,0),(8,0),(8,1),(1,8),(0,8),(0,7)])]),
    0xCF: ("🭽", "U+1FB7D", "left + top edge lines",     [V(0), H(0)]),
    0xD0: ("🭾", "U+1FB7E", "top + right edge lines",    [H(0), V(7)]),
    0xD1: ("●", "U+2022", "filled circle",              [("c",4,4,3,True)]),
    0xD2: ("🭻", "U+1FB7B", "horizontal line, row 6",    [H(6)]),
    0xD3: ("♥", "U+2665", "heart",                      [("t","♥")]),
    0xD4: ("🭰", "U+1FB70", "vertical line, col 1",      [V(1)]),
    0xD5: ("╭", "U+256D", "rounded corner: right and down", [("a","rd")]),
    0xD6: ("╳", "U+2573", "diagonal cross",             [("p",[(0,0),(1,0),(8,7),(8,8),(7,8),(0,1)]), ("p",[(7,0),(8,0),(8,1),(1,8),(0,8),(0,7)])]),
    0xD7: ("○", "U+25CB", "open circle",                [("c",4,4,3,False)]),
    0xD8: ("♣", "U+2663", "club",                       [("t","♣")]),
    0xD9: ("🭵", "U+1FB75", "vertical line, col 6",      [V(6)]),
    0xDA: ("♦", "U+2666", "diamond",                    [("p",[(4,0.5),(7.5,4),(4,7.5),(0.5,4)])]),
    0xDB: ("┼", "U+253C", "cross",                      [H(3), V(4)]),
    0xDC: ("🮌", "U+1FB8C", "left half checkerboard",    [("chk",0,0,4,8)]),
    0xDD: ("│", "U+2502", "vertical line, col 4",       [V(4)]),
    0xDE: ("π", "U+03C0", "pi",                         [("t","π")]),
    0xDF: ("◥", "U+25E5", "upper-right filled triangle", [("p",[(0,0),(8,0),(8,8)])]),
}

# Commodore-key graphics per key (Shift graphics for letters are 0xC1 + index)
CBM = dict(A=0xB0,B=0xBF,C=0xBC,D=0xAC,E=0xB1,F=0xBB,G=0xA5,H=0xB4,I=0xA2,J=0xB5,K=0xA1,L=0xB6,M=0xA7,
           N=0xAA,O=0xB9,P=0xAF,Q=0xAB,R=0xB2,S=0xAE,T=0xA3,U=0xB8,V=0xBE,W=0xB3,X=0xBD,Y=0xB7,Z=0xAD)

# --------------------------------------------------------------------- keys
# (pcb value, group, row y, x center, width u, color, top main, top shifted/upper, front)
# Widths are keycap widths from the switch spacing, not footprint names: the 1.5u CONTROL and
# right SHIFT sit on plain 1u footprints.
# front: ("g", cbm_code, shift_code) two boxed glyphs; ("g1", code) one glyph; ("txt", line1, line2); None
def letters(y, keys_x):
    return [(k, "main", y, x, 1, "light", k, "", ("g", CBM[k], 0xC1 + ord(k) - 65)) for k, x in keys_x]

KEYS = [
    # top row, dark
    ("Esc",      "top1", 59.85, -177.26, 1, "dark", "ESC", "", None),
    ("Tab",      "top1", 59.85, -158.21, 1, "dark", "TAB", "", None),
    ("Alt",      "top1", 59.85, -139.16, 1, "dark", "ALT", "", None),
    ("CapsLk",   "top1", 59.85, -120.11, 1, "dark", "CAPS\nLOCK", "", None),
    ("Help",     "top2", 59.85,  -62.96, 1, "dark", "HELP", "", None),
    ("LineFeed", "top2", 59.85,  -43.91, 1, "dark", "LINE\nFEED", "", None),
    ("40_80",    "top2", 59.85,  -24.86, 1, "dark", "40/80\nDISPLAY", "", None),
    ("NoScroll", "top2", 59.85,   -5.81, 1, "dark", "NO\nSCROLL", "", None),
    ("Crsr-Up",    "top3", 59.85,  51.34, 1, "dark", "↑", "", None),
    ("Crsr-Down",  "top3", 59.85,  70.39, 1, "dark", "↓", "", None),
    ("Crsr-Left",  "top3", 59.85,  89.44, 1, "dark", "←", "", None),
    ("Crsr-Right", "top3", 59.85, 108.49, 1, "dark", "→", "", None),
    ("F1", "top4", 59.85, 141.79, 1, "dark", "F1", "F2", None),
    ("F3", "top4", 59.85, 160.84, 1, "dark", "F3", "F4", None),
    ("F5", "top4", 59.85, 179.89, 1, "dark", "F5", "F6", None),
    ("F7", "top4", 59.85, 198.94, 1, "dark", "F7", "F8", None),
    # row 1
    ("LeftArrow", "main", 30.29, -177.26, 1, "light", "←", "", None),
    ("1", "main", 30.29, -158.21, 1, "light", "1", "!", ("txt", "Blk", "Orng")),
    ("2", "main", 30.29, -139.16, 1, "light", "2", "\"", ("txt", "Wht", "Brn")),
    ("3", "main", 30.29, -120.11, 1, "light", "3", "#", ("txt", "Red", "L Red")),
    ("4", "main", 30.29, -101.06, 1, "light", "4", "$", ("txt", "Cyn", "D Gry")),
    ("5", "main", 30.29,  -82.01, 1, "light", "5", "%", ("txt", "Pur", "M Gry")),
    ("6", "main", 30.29,  -62.96, 1, "light", "6", "&", ("txt", "Grn", "L Grn")),
    ("7", "main", 30.29,  -43.91, 1, "light", "7", "'", ("txt", "Blu", "L Blu")),
    ("8", "main", 30.29,  -24.86, 1, "light", "8", "(", ("txt", "Yel", "L Gry")),
    ("9", "main", 30.29,   -5.81, 1, "light", "9", ")", ("txt", "Rvs", "On")),
    ("0", "main", 30.29,   13.24, 1, "light", "0 (slashed)", "", ("txt", "Rvs", "Off")),
    ("+", "main", 30.29,   32.29, 1, "light", "+", "", ("g", 0xA6, 0xDB)),
    ("-", "main", 30.29,   51.34, 1, "light", "−", "", ("g", 0xDC, 0xDD)),
    ("£", "main", 30.29,   70.39, 1, "light", "£", "", ("g", 0xA8, 0xA9)),
    ("Clr/Home", "main", 30.29,  89.44, 1, "light", "CLR\nHOME", "", None),
    ("Inst/Del", "main", 30.29, 108.49, 1, "light", "INST\nDEL", "", None),
    # row 2
    ("Ctrl", "main", 11.24, -172.34, 1.5, "light", "CONTROL", "", None),
] + letters(11.24, [("Q",-148.53),("W",-129.48),("E",-110.43),("R",-91.38),("T",-72.33),("Y",-53.28),("U",-34.23),("I",-15.18),("O",3.87),("P",22.92)]) + [
    ("@", "main", 11.24, 41.97, 1, "light", "@", "", ("g", 0xA4, 0xBA)),
    ("*", "main", 11.24, 61.02, 1, "light", "*", "", ("g", 0xDF, 0xC0)),
    ("UpArrow", "main", 11.24, 80.07, 1, "light", "↑", "", ("g1", 0xDE)),
    ("Restore", "main", 11.24, 103.88, 1.5, "light", "RESTORE", "", None),
    # row 3
    ("Run/Stop",  "main", -7.81, -177.26, 1, "light", "RUN\nSTOP", "", None),
    ("ShiftLock", "main", -7.81, -158.21, 1, "light", "SHIFT\nLOCK", "", None),
] + letters(-7.81, [("A",-139.16),("S",-120.11),("D",-101.06),("F",-82.01),("G",-62.96),("H",-43.91),("J",-24.86),("K",-5.81),("L",13.24)]) + [
    (":", "main", -7.81, 32.29, 1, "light", ":", "[", None),
    (";", "main", -7.81, 51.34, 1, "light", ";", "]", None),
    ("=", "main", -7.81, 70.39, 1, "light", "=", "", None),
    ("Return", "main", -7.81, 98.96, 2, "light", "RETURN", "", None),
    # row 4
    ("C=",      "main", -26.86, -177.26, 1,   "light", "C= (Commodore logo)", "", None),
    ("L-Shift", "main", -26.86, -153.45, 1.5, "light", "SHIFT", "", None),
] + letters(-26.86, [("Z",-129.64),("X",-110.59),("C",-91.54),("V",-72.49),("B",-53.44),("N",-34.39),("M",-15.34)]) + [
    (",", "main", -26.86,  3.71, 1, "light", ",", "<", None),
    (".", "main", -26.86, 22.76, 1, "light", ".", ">", None),
    ("/", "main", -26.86, 41.81, 1, "light", "/", "?", None),
    ("R-Shift",    "main", -26.86,  65.62, 1.5, "light", "SHIFT", "", None),
    ("Crsr Vert",  "main", -26.86,  89.43, 1, "light", "CRSR", "↑ above, ↓ below", None),
    ("Crsr Horiz", "main", -26.86, 108.48, 1, "light", "CRSR", "← above, → below", None),
    ("Space", "main", -45.91, -34.23, 9, "light", "", "", None),
    # keypad
    ("Num7", "keypad", 30.29, 141.79, 1, "light", "7", "", None),
    ("Num8", "keypad", 30.29, 160.84, 1, "light", "8", "", None),
    ("Num9", "keypad", 30.29, 179.89, 1, "light", "9", "", None),
    ("Num+", "keypad", 30.29, 198.94, 1, "light", "+", "", None),
    ("Num4", "keypad", 11.24, 141.79, 1, "light", "4", "", None),
    ("Num5", "keypad", 11.24, 160.84, 1, "light", "5", "", None),
    ("Num6", "keypad", 11.24, 179.89, 1, "light", "6", "", None),
    ("Num-", "keypad", 11.24, 198.94, 1, "light", "−", "", None),
    ("Num1", "keypad", -7.81, 141.79, 1, "light", "1", "", None),
    ("Num2", "keypad", -7.81, 160.84, 1, "light", "2", "", None),
    ("Num3", "keypad", -7.81, 179.89, 1, "light", "3", "", None),
    ("NumEnter", "keypad", -17.34, 198.94, "2 (vertical)", "light", "ENTER (rotated, reads top to bottom)", "", None),
    ("Num0", "keypad", -26.86, 151.32, 2, "light", "0", "", None),
    ("Num.", "keypad", -26.86, 179.89, 1, "light", ".", "", None),
]

ROWNAME = {59.85: "top", 30.29: "1", 11.24: "2", -7.81: "3", -26.86: "4", -17.34: "3-4", -45.91: "space"}

def g(code):
    ch, cp, desc, _ = GLYPHS[code]
    return ch, cp, desc

# --------------------------------------------------------------------- SVG
CELL = 3.2      # mm, size of one glyph box on the keycap front
GAP = 0.9       # mm between the two boxes
STROKE = 0.12   # box outline
CHK = 1         # checkerboard cell size in grid pixels (2 for UV DTF transfers, see below)

def glyph_svg(code, ox, oy, s=CELL):
    """SVG for one boxed glyph with its top-left corner at (ox, oy) mm."""
    u = s / 8.0
    out = [f'<rect x="{ox:.3f}" y="{oy:.3f}" width="{s:.3f}" height="{s:.3f}" fill="none" stroke="#000" stroke-width="{STROKE}"/>']
    for prim in GLYPHS[code][3]:
        k = prim[0]
        if k == "r":
            _, x, y, w, h = prim
            out.append(f'<rect x="{ox+x*u:.3f}" y="{oy+y*u:.3f}" width="{w*u:.3f}" height="{h*u:.3f}"/>')
        elif k == "p":
            pts = " ".join(f"{ox+x*u:.3f},{oy+y*u:.3f}" for x, y in prim[1])
            out.append(f'<polygon points="{pts}"/>')
        elif k == "c":
            _, cx, cy, r, filled = prim
            fill = "#000" if filled else "none"
            out.append(f'<circle cx="{ox+cx*u:.3f}" cy="{oy+cy*u:.3f}" r="{r*u:.3f}" fill="{fill}" stroke="#000" stroke-width="{u:.3f}"/>')
        elif k == "chk":
            _, x0, y0, x1, y1 = prim
            for y in range(y0, y1, CHK):
                for x in range(x0, x1, CHK):
                    if ((x // CHK) + (y // CHK)) % 2 == 0:
                        out.append(f'<rect x="{ox+x*u:.3f}" y="{oy+y*u:.3f}" width="{CHK*u:.3f}" height="{CHK*u:.3f}"/>')
        elif k == "a":
            # quarter-circle arc of radius 4 px, 1 px wide, from the cell center to two edges
            kind = prim[1]
            cx, cy = ox + 4.5 * u, oy + 3.5 * u
            r = 4 * u
            # arc from edge A to edge B around the center of curvature at the far corner
            if kind == "ld":   # ╮  from left edge (row 3) curving down to bottom (col 4)
                d = f'M {ox:.3f} {cy:.3f} L {ox+0.5*u:.3f} {cy:.3f} A {r:.3f} {r:.3f} 0 0 1 {cx:.3f} {oy+7.5*u:.3f} L {cx:.3f} {oy+s:.3f}'
            elif kind == "ur": # ╰  from top (col 4) curving to right edge (row 3)
                d = f'M {cx:.3f} {oy:.3f} L {cx:.3f} {oy+0.5*u:.3f} A {r:.3f} {r:.3f} 0 0 0 {ox+7.5*u:.3f} {cy:.3f} L {ox+s:.3f} {cy:.3f}'
            elif kind == "lu": # ╯  from top (col 4) curving to left edge (row 3)
                d = f'M {cx:.3f} {oy:.3f} L {cx:.3f} {oy+0.5*u:.3f} A {r:.3f} {r:.3f} 0 0 1 {ox+0.5*u:.3f} {cy:.3f} L {ox:.3f} {cy:.3f}'
            else:              # ╭  from right edge (row 3) curving down to bottom (col 4)
                d = f'M {ox+s:.3f} {cy:.3f} L {ox+7.5*u:.3f} {cy:.3f} A {r:.3f} {r:.3f} 0 0 1 {cx:.3f} {oy+7.5*u:.3f} L {cx:.3f} {oy+s:.3f}'
            out.append(f'<path d="{d}" fill="none" stroke="#000" stroke-width="{u:.3f}"/>')
        elif k == "t":
            out.append(f'<text x="{ox+s/2:.3f}" y="{oy+s*0.78:.3f}" font-size="{s*0.85:.3f}" text-anchor="middle" font-family="DejaVu Sans, Arial Unicode MS, sans-serif">{html.escape(prim[1])}</text>')
    return "\n".join(out)

def front_svg(front, ox=0, oy=0):
    """SVG fragment for a whole front legend at (ox, oy); returns (svg, width, height) in mm."""
    if front is None:
        return "", 0, 0
    if front[0] == "g":
        w = 2 * CELL + GAP
        return glyph_svg(front[1], ox, oy) + "\n" + glyph_svg(front[2], ox + CELL + GAP, oy), w, CELL
    if front[0] == "g1":
        return glyph_svg(front[1], ox, oy), CELL, CELL
    if front[0] == "txt":
        fs = 2.2
        t = (f'<text x="{ox:.3f}" y="{oy+fs*0.85:.3f}" font-size="{fs}" font-family="Helvetica, Arial, sans-serif" font-weight="bold">{html.escape(front[1])}</text>\n'
             f'<text x="{ox:.3f}" y="{oy+fs*0.85+fs*1.05:.3f}" font-size="{fs}" font-family="Helvetica, Arial, sans-serif" font-weight="bold">{html.escape(front[2])}</text>')
        return t, 8, fs * 2.1
    return "", 0, 0

def svg_doc(body, w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" height="{h:.2f}mm" viewBox="0 0 {w:.3f} {h:.3f}">\n'
            f'<g fill="#000">\n{body}\n</g>\n</svg>\n')

# --------------------------------------------------------------------- outputs
here = os.path.dirname(os.path.abspath(__file__))
rows = []
for val, grp, y, x, u, col, top, top2, front in KEYS:
    fl = fr = ("", "", "")
    ftext = ""
    if front and front[0] == "g":
        fl, fr = g(front[1]), g(front[2])
    elif front and front[0] == "g1":
        fr = g(front[1])
    elif front and front[0] == "txt":
        ftext = f"{front[1]} / {front[2]}"
    rows.append(dict(
        key=val, group=grp, row=ROWNAME[y], x_mm=x, width_u=u, color=col,
        top_main=top, top_upper=top2,
        front_text=ftext,
        front_left_glyph=fl[0], front_left_petscii=(f"${front[1]:02X}" if front and front[0]=="g" else ""), front_left_unicode=fl[1], front_left_desc=fl[2],
        front_right_glyph=fr[0], front_right_petscii=(f"${front[2]:02X}" if front and front[0]=="g" else f"${front[1]:02X}" if front and front[0]=="g1" else ""), front_right_unicode=fr[1], front_right_desc=fr[2],
    ))

with open(os.path.join(here, "legend_map.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

# markdown table
md = ["| key | row | u | color | top (main) | top (upper) | front |", "|---|---|---|---|---|---|---|"]
for r in rows:
    if r["front_text"]:
        fr = r["front_text"]
    elif r["front_left_glyph"] or r["front_right_glyph"]:
        fr = " ".join(p for p in [
            f"{r['front_left_glyph']} ({r['front_left_petscii']})" if r["front_left_glyph"] else "",
            f"{r['front_right_glyph']} ({r['front_right_petscii']})" if r["front_right_glyph"] else ""] if p)
    else:
        fr = ""
    md.append(f"| {r['key']} | {r['row']} | {r['width_u']} | {r['color']} | {r['top_main'].replace(chr(10),' / ')} | {r['top_upper']} | {fr} |")
with open(os.path.join(here, "legend_map.md"), "w") as f:
    f.write("\n".join(md) + "\n")

# per-key front SVGs and a sheet
sheet = []
sx, sy, col_w, row_h, ncol = 4, 4, 34, 9, 6
i = 0
for val, grp, y, x, u, colr, top, top2, front in KEYS:
    body, w, h = front_svg(front)
    if not body:
        continue
    name = val.replace("/", "-").replace("£", "pound").replace("*", "star").replace(":", "colon").replace("@", "at").replace("+", "plus").replace("-", "minus") if val not in ("-",) else "minus"
    with open(os.path.join(here, "fronts", f"{name}.svg"), "w") as f:
        f.write(svg_doc(body, w, h))
    cx = sx + (i % ncol) * col_w; cy = sy + (i // ncol) * row_h
    b, _, _ = front_svg(front, cx + 8, cy)
    label = "↑" if val == "UpArrow" else val
    sheet.append(f'<text x="{cx:.2f}" y="{cy+2.6:.2f}" font-size="2.4" font-family="Helvetica, Arial, sans-serif">{html.escape(label)}</text>\n{b}')
    i += 1
nrows = (i + ncol - 1) // ncol
with open(os.path.join(here, "front_legends_sheet.svg"), "w") as f:
    f.write(svg_doc("\n".join(sheet), sx * 2 + ncol * col_w, sy * 2 + nrows * row_h))


# --------------------------------------------------------------------- decal sheet
# Every front legend at actual size, COPIES times, with faint cut guides and a scale bar.
COPIES = 3
MARGIN = 0.5          # cut guide clearance around each legend, mm
PITCH_X, PITCH_Y = 10.0, 7.0
SHEET_COLS = 18
def decal_sheet(filename, title, guides=True):
  fronts = [(val, front) for val, grp, y, x, u, colr, top, top2, front in KEYS if front]
  cells = []
  for val, front in fronts:
      for _ in range(COPIES):
          cells.append((val, front))
  out = []
  x0, y0 = 8, 12
  for n, (val, front) in enumerate(cells):
      cx = x0 + (n % SHEET_COLS) * PITCH_X
      cy = y0 + (n // SHEET_COLS) * PITCH_Y
      body, w, h = front_svg(front, cx, cy)
      label = "↑" if val == "UpArrow" else val
      out.append(f'<text x="{cx-MARGIN:.3f}" y="{cy-MARGIN-0.35:.3f}" font-size="1.3" fill="#999" font-family="Helvetica, Arial, sans-serif">{html.escape(label)}</text>')
      if guides:
          out.append(f'<rect x="{cx-MARGIN:.3f}" y="{cy-MARGIN:.3f}" width="{w+2*MARGIN:.3f}" height="{h+2*MARGIN:.3f}" fill="none" stroke="#bbb" stroke-width="0.08"/>')
      out.append(body)
  nrows = (len(cells) + SHEET_COLS - 1) // SHEET_COLS
  sw = x0 * 2 + SHEET_COLS * PITCH_X
  sh = y0 + nrows * PITCH_Y + 6
  # scale bar and title
  out.append(f'<text x="{x0}" y="6" font-size="3" font-family="Helvetica, Arial, sans-serif">{html.escape(title)} — print at 100%: bar below is exactly 50 mm</text>')
  out.append(f'<rect x="{x0}" y="7.5" width="50" height="1" fill="#000"/>')
  out.append(f'<text x="{x0+51}" y="8.5" font-size="2.2" font-family="Helvetica, Arial, sans-serif">50 mm</text>')
  with open(os.path.join(here, filename), "w") as f:
      f.write(svg_doc("\n".join(out), sw, sh))
  print(f"{filename}: {len(cells)} legends ({COPIES} copies each), {sw:.0f} x {sh:.0f} mm")

decal_sheet("front_decal_sheet.svg", "C128 keycap front legends")
# UV DTF variant: heavier box outline and 0.8 mm checkerboard cells so every element peels off the film
STROKE, CHK = 0.3, 2
decal_sheet("front_decal_sheet_uvdtf.svg", "C128 keycap front legends (UV DTF)", guides=False)
STROKE, CHK = 0.12, 1


# --------------------------------------------------------------------- cheat sheet
# One printable page (US letter landscape, also fits A4) showing every key with its
# Commodore-key and Shift graphics, for keyboards built without front legends.
def cheat_sheet(filename, include=lambda grp: True):
    PAGE_W, PAGE_H = 279.4, 215.9
    M = 10                                   # page margin
    keys = [k for k in KEYS if include(k[1])]
    x_min = min(k[3] - (k[4] if isinstance(k[4], (int, float)) else 1) * 19.05 / 2 for k in keys)
    x_max = max(k[3] + (k[4] if isinstance(k[4], (int, float)) else 1) * 19.05 / 2 for k in keys)
    y_max = max(k[2] for k in keys) + 19.05 / 2   # rearmost key edge (plate +y)
    y_min = min(k[2] for k in keys) - 19.05 / 2
    SCALE = (PAGE_W - 2 * M) / (x_max - x_min + 2)
    KEY = 18.2                               # drawn key size in keyboard mm
    G = 3.6                                  # glyph box size in keyboard mm
    out = []
    def T(x, y, txt, size, anchor="middle", weight="normal", fill="#000", extra=""):
        out.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}" font-family="Helvetica, Arial, sans-serif" {extra}>{html.escape(txt)}</text>')
    for val, grp, y, x, u, colr, top, top2, front in keys:
        w = (u if isinstance(u, (int, float)) else 1) * 19.05 - (19.05 - KEY)
        h = KEY
        if val == "NumEnter":
            w = KEY; h = 2 * 19.05 - (19.05 - KEY)
        kx, ky = x - w / 2, -y - h / 2       # flip y: page y grows downward, plate +y is rear
        fill = "#8c8c8c" if colr == "dark" else "#f2f0ea"
        out.append(f'<rect x="{kx:.2f}" y="{ky:.2f}" width="{w:.2f}" height="{h:.2f}" rx="1.6" fill="{fill}" stroke="#555" stroke-width="0.3"/>')
        # top legend
        main = {"0 (slashed)": "0", "C= (Commodore logo)": "C=", "ENTER (rotated, reads top to bottom)": "ENTER"}.get(top, top)
        lines = main.split("\n")
        if val == "NumEnter":
            T(x, -y, "ENTER", 3.2, extra=f'transform="rotate(90 {x:.2f} {-y:.2f})"')
        elif val in ("Crsr Vert", "Crsr Horiz"):
            a, b = ("↑", "↓") if val == "Crsr Vert" else ("←", "→")
            T(x, ky + 5, a, 3.2); T(x, ky + 9.2, "CRSR", 2.6); T(x, ky + 13.4, b, 3.2)
        elif top2 and not top2.startswith("↑") and not top2.startswith("←"):
            if val.startswith("F") and len(val) == 2:
                T(kx + 2, ky + 6.5, main, 4, anchor="start"); T(kx + w - 2, ky + h - 3, top2, 4, anchor="end")
            else:
                T(kx + 2.2, ky + 5.6, top2, 4, anchor="start"); T(kx + 2.2, ky + 11.2, main, 4.6, anchor="start")
        else:
            size = 4.6 if len(lines) == 1 and len(main) <= 2 else 3.0 if len(lines) > 1 else 3.2 if len(main) <= 7 else 2.6
            base = ky + (h / 2 if not front else 6.0) + (size * 0.35 if len(lines) == 1 else -size * 0.15)
            for k, ln in enumerate(lines):
                T(x, base + k * size * 1.1, ln, size, weight="bold" if len(main) <= 2 else "normal")
        # front legends under the top legend
        if front and front[0] in ("g", "g1"):
            codes = [front[1], front[2]] if front[0] == "g" else [front[1]]
            total = len(codes) * G + (len(codes) - 1) * 1.0
            gx = x - total / 2
            for c in codes:
                out.append(glyph_svg(c, gx, ky + h - G - 1.6, G))
                gx += G + 1.0
        elif front and front[0] == "txt":
            T(kx + w - 1.6, ky + h - 5.0, front[1], 2.5, anchor="end", weight="bold", fill="#333")
            T(kx + w - 1.6, ky + h - 1.8, front[2], 2.5, anchor="end", weight="bold", fill="#333")
    kb = "\n".join(out)
    # place keyboard: page y grows downward, so the rearmost key (plate y_max) goes at the top
    tx = M + (-(x_min - 1)) * SCALE
    ty = 22 + y_max * SCALE
    body = [f'<g transform="translate({tx:.2f} {ty:.2f}) scale({SCALE:.4f})">{kb}</g>']
    body.append(f'<text x="{M}" y="14" font-size="6" font-weight="bold" font-family="Helvetica, Arial, sans-serif">Commodore 128 keyboard — graphics characters</text>')
    body.append(f'<text x="{PAGE_W - M}" y="14" font-size="3.4" text-anchor="end" font-family="Helvetica, Arial, sans-serif">c128-led-keyboard</text>')
    # legend
    ly = ty - y_min * SCALE + 12
    ex = M
    body.append(glyph_svg(0xB0, ex, ly - 3.2, 3.6)); body.append(glyph_svg(0xC1, ex + 4.6, ly - 3.2, 3.6))
    T2 = lambda x, y, t, sz=3.2, w="normal": body.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{sz}" font-weight="{w}" font-family="Helvetica, Arial, sans-serif">{html.escape(t)}</text>')
    T2(ex + 10, ly, "Under each key: left box = hold the C= key, right box = hold SHIFT.  These are the characters printed on the front of the original keycaps.")
    T2(ex + 10, ly + 5, "Number keys: top word = CONTROL + key sets that color, bottom word = C= + key.  9 / 0 with CONTROL turn reverse video on / off.")
    T2(ex + 10, ly + 10, ("Dark keys are the dark color on the original keyboard.  " if any(k[5] == "dark" for k in keys) else "")
                         + "Keys with nothing underneath have no front legend.")
    with open(os.path.join(here, filename), "w") as f:
        f.write(svg_doc("\n".join(body), PAGE_W, PAGE_H))
    print(f"{filename}: letter landscape")

cheat_sheet("cheat_sheet.svg")
cheat_sheet("cheat_sheet_main_block.svg", include=lambda grp: grp == "main")

print(f"{len(rows)} keys, {i} with front legends")
