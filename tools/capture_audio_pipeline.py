"""Fresh current-cartridge CPU stage clocks plus the existing actual SPC/DSP observer."""
import argparse
import json
import os
from pathlib import Path

from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_dsp_latency import capture as dsp_capture
from tools.capture_park_spans import symbols


def points(candidate):
    boot = symbols(candidate/'native_boot.lbl')
    runtime = symbols(candidate/'native_runtime.lbl')
    rom = (candidate/'native-cpu.sfc').read_bytes()

    def unique(table, name):
        values = table.get(name, [])
        if len(values) != 1:
            raise ValueError('Ambiguous or missing symbol: '+name)
        return values[0]

    bridge = unique(boot, 'audio_publish_bridge')
    sender = unique(boot, 'spc_frame')
    # Check the actual code shape rather than inheriting an old local-label PC.
    sendcode = rom[sender:sender+128]
    if not sendcode.startswith(bytes.fromhex('a97d2053d2')):
        raise ValueError('Sender entry shape changed')
    def locate(block, pattern):
        raw = bytes.fromhex(pattern)
        if block.count(raw) != 1:
            raise ValueError('Nonunique machine-code boundary: '+pattern)
        return block.index(raw)
    byte = sender+locate(sendcode, 'b9000a8d4121')
    done = sender+locate(sendcode, 'a017001860')
    bridgecode = rom[bridge:bridge+80]
    bridge_return = bridge+locate(bridgecode, 'ab2b7afa68286b')+6
    for bank in range(1, 9):
        if rom[bank*65536+0xfa54:bank*65536+0xfa65] != bytes.fromhex(
                'adffbf48a90520d1fe2003806820d1fe60'):
            raise ValueError('Original sound wrapper changed')
    pairs = [('driver_entry', 'fa54'), ('driver_return', 'fa64'),
        ('bridge_entry', f'c0{bridge:04x}'), ('sender_entry', f'c0{sender:04x}'),
        ('sender_byte', f'c0{byte:04x}'), ('sender_done', f'c0{done:04x}'),
        ('bridge_return', f'c0{bridge_return:04x}'),
        ('early_audio', f'{unique(runtime,"early_gameplay_audio"):04x}'),
        ('game_nmi_return', f'{unique(runtime,"nmi_rti_return"):04x}'),
        ('hardware_nmi', f'00{unique(boot,"nmi"):04x}'),
        ('original_nmi', 'ff4f'),
        ('video_publish', f'c0{unique(boot,"publish_video"):04x}'),
        ('camera_exit', f'{unique(runtime,"camera_deferred_nmi_exit"):04x}')]
    return [dict(index=i, label=label, pc=pc) for i, (label, pc) in enumerate(pairs)]


def capture(core, candidate, control, out):
    if any(key.startswith('RCR_') for key in os.environ):
        raise ValueError('Inherited instrumentation overrides forbidden')
    if out.exists():
        raise ValueError('Fresh output required')
    baseline, previous = verify_capture(control)
    if baseline['core_sha256'] != sha(core):
        raise ValueError('Require the same core as control')
    wanted = points(candidate)
    for marker in (b'RCR_SPAN_TRACE', b'RCR_SPC_ACK_TRACE', b'RCR_DSP_LATENCY_TRACE'):
        if marker not in core.read_bytes():
            raise ValueError('Core lacks observer: '+marker.decode())
    sources = {str(p): sha(p) for p in (Path(__file__),
        Path('tools/capture_park_spans.py'), Path('tools/capture_combat_instructions.py'),
        Path('tools/capture_dsp_latency.py'), Path('tools/snes9x_span_trace.inc'),
        Path('tools/snes9x_cpu_profile.inc'), Path('.deps/snes9x/cpuexec.cpp'),
        core, candidate/'native-cpu.sfc', candidate/'native_boot.lbl',
        candidate/'native_runtime.lbl', candidate/'manifest.json',
        control/'capture.json', control/'timeline.json', control/'audio.wav')}
    paths = {key: out.with_name(out.name+suffix) for key, suffix in
             (('RCR_SPAN_TRACE', '-spans.csv'), ('RCR_SPC_ACK_TRACE', '-ack.csv'))}
    if any(p.exists() for p in paths.values()):
        raise ValueError('Trace output exists')
    env = {key: str(p.resolve()) for key, p in paths.items()}
    env.update(RCR_PROFILE_FIRST='0', RCR_PROFILE_LAST=str(baseline['frames']+1))
    env.update({f'RCR_SPAN_PC{p["index"]}': p['pc'] for p in wanted})
    try:
        os.environ.update(env)
        dsp_capture(core, candidate/'native-cpu.sfc', out)
    finally:
        for key in env:
            os.environ.pop(key, None)
    receipt, rows = verify_capture(out)
    equivalent(receipt, rows, baseline, previous)
    for path, digest in sources.items():
        if sha(Path(path)) != digest:
            raise ValueError('Source changed: '+path)
    for p in paths.values():
        if not p.stat().st_size:
            raise ValueError('Empty trace')
        sources[str(p)] = sha(p)
    sources[str(out/'capture.json')] = sha(out/'capture.json')
    report = dict(observer_neutral=True, points=wanted, sources=sources,
        scope='Full fresh-process input/RAM/video/PCM equality against same-core DSP control. '
        'CPU absolute elapsed clocks include DMA and interrupts; no CPU/SPC epoch fit. '
        'Existing core observers only; no emulator or cartridge mutation.')
    (out/'pipeline-capture.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows), observer_neutral=True, points=wanted)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'candidate', 'control', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    capture(**vars(parser.parse_args()))
