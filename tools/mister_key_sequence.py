"""Bounded temporary uinput keyboard; run ON MiSTer, not on the workstation.

Only injects keyboard events, with release/destroy in finally. Does not edit
MiSTer settings or start a daemon. Wall-clock timing is not frame-exact input.
Adapted from the user's installed sileval_inject.py uinput layout.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import time

KEYS = dict(up=103,down=108,left=105,right=106,enter=28,esc=1,f12=88,
            a=30,s=31,d=32,f=33,z=44,x=45,c=46,v=47,space=57,
            leftctrl=29,leftalt=56,leftshift=42,tab=15)


def validate(events):
    if not isinstance(events,list) or not 1 <= len(events) <= 200:
        raise ValueError('Need 1..200 bounded key steps')
    total=0
    for step in events:
        if not isinstance(step,dict) or set(step) != {'keys','seconds'}:
            raise ValueError('Each step needs keys and seconds')
        keys,seconds=step['keys'],step['seconds']
        if (not isinstance(keys,list) or any(k not in KEYS for k in keys)
                or len(keys)!=len(set(keys)) or len(keys)>4
                or type(seconds) not in (int,float) or not 0 < seconds <= 5):
            raise ValueError('Invalid keys or duration')
        total+=seconds
    if total>55:raise ValueError('Sequence exceeds55 seconds')
    return total


def run(events):
    validate(events)
    if struct.calcsize('llHHi') != 16 or not Path('/dev/uinput').exists():
        raise ValueError('Run only on the 32-bit MiSTer target')
    settings=Path('/media/fat/config/SNES.CFG')
    before=hashlib.sha256(settings.read_bytes()).hexdigest()
    log=[]
    with open('/dev/uinput','wb',buffering=0) as device:
        fcntl.ioctl(device,0x40045564,1) # UI_SET_EVBIT(EV_KEY)
        for code in KEYS.values():fcntl.ioctl(device,0x40045565,code)
        device.write(struct.pack('80sHHHHi',b'RCR bounded test keyboard',3,1,1,1,0)+bytes(1024))
        fcntl.ioctl(device,0x5501)
        held=set()
        def emit(code,value):device.write(struct.pack('llHHi',0,0,1,code,value))
        def sync():device.write(struct.pack('llHHi',0,0,0,0,0))
        try:
            time.sleep(1)
            origin=time.monotonic()
            for step in events:
                wanted={KEYS[k] for k in step['keys']}
                for code in sorted(held-wanted):emit(code,0)
                for code in sorted(wanted-held):emit(code,1)
                sync();held=wanted
                log.append(dict(keys=step['keys'],seconds=step['seconds'],
                                monotonic_offset=time.monotonic()-origin,utc_epoch=time.time()))
                time.sleep(step['seconds'])
        finally:
            for code in sorted(held):emit(code,0)
            sync()
            time.sleep(.1)
            fcntl.ioctl(device,0x5502)
    return dict(schema='rcr-mister-key-sequence-v1',events=log,
        settings_before=before,settings_after=hashlib.sha256(settings.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Kernel keyboard injection timestamps, not proof of game consumption or frame-exact timing.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('events',help='JSON list of {keys: [...], seconds: number}')
    a=p.parse_args()
    print(json.dumps(run(json.loads(a.events)),indent=2))
