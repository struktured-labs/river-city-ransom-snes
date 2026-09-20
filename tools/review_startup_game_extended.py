"""Bind full-game startup-audio menus/DMA and retained video-stage differences."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_phase_balance import menus


def sprite_cache_cases(before, after):
    if not before or len(before) != len(after):
        raise ValueError('Different state coverage')
    cases = []
    for a, b in zip(before, after):
        if a['frame'] != b['frame']:
            raise ValueError('Different frame identity')
        if a['prepared_oam'] == b['prepared_oam']:
            continue
        cases.append(dict(frame=a['frame'], same_source=a['nes_oam_shadow'] == b['nes_oam_shadow'],
            parent_cache_matches_source=a['cached_oam_source'] == a['nes_oam_shadow'],
            trial_cache_matches_source=b['cached_oam_source'] == b['nes_oam_shadow']))
    counts = Counter((r['same_source'], r['parent_cache_matches_source'],
                      r['trial_cache_matches_source']) for r in cases)
    return dict(cases=cases, populations=[dict(same_source=k[0], parent_current=k[1],
        trial_current=k[2], frames=v) for k, v in sorted(counts.items())],
        scope='End-of-frame source/cache correspondence only. Not actual OAM DMA time, '
              'not a frame-latency bound, and not permission to ignore changed primary frames.')


def review(candidate, prior, dma, video, menu_config, parent_stages, trial_stages, out):
    if out.exists():
        raise ValueError('Fresh combined report required')
    previous = bound_report(prior/'report.json'); timing = bound_report(dma/'report.json')
    picture = bound_report(video/'report.json'); digest = sha(candidate/'native-cpu.sfc')
    if (previous['rom_sha256'] != digest or timing['rom_sha256'] != digest or
            picture['trial_rom_sha256'] != digest or not previous['tested_checks_passed'] or not timing['passed']):
        raise ValueError('Different cartridge or failing prior gates')
    sources = dict(previous['sources'], **timing['sources']); sources.update(picture['sources'])
    spec = json.loads(menu_config.read_text()); results = menus(spec, candidate, sources)
    if set(results) != {'status', 'cursor', 'repeat', 'choice'}:
        raise ValueError('Missing menu coverage')
    stages = []
    for root, expected in ((parent_stages, picture['parent_rom_sha256']), (trial_stages, digest)):
        binding = bound_report(root/'video-stages-capture.json')
        if binding['rom_sha256'] != expected:
            raise ValueError('Wrong video-stage cartridge')
        sources.update(binding['sources'])
        stages.append(json.loads((root/'video-stages.json').read_text()))
    cache = sprite_cache_cases(*stages)
    if len(cache['cases']) != picture['stage_different_frame_counts'].get('prepared_oam', 0):
        raise ValueError('OAM difference population changed')
    out.mkdir(); cards = []
    samples = {'status': 'status_reopen_visible', 'cursor': 'pause_reopen_visible',
               'repeat': 'shop_after_purchase_5', 'choice': 'shop_no_again_idle'}
    for name, phase in samples.items():
        cards.append('<h2>'+html.escape(name+' · '+phase)+'</h2><div class="pair">')
        for label in ('nes', 'snes'):
            root = Path(results[name]['captures'][label]['path']); source = root/(phase+'.png')
            filename = name+'-'+label+'.png'; shutil.copyfile(source, out/filename)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{filename}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    for p in (Path(__file__), Path('tests/test_startup_extended.py'), Path('tools/review_phase_balance.py'),
              menu_config, prior/'report.json', dma/'report.json', video/'report.json',
              parent_stages/'video-stages-capture.json', trial_stages/'video-stages-capture.json'):
        sources[str(p)] = sha(p)
    report = dict(rom_sha256=digest, menus={k: v['passed'] for k, v in results.items()},
        prior_gates=previous['qualified_checks'], dma={k: timing[k] for k in
            ('passed', 'dma_transfers', 'populations', 'latest_visible_end', 'controls')},
        video_differences={k: picture[k] for k in ('changed_frames', 'totals', 'stage_different_frame_counts')},
        sprite_cache=cache, sources=sources, release_ready=False, deployed=False,
        remaining=['Video-stage timing and changed frames', 'broader original-NES audio fidelity and speed',
                   'physical Bluemage audio/video self-test'],
        scope='Current3190 menu/DMA qualification plus measured cross-ROM video differences; '
              'no new ROM, no MiSTer/OBS access, no full-game speed or pop-free verdict.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Audio trial: menus and DMA</title>'
        '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}'
        'a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}</style>'
        '<h1>Startup-audio game trial: menus and DMA pass</h1>'
        '<p>All four original-NES menu oracles pass across 19,990 frames. Known-broken cursor/shop controls still fail.</p>'
        f'<p>{timing["dma_transfers"]:,} general DMA envelopes: {timing["populations"]["vblank"]:,} within VBlank, '
        f'{timing["populations"]["forced_blank"]:,} forced blank, {timing["populations"]["other"]} other; '
        'none aborted or unsafe/unproven. HDMA and physical per-byte timing remain outside this check.</p>'
        '<p>365 changed images remain. The paired snapshots reveal 77 prepared-sprite differences: '
        'with equal source data, the parent cache is current and trial stale in 40 frames; '
        'the reverse occurs in 33; both caches differ from their source in 3. One frame has different source data. '
        'These are snapshot observations, not a hardware publication-latency certificate.</p>'
        '<p>No deployment. Graphics scheduling, broader fidelity/speed and physical audio remain open.</p>'
        f'<p><a href="../{video.name}/">All changed-frame evidence and largest differences</a> · '
        f'<a href="../{prior.name}/">Audio timing and combat</a> · '
        f'<a href="../{dma.name}/">DMA and negative controls</a> · '
        '<a href="report.json">Bound results</a></p>'+''.join(cards))
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Changed source')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(menus=report['menus'], dma=report['dma'], sprite_cache=cache['populations'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'prior', 'dma', 'video', 'menu-config', 'parent-stages', 'trial-stages', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    review(**vars(p.parse_args()))
