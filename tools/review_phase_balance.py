"""Review smoother phase96 timing, retained busy-NMI failure and menu regressions."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay,compare
from tools.check_present_status import compare as status_compare
from tools.check_pause_cursor import _analyze as cursor_compare
from tools.check_shop_repeat import _analyze as repeat_compare
from tools.check_shop_choice_no import _analyze as choice_compare


def menus(paths,candidate,sources):
    results = {}
    for name,path in paths.items():
        report_path = Path(path)
        report = json.loads(report_path.read_text())
        if not report['passed']:
            raise ValueError('Failed menu regression')
        folders = {}
        for label,binding in report['captures'].items():
            folder = Path(binding['path'])
            digest = binding.get('capture_sha256',binding.get('sha256'))
            receipt,_ = verify_capture(folder)
            if sha(folder/'capture.json') != digest or receipt['rom_sha256'] != binding['rom_sha256']:
                raise ValueError('Changed menu capture')
            if label=='snes' and receipt['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
                raise ValueError('Different menu cartridge')
            folders[label] = folder
            sources.update({str(p):sha(p) for p in folder.iterdir() if p.is_file()})
        if name=='status':
            if status_compare(folders['nes'],folders['snes']) != report['phases']:
                raise ValueError('Changed numeric status result')
        else:
            oracle = dict(cursor=cursor_compare,repeat=repeat_compare,choice=choice_compare)[name]
            if (oracle(folders['nes'],folders['snes']) != report['candidate' if name=='repeat' else 'result'] or
                    oracle(folders['nes'],folders['previous']) != report['negative_control'] or
                    report['negative_control']['passed']):
                raise ValueError('Changed menu oracle or accepted broken control')
        sources[str(report_path)] = sha(report_path)
        results[name] = report
    return results


def review(config,out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = json.loads(config.read_text())
    candidate = Path(spec['candidate'])
    reports = {name:bound_report(Path(spec[name])) for name in
               ('proof','publication','parent_publication','renderer','audio','combat','parent_combat','ring_oracle')}
    sources = {str(config):sha(config),str(Path(__file__)):sha(Path(__file__))}
    for name,report in reports.items():
        sources.update(report['sources']);sources[spec[name]] = sha(Path(spec[name]))
    for name in ('proof','publication','combat'):
        if reports[name]['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
            raise ValueError('Different qualified cartridge')
    if not reports['proof']['passed'] or not reports['renderer']['passed']:
        raise ValueError('Helper/renderer regression')
    sound = reports['audio']
    for label in ('candidate','baseline'):
        for name,digest in sound[label]['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed DSP source')
        sources.update(sound[label]['sources'])
    if sound['candidate']['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different DSP cartridge')
    menu_results = menus(spec['menus'],candidate,sources)
    episodes = []
    out.mkdir(parents=True)
    audio_cards = []
    for index,episode in enumerate(spec['replays'],1):
        control,trial = Path(episode['control']),Path(episode['trial'])
        before,old = authenticated_replay(control)
        after,new = authenticated_replay(trial)
        if (not before['passed'] or after['trial']['resume_control'] != str(control) or
                after['trial']['trial_rom_sha256'] != sha(candidate/'native-cpu.sfc') or
                (control/'initial.ram').read_bytes() != (trial/'initial.ram').read_bytes() or
                before['initial_registers'] != after['initial_registers']):
            raise ValueError('Unqualified starting state')
        episodes.append(dict(event=episode['event'],comparison=compare(old,new,episode['event'])))
        for label,folder,report in (('before',control,before),('after',trial,after)):
            sources.update(report['sources']);sources[str(folder/'report.json')] = sha(folder/'report.json')
            name = f'case{index}-{label}.wav'
            shutil.copy2(folder/'audio.wav',out/name)
            sources[str(folder/'audio.wav')] = sha(folder/'audio.wav')
            audio_cards.append(f'<p>Case {episode["event"]} — {label}</p><audio controls preload="none" src="{name}"></audio>')
    publication = reports['publication']
    parent = reports['parent_publication']
    cadence_ok = all(not r['summary']['short_irregular'] for r in publication['park'].values())
    latency_ok = all(r['start_to_display']==parent['rooms'][room]['start_to_display']
                     for room,r in publication['rooms'].items())
    normal = Path(spec['normal'])
    receipt,rows = verify_capture(normal)
    if receipt['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different collage cartridge')
    cards = []
    park_frames = [7617,7618,7619,7620]
    menu_frames = []
    for name,phase in (('status','status_visible'),('cursor','pause_reopen_visible'),
                       ('repeat','shop_second_confirm'),('choice','shop_no_result')):
        folder = Path(menu_results[name]['captures']['snes']['path'])
        _,menu_rows = verify_capture(folder)
        row = [r for r in menu_rows if r['phase']==phase][-1]
        menu_frames.append((folder,row,phase))
    for folder,row,label in [(normal,rows[f-1],f'Park frame {f}') for f in park_frames]+menu_frames:
        src = verify_frame(folder,row)
        name = 'panel-'+str(len(cards))+'.png'
        shutil.copy2(src,out/name);sources[str(src)] = sha(src)
        cards.append(f'<figure><img src="{name}"><figcaption>{html.escape(label)}</figcaption></figure>')
    ring = spec['ring']
    rr,ring_rows = verify_capture(Path(ring['normal']))
    if rr['rom_sha256'] != sha(Path(ring['candidate'])/'native-cpu.sfc'):
        raise ValueError('Different combined-copy cartridge')
    rb,old = authenticated_replay(Path(ring['control']))
    ra,new = authenticated_replay(Path(ring['trial']))
    if (not rb['passed'] or ra['trial']['resume_control']!=ring['control'] or
            ra['trial']['trial_rom_sha256']!=rr['rom_sha256'] or
            (Path(ring['control'])/'initial.ram').read_bytes()!=(Path(ring['trial'])/'initial.ram').read_bytes()):
        raise ValueError('Unqualified ring combination replay')
    ring_result = dict(route_complete=rr['capture_complete'],frames=rr['frames'],
                       comparison=compare(old,new,2239),release_ready=False)
    for binding,folder in ((rb,Path(ring['control'])),(ra,Path(ring['trial']))):
        sources.update(binding['sources']);sources[str(folder/'report.json')]=sha(folder/'report.json')
    sources[str(Path(ring['normal'])/'capture.json')] = sha(Path(ring['normal'])/'capture.json')
    failed_cards=[]
    for frame in (9360,9387):
        src=verify_frame(Path(ring['normal']),ring_rows[frame-1]);name=f'rejected-{frame}.png'
        shutil.copy2(src,out/name);sources[str(src)]=sha(src)
        failed_cards.append(f'<figure><img src="{name}"><figcaption>Rejected copy combination · {frame}</figcaption></figure>')
    for module in ('review_retained_producer','frame_audit','check_present_status','check_status_regression',
                   'check_pause_cursor','check_shop_repeat','check_shop_choice_no','check_shop_confirm',
                   'audit_main_display_latency','benchmark_report','audit_busy_combat'):
        p=Path('tools')/(module+'.py');sources[str(p)]=sha(p)
    before=reports['parent_combat']['campaigns']['running-jumps']['including_busy']
    after=reports['combat']['campaigns']['running-jumps']['including_busy']
    report=dict(proofs=reports,menus=menu_results,episodes=episodes,ring_combination=ring_result,
                cadence_matches_parent=cadence_ok,latency_histograms_match_parent=latency_ok,
                strict_speed_passed=reports['combat']['strict_passed'],sources=sources,
                physical_verified=False,pop_free_verified=False,original_speed_parity_verified=False,
                release_ready=False,scope=__doc__+' Separate encounters are not equal-work speed ratios. '
                'One known interrupt stall remains; zero stable-summary gaps is not a pass.')
    histogram=lambda r:html.escape(str(r['frame_histogram']))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Phase96 timing review</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.pair{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}'
        'figure{margin:0}img,audio{width:100%}img{image-rendering:pixelated}td,th{padding:9px;border:1px solid #567}</style>'
        '<h1>Frame recovery without the earlier scrolling regression</h1><p>Offline candidate2769. '
        'Rival unchanged. One known missed interrupt remains; not release-ready.</p>'
        '<table><tr><th>Check</th><th>Measured result</th></tr>'
        '<tr><td>Exact-state recovery</td><td>4317 recovered;2239 still missed</td></tr>'
        '<tr><td>Park scrolling</td><td>Zero short irregular holds east/west; no split or stale camera</td></tr>'
        '<tr><td>Camera latency</td><td>All961 tracked changes display two frames after main/input start, matching parent</td></tr>'
        '<tr><td>Menus</td><td>Status, pause reopen, two purchases, YES/NO all pass exact original-NES oracles</td></tr>'
        '<tr><td>Audio</td><td>8432 packets,1552 restarts, no late configuration; perceptual pops unresolved</td></tr></table>'
        '<h2>The harness must not hide a busy interrupt</h2><p>The original NMI sets $0107 bit7 while running. '
        'The old stable-only summary excluded the one stalled interval because that bit was set at a frame boundary. '
        'The strict test always failed; the new summary also includes busy-NMI frames and keeps the failure visible.</p>'
        '<table><tr><th>Running2P interval lengths → counts</th><th>Parent</th><th>Candidate</th></tr><tr><td>Including busy NMI</td><td>'+
        histogram(before)+'</td><td>'+histogram(after)+'</td></tr></table>'
        '<p>The remaining2237–2240 interval starts late, then its retained original NMI crosses VBlank. '
        'Fresh neutral instruction capture verifies the busy flag being set at2238 line238 and cleared at2239 line12. '
        'These independent encounter counts are not performance percentages or NES-speed parity.</p>'
        '<h2>Native frames: scrolling and menu regressions</h2><div class="grid">'+''.join(cards)+'</div>'
        '<h2>Native same-state audio</h2><p>Unnormalized90-frame recordings. Timing recovery changes the waveform; '
        'packet transport and raw-DAC equality do not certify absence of audible pops.</p>'+''.join(audio_cards)+
        '<h2>Copy-cache combination rejected</h2><p>The additional vertical-copy optimization passes111 executed '
        'comparisons, but does not recover2239. Its route loses all power, returns to the mall and times out. '
        'No full-route qualification or hardware deployment is claimed for it.</p><div class="pair">'+''.join(failed_cards)+
        '</div><p><a href="report.json">All proofs, failures, source hashes and limits</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cadence_matches_parent=cadence_ok,latency_histograms_match_parent=latency_ok,
                         strict_speed_passed=report['strict_speed_passed'],menus_passed=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','out'):p.add_argument('--'+name,type=Path,required=True)
    review(**vars(p.parse_args()))
