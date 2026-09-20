"""Capture complete NES store/fetch evidence with the baseline's telemetry."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha,verify_capture


def capture(rom,core,normal,out):
    baseline,rows=verify_capture(normal)
    if (baseline['system']!='nes' or not baseline['capture_complete'] or
            baseline['scenario_name']!='traversal-park-single-sweep' or
            not baseline['frame_images'] or any(len(bytes.fromhex(r['game_ram_hex']))!=2048 for r in rows) or
            'nes_ppu_observer' not in baseline or sha(rom)!=baseline['rom_sha256']):
        raise ValueError('Need original complete RAM/PPU/image baseline')
    render=out.with_name(out.name+'-render.csv');events=out.with_name(out.name+'-store.csv')
    if any(p.exists() for p in (out,render,events)):raise ValueError('Use fresh output paths')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
        Path('tools/fceumm_raster_scroll.inc'),Path('tools/fceumm_queue_trace.inc'),
        normal/'capture.json',rom,core]
    sources={str(p):sha(p) for p in paths}
    env=os.environ.copy()
    if any(k.startswith(('RCR_NES_','RCR_RENDER_')) for k in env):
        raise ValueError('Unexpected inherited observer configuration')
    env.update(RCR_RENDER_SCROLL_TRACE=str(render.resolve()),RCR_RENDER_FIRST='1',
        RCR_RENDER_LAST=str(baseline['frames']),RCR_NES_EVENT_TRACE=str(events.resolve()),
        RCR_NES_TRACE_FIRST='1',RCR_NES_TRACE_LAST=str(baseline['frames']),
        RCR_NES_EVENT_PC0='f27d',RCR_NES_EVENT_PC1='e2b1',RCR_NES_EVENT_PC2='f282')
    subprocess.run([sys.executable,'tools/benchmark_capture.py','--system','nes',
        '--core',str(core),'--rom',str(rom),'--title','build/reference-title-05',
        '--walk','build/reference-walk-02','--scenario','traversal-park-single-sweep',
        '--frame-images','--full-ram-telemetry','--ppu-telemetry','--out',str(out)],env=env,check=True)
    for name,digest in sources.items():
        if sha(Path(name))!=digest:raise ValueError('Source changed during capture: '+name)
    receipt=out/'capture.json';r=json.loads(receipt.read_text())
    r['route_store_observer']=dict(sources=sources,
        scope='Host-only original main/input/pre-store plus every actual rendered pixel group. '
              'Fresh subprocess; full original baseline RAM/PPU/image telemetry retained.')
    receipt.write_text(json.dumps(r,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('rom','core','normal','out'):parser.add_argument('--'+name,type=Path,required=True)
    capture(**vars(parser.parse_args()))
