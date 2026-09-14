PYTHON ?= python3
CA65 ?= .deps/cc65/bin/ca65
LD65 ?= .deps/cc65/bin/ld65
SPC_DIR ?= .deps/upernes/source/asm

.PHONY: all bootstrap test verify prepare port
all: build/audio-bringup.sfc

bootstrap:
	$(PYTHON) tools/bootstrap.py

build:
	mkdir -p build

build/bringup.o: snes/bringup.asm $(SPC_DIR)/Memblers_2a03.bin | build
	$(CA65) --bin-include-dir $(SPC_DIR) -g -l build/bringup.lst -o $@ $<

build/audio-bringup.sfc: build/bringup.o snes/lorom.cfg tools/checksum.py
	$(LD65) -C snes/lorom.cfg -m build/bringup.map --dbgfile build/bringup.dbg -o $@ $<
	$(PYTHON) tools/checksum.py $@

test:
	$(PYTHON) -m unittest discover -s tests -v

verify: all test
	$(PYTHON) tools/checksum.py --check build/audio-bringup.sfc

prepare:
	@test -n "$(ROM)" || { echo 'Usage: make prepare ROM="/path/to/River City Ransom (USA).nes"'; exit 1; }
	$(PYTHON) tools/rom.py prepare "$(ROM)"

port:
	@echo 'Gameplay port is not implemented yet; see docs/ROADMAP.md. No game ROM generated.'
	@exit 1
