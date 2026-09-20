"""Current phase80 checks, preserving room-load failures and acoustic limits."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha
from tools.two_player_combat import installed_policy, validate_ports


def review(candidate, campaigns, renderer, cadence, deadline, audio, out):
    if out.exists():
        raise ValueError('Fresh output required')
    digest = sha(candidate/'native-cpu.sfc')
    sources = {}
    data = {}
    for key, root in dict(renderer=renderer, cadence=cadence, deadline=deadline, audio=audio).items():
        report = bound_report(root/'report.json')
        for name, value in report.get('artifacts', {}).items():
            if sha(root/name) != value:
                raise ValueError('Changed artifact')
        sources.update(report['sources'])
        sources[str(root/'report.json')] = sha(root/'report.json')
        data[key] = report
    for key in ('audio', 'deadline'):
        if data[key]['rom_sha256'] != digest:
            raise ValueError('Wrong candidate')
    for name in [p for p in data['renderer']['sources'] if p.endswith('/capture.json')]:
        if json.loads(Path(name).read_text())['rom_sha256'] != digest:
            raise ValueError('Wrong renderer candidate')
    run = data['cadence']['runs']['phase80']
    if run['rom_sha256'] != digest:
        raise ValueError('Wrong cadence candidate')
    for entry in data['cadence']['runs'].values():
        for name, value in entry['sources'].items():
            if sha(Path(name)) != value:
                raise ValueError('Changed cadence dependency')
        sources.update(entry['sources'])
    holds = {p: summarize(v) for p, v in run['phases'].items()}
    details = {}
    with installed_policy():
        for policy in combat.POLICIES:
            receipt, result, rows, normal = combat.verify_pair(campaigns, policy, 'snes', candidate)
            ports = []
            for kind in ('normal', 'observed'):
                folder = campaigns/f'{policy}-snes-{kind}'
                proof = bound_report(folder/'two-player.json')
                actual = json.loads((folder/'two-port-input.json').read_text())
                if validate_ports(actual, rows, 'snes') != proof['delivery']:
                    raise ValueError('Changed two-port delivery')
                ports.append(actual)
                sources.update(proof['sources'])
                sources.update(bound_report(folder/'combat-observer.json')['sources'])
                for name in ('two-player.json', 'combat-observer.json', 'timeline.json', 'audio.wav'):
                    sources[str(folder/name)] = sha(folder/name)
            if ports[0] != ports[1]:
                raise ValueError('Observer altered ports')
            details[policy] = dict(strict=result, including_busy=measure(result, rows), frames=receipt['frames'])
    meta = json.loads((candidate/'manifest.json').read_text())
    parent = Path(meta['experimental_fused_phase80']['parent'])
    start, size = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    engine = (candidate/'native-cpu.sfc').read_bytes()[start:start+size]
    if (engine != (parent/'native-cpu.sfc').read_bytes()[start:start+size] or
            hashlib.sha256(engine).hexdigest() != meta['spc_sha256']):
        raise ValueError('Unexpected SPC change')
    paths = [Path(__file__), Path('tools/audit_busy_combat.py'), Path('tools/audit_uniform_holds.py'),
             Path('tools/combat_campaign.py'), Path('tools/two_player_combat.py'),
             candidate/'native-cpu.sfc', candidate/'manifest.json', parent/'native-cpu.sfc']
    sources.update({str(p): sha(p) for p in paths})
    gates = dict(exact_stall_improved=data['deadline']['symptom_improved'], renderer=data['renderer']['passed'],
                 no_short_camera_jitter=all(not v['short_irregular'] for v in holds.values()),
                 stable_combat_including_busy=all(v['including_busy']['passed'] for v in details.values()),
                 strict_combat=all(v['strict']['passed'] for v in details.values()),
                 four_room_cadence=data['audio']['route_cadence']['passed'],
                 audio_restart_timing=data['audio']['restart_timing_passed'])
    report = dict(rom_sha256=digest, gates=gates, combat=details, holds=holds,
                  audio={k: data['audio'][k] for k in ('packets', 'staged_restarts', 'wrong_first_pitch',
                         'stale_nonzero_onsets', 'restart_timing_passed', 'route_cadence')},
                  sources=sources, release_ready=False, hardware_tested=False, pop_free_verified=False,
                  scope=__doc__+' This candidate changes main-loop admission from line96 to80 on the fused '
                  'sprite parent. It does not change the SPC engine. Actual PCM and DSP restarts are '
                  'tested; restart correctness is not acoustic fidelity. Fresh DMA and menu checks, '
                  'room-load qualification and physical audio remain outstanding.')
    out.mkdir()
    page = '<!doctype html><meta charset="utf-8"><title>Phase80 current checks</title>'
    page += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}pre{white-space:pre-wrap}audio{width:100%}</style>'
    page += '<h1>Phase80: recovered combat update; room loads and audio remain open</h1><p>'+html.escape(report['scope'])+'</p>'
    page += '<pre>'+html.escape(json.dumps(gates, indent=2))+'</pre>'
    for policy, value in details.items():
        page += '<p>'+html.escape(policy+': busy-inclusive intervals '+str(value['including_busy']['frame_histogram'])+
                                  '; strict gate '+str(value['strict']['passed']))+'</p>'
    for label, root in (('Exact-state collage and full native clips', deadline), ('Actual renderer failures', renderer),
                        ('Every displayed park-camera hold, including long stops', cadence)):
        page += '<p><a href="../'+root.name+'/">'+label+'</a></p>'
    page += '<h2>Native audio excerpt — no pop-free claim</h2>'
    for clip in data['audio']['clips']:
        name = clip['label']+'.wav'
        shutil.copyfile(audio/name, out/name)
        sources[str(audio/name)] = sha(audio/name)
        page += '<p>'+html.escape(clip['label'])+'</p><audio controls src="'+name+'"></audio>'
    page += '<p><a href="report.json">Complete strict results, exclusions and source bindings</a></p>'
    (out/'index.html').write_text(page)
    if any(sha(Path(p)) != value for p, value in sources.items()):
        raise ValueError('Changed report dependency')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(gates))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('candidate', 'campaigns', 'renderer', 'cadence', 'deadline', 'audio', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    review(**vars(parser.parse_args()))
