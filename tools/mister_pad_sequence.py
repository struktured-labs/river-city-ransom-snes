"""Bounded evdev injection through Rival's existing, idle USB SNES pad.

No controller mapping/configuration writes, device grabs or background daemon.
Requires exact device ID and idle axes/keys. All owned controls are released
on exit. Linux evdev_write uses input_inject_event; game consumption must be
verified separately in captured video. Timing is wall-clock, not frame-exact.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import signal
import struct
import time

BUTTONS=dict(y=288,b=289,a=290,x=291,l=292,r=293,select=296,start=297)
DIRECTIONS={'left':(0,0),'right':(0,255),'up':(1,0),'down':(1,255)}


def validate(events):
    if not isinstance(events,list) or not 1<=len(events)<=200:raise ValueError('Invalid sequence size')
    total=0
    for step in events:
        if not isinstance(step,dict) or set(step)!={'keys','seconds'}:raise ValueError('Invalid step')
        keys,seconds=step['keys'],step['seconds']
        if (not isinstance(keys,list) or any(not isinstance(k,str) or k not in BUTTONS|DIRECTIONS for k in keys)
                or len(keys)!=len(set(keys)) or len(keys)>4
                or type(seconds) not in (int,float) or not 0<seconds<=5
                or {'left','right'}<=set(keys) or {'up','down'}<=set(keys)):
            raise ValueError('Invalid controls or duration')
        total+=seconds
    if total>55:raise ValueError('Sequence exceeds55 seconds')
    return total


def run(events):
    validate(events)
    if struct.calcsize('llHHi')!=16:raise ValueError('Run only on32-bit MiSTer')
    settings=Path('/media/fat/config/SNES.CFG')
    before=hashlib.sha256(settings.read_bytes()).hexdigest()
    def stop(signum,frame):raise InterruptedError('Release controls on termination')
    signal.signal(signal.SIGTERM,stop)
    log=[]
    with open('/dev/input/event1','r+b',buffering=0) as device:
        identity=struct.unpack('HHHH',fcntl.ioctl(device,0x80084502,bytes(8)))
        axes=[struct.unpack('iiiiii',fcntl.ioctl(device,0x80184540+i,bytes(24))) for i in (0,1)]
        keys=fcntl.ioctl(device,0x80604518,bytes(96))
        if identity!=(3,0x0810,0xe501,0x0110) or any(keys) or any(a[:3]!=(127,0,255) for a in axes):
            raise ValueError('USB device changed or is not idle')
        def emit(kind,code,value):device.write(struct.pack('llHHi',0,0,kind,code,value))
        def apply(wanted):
            for name,code in BUTTONS.items():emit(1,code,int(name in wanted))
            state=[127,127]
            for name in wanted:
                if name in DIRECTIONS:
                    axis,value=DIRECTIONS[name];state[axis]=value
            for axis,value in enumerate(state):emit(3,axis,value)
            emit(0,0,0)
        try:
            origin=time.monotonic()
            for step in events:
                apply(step['keys'])
                log.append(dict(keys=step['keys'],seconds=step['seconds'],
                    monotonic_offset=time.monotonic()-origin,utc_epoch=time.time()))
                time.sleep(step['seconds'])
        finally:
            apply([])
    return dict(schema='rcr-mister-pad-sequence-v1',device_id=identity,events=log,
        settings_before=before,settings_after=hashlib.sha256(settings.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Injected evdev requests with wall-clock timestamps; not frame-exact or proof of game consumption.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('events')
    a=p.parse_args()
    print(json.dumps(run(json.loads(a.events)),indent=2))
