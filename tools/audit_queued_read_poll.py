"""Bind cheaper-poll cost and retained recovery to the remaining live combat interval."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.build_retained_producer_guard import symbols
from tools.frame_audit import verify_frame
from tools.review_retained_producer import authenticated_replay, compare
from tools.two_player_combat import installed_policy, validate_ports


def decode(raw):
    if len(raw)!=10:
        raise ValueError('Wrong fresh instruction schema')
    fields = ('frame','line','cycle','clock','pc','opcode','a','x','y','s')
    return {k:int(v,16 if k in ('pc','opcode') else 10) for k,v in zip(fields,raw)}


def interval_evidence(rows, interval, runtime, boot, queue):
    def exact(point):
        matches = [r for r in rows if all(r[k]==point[k] for k in
                   ('frame','line','cycle','clock','pc','opcode','a','x','y','s'))]
        if len(matches)!=1:
            raise ValueError('Sparse event not reproduced by full instruction trace')
        return matches[0]
    start, finish, next_start = map(exact, (interval['start'],interval['finish'],interval['next_start']))
    selected = [r for r in rows if start['clock']<=r['clock']<next_start['clock']]
    native = [r for r in selected if r['pc']==boot['nmi']]
    queued = [r for r in selected if 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==queue['queued_entry']]
    # This is a classification, not a new passing performance threshold.
    # Refuse to label a trace with missing event entries as a main-work overrun.
    every_vblank = ([r['frame'] for r in native]==list(range(start['frame'],next_start['frame']))
                    and all(r['line']==240 for r in native) and
                    len(native)==interval['nmi_advances'] and not queued)
    names = {runtime[k]:k for k in ('gameplay_iteration_start','camera_deferred_nmi_exit',
        'nmi_rti_return','camera_deferred_nmi_return','second_tick_prepare_service','second_tick_prepare_fallback')}
    names.update({0xff4f:'original_game_nmi',0xf2da:'main_completion',queue['queued_entry']:'queued_entry'})
    native_names = {boot[k]:k for k in ('nmi','audio_publish_bridge','video_prepare_bridge')}
    events = []
    for r in selected:
        name = names.get(r['pc']&65535) if 0xc1<=r['pc']>>16<=0xc8 else native_names.get(r['pc'])
        # Bridge aliases in C0 use the same low address as bank00.
        if name is None and r['pc']>>16==0xc0:
            name = native_names.get(r['pc']&65535)
        if name:
            events.append(dict(name=name,**r))
    return dict(start=start,finish=finish,next_start=next_start,events=events,
        hardware_entries=native,queued_entries=queued,
        every_frame_had_hardware_nmi=every_vblank,
        main_clocks=finish['clock']-start['clock'],
        start_interval_clocks=next_start['clock']-start['clock'],
        scope='Exact sparse/full-trace agreement. Hardware entry on every frame rules out a lost '
              'VBlank entry in this interval, not duplicate/lost original-body dispatch or sufficient CPU budget.')


def audit(config, out):
    if out.exists():
        raise ValueError('Fresh output required')
    spec = json.loads(config.read_text())
    paths = {k:Path(v) for k,v in spec.items()}
    candidate = paths['candidate']
    sources = {str(config):sha(config),str(Path(__file__)):sha(Path(__file__))}
    def bind(path):
        r = bound_report(path)
        sources.update(r['sources']);sources[str(path)] = sha(path)
        def check(value):
            if isinstance(value,dict):
                for key,child in value.items():
                    if key in ('artifacts','mutant_artifacts'):
                        for name,d in child.items():
                            p=Path(name) if name.startswith('build/') else path.parent/name
                            if sha(p)!=d:raise ValueError('Changed artifact: '+str(p))
                            sources[str(p)]=d
                    else:check(child)
            elif isinstance(value,list):
                for child in value:check(child)
        check(r)
        return r
    proofs = {k:bind(paths[k]/'report.json') for k in ('oracle','priority','events','timing')}
    for k in ('oracle','priority','events'):
        if not proofs[k]['passed'] or proofs[k]['sources'].get(str(candidate/'native-cpu.sfc'))!=sha(candidate/'native-cpu.sfc'):
            raise ValueError('Unqualified candidate '+k)
    before, old = authenticated_replay(paths['control'])
    after, new = authenticated_replay(paths['replay'])
    for k in ('control','replay'):bind(paths[k]/'report.json')
    if (not before['passed'] or after['trial']['resume_control']!=str(paths['control']) or
            after['trial']['trial_rom_sha256']!=sha(candidate/'native-cpu.sfc') or
            not after['cross_rom_restore_verified'] or
            (paths['control']/'initial.ram').read_bytes()!=(paths['replay']/'initial.ram').read_bytes()):
        raise ValueError('Different replay state or cartridge')
    recovery = compare(old,new,2239)
    with installed_policy():
        receipt, strict, rows, _ = combat.verify_pair(paths['combat'],'running-jumps','snes',candidate)
    ports=[]
    for kind in ('normal','observed'):
        folder=paths['combat']/f'running-jumps-snes-{kind}'
        bind(folder/'combat-observer.json')
        p=bind(folder/'two-player.json')
        log=json.loads((folder/'two-port-input.json').read_text())
        if validate_ports(log,rows,'snes')!=p['delivery']:raise ValueError('Changed port delivery')
        ports.append(log)
    if ports[0]!=ports[1]:raise ValueError('Observer changed input ports')
    busy=measure(strict,rows)
    instruction=bind(paths['instructions']/'instruction-control.json')
    delivery=bind(paths['instructions']/'two-player-instructions.json')
    if not instruction['observer_neutral'] or not delivery['observer_neutral']:
        raise ValueError('Nonneutral instructions')
    with installed_policy(),combat.installed('running-jumps'):
        ir, irows=verify_capture(paths['instructions'])
    if irows!=rows or ir['audio_sha256']!=receipt['audio_sha256']:
        raise ValueError('Instruction core and combat core disagree')
    trace=paths['instructions'].with_suffix('.csv')
    if instruction['sources'].get(str(trace))!=sha(trace):raise ValueError('Unbound trace')
    with trace.open() as stream:instructions=[decode(r) for r in csv.reader(stream)]
    image=(candidate/'native-cpu.sfc').read_bytes()
    for i,r in enumerate(instructions):
        if (image[r['pc']&0x3fffff]!=r['opcode'] or
                i and r['clock']<=instructions[i-1]['clock']):
            raise ValueError('Instruction opcode/clock mismatch')
    runtime=symbols(candidate/'native_runtime.lbl');boot=symbols(candidate/'native_boot.lbl')
    queue=symbols(candidate/'queued-vblank.lbl')
    off=[r for r in busy['off_cadence'] if instructions[0]['frame']<=r['first']<r['last']<=instructions[-1]['frame']]
    details=[interval_evidence(instructions,r,runtime,boot,queue) for r in off]
    if not details:raise ValueError('No covered off-cadence interval')
    modules=('review_retained_producer','audit_busy_combat','combat_campaign','two_player_combat',
             'benchmark_report','frame_audit','build_retained_producer_guard')
    own=[Path('tools')/(n+'.py') for n in modules]+[candidate/(n+'.lbl') for n in
            ('native_runtime','native_boot','queued-vblank')]+[Path('tests/test_queued_read_poll.py'),Path('tests/test_queued_interval.py')]
    sources.update({str(p):sha(p) for p in own})
    out.mkdir(parents=True)
    cards=[]
    folder=paths['combat']/'running-jumps-snes-normal'
    for frame in range(details[0]['start']['frame'],details[0]['next_start']['frame']+1):
        source=verify_frame(folder,rows[frame-1]);name=f'combat-{frame}.png'
        shutil.copy2(source,out/name);sources[str(source)]=sha(source)
        cards.append(f'<figure><img src="{name}"><figcaption>Frame {frame}</figcaption></figure>')
    clips=[]
    for key in ('control','replay'):
        source=paths[key]/'audio.wav';name=key+'.wav';shutil.copy2(source,out/name)
        sources[str(source)]=sha(source);clips.append(dict(file=name,source=str(source)))
    for p,d in sources.items():
        if sha(Path(p))!=d:raise ValueError('Changed source: '+p)
    report=dict(proofs=proofs,recovery=recovery,strict_combat=strict,including_busy=busy,
        remaining_intervals=details,sources=sources,clips=clips,release_ready=False,
        physical_verified=False,pop_free_verified=False,original_speed_parity_verified=False,
        scope=__doc__+' No new full-route/menu/DSP qualification for this follow-up.')
    summary=dict(saved_clocks=sorted(set(r['saved_clocks'] for r in proofs['timing']['cases'])),
        recovered=all(recovery['gates'].values()),combat_histogram=busy['frame_histogram'],strict_passed=strict['passed'])
    events=details[0]['events']+[dict(name='next_main_start',**details[0]['next_start'])]
    table=''.join(f'<tr><td>{e["frame"]}</td><td>{e["line"]}:{e["cycle"]}</td><td>{e["name"]}</td></tr>' for e in events)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Cheaper polling and remaining stall</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1120px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}td,th{padding:5px 15px;text-align:left}</style>'
        '<h1>Less polling overhead; remaining stall is late main work</h1><p>Offline2944, Rival unchanged. '
        'All24 measured active-display read calls save120 master clocks. All234 executed queue/priority cases '
        'pass; six deliberate faults fail. The old exact-state stall stays recovered.</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
        '<h2>Remaining three-frame interval</h2><p>The main iteration starts at2248 line171, finishes at2251 '
        'line69, and restarts at line96. Actual hardware NMI entries occur at line240 of2248,2249 and2250. '
        'No queued entry occurs inside this interval. This is not another missing hardware VBlank entry: '
        'game work and interrupt/preparation work finish late. Original-body dispatch ownership and '
        'critical-path budgeting still require investigation.</p><div class="grid">'+''.join(cards)+'</div>'
        '<table><tr><th>Frame</th><th>Scanline:clock</th><th>Executed entry</th></tr>'+table+'</table>'
        '<h2>Saved-state replay audio</h2><p>Parent then cheaper-poll candidate; exact unnormalized WAVs. '
        'Intact, ordered packets do not guarantee even arrival timing or pop-free music.</p>'+''.join(
            f'<audio controls preload="none" src="{c["file"]}"></audio>' for c in clips)+
        '<p>No fresh full-route, menu, DSP or physical qualification for this follow-up. '
        '<a href="../queued-vblank-review-2943/">Earlier combined-candidate qualification</a>.</p>'
        '<p><a href="report.json">Measurements, failures and source hashes</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,hardware_every_frame=[r['every_frame_had_hardware_nmi'] for r in details],sources=len(sources))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('config','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
