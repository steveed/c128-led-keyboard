# Spacebar offset adapter

Puts the C128's own spacebar on the rev 3 board's Cherry PCB-mount stabilizers.

The original Mitsumi spacebar has its two stabilizer sockets **125.35 mm** apart, and the
rev 2.3 board drilled its stabilizers there.  Rev 3 drills the standard MX spacings instead,
**133.35 mm** for a 9u bar and 100 mm for a 6.25u (`SPACEBAR_STABS` in `pcb/tools/gen_fp.py`),
so a standard MX 9u keycap fits.  This adapter bridges the 4 mm difference on each side.

It is [the-c128-keyboard-project](https://codeberg.org/jflitton/the-c128-keyboard-project)'s
`adapter_mitsumi_spacebar_to_cherry_stabilizer` (by Jeff Flitton, CC-BY-SA 4.0), rebuilt
in OpenSCAD from that part's measurements with its MX socket moved 4 mm along the bar:

- the **plug** on top goes into the bar's stabilizer socket, as on the original;
- a **bridge** at the original block's height (2.1 mm thick) carries it 4 mm outward;
- the **MX socket** underneath takes the Cherry stabilizer insert's stem there.

At full travel the bridge stays 3.6 mm above the insert's top, as the original block does, so
it should clear the stabilizer housing it now passes over.

## Files

| File | What |
|---|---|
| `adapter.scad` | the model; every dimension is a named constant at the top |
| `stl/offset_adapter_left.stl` | for the left stabilizer (socket offset to the left) |
| `stl/offset_adapter_right.stl` | for the right stabilizer |

`make adapters` at the repository root rebuilds the STLs in the OpenSCAD container.

## Test fit

**Tested 2026-11-23**: the committed STLs fit and work, on Cherry stabilizers at 133.35 mm
(an MX Amiga keyboard's 9u spacebar mount).  To check a new print, any Cherry-stabilized 9u
board will do:

1. Print one pair upright, socket down, in PETG or a resin; 0.12-0.16 mm layers.
2. Push each plug into the bar's socket.  The plug's long arm is wider on one side, so it
   goes in one way only; if the bridge then runs across the bar instead of along it, rebuild
   with `-D offset_axis="y"`.
3. Seat the bar on the stabilizers and press it fully, at the ends and in the middle.  Watch
   for the bridge touching the bar's underside (ribs near the sockets) or the stabilizer
   housing, and for the bar binding or rattling.
4. A tight socket: raise `clear` (0.05-0.10 mm on FDM).  Loose: a resin print, or `clear`
   below zero.
