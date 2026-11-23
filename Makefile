export UID := $(shell id -u)
export GID := $(shell id -g)

NAME  := C128-keyboard-rev3
BOARD := pcb/$(NAME).kicad_pcb
PLATE := pcb/plate/plate-dual.kicad_pcb
BUILD := build
KICAD := docker compose run --rm kicad kicad-cli

.PHONY: render clean

# 3D renders for the README (published to the renders branch by CI): the switch side, the
# electronics side, an angled view, and the plate.
RENDER := pcb render --quality high --background transparent
render:
	mkdir -p $(BUILD)/render
	$(KICAD) $(RENDER) --side top --width 2400 --height 800 --zoom 2.9 -o $(BUILD)/render/board-top.png $(BOARD)
	$(KICAD) $(RENDER) --side bottom --width 2400 --height 800 --zoom 2.9 -o $(BUILD)/render/board-bottom.png $(BOARD)
	$(KICAD) $(RENDER) --width 2400 --height 1200 --perspective --rotate "-45,0,-20" --zoom 1.35 \
		-o $(BUILD)/render/board-iso.png $(BOARD)
	$(KICAD) $(RENDER) --side top --width 2400 --height 840 --zoom 2.8 -o $(BUILD)/render/plate-top.png $(PLATE)

clean:
	rm -rf $(BUILD)
