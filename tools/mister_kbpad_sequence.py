"""Bounded pad sequence on a MiSTer without a USB pad (bluemage): a transient uinput
keyboard with VID:PID 4711:0815 (same ids as the lab's misterclaw/mrext devices), mapped to
SNES P1 by config/inputs/SNES_input_4711_0815_v3.map (installed by tools/mister_bluemage_rcr.sh).
Same event schema as mister_pad_sequence.py; all keys released and device destroyed on exit."""
import fcntl, hashlib, json, struct, sys, time
from pathlib import Path
KEYS = dict(right=106, left=105, down=108, up=103, a=45, b=44, x=31, y=30, l=16, r=17, select=54, start=28)
def validate(events):
    if not isinstance(events, list) or not 1 <= len(events) <= 200: raise ValueError('Invalid sequence size')
    tot = 0
    for st in events:
        if not isinstance(st, dict) or set(st) != {'keys', 'seconds'}: raise ValueError('Invalid step')
        if any(k not in KEYS for k in st['keys']) or not 0 < st['seconds'] <= 10: raise ValueError('Invalid step')
        tot += st['seconds']
    if tot > 58: raise ValueError('Too long')
def run(events):
    validate(events)
    log = []
    with open('/dev/uinput', 'wb', buffering=0) as d:
        fcntl.ioctl(d, 0x40045564, 1)
        for c in KEYS.values(): fcntl.ioctl(d, 0x40045565, c)
        d.write(struct.pack('80sHHHHi', b'RCR kbpad', 3, 0x4711, 0x0815, 1, 0) + bytes(1024))
        fcntl.ioctl(d, 0x5501)
        held = set()
        def emit(c, v): d.write(struct.pack('llHHi', 0, 0, 1, c, v))
        def sync(): d.write(struct.pack('llHHi', 0, 0, 0, 0, 0))
        try:
            time.sleep(1.0)
            t0 = time.monotonic()
            for st in events:
                w = {KEYS[k] for k in st['keys']}
                for c in sorted(held - w): emit(c, 0)
                for c in sorted(w - held): emit(c, 1)
                sync(); held = w
                log.append(dict(keys=st['keys'], at=round(time.monotonic() - t0, 3)))
                time.sleep(st['seconds'])
        finally:
            for c in held: emit(c, 0)
            sync(); time.sleep(0.1); fcntl.ioctl(d, 0x5502)
    return dict(schema='rcr-mister-kbpad-sequence-v1', events=log,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
if __name__ == '__main__':
    print(json.dumps(run(json.loads(sys.argv[1]))))
