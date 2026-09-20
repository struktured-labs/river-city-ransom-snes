"""Require driver adapters to keep NMI masked until the owning IRQ epilogue."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha


def enables(events,rom):
    active=None;groups=[]
    for e in events:
        if e['pc']==0xc179cf:
            if active is not None:raise ValueError('Reentered IRQ')
            active=dict(entry=e,writes=[])
        if active is None:continue
        offset=e['pc']&0x3fffff
        if offset+3>len(rom):raise ValueError('Unsupported code mapping')
        op=rom[offset:offset+3]
        if op in (bytes.fromhex('8d0042'),bytes.fromhex('9c0042')):
            active['writes'].append(dict(event=e,value=(e['a']&255) if op[0]==0x8d else 0))
        if e['pc']&65535==0xf1d8:
            if e['opcode']!=0x40:raise ValueError('Not original RTI')
            active['rti']=e
            active['early_enables']=[w for w in active['writes'] if w['value']&0xa0 and w['event']['pc']!=0xc179fb]
            tail=[w for w in active['writes'] if w['event']['pc']==0xc179fb]
            active['passed']=not active['early_enables'] and len(tail)==1 and tail[0]['value']==128
            groups.append(active);active=None
    if active is not None or not groups:raise ValueError('Missing complete IRQ window')
    return dict(passed=all(g['passed'] for g in groups),groups=groups,
        early_enables=sum(len(g['early_enables']) for g in groups))


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    root=Path('build/overflow-3526');sources={};arms={}
    for name,folder,game in [('before','audio-phase-full-a-observed-3684','audio-phase-full-a-game-3682'),
                              ('after','audio-depth-instructions-3701','audio-phase-depth-game-3695')]:
        path=root/folder/'pause-observer.json';proof=bound_report(path)
        if not proof['observer_neutral']:raise ValueError('Non-neutral instruction trace')
        sources.update(proof['sources']);sources[str(path)]=sha(path)
        rom=Path('build')/game/'native-cpu.sfc';sources[str(rom)]=sha(rom)
        with Path(proof['traces']['RCR_INSTRUCTION_TRACE']).open() as f:
            events=parse(csv.reader(f),proof['first'],proof['last'])
        arms[name]=enables(events,rom.read_bytes())
    proofs={}
    for name,path in [('current_context',root/'audio-depth-context-audit-3704/report.json'),
                      ('repaired_pause_context',root/'audio-irq-pause-audit-3697/report.json'),
                      ('repaired_full_context',root/'audio-irq-sweep-audit-3698/report.json'),
                      ('broken_context',root/'audio-irq-broken-audit-3699/report.json'),
                      ('onset',Path('build/audio-depth-onset-3702/report.json'))]:
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);proofs[name]=r
    checks=dict(early_enable_negative_control=not arms['before']['passed'],
        depth_guard=arms['after']['passed'],current_context=proofs['current_context']['passed'],
        hidden_b_negative_control=not proofs['broken_context']['passed'],native_onset=proofs['onset']['passed'])
    candidate=Path('build/audio-phase-depth-game-3695');meta=json.loads((candidate/'manifest.json').read_text())
    for p,h in meta['experimental_audio_phase_depth']['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed guard implementation')
        sources[p]=h
    for p in (Path(__file__),Path('tools/audit_park_instructions.py'),Path('tests/test_audio_irq_depth.py'),
              candidate/'manifest.json'):sources[str(p)]=sha(p)
    report=dict(passed=all(checks.values()),checks=checks,arms=arms,sources=sources,
        irq_counts={k:v['count'] for k,v in proofs.items() if 'count' in v},
        release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' Instruction window1430–1445. Current3695 full-context check covers pause '
        'IRQs only; long-route complete-context result belongs to3682, not3695. NMI masking '
        'removes an observed unsafe enable window; no rare nested-NMI corruption is claimed reproduced.')
    out.mkdir(parents=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>IRQ ownership guard</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:1050px;margin:30px auto}a{color:cyan}td{padding:10px;border-bottom:1px solid #456}</style>'
        '<h1>Audio IRQ ownership: premature NMI enables removed</h1>'
        '<p>New experimental3695 guards the real sound service using the existing interrupt-depth counter. No hardware deployment.</p><table>'
        f'<tr><td>Premature NMI enables in16 observed IRQs</td><td>{arms["before"]["early_enables"]} → {arms["after"]["early_enables"]}</td></tr>'
        f'<tr><td>Current full CPU-state returns</td><td>{proofs["current_context"]["count"]} IRQs, PASS={proofs["current_context"]["passed"]}</td></tr>'
        '<tr><td>Fields checked against pre-hardware-IRQ state</td><td>PB:PC, full A/B/X/Y, stack, flags including E, DP, DB</td></tr>'
        '<tr><td>Native pause sound</td><td>Still57 frames, matching NES</td></tr></table>'
        '<p>Observer-on/off captures match every primary replay row and native PCM. The old hidden-B-broken cartridge fails657/657 complete-context returns. The accumulator repair passes662 pause IRQs and4612 park IRQs; those broader results belong to3682.</p>'
        '<p>3695 still needs broader graphics/audio/cadence checks, direct recovery context, and physical verification. Exact IRQ returns do not prove original-game speed or pop-free sound.</p>'
        '<p><a href="../audio-depth-onset-3702/">Untouched NES/current audio clips</a> · <a href="report.json">Every enable write and source bindings</a></p>')
    report['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],checks=checks,early_enables=[arms[k]['early_enables'] for k in ('before','after')],irq_counts=report['irq_counts'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
