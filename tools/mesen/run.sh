#!/bin/bash
# Headless Mesen2 test run for the SNES port.
# usage: tools/mesen/run.sh ROM SCRIPT.lua OUTDIR [timeout_s]
# Needs MESEN (default ~/tools/mesen2-rcr/Mesen-src, a Mesen2 2.1.1 build from
# source; the upstream Linux binary aborts on this distro) and xvfb-run.
# Each run gets a fresh Mesen home, so no SRAM or settings carry over.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
MESEN=${MESEN:-$HOME/tools/mesen2-rcr/Mesen-src}
ROM=$(readlink -f "$1"); SCRIPT=$(readlink -f "$2")
export RCR_OUT=$(mkdir -p "$3" && readlink -f "$3")
export RCR_LIB="$HERE/lib.lua"
H=$(mktemp -d /tmp/mesenhome.XXXXXX); mkdir -p "$H/.config/Mesen2"
cat > "$H/.config/Mesen2/settings.json" <<'JSON'
{"Debug": {"ScriptWindow": {"AllowIoOsAccess": true}}, "Snes": {"Port1": {"Type": "SnesController"}, "Port2": {"Type": "SnesController"}}}
JSON
HOME=$H timeout $(( ${4:-300} + 30 )) xvfb-run -a "$MESEN" --testrunner "$ROM" "$SCRIPT" --timeout=${4:-300} > "$RCR_OUT/log.txt" 2>&1
rc=$?; echo "exit=$rc" >> "$RCR_OUT/log.txt"; rm -rf "$H"; exit $rc
