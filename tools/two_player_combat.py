"""Input-only two-player combat stress, with both controller ports recorded.

Extends the existing combat policies without editing historical harnesses.
P1 selects 2P through the menu. P2 mirrors attack/direction inputs, never Start
or Select. No RAM writes, saves, frame skipping or emulator speed override.
"""
import argparse
from contextlib import contextmanager
import ctypes as C
from copy import deepcopy
import json
import os
from pathlib import Path

from tools import combat_campaign as combat
from tools.benchmark_report import sha, verify_capture

BASE_SCENARIO = combat.scenario
INPUT = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


def scenario(policy):
    phases = deepcopy(BASE_SCENARIO(policy))
    at = next(i for i,p in enumerate(phases) if p['name']=='open_settings')
    phases[at:at] = [dict(name='select_two_players',frames=6,buttons=['Down']),
                    dict(name='release_two_player_select',frames=12)]
    return phases


@contextmanager
def installed_policy():
    old = combat.scenario
    combat.scenario = scenario
    try:
        yield
    finally:
        combat.scenario = old


def mirror_input(callback, port, device, index, ident):
    if port == 1 and device == 1 and index == 0:
        return 0 if ident in (2,3) else callback(0,device,index,ident)
    return callback(port,device,index,ident)


@contextmanager
def two_ports(core_path, frames):
    """Wrap only the selected core, and keep C callbacks alive until teardown."""
    original = C.CDLL
    expected = core_path.resolve()
    callbacks = []
    loaded = []

    def library(name,*args,**kwargs):
        core = original(name,*args,**kwargs)
        if not isinstance(name,(str,bytes,os.PathLike)) or Path(os.fsdecode(name)).resolve()!=expected:
            return core
        loaded.append(str(expected))
        setter, run = core.retro_set_input_state, core.retro_run
        setter.argtypes = [INPUT]
        current = None
        failure = []

        def install(callback):
            @INPUT
            def state(port,device,index,ident):
                try:
                    value = mirror_input(callback,port,device,index,ident)
                    if current is None:
                        raise ValueError('Input queried outside retro_run')
                    if device == 1 and index == 0 and port in (0,1):
                        current['queried'][port].add(ident)
                        if value: current['pressed'][port].add(ident)
                    return value
                except Exception as exc:
                    failure.append(str(exc)); return 0
            callbacks.append(state)
            setter(state)

        def execute():
            nonlocal current
            current = dict(queried=[set(),set()],pressed=[set(),set()])
            run()
            if failure: raise ValueError(failure)
            frames.append(dict(frame=len(frames)+1,
                queried=[sorted(x) for x in current['queried']],
                pressed=[sorted(x) for x in current['pressed']]))
            current = None

        core.retro_set_input_state = install
        core.retro_run = execute
        return core

    C.CDLL = library
    try:
        yield
        if loaded != [str(expected)]:
            raise ValueError('Expected exactly one selected core load')
    finally:
        C.CDLL = original


def validate_ports(records, rows, system):
    if system not in ('nes','snes'):
        raise ValueError('Unknown controller mapping')
    # Require the eight logical NES buttons, not unused SNES face/shoulder IDs.
    required = {0,2,3,4,5,6,7,8} if system=='nes' else set(range(8))
    if not records or len(records)!=len(rows):
        raise ValueError('Missing controller frame coverage')
    for record,row in zip(records,rows):
        wanted = row['input_requested']
        if (record['frame']!=row['frame'] or record['pressed']!=[wanted,[k for k in wanted if k not in (2,3)]]
                or any(not required.issubset(set(p)) for p in record['queried'])):
            raise ValueError(f'Wrong/missing two-port input at frame {row["frame"]}')
    return dict(frames=len(records), p2_active_frames=sum(bool(r['pressed'][1]) for r in records))


def capture(system,core,candidate,policy,observed,out):
    frames=[]
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/combat_campaign.py'),
        Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),core)}
    with installed_policy(),two_ports(core,frames):
        combat.capture(system,core,candidate,policy,observed,out)
    with installed_policy(),combat.installed(policy):
        receipt,rows=verify_capture(out)
    # Keep attempted input evidence even if a strict coverage check rejects it.
    (out/'two-port-input.json').write_text(json.dumps(frames,separators=(',',':'))+'\n')
    delivery=validate_ports(frames,rows,system)
    if sources!={p:sha(Path(p)) for p in sources}:
        raise ValueError('Sources changed during run')
    sources.update({str(out/n):sha(out/n) for n in ('capture.json','combat-observer.json','two-port-input.json')})
    report=dict(system=system,policy=policy,observed=observed,delivery=delivery,
        sources=sources,release_ready=False,
        scope=__doc__+' Controller delivery is not proof that P2 entered gameplay; inspect original game state and pictures.')
    (out/'two-player.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(delivery))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    p.add_argument('--policy',choices=combat.POLICIES,required=True)
    p.add_argument('--observed',action='store_true')
    for name in ('core','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
