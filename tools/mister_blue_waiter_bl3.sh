#!/bin/bash
# Issue #8: start bl3 on bluemage after bl2 exits, only if bluemage is still ours.
# Aborts (no start) if: STOP-bl2 / STOP-bl3 / HANDOVER exists (another bot asked for bluemage),
# a foreign SSH peer is connected, or a core other than RCR_4305e.mgl is loaded.
H=$HOME/rcr-work/hw-blue; cd $HOME/rcr-work/autojoy || exit 1
log() { echo "$(date '+%F %T %Z') $*" >> $H/bl3_waiter.log; }
log "waiting for bl2 pid $(cat $H/bl2.pid)"
while kill -0 "$(cat $H/bl2.pid)" 2>/dev/null; do sleep 60; done
log "bl2 exited"; sleep 30
for f in STOP-bl2 STOP-bl3 HANDOVER; do [ -e $H/$f ] && { log "abort: $f present"; exit 0; }; done
chk=$(ssh -o BatchMode=yes -o ConnectTimeout=15 bluemage 'cat /tmp/CORENAME; echo; ps | grep "[/]media/fat/MiSTer"; netstat -tn | grep ":22 " | grep ESTABLISHED') || { log "abort: bluemage unreachable"; exit 0; }
log "check: $(echo "$chk" | tr '\n' '|')"
echo "$chk" | grep -q "RCR_4305e.mgl" || { log "abort: foreign core loaded"; exit 0; }
if echo "$chk" | grep ":22 " | awk '{print $5}' | grep -v '^192\.168\.1\.157:' | grep -q .; then log "abort: foreign SSH peer"; exit 0; fi
export HW_HOST=bluemage HW_SHOT=mister HW_PADDEV=kbd HW_OUT=$H SEED=33 GRIND=1 REDO=1 WEAP=1 COMBO=1 NEWP=0.3
setsid nohup python3 tools/mister_rcr_blue_loop.py 4000 bl3 > $H/bl3.out 2>&1 < /dev/null &
echo $! > $H/bl3.pid; log "started bl3 pid $!"
