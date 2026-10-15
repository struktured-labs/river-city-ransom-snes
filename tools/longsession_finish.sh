#!/bin/bash
# longsession_finish.sh RUNID SRCDIR PID : wait for PID, copy SRCDIR into build/longsession/RUNID
# (if different), append a summary to the repro log.
cd "$(dirname "$0")/.." || exit 1
id=$1 src=$2 pid=$3 dst=build/longsession/$1
while kill -0 "$pid" 2>/dev/null; do sleep 60; done
[ "$src" != "$dst" ] && { mkdir -p "$dst"; cp -a "$src"/. "$dst"/; }
last=$(grep -E "CK emu|SUMMARY" "$dst/log.txt" | tail -n 1 | cut -c1-260)
nh=$(grep -c "HIT" "$dst/log.txt")
{ echo "- long-session $id ended $(date '+%F %H:%M %Z'): HIT lines $nh; last: \`$last\`"; } >> docs/ROOM-ENTRY-BG-REPRO-LOG.md
