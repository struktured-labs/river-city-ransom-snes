#!/bin/bash
# longsession_run.sh RUNID bsnes|mesen SEED [FRAMES] [ROM] : detached, niced long session.
cd "$(dirname "$0")/.." || exit 1
id=$1 emu=$2 seed=$3 frames=${4:-864000} rom=${5:-build/trial-logo-sfx-4305e/native-cpu.sfc}
dir=$PWD/build/longsession/$id; mkdir -p "$dir"
export SEED=$seed FRAMES=$frames VC_SKIP_PENDING=1 INV_LIB=$PWD/tools/mesen/row_invariant.lua VC_LIB=$PWD/tools/mesen/vis_check.lua
setsid nohup nice -n 15 tools/$emu/run.sh "$rom" tools/mesen/room_bg_long.lua "$dir" 30000 >"$dir/run.out" 2>&1 < /dev/null &
pid=$!; echo "$pid" > "$dir/pid"
setsid nohup tools/longsession_finish.sh "$id" "$dir" "$pid" >/dev/null 2>&1 < /dev/null &
echo "$id pid $pid dir $dir"
