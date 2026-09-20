"""Authenticate queued-event recovery without hiding remaining combat/audio limits."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha, verify_capture
from tools.frame_audit import verify_frame
from tools.review_phase_balance import menus
from tools.review_retained_producer import authenticated_replay, compare
from tools.two_player_combat import installed_policy, validate_ports


def review(config, out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = json.loads(config.read_text())
    candidate, control = Path(spec['candidate']), Path(spec['control'])
    sources = {}

    def bind(path):
        record = bound_report(path)
        sources.update(record['sources'])
        sources[str(path)] = sha(path)
        def artifacts(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in ('artifacts', 'mutant_artifacts'):
                        for name, digest in child.items():
                            p = Path(name) if name.startswith('build/') else path.parent/name
                            if sha(p) != digest:
                                raise ValueError('Changed artifact: '+str(p))
                            sources[str(p)] = digest
                    else:
                        artifacts(child)
            elif isinstance(value, list):
                for child in value:
                    artifacts(child)
        artifacts(record)
        return record

    before, old = authenticated_replay(control)
    bind(control/'report.json')
    if not before['passed']:
        raise ValueError('Failed same-ROM control')
    arms, replay_rows = {}, {}
    for name, raw in spec['arms'].items():
        folder = Path(raw)
        after, rows = authenticated_replay(folder)
        bind(folder/'report.json')
        if (not after['cross_rom_restore_verified'] or
                after['trial']['resume_control'] != str(control) or
                after['initial_registers'] != before['initial_registers'] or
                (folder/'initial.ram').read_bytes() != (control/'initial.ram').read_bytes()):
            raise ValueError('Different or unauthenticated starting state')
        causal = compare(old, rows, 2239)
        arms[name] = dict(comparison=causal, recovered=all(causal['gates'].values()),
                          rom_sha256=after['trial']['trial_rom_sha256'])
        replay_rows[name] = rows
    if arms['combined']['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different combined replay cartridge')
    proofs = {k:bind(Path(spec[k])) for k in ('oracle', 'priority', 'events', 'renderer_audit', 'dsp')}
    for key in ('oracle', 'priority', 'events'):
        if not proofs[key]['passed'] or proofs[key]['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
            raise ValueError('Failed or mismatched candidate proof: '+key)
    if not proofs['renderer_audit']['passed']:
        raise ValueError('Failed rendered-camera audit')
    for side in ('candidate', 'baseline'):
        for name, digest in proofs['dsp'][side]['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed DSP source: '+name)
        sources.update(proofs['dsp'][side]['sources'])
    if proofs['dsp']['candidate']['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different DSP cartridge')
    campaigns = Path(spec['campaigns'])
    with installed_policy():
        receipt, strict, rows, _ = combat.verify_pair(campaigns, 'running-jumps', 'snes', candidate)
    logs = []
    for kind in ('normal', 'observed'):
        folder = campaigns/f'running-jumps-snes-{kind}'
        bind(folder/'combat-observer.json')
        port = bind(folder/'two-player.json')
        log = json.loads((folder/'two-port-input.json').read_text())
        if validate_ports(log, rows, 'snes') != port['delivery']:
            raise ValueError('Changed actual controller inputs')
        logs.append(log)
    if logs[0] != logs[1]:
        raise ValueError('Observer changed actual inputs')
    busy = measure(strict, rows)
    display = observe(Path(spec['renderer']), Path(spec['route']), 'snes')
    if display['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different rendered cartridge')
    sources.update(display['sources'])
    holds = {name:summarize(phase) for name, phase in display['phases'].items()}
    menu_results = menus(spec['menus'], candidate, sources)
    out.mkdir(parents=True)
    cards, menu_cards, clips = [], [], []
    def picture(folder, row, label, target):
        source = verify_frame(folder, row)
        name = f'panel-{len(cards)+len(menu_cards)}.png'
        shutil.copy2(source, out/name)
        sources[str(source)] = sha(source)
        target.append(f'<figure><img src="{name}"><figcaption>{html.escape(label)}</figcaption></figure>')
    for name, folder, rows in (('parent', control, old),
            ('combined', Path(spec['arms']['combined']), replay_rows['combined'])):
        for row in rows:
            if row['frame'] in (2237, 2238, 2239, 2240):
                picture(folder, row, f'{name} · {row["frame"]}', cards)
        source = folder/'audio.wav'
        shutil.copy2(source, out/(name+'.wav'))
        sources[str(source)] = sha(source)
        clips.append(dict(file=name+'.wav', source=str(source), sha256=sha(source)))
    for name, phase in (('status','status_visible'), ('cursor','pause_reopen_visible'),
                         ('repeat','shop_second_confirm'), ('choice','shop_no_result')):
        folder = Path(menu_results[name]['captures']['snes']['path'])
        _, rows = verify_capture(folder)
        row = [r for r in rows if r['phase']==phase][-1]
        picture(folder, row, phase, menu_cards)
    modules = ('review_phase_balance', 'review_retained_producer', 'audit_busy_combat',
               'audit_display_cadence', 'audit_uniform_holds', 'frame_audit',
               'check_present_status', 'check_pause_cursor', 'check_shop_repeat',
               'check_shop_choice_no', 'benchmark_report', 'combat_campaign', 'two_player_combat')
    paths = [Path(__file__), config]+[Path('tools')/(m+'.py') for m in modules]
    sources.update({str(p):sha(p) for p in paths})
    for name, digest in sources.items():
        if sha(Path(name)) != digest:
            raise ValueError('Changed source: '+name)
    report = dict(arms=arms, proofs=proofs, combat=dict(strict=strict, including_busy=busy,
        frames=receipt['frames']), display=display, holds=holds, menus=menu_results, clips=clips,
        sources=sources, release_ready=False, physical_verified=False, pop_free_verified=False,
        original_speed_parity_verified=False, scope=__doc__+' Queued service is real-event-backed, '
        'but late audio publication and a fresh combat interval remain. No full-game or hardware certification.')
    order = proofs['events']['order']
    summary = dict(saved_state={k:v['recovered'] for k,v in arms.items()},
        combat_intervals=busy['frame_histogram'], strict_combat_passed=strict['passed'],
        camera={k:dict(histogram=v['histogram'], short_irregular=len(v['short_irregular'])) for k,v in holds.items()},
        collected_and_served=len(order['services']), audio_packets=len(order['packets']),
        packet_intervals_master_clocks=order['packet_intervals_clocks'])
    audio_html = ''.join(f'<p>{c["file"]}</p><audio controls preload="none" src="{c["file"]}"></audio>' for c in clips)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Queued VBlank recovery</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1120px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Known interrupt stall recovered — broader slowdown still open</h1>'
        '<p>Offline candidate2916. Rival unchanged. The combined event queue, priority guard and faster PPU '
        'stubs complete the affected update on2239 instead of2240, with matching pictures through2240. '
        'All four simpler variants remain recorded failures.</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
        '<h2>What actually executed</h2><p>130 queue-helper cases,104 producer-priority cases, and six deliberate '
        'faults rejected. The same-state instruction trace proves three real VBlank flag acknowledgments and '
        'three subsequent original-interrupt dispatches, each after the previous sound publication returned. '
        'Nine audio sender entries occur once per native event. This does not prove every nonqueued event '
        'dispatches the original body, nor that packets arrive evenly.</p>'
        '<h2>Same-state frames2237–2240</h2><div class="grid">'+''.join(cards)+'</div>'
        '<h2>Menu regressions</h2><p>Original-NES oracles pass for status, pause reopening, repeat purchases, '
        'and YES/NO movement; known broken cursor/purchase controls remain rejected.</p><div class="grid">'+''.join(menu_cards)+'</div>'
        '<h2>Native before/after audio</h2><p>Exact unnormalized90-frame replay WAVs. Different sound timing '
        'is retained. Full-route packet delivery and restart ordering pass, but that is not a pop-free verdict.</p>'+audio_html+
        '<h2>Still not ready to deploy</h2><p>A fresh running/jumping combat run retains one three-frame interval. '
        'Park short-hold cadence is even in both directions; fourteen-frame encounter stops remain in the histogram. '
        'Original NES speed parity, physical scrolling and perceptual audio qualification are still open. '
        'The isolated queue fixture uses controlled task bodies, not the real SPC; integration traces cover sound separately.</p>'
        '<p><a href="report.json">All results, failures, source hashes and limits</a></p>')
    report['artifacts'] = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary, sources=len(sources), artifacts=len(report['artifacts']))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    review(**vars(parser.parse_args()))
