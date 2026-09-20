"""Read-only serialization of failed timed-receiver boot; no restoration."""
import ctypes as C
import json
from pathlib import Path
from tools import benchmark_capture as bench
from tools.capture_sprite_prefix import installed_prefix
from tools.benchmark_report import sha


def main():
    core=Path('.deps/snes9x-voice-2292/libretro/rcr_voice_edge_libretro.so')
    rom=Path('build/timed-receiver-immediate-game-4075/native-cpu.sfc')
    out=Path('build/timed-receiver-boot-state-4077')
    if out.exists():raise ValueError('Fresh output required')
    original=C.CDLL;snaps=[]
    def loader(name,*args,**kw):
        lib=original(name,*args,**kw)
        if name is None or Path(name).resolve()!=core.resolve():return lib
        lib.retro_serialize_size.restype=C.c_size_t
        lib.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];lib.retro_serialize.restype=C.c_bool
        run=lib.retro_run;frame=0
        def step():
            nonlocal frame
            run();frame+=1
            if frame not in (305,320,340,345,400):return
            size=lib.retro_serialize_size();buf=C.create_string_buffer(size)
            if not lib.retro_serialize(buf,size):raise ValueError('Serialization failed')
            path=out/f'frame-{frame}.savestate';path.write_bytes(buf.raw)
            snaps.append(dict(frame=frame,path=str(path),sha256=sha(path)))
        lib.retro_run=step;return lib
    refs=dict(menu=(Path('build/reference-title-05'),600),settings=(Path('build/reference-walk-02'),600),
        story=(Path('build/reference-walk-02'),900),street=(Path('build/reference-walk-02'),1800))
    C.CDLL=loader
    try:
        with installed_prefix('right_08'):bench.capture(core,rom,'snes',refs,out,'traversal-park-single-sweep',True,True)
    finally:C.CDLL=original
    old=Path('build/timed-receiver-immediate-prefix-4076')
    equal=all((old/n).read_bytes()==(out/n).read_bytes() for n in ('timeline.json','audio.wav'))
    (out/'boot-state.json').write_text(json.dumps(dict(snapshots=snaps,primary_equal=equal,
        sources={str(p):sha(p) for p in (Path(__file__),core,rom,old/'timeline.json',old/'audio.wav')},
        scope=__doc__),indent=2)+'\n')
    print(json.dumps(dict(primary_equal=equal,snapshots=snaps)))


if __name__=='__main__':main()
