"""Extend ordinary-early audio qualification with all menus, sustained combat and full-route DMA."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_busy_combat import measure
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.combat_campaign import verify_pair
from tools.review_phase_balance import menus
from tools.two_player_combat import installed_policy


def review(candidate,prior,dma,menu_config,campaign,out):
    if out.exists():raise ValueError('Fresh review required')
    previous=bound_report(prior/'report.json');timing=bound_report(dma/'report.json')
    digest=sha(candidate/'native-cpu.sfc')
    if any(not p['passed'] or p['rom_sha256']!=digest for p in (previous,timing)):
        raise ValueError('Failing or different candidate evidence')
    sources={**previous['sources'],**timing['sources']}
    spec=json.loads(menu_config.read_text());menu_results=menus(spec,candidate,sources)
    if set(menu_results)!={'status','cursor','repeat','choice'}:raise ValueError('Missing menu coverage')
    with installed_policy():receipt,strict,rows,_=verify_pair(campaign,'sustained-attacks','snes',candidate)
    busy=measure(strict,rows)
    if not strict['passed'] or not busy['passed']:raise ValueError('Sustained combat regression')
    for kind in ('normal','observed'):
        root=campaign/f'sustained-attacks-snes-{kind}'
        for name in ('combat-observer.json','two-player.json'):
            p=root/name;sources.update(bound_report(p)['sources']);sources[str(p)]=sha(p)
        for p in root.iterdir():
            if p.is_file():sources[str(p)]=sha(p)
    for p in (Path(__file__),Path('tools/review_phase_balance.py'),Path('tools/audit_busy_combat.py'),
        Path('tools/combat_campaign.py'),Path('tools/two_player_combat.py'),menu_config,
        prior/'report.json',dma/'report.json',candidate/'native-cpu.sfc',candidate/'manifest.json'):
        sources[str(p)]=sha(p)
    out.mkdir(parents=True);cards=[]
    samples={'status':'status_reopen_visible','cursor':'pause_reopen_visible',
             'repeat':'shop_after_purchase_5','choice':'shop_no_again_idle'}
    for name,phase in samples.items():
        figures=[]
        for label in ('nes','snes'):
            root=Path(menu_results[name]['captures'][label]['path']);original=root/f'{phase}.png'
            target=f'{name}-{label}.png';shutil.copy2(original,out/target)
            sources[str(original)]=sha(original)
            figures.append(f'<figure><figcaption>{label}</figcaption><img src="{target}"></figure>')
        cards.append('<section><h2>'+html.escape(name)+' · '+html.escape(phase)+'</h2>'+''.join(figures)+
            '<p><a href="../'+Path(spec[name]).parent.name+'/">Full original-NES oracle and checkpoints</a></p></section>')
    report=dict(passed=True,rom_sha256=digest,sources=sources,menus={k:v['passed'] for k,v in menu_results.items()},
        sustained_combat=dict(frames=receipt['frames'],strict=strict,busy=busy),
        dma={k:timing[k] for k in ('dma_transfers','populations','latest_visible_end','controls')},
        previous_qualification=str(prior/'report.json'),release_ready=False,physical_verified=False,
        pop_free_verified=False,scope=__doc__+' No new cartridge revision or hardware deployment. '
        'Picture checks use fixed menu regions, not equal enemy positions. DMA observer excludes HDMA '
        'and covers this9248-frame route, not every reachable game state. Original-NES full-game speed '
        'and physical Bluemage audio/video qualification remain open.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Audio trial extended qualification</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}figure{display:inline-block;margin:1em}img{width:384px;image-rendering:pixelated}'
        'section{border-top:1px solid #567;margin-top:2em}pre{white-space:pre-wrap}</style>'
        '<h1>Audio scheduling trial: expanded regression checks</h1>'
        '<p>Same offline3065 cartridge. Four menu oracles pass, with known-broken cursor/shop controls still rejected. '
        'Sustained attacks joins running jumps: each passes1,753 busy-inclusive two-frame intervals.</p>'
        f'<p>All{timing["dma_transfers"]:,} observed general-DMA envelopes are classified. '
        f'{timing["populations"]["vblank"]:,} display-memory transfers stay within VBlank; '
        f'{timing["populations"]["forced_blank"]:,} occur with forced blank set at both endpoints. '
        f'Latest visible-frame transfer ends at scanline{timing["latest_visible_end"]}. '
        'No aborted or unsafe/unproven display-memory envelopes.</p>'
        '<p>These are bounded emulator checks, not a pop-free or full-game speed certificate. '
        'Neither MiSTer was restarted. Bluemage was inspected read-only; its capture connection is unconfirmed. '
        'Active OBS recording/replay and Rivalmage were left untouched.</p>'
        '<p><a href="../ordinary-early-audio-review-3073/">71.36% timing-spread reduction and exact audio clips</a> · '
        '<a href="../ordinary-early-audio-dma-audit-3088/">DMA evidence and negative controls</a> · '
        '<a href="report.json">Full bound qualification</a></p>'+''.join(cards))
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Changed source: '+p)
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,menus=report['menus'],sustained_intervals=busy['intervals'],
        sustained_histogram=busy['frame_histogram'],dma=report['dma'],sources=len(sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','prior','dma','menu-config','campaign','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
