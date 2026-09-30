# Rev 3 firmware.  Builds run in the ESP-IDF container (see ../docker-compose.yml);
# flashing and the monitor need the USB port and run a small host-side esptool.
#
#   make build        compile (first run pulls the ~2 GB image and takes a few minutes)
#   make build-wokwi  compile the simulator variant into build-wokwi/ (see wokwi/README.md)
#   make sim          run the simulator build headless in wokwi-cli, console on this terminal
#   make sim-test     run wokwi/smoke.scenario.yaml against the simulator build (CI-style pass/fail)
#   make menuconfig   ESP-IDF configuration UI
#   make flash        write bootloader + partitions + app over the devkit's USB port
#   make monitor      serial console at 115200 (quit: ctrl-a then k)
#   make clean

COMPOSE := docker compose -f ../docker-compose.yml
PORT    ?= $(firstword $(wildcard /dev/cu.usbmodem*))
VENV    := .venv
ESPTOOL := $(VENV)/bin/esptool.py
# wokwi-cli binary from https://github.com/wokwi/wokwi-cli/releases; needs WOKWI_CLI_TOKEN
# (wokwi.com/dashboard/ci) in the environment
WOKWI   ?= $(firstword $(wildcard $(HOME)/.wokwi/bin/wokwi-cli) wokwi-cli)

build:
	$(COMPOSE) run --rm idf idf.py build

# simulator build: UART console, columns driven straight from GPIO (no decoder), own build dir
build-wokwi:
	$(COMPOSE) run --rm idf idf.py -B build-wokwi -DSDKCONFIG=build-wokwi/sdkconfig -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.wokwi" -DMATRIX_DIRECT_COLUMNS=1 build

sim: build-wokwi
	$(WOKWI) --interactive --timeout 0 wokwi/

sim-test: build-wokwi
	$(WOKWI) --timeout 30000 --scenario smoke.scenario.yaml wokwi/

menuconfig:
	$(COMPOSE) run --rm idf idf.py menuconfig

clean:
	$(COMPOSE) run --rm idf idf.py fullclean

$(ESPTOOL):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet esptool

flash: $(ESPTOOL)
	@test -n "$(PORT)" || (echo "no /dev/cu.usbmodem* found; plug the devkit's USB port (not UART) in, or pass PORT=" && exit 1)
	$(ESPTOOL) --chip esp32s3 --port $(PORT) --baud 921600 write_flash \
	    0x0 build/bootloader/bootloader.bin \
	    0x8000 build/partition_table/partition-table.bin \
	    0x10000 build/c128kb.bin

monitor:
	@test -n "$(PORT)" || (echo "no /dev/cu.usbmodem* found" && exit 1)
	screen $(PORT) 115200

keymap:
	python3 tools/gen_keymap.py

.PHONY: build build-wokwi sim sim-test menuconfig clean flash monitor keymap
