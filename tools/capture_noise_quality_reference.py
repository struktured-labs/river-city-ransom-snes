"""Fresh-process NES packet-state replay with explicit sound quality and RF filter.

No ROM/stimulus changes. An optional existing host filter observer records the
actual quality mode at every output block, not merely the requested option.
"""
import argparse
from contextlib import contextmanager
import ctypes as C
import json
import os
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_noise_packet_reference import stimulus
from tools.replay_nes_apu_stimulus import capture_player
from tools.smoke_libretro import Variable


QUALITIES = ('Low','High','Very High')


@contextmanager
def quality_options(quality):
    if quality not in QUALITIES:raise ValueError('Unknown sound quality')
    options={b'fceumm_sndquality':quality.encode(),b'fceumm_sndlowpass':b'disabled'}
    original,retained,queries=C.CDLL,[],{}
    updated=False
    def loader(path):
        lib=original(path);setter=lib.retro_set_environment
        def register(callback):
            @type(callback)
            def hooked(cmd,data):
                nonlocal updated
                if cmd==17 and not updated:
                    C.cast(data,C.POINTER(C.c_bool))[0]=True;updated=True
                    return True
                if cmd==15:
                    var=C.cast(data,C.POINTER(Variable)).contents
                    if var.key in options:
                        queries[var.key.decode()]=options[var.key].decode()
                        var.value=options[var.key]
                        return True
                return callback(cmd,data)
            retained.append(hooked);setter.argtypes=[type(callback)];setter(hooked)
        lib.retro_set_environment=register
        return lib
    C.CDLL=loader
    try:
        yield queries
        if not updated or queries!={k.decode():v.decode() for k,v in options.items()}:
            raise ValueError('Required quality/RF options not queried after load')
    finally:C.CDLL=original


def run(reference,fixture,core,quality,out,observe=False):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    spec=bound_report(reference/'report.json');bound_report(fixture/'manifest.json')
    if spec['sources'].get(str(fixture/'stream.bin'))!=sha(fixture/'stream.bin'):
        raise ValueError('Different packet-state reference')
    grouped=stimulus((fixture/'stream.bin').read_bytes())
    payload=bytes(v for row in grouped for v in [len(row),*[v for pair in row for v in pair]])
    if len(grouped)!=spec['source_frames'] or payload!=(reference/'stimulus.bin').read_bytes():
        raise ValueError('Different executed state stimulus')
    out.mkdir(parents=True)
    for name in ('player.nes','stimulus.bin'):shutil.copyfile(reference/name,out/name)
    paths=[Path(__file__),Path('tools/build_noise_packet_reference.py'),
        Path('tools/replay_nes_apu_stimulus.py'),Path('tools/smoke_libretro.py'),
        Path('tools/fceumm_filter_observer.inc'),Path('.deps/fceumm/src/filter.c'),
        Path('.deps/fceumm/src/sound.c'),Path('.deps/fceumm/src/drivers/libretro/libretro.c'),
        Path('.deps/fceumm/src/drivers/libretro/libretro_core_options.h'),
        core,reference/'report.json',fixture/'manifest.json',fixture/'stream.bin',
        reference/'player.nes',reference/'stimulus.bin']
    sources={str(p):sha(p) for p in paths}
    traces={}
    if observe:
        traces=dict(samples=str(out/'filter.pcm'),blocks=str(out/'filter.csv'))
        os.environ['RCR_NES_FILTER_PCM']=str((out/'filter.pcm').resolve())
        os.environ['RCR_NES_FILTER_BLOCKS']=str((out/'filter.csv').resolve())
    try:
        with quality_options(quality) as queries:
            capture_player(core,out/'player.nes',out,grouped)
    finally:
        os.environ.pop('RCR_NES_FILTER_PCM',None)
        os.environ.pop('RCR_NES_FILTER_BLOCKS',None)
    # Observer streams are static FILE*s flushed at process exit. Hash/inspect
    # them in a separate audit process, never while this process owns them.
    for name in ('player.nes','stimulus.bin','audio.wav','timeline.json','receipt.json','memory.ram'):
        sources[str(out/name)]=sha(out/name)
    if any(sha(Path(p))!=v for p,v in sources.items()):raise ValueError('Source changed during replay')
    report=dict(passed=True,source_frames=len(grouped),quality=quality,quality_index=QUALITIES.index(quality),
        options_queried=queries,post_load_update_delivered=True,traces=traces,
        scope=__doc__,sources=sources,release_ready=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','fixture','core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--quality',choices=QUALITIES,required=True)
    p.add_argument('--observe',action='store_true')
    run(**vars(p.parse_args()))
