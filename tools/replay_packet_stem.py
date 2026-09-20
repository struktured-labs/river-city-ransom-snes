"""Host-mixer stems of authenticated physical-command replay; never a normal mix."""
import argparse
import json
import os
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.capture_audio_stem import isolated, options_for
from tools.replay_spc_packets import execute


def run(core, fixture, normal, mode, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    base = bound_report(normal/'report.json')
    spec = bound_report(fixture/'manifest.json')
    if not base['passed'] or base['sources'].get(str(core)) != sha(core):
        raise ValueError('Need complete same-core replay control')
    if base['sources'].get(str(fixture/'player.sfc')) != spec['rom_sha256']:
        raise ValueError('Different replay cartridge')
    paths = [Path(__file__), Path('tools/capture_audio_stem.py'),
             Path('tools/replay_spc_packets.py'), Path('tools/smoke_libretro.py'),
             core, fixture/'manifest.json', fixture/'player.sfc', normal/'report.json']
    sources = {str(p): sha(p) for p in paths}
    with isolated('snes', mode) as queries:
        execute(core, fixture, out)
    result = bound_report(out/'report.json')
    if not result['passed'] or any(result[k] != base[k] for k in ('frames', 'packets')):
        raise ValueError('Incomplete or different replay')
    # Mixer masks must not alter command timing, CPU state, WRAM, or picture.
    equal = {name: sha(out/name) == sha(normal/name)
             for name in ('timeline.json', 'memory.ram', 'last.png')}
    if not all(equal.values()):
        raise ValueError('Voice isolation changed nonaudio execution')
    if queries != {k.decode(): v.decode() for k, v in options_for('snes', mode).items()}:
        raise ValueError('Unapplied mixer options')
    for name in ('audio.wav', 'timeline.json', 'memory.ram', 'last.png', 'report.json'):
        sources[str(out/name)] = sha(out/name)
        sources[str(normal/name)] = sha(normal/name)
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Source changed during stem capture')
    binding = dict(mode=mode, same_core=True, nonaudio_equal=equal, options_queried=queries,
        post_load_update_delivered=True, sources=sources, release_ready=False,
        scope='Host mixer voice masking only. Original fixture, packet stream and replay timing unchanged. '
        'Complete nonaudio output equals same-core control; native stem audio differs intentionally. '
        'Not an altered production cartridge, physical isolated channel, NES fidelity or pop-free proof.')
    (out/'stem.json').write_text(json.dumps(binding, indent=2)+'\n')
    print(json.dumps(dict(mode=mode, nonaudio_equal=equal)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'fixture', 'normal', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--mode', choices=('noise', 'without-noise', 'triangle', 'without-triangle'), required=True)
    run(**vars(p.parse_args()))
