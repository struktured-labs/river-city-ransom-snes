PYTHON ?= python3
CA65 ?= .deps/cc65/bin/ca65
LD65 ?= .deps/cc65/bin/ld65
SPC_DIR ?= .deps/upernes/source/asm

.PHONY: all bootstrap test verify prepare port playable
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
	@echo 'Gameplay port is not a finished conversion. Named trials: make playable ROM=/path/to/River\ City\ Ransom\ \(USA\).nes BUILD=4108|4163'
	@exit 1

# Experimental 4108/4146/4162/4163. Fails with a named gap when build 3955 or 3800 is absent.
playable:
	@test -n "$(ROM)" || { echo 'Usage: make playable ROM="/path/to/River City Ransom (USA).nes" [BUILD=4108|4146|4162|4163]'; exit 1; }
	$(PYTHON) tools/rebuild_playable.py --rom "$(ROM)" --build "$(or $(BUILD),4163)"
