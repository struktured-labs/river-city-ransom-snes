"""Boot-driven game audio prefix through right_15, with same-core controls."""
import argparse
import json
import os
from pathlib import Path
import time

from tools import benchmark_capture as bench
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_sprite_prefix import installed_prefix

LAST_PHASE='right_15'


def capture(candidate,core,out,normal=None):
    started=time.monotonic()
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh capture/clean environment required')
    meta=json.loads((candidate/'manifest.json').read_text())
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed candidate')
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    points={0:labels['gameplay_iteration_start'],1:0xf282,2:labels['camera_deferred_nmi_exit']+2,3:0xf2da}
    paths=[Path(__file__),Path('tools/capture_sprite_prefix.py'),Path('tools/benchmark_capture.py'),
        Path('tools/benchmark_report.py'),Path('tools/capture_combat_instructions.py'),Path('tools/smoke_libretro.py'),
        core,candidate/'manifest.json',candidate/'native-cpu.sfc',candidate/'native_runtime.lbl']
    paths += [Path('tools')/n for n in ('snes9x_dsp_latency.inc','snes9x_pulse_onset.inc','snes9x_main_store.inc')]
    paths += [core.parent.parent/n for n in ('apu/apu.cpp','apu/bapu/smp/core.cpp','apu/bapu/dsp/SPC_DSP.cpp','apu/bapu/dsp/SPC_DSP.h','cpuexec.cpp')]
    sources={str(p):sha(p) for p in paths}
    traces={};env={}
    if normal:
        for key,suffix in [('RCR_DSP_LATENCY_TRACE','dsp.csv'),('RCR_DSP_DAC_PCM','dac.pcm'),
            ('RCR_SPC_SYNTH_TRACE','synth.csv'),('RCR_SPC_GAME_KEYON_TRACE','keyon.csv'),
            ('RCR_SPC_RECEIVE_TRACE','received.csv'),('RCR_AUDIO_BUS_TRACE','bus.csv'),
            ('RCR_PULSE_ONSET_TRACE','onset.csv'),('RCR_MAIN_STORE_TRACE','main.csv')]:
            path=out.with_name(out.name+'-'+suffix)
            if path.exists():raise ValueError('Trace already exists')
            traces[key]=path;env[key]=str(path.resolve())
        env.update({f'RCR_MAIN_STORE_PC{k}':f'{v:04x}' for k,v in points.items()})
    refs=dict(menu=(Path('build/reference-title-05'),600),settings=(Path('build/reference-walk-02'),600),
        story=(Path('build/reference-walk-02'),900),street=(Path('build/reference-walk-02'),1800))
    try:
        os.environ.update(env)
        with installed_prefix(LAST_PHASE):
            bench.capture(core,candidate/'native-cpu.sfc','snes',refs,out,'traversal-park-single-sweep',
                frame_images=True,full_ram_telemetry=True)
            receipt,rows=verify_capture(out)
            if normal:
                old,prior=verify_capture(normal)
                if old['core_sha256']!=sha(core):raise ValueError('Different observer core')
                equivalent(receipt,rows,old,prior)
    finally:
        for k in env:os.environ.pop(k,None)
    if not receipt['capture_complete'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Incomplete/faulty prefix')
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed capture source')
    if normal:
        if any(not p.stat().st_size for p in traces.values()):raise ValueError('Empty observer output')
        receipt['dsp_latency_observer']=dict(sources=sources,traces={k:dict(path=str(p),sha256=sha(p)) for k,p in traces.items()
            if k not in ('RCR_PULSE_ONSET_TRACE','RCR_MAIN_STORE_TRACE')},scope=__doc__)
        (out/'capture.json').write_text(json.dumps(receipt,indent=2)+'\n')
        sources.update({str(p):sha(p) for p in traces.values()})
        sources[str(normal/'capture.json')]=sha(normal/'capture.json')
    sources.update({str(out/n):sha(out/n) for n in ('capture.json','timeline.json','audio.wav')})
    report=dict(sources=sources,candidate=str(candidate),core=str(core),normal=str(normal) if normal else None,
        observed=bool(normal),observer_neutral=bool(normal),frames=len(rows),last_phase=LAST_PHASE,
        traces={k:str(p) for k,p in traces.items()},elapsed_seconds=time.monotonic()-started,
        scope=__doc__+' Explicitly shortened scenario, not full route; no state restoration or RAM writes.')
    (out/'volume-prefix.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows),seconds=report['elapsed_seconds'],observed=bool(normal))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--normal',type=Path)
    capture(**vars(p.parse_args()))
