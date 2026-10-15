#!/bin/bash
# Status of issue #8 long sessions (build/longsession/* and adopted /tmp/long-*).
cd "$(dirname "$0")/.." || exit 1
for d in build/longsession/*/ /tmp/long-b11/ /tmp/long-m21/; do
  [ -f "$d/log.txt" ] || continue
  pid=$(cat "$d/pid" 2>/dev/null); st=done; [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && st="running pid $pid"
  echo "== $d ($st) HIT lines: $(grep -c HIT "$d/log.txt")"
  grep -E "CK emu|SUMMARY|exit=" "$d/log.txt" | tail -n 1 | cut -c1-200
done
