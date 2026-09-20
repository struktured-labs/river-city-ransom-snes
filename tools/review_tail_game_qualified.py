"""Current-ROM scoped qualification with actual sprite-latency limits retained."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_phase_balance import menus


def review(candidate, prior, dma, sprites, menu_config, out):
    if out.exists(): raise ValueError('Fresh qualification required')
    previous = bound_report(prior/'report.json'); transfer = bound_report(dma/'report.json')
    publication = bound_report(sprites/'report.json'); digest = sha(candidate/'native-cpu.sfc')
    if (previous['rom_sha256'] != digest or transfer['rom_sha256'] != digest or
        publication['sources'].get(str(candidate/'native-cpu.sfc')) != digest or
        not previous['tested_checks_passed'] or not transfer['passed']):
        raise ValueError('Failing gates or different cartridge')
    sources = dict(previous['sources'], **transfer['sources']); sources.update(publication['sources'])
    spec = json.loads(menu_config.read_text()); result = menus(spec, candidate, sources)
    if set(result) != {'status', 'cursor', 'repeat', 'choice'}: raise ValueError('Missing menu suite')
    out.mkdir(); cards = []
    phases = dict(status='status_reopen_visible', cursor='pause_reopen_visible',
                  repeat='shop_after_purchase_5', choice='shop_no_again_idle')
    for name, phase in phases.items():
        cards.append('<h2>'+html.escape(name+' · '+phase)+'</h2><div class="pair">')
        for label in ('nes', 'snes'):
            root = Path(result[name]['captures'][label]['path']); source = root/(phase+'.png')
            target = name+'-'+label+'.png'; shutil.copyfile(source, out/target)
            sources[str(source)] = sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    for p in (Path(__file__), Path('tools/review_phase_balance.py'), menu_config,
              prior/'report.json', dma/'report.json', sprites/'report.json',
              candidate/'manifest.json', candidate/'native-cpu.sfc'):
        sources[str(p)] = sha(p)
    report = dict(rom_sha256=digest, prior_gates=previous['qualified_checks'],
        menus={k: v['passed'] for k, v in result.items()},
        dma={k: transfer[k] for k in ('passed', 'dma_transfers', 'populations', 'latest_visible_end', 'controls')},
        sprite_publication={arm: {k: publication[arm][k] for k in
            ('structural_passed', 'first', 'last', 'known_source_generations',
             'source_to_first_render_histogram', 'not_rendered_in_window')} for arm in ('parent', 'trial')},
        sources=sources, release_ready=False, hardware_tested=False,
        remaining=['Sprite publication latency and omitted generations',
                   'remaining cross-ROM frames and callback timing',
                   'original-NES audio fidelity and broader full-game speed', 'physical Bluemage audio/video'],
        scope='Fresh exact3219 scoped regressions. Correct OAM copy/render mapping is not acceptable '
              'sprite cadence. Whole-game and physical audio requirements remain open; no deployment.')
    body = '<!doctype html><meta charset="utf-8"><title>Tail audio build qualification</title>'
    body += '<style>body{background:#111a26;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}a{color:#8df}.pair{display:flex}figure{margin:8px;flex:1}img{width:100%;image-rendering:pixelated}</style>'
    body += '<h1>Leaner audio build: fresh regression checks</h1>'
    body += f'<p>ROM <code>{digest}</code>. No MiSTer or OBS operation.</p>'
    body += '<p>All four menu oracles pass. Same-core renderer reports no missing coverage, splits or stale camera frames. '
    body += 'Both two-player combat policies pass their strict and busy-inclusive cadence checks.</p>'
    body += f'<p>General DMA: {transfer["dma_transfers"]:,} transfers, populations {transfer["populations"]}; '
    body += f'latest visible end line {transfer["latest_visible_end"]}. No aborted or unsafe/unproven envelope.</p>'
    body += '<h2>Remaining: actual sprite display latency</h2>'
    for name, r in report['sprite_publication'].items():
        body += f'<p>{name}: first-render frame-delay histogram {r["source_to_first_render_histogram"]}; '
        body += f'{len(r["not_rendered_in_window"])} of {r["known_source_generations"]} known source generations '
        body += f'not rendered within frames {r["first"]}–{r["last"]}. All are retained in the report.</p>'
    body += '<p>This is a fixed-window diagnosis, not original-NES latency equivalence. Correct transfer '
    body += 'bytes do not prove smooth animation. Not release-ready or pop-free certified.</p>'
    body += f'<p><a href="../{sprites.name}/">Source → prepared → DMA → actual display</a> · '
    body += f'<a href="../{prior.name}/">Audio timing, scrolling and combat</a> · '
    body += f'<a href="../{dma.name}/">DMA evidence</a> · <a href="report.json">Bound qualification</a></p>'+''.join(cards)
    (out/'index.html').write_text(body)
    if any(sha(Path(p)) != h for p, h in sources.items()): raise ValueError('Changed source')
    report['artifacts'] = {p.name: sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(menus=report['menus'], dma=report['dma'], sprites=report['sprite_publication'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'prior', 'dma', 'sprites', 'menu-config', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    review(**vars(p.parse_args()))
