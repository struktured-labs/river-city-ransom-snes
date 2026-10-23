#!/bin/bash
# usage: tools/bsnes/run.sh ROM SCRIPT.lua OUTDIR [max_seconds]   (headless, no display)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
CORE=${BSNES_CORE:-$HOME/rcr-work/emu/bsnes/bsnes/out/bsnes_libretro.so}
mkdir -p "$3"
env -u DISPLAY -u WAYLAND_DISPLAY RCR_LIB="$HERE/../mesen/lib.lua" PYTHONPATH=$HOME/rcr-work/emu/pylib \
  python3.13 "$HERE/host.py" "$CORE" "$1" "$2" "$3" "${4:-600}" > "$3/log.txt" 2>&1
rc=$?; echo "exit=$rc" >> "$3/log.txt"; exit $rc
