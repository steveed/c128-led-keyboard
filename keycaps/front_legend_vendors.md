# Getting the front legends made — vendor notes

Research notes, September 2026.  The problem: Signature Plastics will make the DCS set with
top legends but will not print the front (typist-facing) face, and the C128 look depends on
the 42 front legends (see [README.md](README.md)).  This page tracks who can do what.

## Status

- **Signature Plastics** — DCS in Commodore colors (GAL/GAW, NN font) for the tops.
  **Quote, 2026-09-18:** $67 per set with top legends only, $95 per set with front-face
  printing as well, both at a **50-set minimum** (so $3,350 or $4,750 up front).  So they
  will front-print after all, at $28 per set over the plain set.  That makes the decision a
  group-buy sizing question rather than a vendor search: fifty sets is roughly the whole
  expected community for a while.  Options: run the buy for the $95 set and be done with front
  legends; or buy the $67 set and let builders add the UV DTF decal sheet below, which costs a
  few dollars per keyboard and is already drawn.  The set includes the **9u spacebar**, so the
  stock plate and the stock stabilizer spacing carry over; the 6.25u plate variant is only for
  builds using a different keycap set.
- **StickerApp UV DTF transfer** — test order placed ($35 / 6 sheets of 126 legends) using
  [`front_decal_sheet_uvdtf.svg`](front_decal_sheet_uvdtf.svg).  Result: *pending.*

## Vendors that print on the front face — but only on their own caps

Nobody found advertises printing on keycaps the customer supplies.

| vendor | caps | method | front legends | custom art | price | notes |
|---|---|---|---|---|---|---|
| [Max Keyboard](https://maxkeyboard.com/shop/cherry-mx-keycaps/custom-color-printed-keycaps/) (Fremont, CA) | OEM profile ABS, their colors | UV print | **yes** — "We could do TOP or FRONT SIDE print" | yes, AI/SVG, full color | singles $10 ($7 at 100+); full set $70, up to 4 print colors, +$20 per extra color | Side-print template on their download page.  "Contact us beforehand" for anything non-standard.  Nothing on the site about supplied caps. |
| [Etsy sellers](https://www.etsy.com/market/custom_print_keycaps), e.g. [this listing](https://www.etsy.com/listing/1542127059/create-your-own-custom-backlit-keycap) | their OEM caps | UV print | yes | yes | per key | One-offs; quality varies. |

## Custom printing, but top-only or wrong profile

| vendor | caps | method | front legends | notes |
|---|---|---|---|---|
| [Thockfactory](https://thockfactory.com/us) | Cherry profile PBT | dye-sub | not offered | custom images OK, sets from ~$10, made in China |
| [FK Custom](https://fkcaps.com/custom) ([review](https://flatfootfox.com/design-your-own-low-profile-keycaps-with-fk-custom/)) | Cherry / DSA / MDA / MBK, their stock | laser engraving | not mentioned | custom SVG upload |
| QWERkeys (UK) | MX caps | laser, engraving + infill, UV | not mentioned | Site unreachable; appears to operate via Facebook.  Listed on the [Deskthority keycap-printing page](https://deskthority.net/wiki/Keycap_printing). |
| [Signature Plastics DCS](https://deskthority.net/wiki/Signature_Plastics_DCS_family) | DCS ABS | double-shot / dye-sub | no | tops only |

## Routes for caps you already own

1. **UV DTF transfer** (StickerApp) — see status above.  Cheap, no film left behind, raised
   cured ink.  Unknown until the test: whether 0.4 mm lines and isolated specks peel cleanly.
2. **Dry-transfer (rub-down) decals** — best-looking decal option for tiny type; single color;
   custom sheets from model-decal shops.  Sheet artwork: [`front_decal_sheet.svg`](front_decal_sheet.svg).
3. **Laser / UV engraving shop** — any trophy or sign shop with a fiber/CO2 laser or flatbed UV
   printer will mark what you bring.  Needs a jig holding a row of DCS caps with the front
   faces level; per-key artwork in [`fronts/`](fronts/).  (Jig can be added to the repo as an
   OpenSCAD part if this route is taken.)
4. **Waterslide decals** — DIY on clear laser waterslide paper; the film edge shows unless cut
   very tight and clear-coated.

## Questions to settle with SP

- Will they sell the set as tops-only in the chosen colors and font, leaving the fronts to us?
- Exact DCS front-face height per row (R1–R4) — sets the glyph box size (`CELL` in
  `legend_map.py`, currently 3.2 mm).
- Would they print on the front for a surcharge / larger run, or subcontract it?
- Minimum quantity and tooling for the two-color set, so a group buy can be sized.

## Questions to ask Max Keyboard

- Will they front-print supplied SP DCS caps?  (Probably not, but ask.)
- Cost of a full custom set, tops + fronts, in two cap colors with the legend map supplied.
