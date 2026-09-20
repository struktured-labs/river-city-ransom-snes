"""Bind the focused sprite improvement to the exact cartridge's broader checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_phase_balance import menus


def review(candidate, focused, negative, audio, renderer, dma, menu_config, out):
    if out.exists(): raise ValueError('Fresh review required')
    roots = dict(focused=focused, negative=negative, audio=audio, renderer=renderer, dma=dma)
    data = {k: bound_report(p/'report.json') for k, p in roots.items()}
    digest = sha(candidate/'native-cpu.sfc'); sources = {}
    for key, report in data.items():
        sources.update(report['sources']); sources[str(roots[key]/'report.json')] = sha(roots[key]/'report.json')
        if key in ('focused', 'audio', 'dma') and report['rom_sha256'] != digest:
            raise ValueError('Different qualified cartridge')
    receipts = [Path(p) for p in data['renderer']['sources'] if p.endswith('/capture.json')]
    if len(receipts) != 2 or any(json.loads(p.read_text())['rom_sha256'] != digest for p in receipts):
        raise ValueError('Different renderer cartridge')
    if len({json.loads(p.read_text())['core_sha256'] for p in receipts}) != 1:
        raise ValueError('Renderer control must use same core')
    if data['negative']['passed'] or data['negative']['gates']['every_known_generation_displayed_next_frame']:
        raise ValueError('Broken sprite control survived')
    meta = json.loads((candidate/'manifest.json').read_text()); image = (candidate/'native-cpu.sfc').read_bytes()
    at = meta['sweep_driver_rom_offset']; size = meta['sweep_driver_layout']['engine_bytes']
    parent = Path(meta['experimental_sprite_copy_prepare']['parent'])
    if image[at:at+size] != (parent/'native-cpu.sfc').read_bytes()[at:at+size]:
        raise ValueError('Sprite candidate also changed the sound engine')
    if hashlib.sha256(image[at:at+size]).hexdigest() != meta['spc_sha256']:
        raise ValueError('Unbound embedded sound engine')
    menu = menus(json.loads(menu_config.read_text()), candidate, sources)
    gates = dict(focused_sprite=data['focused']['passed'], known_broken_sprite_rejected=True,
        renderer=data['renderer']['passed'], dma=data['dma']['passed'],
        restart_timing=data['audio']['restart_timing_passed'],
        four_room_cadence=data['audio']['route_cadence']['passed'],
        menus=set(menu) == {'status', 'cursor', 'repeat', 'choice'} and all(r['passed'] for r in menu.values()))
    for p in (Path(__file__), Path('tools/review_phase_balance.py'), menu_config,
              candidate/'native-cpu.sfc', candidate/'manifest.json', parent/'native-cpu.sfc'):
        sources[str(p)] = sha(p)
    out.mkdir(); cards = []
    for name, phase in dict(status='status_reopen_visible', cursor='pause_reopen_visible',
                            repeat='shop_after_purchase_5', choice='shop_no_again_idle').items():
        cards.append(f'<h3>{name}</h3><div class="pair">')
        for label in ('nes', 'snes'):
            source = Path(menu[name]['captures'][label]['path'])/(phase+'.png')
            filename = name+'-'+label+'.png'; shutil.copyfile(source, out/filename)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{filename}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    # Retain unchanged native excerpts; the audio audit compares to3065, not3219.
    clips = []
    for clip in data['audio']['clips']:
        name = clip['label']+'.wav'; shutil.copyfile(audio/name, out/name)
        sources[str(audio/name)] = sha(audio/name); clips.append(clip)
    intervals = sum(r['intervals'] for r in data['audio']['route_cadence']['rooms'].values())
    report = dict(rom_sha256=digest, tested_checks=gates, tested_checks_passed=all(gates.values()),
        focused_cycle=data['focused']['timing'], focused_sprite={k: data['focused'][k] for k in ('parent', 'trial')},
        cadence_intervals=intervals, renderer_eligible_frames=data['renderer']['eligible_frames'],
        dma_transfers=data['dma']['dma_transfers'], latest_dma_end=data['dma']['latest_visible_end'],
        staged_restarts=data['audio']['staged_restarts'], menus={k: r['passed'] for k, r in menu.items()},
        sources=sources, native_audio_clips=clips, release_ready=False, hardware_tested=False,
        remaining=['Exact-build two-player stress checks', 'broader sprite and original-NES speed equivalence',
                   'original-NES audio fidelity and physical pop-free audio/video verification'],
        scope=__doc__+' Sprite preparation code changes; SPC bytes unchanged from3219. '
        'Audio/cadence comparison uses older3065, while focused sprite comparison uses3219. '
        'Full cross-ROM differences remain in source reports; no promotion/deployment.')
    body = '<!doctype html><meta charset="utf-8"><title>Sprite-lag fix and faster test cycle</title>'
    body += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}audio{width:100%}</style>'
    body += '<h1>Sprite-lag fix: measured improvement</h1>'
    body += f'<p>ROM <code>{digest}</code>. Offline only; neither MiSTer nor OBS touched.</p>'
    focus = data['focused']; old = focus['parent']; new = focus['trial']
    body += '<p>Sprite-only conversion now runs after the game copies its sprite list. '
    body += f'Observed window {focus["observed_window"]}: parent delay histogram {old["source_to_first_render_histogram"]}, '
    body += f'{len(old["not_rendered_in_window"])} unrendered known generations; trial histogram '
    body += f'{new["source_to_first_render_histogram"]}, {len(new["not_rendered_in_window"])} unrendered '
    body += f'of {new["known_source_generations"]} known generations. Counter/camera/input gates: '
    body += f'{focus["gates"]}, across {focus["prefix_frames"]:,} prefix frames.</p>'
    body += f'<p>Fresh focused cycle: {data["focused"]["timing"]["total_seconds"]:.2f} seconds. '
    body += f'<a href="../{focused.name}/">Before/after collage and exact symptom gates</a>. '
    body += f'<a href="../{negative.name}/">Actual old build correctly fails</a>.</p>'
    body += f'<p>Broader route: {intervals:,} sampled game-loop intervals meet the two-frame cadence; '
    body += f'{report["renderer_eligible_frames"]:,} eligible renderer frames have no missing coverage, splits or stale camera. '
    body += f'{report["dma_transfers"]:,} general DMA envelopes pass; latest visible end line {report["latest_dma_end"]}. '
    body += f'All {report["staged_restarts"]:,} measured sound restarts meet the timing gate.</p>'
    body += '<p>Four menu regressions pass against their NES references; broken cursor/shop controls remain rejected.</p>'
    body += '<p>This is not whole-game speed equivalence or pop-free certification. Two-player stress for this '
    body += 'exact sprite build and physical audio/video remain open. AI P2 is a separate prototype.</p>'
    for clip in clips:
        label = 'older3065 parent' if clip['label'] == 'parent' else 'sprite3252 trial'
        body += f'<p>Native sound excerpt: {label}, identical absolute sample range; no processing.</p>'
        body += f'<audio controls preload="none" src="{clip["label"]}.wav"></audio>'
    body += '<p><a href="report.json">Source-bound current summary</a> · '
    body += f'<a href="../{audio.name}/report.json">Complete audio/timing differences</a></p>'+''.join(cards)
    (out/'index.html').write_text(body)
    if any(sha(Path(p)) != h for p, h in sources.items()): raise ValueError('Changed source')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(gates=gates, intervals=intervals, release_ready=False)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'focused', 'negative', 'audio', 'renderer', 'dma', 'menu-config', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    review(**vars(p.parse_args()))
