"""Aggregate exact fused-cartridge checks while retaining transition/audio limits."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_combat_checkpoints import load, transition
from tools.review_phase_balance import menus
from tools.review_two_player_combat import stable_gaps
from tools.two_player_combat import installed_policy, validate_ports


def bound(root):
    report = bound_report(root/'report.json')
    for name, digest in report.get('artifacts', {}).items():
        if sha(root/name) != digest:
            raise ValueError('Changed report artifact')
    return report


def review(config, out):
    if out.exists():
        raise ValueError('Fresh review required')
    spec = json.loads(config.read_text())
    candidate = Path(spec['candidate'])
    digest = sha(candidate/'native-cpu.sfc')
    sources = {str(config): sha(config), str(Path(__file__)): sha(Path(__file__))}
    data = {}
    for name in ('focused', 'deadline', 'runtime', 'bad_y', 'bad_x', 'audio', 'renderer', 'dma'):
        root = Path(spec[name])
        data[name] = bound(root)
        sources.update(data[name]['sources'])
        sources[str(root/'report.json')] = sha(root/'report.json')
    if any(data[k]['rom_sha256'] != digest for k in ('focused', 'deadline', 'audio', 'dma')):
        raise ValueError('Different qualified ROM')
    if data['runtime']['sources'].get(str(candidate/'native-cpu.sfc')) != digest:
        raise ValueError('Runtime matrix did not execute candidate helper')
    for p in [p for p in data['renderer']['sources'] if p.endswith('/capture.json')]:
        if json.loads(Path(p).read_text())['rom_sha256'] != digest:
            raise ValueError('Different renderer ROM')
    menu = menus(spec['menus'], candidate, sources)
    if set(menu) != {'status', 'cursor', 'repeat', 'choice'}:
        raise ValueError('Missing menu suite')
    campaigns = {}
    with installed_policy():
        for policy, folder in spec['combat'].items():
            root = Path(folder)
            receipt, result, rows, normal = combat.verify_pair(root, policy, 'snes', candidate)
            ports = []
            for kind in ('normal', 'observed'):
                p = root/f'{policy}-snes-{kind}'
                proof = bound_report(p/'two-player.json')
                actual = json.loads((p/'two-port-input.json').read_text())
                if validate_ports(actual, rows, 'snes') != proof['delivery']:
                    raise ValueError('Changed controller evidence')
                ports.append(actual)
                sources.update(proof['sources'])
                observer = bound_report(p/'combat-observer.json')
                sources.update(observer['sources'])
                for name in ('combat-observer.json', 'two-player.json', 'timeline.json', 'audio.wav'):
                    sources[str(p/name)] = sha(p/name)
            if ports[0] != ports[1]:
                raise ValueError('Observer changed port input')
            campaigns[policy] = dict(strict=result, stable=stable_gaps(result, rows, 'snes'),
                                     frames=receipt['frames'])
    if set(campaigns) != set(combat.POLICIES):
        raise ValueError('Missing combat policy')
    control, old = Path(spec['transition_control']), Path(spec['transition_unfused'])
    rc, a = load(control)
    ro, b = load(old)
    if (not rc['passed'] or ro['trial']['variant'] != 'reverse-sprite-fused' or
            ro['trial']['resume_control'] != str(control) or
            ro['trial']['parent_rom_sha256'] != digest or
            rc['initial_registers'] != ro['initial_registers'] or
            (control/'initial.ram').read_bytes() != (old/'initial.ram').read_bytes() or
            (control/'two-port-input.json').read_bytes() != (old/'two-port-input.json').read_bytes()):
        raise ValueError('Unqualified same-state transition comparison')
    transitions = dict(fused=transition(a), unfused=transition(b),
        identical_picture_frames=sum(x['video_sha256'] == y['video_sha256'] for x,y in zip(a,b)),
        identical_pcm_frames=sum(x['audio_sha256'] == y['audio_sha256'] for x,y in zip(a,b)),
        frames=len(a))
    for root, report in ((control,rc), (old,ro)):
        sources.update(report['sources'])
        for name in ('report.json','timeline.json','audio.wav','two-port-input.json'):
            sources[str(root/name)] = sha(root/name)
    meta = json.loads((candidate/'manifest.json').read_text())
    parent = Path(meta['experimental_sprite_fused_copy']['parent'])
    at, count = meta['sweep_driver_rom_offset'], meta['sweep_driver_layout']['engine_bytes']
    image = (candidate/'native-cpu.sfc').read_bytes()
    engine = image[at:at+count]
    if (hashlib.sha256(engine).hexdigest() != meta['spc_sha256'] or
            engine != (parent/'native-cpu.sfc').read_bytes()[at:at+count]):
        raise ValueError('Unexpected sound engine change')
    gates = dict(focused=data['focused']['passed'], deadline_improved=data['deadline']['symptom_improved'],
        helper_runtime=data['runtime']['passed'], bad_coordinate_rejected=not data['bad_y']['passed'],
        bad_register_rejected=not data['bad_x']['passed'], renderer=data['renderer']['passed'],
        dma=data['dma']['passed'], restart_timing=data['audio']['restart_timing_passed'],
        four_room_cadence=data['audio']['route_cadence']['passed'],
        menu_oracles=all(r['passed'] for r in menu.values()),
        unchanged_transition_counters=transitions['fused'] == transitions['unfused'],
        stable_combat=all(not r['stable']['longer_than_two'] for r in campaigns.values()))
    out.mkdir()
    cards = []
    for name, phase in dict(status='status_reopen_visible', cursor='pause_reopen_visible',
                            repeat='shop_after_purchase_5', choice='shop_no_again_idle').items():
        cards.append('<h3>'+html.escape(name)+'</h3><div class="pair">')
        for system in ('nes','snes'):
            source = Path(menu[name]['captures'][system]['path'])/(phase+'.png')
            target = name+'-'+system+'.png'
            shutil.copyfile(source, out/target)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{system}</figcaption></figure>')
        cards.append('</div>')
    audio = Path(spec['audio'])
    for clip in data['audio']['clips']:
        name = clip['label']+'.wav'
        shutil.copyfile(audio/name, out/name)
        sources[str(audio/name)] = sha(audio/name)
    for module in ('review_phase_balance','review_combat_checkpoints','review_two_player_combat',
                   'combat_campaign','two_player_combat','audit_combat_loops','benchmark_report',
                   'check_present_status','check_pause_cursor','check_shop_repeat','check_shop_choice_no'):
        p=Path('tools')/(module+'.py'); sources[str(p)] = sha(p)
    for p in (candidate/'manifest.json', candidate/'native-cpu.sfc', parent/'native-cpu.sfc'):
        sources[str(p)] = sha(p)
    result = dict(rom_sha256=digest, tested_checks=gates, tested_checks_passed=all(gates.values()),
        runtime_cases=data['runtime']['cases'], transition=transitions, combat=campaigns,
        strict_combat_passed=all(r['strict']['passed'] for r in campaigns.values()),
        route_intervals=sum(r['intervals'] for r in data['audio']['route_cadence']['rooms'].values()),
        renderer_frames=data['renderer']['eligible_frames'], dma_transfers=data['dma']['dma_transfers'],
        latest_dma_end=data['dma']['latest_visible_end'], staged_restarts=data['audio']['staged_restarts'],
        full_audio_difference_summary={k:data['audio']['cross_game'][k] for k in
            ('exact_nonaudio_timeline_equal','changed_field_counts','exact_callback_timeline_equal')},
        native_clips=data['audio']['clips'], sources=sources,
        hardware_tested=False, release_ready=False, pop_free_audio_verified=False,
        scope=__doc__+' Sprite CPU code changed; sound-engine bytes are unchanged. '
              'All strict combat/load outliers retained. Identical same-state room-load counters '
              'only show no new regression versus3252, not equivalence to NES loading speed. '
              'Stable combat and route gates do not certify all-game timing. Sound restart '
              'timing does not certify NES waveform fidelity or perceived/physical pop removal.')
    body = '<!doctype html><meta charset="utf-8"><title>Fused sprite build: regression evidence</title>'
    body += '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{flex:1;margin:8px}img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
    body += '<h1>Fused sprite build: regression evidence</h1><p>'+html.escape(result['scope'])+'</p>'
    body += '<p>ROM <code>'+digest+'</code>. Offline qualification only; not deployed.</p>'
    body += '<p>'+str(result['runtime_cases'])+' executed helper cases; bad-coordinate and bad-register controls rejected.</p>'
    body += f'<p>{result["route_intervals"]:,} two-frame route intervals; {result["renderer_frames"]:,} eligible renderer frames without split/stale/coverage failures; {result["dma_transfers"]:,} safe general-DMA envelopes; {result["staged_restarts"]:,} sound restarts pass timing checks.</p>'
    body += '<h2>Combat and transition limits</h2><pre>'+html.escape(json.dumps({p:dict(strict=r['strict']['passed'],stable=r['stable']['frame_histogram']) for p,r in campaigns.items()},indent=2))+'</pre>'
    body += '<p>The old three-frame fighting stall is removed in the exact-start-state replay. '
    body += 'The separate room-load failure remains in strict results: both builds have the same15-frame load interval and following3-frame interval from the identical state.</p>'
    body += f'<p><a href="../{Path(spec["deadline"]).name}/">Exact combat-stall comparison</a> · <a href="../{Path(spec["focused"]).name}/">Next-frame sprite publication</a> · <a href="report.json">All gates, failures and bindings</a></p>'
    body += '<h2>Native audio, not a pop-free verdict</h2><p>Older3065 comparison</p><audio controls src="parent.wav"></audio><p>Fused3303 candidate, same absolute sample bounds</p><audio controls src="trial.wav"></audio>'
    body += '<h2>Menu regressions against original NES</h2>'+''.join(cards)
    (out/'index.html').write_text(body)
    if any(sha(Path(p)) != h for p,h in sources.items()):
        raise ValueError('Changed evidence dependency')
    result['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(gates=gates, strict_combat_passed=result['strict_combat_passed'])))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
