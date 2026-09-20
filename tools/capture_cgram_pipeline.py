"""Observe original/staged palettes and physical CGRAM at every short-prefix frame boundary."""
import argparse
import ctypes as C
import json
from pathlib import Path
import time
from tools import capture_audio_prefix as prefix
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_sprite_prefix import installed_prefix


def snapshot(lib,memory_id):
    if lib.retro_get_memory_size(2)!=131072 or lib.retro_get_memory_size(memory_id)!=512:
        raise ValueError('Missing exact WRAM/CGRAM geometry')
    ram=lib.retro_get_memory_data(2);cg=lib.retro_get_memory_data(memory_id)
    if not ram or not cg:raise ValueError('Null memory query')
    def read(at,n):return C.string_at(ram+at,n).hex()
    return dict(game_ram=read(0,2048),shadow=read(0x13f00,32),prepared_source=read(0x5580,32),
                prepared_bg=read(0x5400,32),prepared_obj=''.join(read(0x5500+i*32,8) for i in range(4)),
                cgram=C.string_at(cg,512).hex())


def capture(build,candidate,reference,out,observed=False):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh output required')
    spec=bound_report(build/'cgram-build.json');core=Path(spec['core'])
    if sha(core)!=spec['core_sha256']:raise ValueError('Changed observer core')
    with installed_prefix('right_08'):baseline,old=verify_capture(reference)
    if baseline['core_sha256']!=(sha(core) if observed else spec['parent_core_sha256']):
        raise ValueError('Wrong same-core control or parent-core compatibility reference')
    rom=candidate/'native-cpu.sfc'
    if sha(rom)!=baseline['rom_sha256']:raise ValueError('Wrong cartridge reference')
    sources=dict(spec['sources'])
    paths=[Path(__file__),build/'cgram-build.json',core,rom,candidate/'manifest.json',
           reference/'capture.json',reference/'timeline.json',reference/'audio.wav']
    sources.update({str(p):sha(p) for p in paths})
    samples=[];original=C.CDLL
    def loader(path):
        if Path(path).resolve()!=core.resolve():raise ValueError('Unexpected library')
        lib=original(path);run=lib.retro_run
        def step():
            run();samples.append(snapshot(lib,spec['memory_id']))
        lib.retro_run=step
        return lib
    verified=time.monotonic()
    try:
        if observed:C.CDLL=loader
        prefix.capture(candidate,core,out)
    finally:C.CDLL=original
    captured=time.monotonic()
    with installed_prefix('right_08'):receipt,rows=verify_capture(out)
    for key in ('system','rom_sha256','scenario_sha256','frames','audio_sha256'):
        if receipt[key]!=baseline[key]:raise ValueError('Changed compatibility/observation: '+key)
    if rows!=old or not receipt['capture_complete'] or any(r['fault'] for r in rows):
        raise ValueError('Changed or faulty primary timeline')
    if observed:
        if len(samples)!=len(rows):raise ValueError('Incomplete snapshot coverage')
        for sample,row in zip(samples,rows):
            if sample.pop('game_ram')!=row['game_ram_hex']:raise ValueError('Wrong snapshot boundary')
            sample['frame']=row['frame']
        payload=out/'palette-pipeline.json';payload.write_text(json.dumps(samples)+'\n');sources[str(payload)]=sha(payload)
    for p in (out/'audio-prefix.json',out/'capture.json',out/'timeline.json',out/'audio.wav'):
        sources[str(p)]=sha(p)
    if any(sha(p)!=h for p,h in sources.items()):raise ValueError('Changed bound source')
    report=dict(sources=sources,observed=observed,observer_neutral=observed,
                parent_core_compatible=not observed,reference=str(reference),frames=len(rows),
                candidate=str(candidate),samples='palette-pipeline.json' if observed else None,
                timing=dict(verify_control_seconds=verified-started,capture_seconds=captured-verified,
                            verify_result_seconds=time.monotonic()-captured),release_ready=False,
                scope=__doc__+' Direct host memory copies only. New-core normal run authenticates '
                'compatibility; observation uses its exact same core and compares every primary frame/nativePCM. '
                'Frame boundaries are not per-scanline palette freshness evidence.')
    (out/'cgram-pipeline.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('observer_neutral','parent_core_compatible','frames','timing')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('build','candidate','reference','out'):parser.add_argument('--'+k,type=Path,required=True)
    parser.add_argument('--observed',action='store_true')
    capture(**vars(parser.parse_args()))
