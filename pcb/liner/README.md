# Bottom liner

A thin insulating sheet under the PCB, so the switch pins, solder joints and back-side parts
can't touch the flat 128's RF shield, a bench or a hand.  Commodore did the same on the
Amiga 1000 keyboard.  It needs no screws and no holes in the board.  In a printed 128D case
the tray already does this job, so the liner is for flat builds and bare keyboards.

| File | What |
| --- | --- |
| `liner.dxf` | For the cutter: mm, origin at the liner's front left corner.  Layer `CUT` is the die line, layer `TAPE` the foam strips, one closed polyline per contour |
| `liner.pdf` | Dimensioned drawing with a table of every notch, window and tape strip, and the PCB behind it for reference.  1:1 on A2, so a print at 100 % is also a hand-cutting template |
| `plot-theme.json` | The PDF's colors (`make liner` installs it in the container) |
| `liner.kicad_pcb` | The drawing's source, on an A2 sheet |

## Spec

- **Sheet:** Formex GK-17 (0.43 mm polypropylene).  0.4 mm fish paper also works, and
  GK-10 (0.25 mm) if it's stiff enough on the bench.  393.3 x 92.9 mm, corners R3, window
  corners R1, ±0.3 mm.
- **Tape:** 5 strips of double-sided foam tape, 2.3 mm thick and 4 mm wide (985 mm in all),
  laminated to the face that goes against the PCB, with the release liner left on.  3M VHB
  4991 is the reference.  Any 2–2.5 mm foam tape works, and a PE foam mounting tape is
  easier to peel off later than VHB.
- **View:** the drawing and the DXF are seen from the tape side, which is the PCB's own
  front view.  Flip it left to right for the view with the keyboard upside down.

## How it fits

The sheet hangs 2.3 mm below the board on the tape.  That clears the 1.7 mm of switch pins,
so only the tape touches the PCB.

- **Tape:** a few long strips on bare board, as on the A1000.  There are two in the rear
  band, one on each side of the cable header, and one the full width behind the number row.
  One more runs along the last gap before the front edge.  The Return and keypad
  stabilizers break that gap up on the right, so a 92 mm strip one row back carries the
  front-right corner.  Each strip is clear of every pin, pad and back-side part by at least
  0.6 mm.
- **Windows:** every back-side part taller than 1.9 mm gets a window, which leaves at least
  0.4 mm under the sheet for everything else.  Those parts are U1 (the ESP32 and its U.FL
  lead), J1 (USB-C), J2 (the cable header), C5, J3 and J4, SW93 and SW94 (reset and boot,
  so they stay reachable), U6, and D1 and D2.  Windows that reach the rear edge open into
  notches, which also give the USB-C plug, ribbon and antenna lead a way out.
- **Coverage:** the sheet stops at the Z row, where the 128's main board ends and the case
  closes to about 2 mm.  At its front edge there's still about 6 mm under the PCB, against
  the liner's 2.7 mm.

## Fitting

1. Clean the back of the board with isopropyl alcohol where the tape lands.
2. Peel the release liner, line up the rear edge and the notches with J1, J2 and C5, and
   press it down along each strip.

Hand cut: print `liner.pdf` at 100 % on A2 (a print shop, or tiled) and check the 393.3 mm
dimension.  Tape it to the
sheet, cut along the die line, and stick the tape on where the gray strips are.

## Regenerating

Everything comes from the board, so after a layout change:

```sh
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 pcb/tools/gen_liner.py
make liner
```

The generator checks that every strip is clear of every obstacle.  Part heights, tape
thickness, width and margins are constants at the top of `pcb/tools/gen_liner.py`.
