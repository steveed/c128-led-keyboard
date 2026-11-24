export UID := $(shell id -u)
export GID := $(shell id -g)

NAME  := C128-keyboard-rev3
BOARD := pcb/$(NAME).kicad_pcb
PLATE := pcb/plate/plate-dual.kicad_pcb
BUILD := build
KICAD := docker compose run --rm kicad kicad-cli

.PHONY: render models adapters liner clean

# 3D models the KiCad library lacks, fetched for the renders rather than kept in the repo.
# The ESP32-S3-MINI-1U is Espressif's (github.com/espressif/kicad-libraries, CC-BY-SA 4.0
# with KiCad's library exception), pinned to a commit; U1 points at it through
# ${KIPRJMOD}/../build/3dmodels, so pcbnew's 3D viewer shows it too once this has run.
ESPRESSIF_LIB := https://raw.githubusercontent.com/espressif/kicad-libraries/d5b68fd9269c639b3a60681e00b91df33b4db4a3
MODELS := $(BUILD)/3dmodels/ESP32-S3-MINI-1U.STEP
models: $(MODELS)
$(BUILD)/3dmodels/ESP32-S3-MINI-1U.STEP:
	mkdir -p $(dir $@)
	curl -fsSL -o $@ $(ESPRESSIF_LIB)/3dmodels/espressif.3dshapes/ESP32-S3-MINI-1U.STEP

# 3D renders for the README (published to the renders branch by CI): the switch side, the
# electronics side, an angled view, and the plate.
RENDER := pcb render --quality high --background transparent
render: models
	mkdir -p $(BUILD)/render
	$(KICAD) $(RENDER) --side top --width 2400 --height 800 --zoom 2.9 -o $(BUILD)/render/board-top.png $(BOARD)
	$(KICAD) $(RENDER) --side bottom --width 2400 --height 800 --zoom 2.9 -o $(BUILD)/render/board-bottom.png $(BOARD)
	$(KICAD) $(RENDER) --width 2400 --height 1200 --perspective --rotate "-45,0,-20" --zoom 1.35 \
		-o $(BUILD)/render/board-iso.png $(BOARD)
	$(KICAD) $(RENDER) --side top --width 2400 --height 840 --zoom 2.8 -o $(BUILD)/render/plate-top.png $(PLATE)

# Printed parts.  The spacebar offset adapter puts the C128's own spacebar on the board's
# 9u (133.35 mm) stabilizers; one STL per side, committed so they print without tools.
OPENSCAD := docker compose run --rm openscad openscad --backend=manifold --export-format=binstl
ADAPTER  := printables/spacebar_offset_adapter
adapters: $(ADAPTER)/stl/offset_adapter_left.stl $(ADAPTER)/stl/offset_adapter_right.stl
$(ADAPTER)/stl/offset_adapter_left.stl: $(ADAPTER)/adapter.scad
	mkdir -p $(dir $@)
	$(OPENSCAD) -D side=-1 -o $@ $<
$(ADAPTER)/stl/offset_adapter_right.stl: $(ADAPTER)/adapter.scad
	mkdir -p $(dir $@)
	$(OPENSCAD) -D side=1 -o $@ $<

# Bottom liner drawings for a die-cut quote, committed so they need no tools.
# pcb/tools/gen_liner.py (KiCad's bundled python, for pcbnew) writes the liner board and the
# cutter's DXF; this plots the dimensioned drawing (1:1 on A2, so it doubles as a template),
# in the colors of plot-theme.json.
LINER := pcb/liner
LINER_THEME := /tmp/.config/kicad/10.0/colors
liner:
	docker compose run --rm --entrypoint sh kicad -c 'mkdir -p $(LINER_THEME) && \
		cp $(LINER)/plot-theme.json $(LINER_THEME)/liner-plot.json && \
		kicad-cli pcb export pdf --mode-single --include-border-title --theme liner-plot \
		--layers Edge.Cuts,User.1,User.2,User.Drawings -o $(LINER)/liner.pdf $(LINER)/liner.kicad_pcb'

clean:
	rm -rf $(BUILD)
