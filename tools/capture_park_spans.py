"""Resolve linked symbols and collect read-only exact-clock producer observations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
POINTS=(('nmi','boot','nmi','00'),('rows','boot','native_prepare','c0'),
        ('palette','boot','prepare_palette','c0'),('sprites','boot','prepare_sprites','c0'),
        ('chr','boot','prepare_tail','c0'),('audio','boot','audio_publish_bridge','c0'),
        ('video_bridge','boot','video_prepare_bridge','c0'),
        ('game_nmi_return','runtime','nmi_rti_return',''),
        ('camera_exit','runtime','camera_deferred_nmi_exit',''),
        ('outside_vblank','runtime','@outside_vblank',''),
        ('game_sound','literal','fa54',''),('game_sound_finish','literal','ff29',''))


def symbols(path):
    result={}
    for row in path.read_text().splitlines():
        _,pc,name=row.split()
        result.setdefault(name.lstrip('.'),[]).append(int(pc,16))
    return result


def capture(candidate,core,out,first,last,scenario='traversal-park-stress'):
    if out.exists():
        raise ValueError('Use a fresh capture directory')
    source={name:symbols(candidate/f'native_{name}.lbl') for name in ('boot','runtime')}
    points=[]
    env=os.environ.copy()
    for name in list(env):
        if name.startswith('RCR_SPAN_PC'):
            env.pop(name)
    for i,(label,kind,symbol,bank) in enumerate(POINTS):
        values=[int(symbol,16)] if kind=='literal' else source[kind].get(symbol,[])
        if len(values)!=1:
            raise ValueError(f'Missing or ambiguous linked timing symbol: {symbol}')
        pc=bank+f'{values[0]:04x}'
        env[f'RCR_SPAN_PC{i}']=pc
        points.append(dict(index=i,label=label,pc=pc))
    ack=out.with_name(out.name+'-ack.csv')
    spans=out.with_name(out.name+'-spans.csv')
    env.update(RCR_PROFILE_FIRST=str(first),RCR_PROFILE_LAST=str(last),
               RCR_SPAN_TRACE=str(spans),RCR_SPC_ACK_TRACE=str(ack))
    subprocess.run([sys.executable,str(ROOT/'tools/benchmark_capture.py'),'--system','snes',
        '--core',str(core),'--rom',str(candidate/'native-cpu.sfc'),'--title',str(ROOT/'build/reference-title-05'),
        '--walk',str(ROOT/'build/reference-walk-02'),'--scenario',scenario,
        '--frame-images','--out',str(out)],check=True,env=env)
    metadata=dict(points=points,first=first,last=last,scenario=scenario,scope='Host-only absolute clocks at linked entry points; no emulated cycles or state writes.',
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            ROOT/'tools/snes9x_span_trace.inc',ROOT/'.deps/snes9x/cpuexec.cpp',
            candidate.resolve()/'native_boot.lbl',candidate.resolve()/'native_runtime.lbl')})
    (out/'span-points.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','core','out'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--first',type=int,default=7535)
    p.add_argument('--last',type=int,default=8105)
    p.add_argument('--scenario',choices=('traversal-park-stress','traversal-park-single-sweep'),
        default='traversal-park-stress')
    a=p.parse_args()
    capture(a.candidate,a.core,a.out,a.first,a.last,a.scenario)
