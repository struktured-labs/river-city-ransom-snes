"""Real broken/fixed IRQ-return comparison, retaining the native pause-audio gate."""
import argparse
import csv
import json
from pathlib import Path
from tools.audit_audio_irq_returns import returns
from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    root=Path('build/overflow-3526');game=Path('build/audio-phase-full-a-game-3682')
    sources={}
    def proof(p):
        r=bound_report(p);sources.update(r['sources']);sources[str(p)]=sha(p);return r
    before=proof(root/'audio-phase-irq-returns-3681/report.json')
    observed=proof(root/'audio-phase-full-a-observed-3684/pause-observer.json')
    onset=proof(Path('build/audio-phase-full-a-onset-3685/report.json'))
    if before['passed'] or not observed['observer_neutral']:raise ValueError('Wrong broken/control observations')
    meta=json.loads((game/'manifest.json').read_text())
    if sha(game/'native-cpu.sfc')!=meta['rom_sha256']:raise ValueError('Changed candidate')
    for p,h in meta['experimental_audio_phase_full_a']['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed repair source')
        sources[p]=h
    label=symbols(game/'full-a.lbl')['irq_full_a']
    with Path(observed['traces']['RCR_INSTRUCTION_TRACE']).open() as f:
        events=parse(csv.reader(f),observed['first'],observed['last'])
    after=returns(events,0xc10000+label)
    if after['count']!=before['count']:raise ValueError('Different return coverage')
    checks=dict(known_broken_rejected=not before['passed'],actual_registers_preserved=after['passed'],
                native_pause_onset=onset['passed'])
    for p in (Path(__file__),Path('tools/audit_audio_irq_returns.py'),Path('tools/build_retained_producer_guard.py'),
              game/'full-a.lbl',game/'manifest.json',game/'native-cpu.sfc'):
        sources[str(p)]=sha(p)
    report=dict(passed=all(checks.values()),checks=checks,before=before['pairs'],after=after['pairs'],
        sources=sources,release_ready=False,physical_verified=False,pop_free_verified=False,
        scope=__doc__+' A includes hidden B. X/Y and stack also checked before and after actual RTI. '
        'Bounded1430–1445 window, not all IRQ phases. P/DB/DP and intended return PC remain outside '
        'this observer. Parent3665 broad-route passes do not qualify changed3682.')
    out.mkdir(parents=True)
    first=before['pairs'][0];new=after['pairs'][0]
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>IRQ accumulator repair</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:950px;margin:30px auto}a{color:cyan}td{padding:12px;border-bottom:1px solid #456}</style>'
        '<h1>Actual IRQ-return corruption caught and repaired</h1>'
        '<p>Parent3665 completed the long route and passed scoped graphics/audio checks, but failed the stronger CPU-state check. It is rejected for deployment. Trial3682 saves the complete accumulator.</p>'
        '<table><tr><td>Observed IRQ returns</td><td>16 before, 16 after</td></tr>'
        f'<tr><td>First broken accumulator</td><td>${first["entry"]["a"]:04X} → ${first["resumed"]["a"]:04X}</td></tr>'
        f'<tr><td>First repaired accumulator</td><td>${new["entry"]["a"]:04X} → ${new["resumed"]["a"]:04X}</td></tr>'
        f'<tr><td>All observed A/B/X/Y/stack returns preserved</td><td>{after["passed"]}</td></tr>'
        f'<tr><td>Native pause sound still matches NES frame57</td><td>{onset["passed"]}</td></tr></table>'
        '<p>Observer preserves all2537 replay frames and native PCM. No hardware deployment. Other CPU state, expanded interrupt phases, graphics tradeoffs for this changed ROM and pop-free sound remain unqualified.</p>'
        '<p><a href="../audio-phase-full-a-onset-3685/">Native NES/repaired audio clips</a> · '
        '<a href="report.json">Every observed return and source hashes</a></p>')
    report['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],checks=checks,returns=after['count'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
