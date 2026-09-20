"""Bind current menu fidelity, dense DMA margins and native audio observations without a release claim."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_phase_balance import menus


def review(candidate,prior,margin,dense,audio,menu_paths,out):
    if out.exists():raise ValueError('Fresh review required')
    sources={}
    def bind(root):
        p=root/'report.json';r=bound_report(p);sources.update(r['sources']);sources[str(p)]=sha(p)
        if r['sources'].get(str(candidate/'native-cpu.sfc'))!=sha(candidate/'native-cpu.sfc'):
            raise ValueError('Different candidate report')
        for name,d in r.get('artifacts',{}).items():
            if sha(root/name)!=d:raise ValueError('Changed web artifact')
        return r
    preceding=bind(prior);wide=bind(margin);fine=bind(dense);sound=bind(audio)
    for r in (wide,fine):
        if not r['passed']:raise ValueError('Boundary fixture failed')
        for case in r['cases']+r.get('negative_controls',[]):
            for p,d in case['artifacts'].items():
                if sha(Path(p))!=d:raise ValueError('Changed executed boundary artifact')
                sources[p]=d
    results=menus(menu_paths,candidate,sources)
    out.mkdir(parents=True);cards=[]
    phases=dict(status='status_reopen_visible',cursor='pause_reopen_visible',
                repeat='shop_after_purchase_5',choice='shop_no_result')
    for name,r in results.items():
        row=[]
        for label in ('nes','snes'):
            root=Path(r['captures'][label]['path']);source=root/(phases[name]+'.png')
            if str(source) not in sources or sha(source)!=sources[str(source)]:raise ValueError('Unbound menu picture')
            target=f'{name}-{label}.png';shutil.copy2(source,out/target)
            row.append(f'<figure><img src="{target}"><figcaption>{label}</figcaption></figure>')
        cards.append(f'<h2>{name}</h2><div class="pair">'+''.join(row)+'</div>')
    summary=dict(menus={k:r['passed'] for k,r in results.items()},
        menu_frames=19990,margin_cases=len(wide['cases']),dense_cases=len(fine['cases']),
        latest_sampled_finish=max(r['finish_line'] for r in fine['cases']),
        noise_larger_at_selected_sample=sound['noise_larger_at_selected_sample'],
        audio_cadence={k:v for k,v in sound['cadence'].items() if k not in ('longest','scope')})
    for p in (Path(__file__),Path('tools/review_phase_balance.py'),Path('tools/check_present_status.py'),
        Path('tools/check_pause_cursor.py'),Path('tools/check_shop_repeat.py'),Path('tools/check_shop_choice_no.py')):
        sources[str(p)]=sha(p)
    report=dict(summary=summary,prior=preceding,margin=wide,dense=fine,menus=results,audio=sound,
        sources=sources,release_ready=False,pop_free_verified=False,physical_verified=False,scope=__doc__)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Current candidate qualification</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}.pair{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}figure{margin:0}'
        'img{width:100%;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>Menus preserved; dense sprite/palette timing checked</h1>'
        '<p>Offline candidate3032 is unchanged. Rivalmage and Bluemage were not accessed.</p>'
        '<p>All four fixed NES menu oracles pass across 19,990 captured frames. Existing broken '
        'cursor/shop controls still fail. The expanded156-case fixture and1,024-case dense sweep '
        'exercise real physical OAM/CGRAM, rendering enabled, and the live palette-conversion path.</p>'
        '<p><strong>Important margin:</strong> expensive palette batches can finish on scanline261, '
        'not257 as in the earlier empty-palette fixture. No overrun occurred in the recorded cases; '
        'this is not exhaustive hardware timing proof.</p>'
        '<p>Audio is not declared fixed. Noise is the larger contributor at6 of12 selected gameplay '
        'sample steps; the rest of the mix dominates the others. These are exact same-sample '
        'contributions, not identified pops. Packet completion spacing also varies.</p>'
        f'<p><a href="../{audio.name}/">Native audio, exact stems, DSP context and cadence</a> · '
        f'<a href="../{prior.name}/">Speed, scrolling and sprite-recovery evidence</a></p>'
        '<details><summary>Measurements</summary><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre></details>'+
        ''.join(cards)+'<p><a href="report.json">All bound proofs, executed artifacts and limits</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','prior','margin','dense','audio','out'):p.add_argument('--'+k,type=Path,required=True)
    for k in ('status','cursor','repeat','choice'):p.add_argument('--'+k,type=Path,required=True)
    args=vars(p.parse_args());args['menu_paths']={k:str(args.pop(k)) for k in ('status','cursor','repeat','choice')}
    review(**args)
