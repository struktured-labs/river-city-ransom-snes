"""Publish source-bound sweep timing and executed scheduler characterization."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_stimulus_audio import verify_sources
from tools.audit_sweep_timing import reload_context
from tools.benchmark_report import sha


def build(timing,divider,out):
    report=bound_report(timing);executed=verify_sources(divider)
    if not report['observer_neutral'] or not executed['passed']:
        raise ValueError('Unqualified prerequisites')
    # Recheck the neutral observer prerequisites, not just their receipt files.
    for name in report['sources']:
        if name.endswith('sweep-observer.json'):bound_report(Path(name))
    interleaves=[p for p in report['pairs'] if p['reload_context']['classification']==
                 'nes_half_frame_between_split_timer_writes']
    if len(interleaves)!=1:raise ValueError('Expected one retained split-write example')
    case=interleaves[0];context=case['reload_context']
    sensitivity={}
    for name,changes,reload in (
        ('remove_observed_half_frame',[],case['spc_reload']),
        ('change_observed_sweep_target',[dict(c,period=c['period']+1) for c in
             context['changes_between_last_timer_writes']],case['spc_reload']),
        ('change_received_timer',context['changes_between_last_timer_writes'],
             dict(case['spc_reload'],period=case['spc_reload']['period']+1))):
        result=reload_context(case['timer_write'],reload,context['packet_writes'],changes)
        sensitivity[name]=result['classification']=='unexplained_reload_difference'
    if not all(sensitivity.values()):raise ValueError('Interleave sensitivity failed')
    paths=[Path(__file__),Path('tools/audit_sweep_timing.py'),timing,divider]
    sources={str(p):sha(p) for p in paths}
    sources.update(report['sources']);sources.update(executed['sources'])
    cards=[]
    for label in ('settle_street','observe_shop','park_00_east_settle'):
        p=Path('build/pulse-sweep-game-1060')/(label+'.png')
        sources[str(p)]=sha(p)
        cards.append(f'<figure><img src="../pulse-sweep-game-1060/{label}.png" '
                     f'alt="Candidate {label}"><figcaption>{label}</figcaption></figure>')
    rows=[]
    for voice,summary in report['summary'].items():
        rows.append(f'<tr><td>Pulse {int(voice)+1}</td><td>{summary["paired"]}</td>'
            f'<td>{summary["minimum_difference_ms"]:.3f} … {summary["maximum_difference_ms"]:.3f}</td>'
            f'<td>{summary["mean_difference_ms"]:.3f}</td><td>{summary["first_target_mismatches"]}</td></tr>')
    events=sorted(context['packet_writes']+context['changes_between_last_timer_writes'],
                  key=lambda e:e['clock'])
    event_rows=[]
    for e in events:
        label=f'Write ${0x4000+e["address"]:04X} = ${e["value"]:02X}' if e['kind']=='W' else 'Half-frame sweep'
        event_rows.append(f'<tr><td>{e["clock"]}</td><td>{label}</td><td>{e["period"]}</td></tr>')
    out.mkdir(parents=True,exist_ok=False)
    # The evidence server deliberately disallows CSV. Publish unchanged rows
    # as JSON without widening its file-type allowlist.
    for system,source in (('snes',Path('build/sweep-timing-snes-1073-sweep.csv')),
                          ('nes',Path('build/sweep-timing-nes-1074-sweep.csv'))):
        if sources.get(str(source))!=sha(source):raise ValueError('Unbound raw trace')
        with source.open() as stream:raw_rows=list(csv.reader(stream))
        target=out/(system+'-trace.json')
        target.write_text(json.dumps(dict(source=str(source),rows=raw_rows))+'\n')
        sources[str(target)]=sha(target)
    result=dict(dataset_verified=True,release_ready=False,physical_audio_verified=False,
        summary=report['summary'],executed_cases=executed['cases'],
        interleave_sensitivity=sensitivity,sources=sources,
        scope='Timing investigation and regression baseline, not an implemented scheduler fix. '
        'NES reference batches original ordered commands at publication-frame timing, '
        'not original sub-frame game timing. Current Rival ROM remains unchanged.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RCR sweep timing</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1150px;margin:auto;padding:24px}
a{color:#9df}td,th{padding:9px;border:1px solid #567}table{border-collapse:collapse}.open{color:#ffd68b}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
figure{margin:0}img{width:100%;image-rendering:pixelated}</style>
<h1>Sweep timing: measured, not fixed yet</h1>
<p>Both instrumented captures retain the complete normal timeline and WAV exactly.
All 23,189 ordered NES pulse writes match the candidate bus; all 8,950 SPC packets match the receiver.
Delays below run from each system's last timer write/reload to its first observed pitch change.
They are not fitted waveform offsets or hardware input latency.</p>
<table><tr><th>Voice</th><th>Pairs</th><th>SPC − NES delay range (ms)</th><th>Mean (ms)</th>
<th>Unlike first targets</th></tr>'''+''.join(rows)+'''</table>
<p class="open">NES replay is frame-quantized. These differences do not recover the original game's
sub-frame write timing or prove the cause of physical combat sputtering. No pairs were silently dropped.</p>
<h2>The one unlike starting timer is accounted for, not hidden</h2>
<p>Packet 6104, source frame 6522, pulse 2: the NES half-frame runs between low and high timer writes.
The high write preserves an already-swept low byte. NES starts the next sweep at 153; SPC reloads the
final raw register pair as 144. Their next targets are therefore 162 and 153. This is an observed replay
interleave, not evidence the corrected arithmetic is wrong or that the original game interleaved identically.</p>
<table><tr><th>NES CPU clock</th><th>Observed event</th><th>Actual period</th></tr>'''+''.join(event_rows)+'''</table>
<p>Removing the observed half-frame, changing its target, or changing the received timer all reject
this explanation in actual-data sensitivity checks. The mismatched pair remains in the report.</p>
<h2>Executed scheduler regression baseline</h2>
<p>36,864 actual SPC routine calls cover both voices, all eight divider settings, every software count
0–23 and pending hardware count 0–15, enabled/disabled/zero-shift sweeps, and timer reloads.
All match the legacy behavior; three deliberately mutated engine variants are detected.</p>
<ul><li>Disabled or zero-shift sweeps return without reading the hardware counter.</li>
<li>A timer reload clears pending hardware ticks but retains the software count.</li>
<li>The threshold is three timer ticks times the selected divider; updating discards excess count.</li></ul>
<p>This is a characterization pass, <strong>not an NES-conformance pass</strong>.
The probe uses a fresh hardware timer phase and does not qualify long-run counter wrap or audio fidelity.
The first probe attempt exposed a missing diagnostic DSP output sink and crashed; that harness setup
was corrected before the successful complete run. No production emulator or game was changed.</p>
<h2>Same candidate, untouched checkpoint frames</h2><div class="grid">'''+''.join(cards)+'''</div>
<p>These are existing candidate capture 1060 frames, not new hardware captures or a new graphics fix.
<a href="../pulse-sweep-review-1070/">Previous arithmetic correction, native listening clips and gameplay checks</a>.</p>
<p class="open">No ROM deployment or restart. Sweep scheduler correction, intermittent combat sound,
strict scrolling publication and full-game speed qualification remain open.</p>
<p><a href="report.json">Source hashes and sensitivity checks</a> ·
<a href="../'''+timing.parent.name+'''/report.json">All 247 timing pairs and exact clocks</a> ·
<a href="../'''+divider.parent.name+'''/report.json">Executed cases and mutations</a> ·
<a href="snes-trace.json">Actual SPC trace (unchanged rows)</a> ·
<a href="nes-trace.json">Actual NES trace (unchanged rows)</a> ·
<a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>''')
    print(json.dumps(dict(dataset_verified=True,bindings=len(sources),sensitivity=sensitivity)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('timing','divider','out'):parser.add_argument('--'+name,type=Path,required=True)
    build(**vars(parser.parse_args()))
