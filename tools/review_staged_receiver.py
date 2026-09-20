"""Auditable executed staging prototype, with explicit non-release scope."""
import argparse
import html
import json
from pathlib import Path
import shutil
from tools.review_command_priority import bound
from tools.benchmark_report import sha


def review(first,qualification,audio,out):
    if out.exists():raise ValueError('Fresh report required')
    a=bound(first/'report.json');b=bound(qualification/'report.json');sound=bound(audio/'report.json')
    if not a['passed'] or not b['passed']:raise ValueError('Failed staging evidence')
    chosen=next(c for c in a['cases'] if c['mode']==0 and c['delay']==512 and c['hold']==20000)
    rows=[('Old active',chosen['before'][0x40:0x57]),('Held active',chosen['snapshots'][12][0x40:0x57]),
          ('Staged new packet',chosen['snapshots'][12][388:411]),('Committed before decoding',chosen['snapshots'][14][0x40:0x57])]
    table='<tr><th>State / APU mirror address</th>'+''.join(f'<th>{n:02X}</th>' for n in range(0x40,0x57))+'</tr>'
    for label,values in rows:
        table+='<tr><th>'+label+'</th>'+''.join(f'<td>{n:02X}</td>' for n in values)+'</tr>'
    negatives=''.join('<tr><td>'+html.escape(name)+'</td><td>'+html.escape(', '.join(sorted({e['kind'] for e in result['errors']})))+'</td></tr>' for name,result in b['mutants'].items())
    summary=dict(cases=len(a['cases']),repeated_packets=sum(len(c['records']) for c in b['repeated']),
        negative_controls=len(b['mutants']),core_compatibility_cases=len(b['compatibility']),
        first_check_seconds=a['seconds'],qualification_seconds=b['seconds'],audio=sound['summary'],
        fixture_only=True,game_integration=False,release_ready=False)
    out.mkdir();shutil.copyfile(audio/'native-audio.wav',out/'native-audio.wav')
    body='''<!doctype html><meta charset="utf-8"><title>Staged sound receiver prototype</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1300px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}td,th{padding:5px;border-bottom:1px solid #456;text-align:left}.bytes{font:13px monospace}audio{width:100%}.notice{background:#30291b;padding:16px;border-left:4px solid #efb75c}</style>
<h1>Staged SPC receiver: executed prototype passes isolation checks</h1>
<p class="notice">Fixture only. No game ROM, MiSTer or physical SNES changed. This is the prerequisite buffer, not a finished timing fix: commit is explicitly requested by the fixture, not scheduled to a display deadline. No pop-free, original-speed or onset-latency approval.</p>
<p>Incoming23-byte updates now land in a separate buffer. Active APU state remains unchanged across every tested partial acknowledgement and a complete-but-held update. Explicit D8 commit copies all23 bytes before the existing adapter/translator runs.</p>
<p>24 delay/hold/frame-mode cases pass.202 successive varying packets retain order and complete contents. Eight ordinary-protocol compatibility cases match the old execution core exactly. Four damaged receivers below are rejected. Both half-frame modes keep their existing continuous timer deadlines during the24 held-update cases.</p>
<h2>Native DSP audio, unmodified samples</h2>
<audio controls preload="none" src="native-audio.wav"></audio>
<p>One pulse tone, a staged replacement held for20,000 SPC clocks, then commit. DSP pitch remains052C while held and becomes040C after commit.33,168 stereo sample frames, zero clipped samples. This synthetic fixture clip is not game music or a listening verdict; terminal DSP backlog is not forced to flush.</p>
<h2>Actual active/staged bytes (delay512, hold20,000)</h2><table class="bytes">'''+table+'''</table>
<p>The commit snapshot precedes normal adapter decoding, which deliberately consumes metadata and event flags. All partial snapshots and every repeated packet remain in the source-bound reports.</p>
<h2>Executed broken controls</h2><table><tr><th>Mutation</th><th>Detected failure</th></tr>'''+negatives+'''</table>
<h2>What remains</h2><p>Automatic bounded presentation scheduling, a portable CPU/SPC timing contract, late/missing update and resynchronization policy, current-game integration, native music/SFX/onset comparisons, and graphics/speed tradeoff tests. The prototype withholds ready until commit, so the next producer update must never be allowed to block past its budget.</p>
<p><a href="report.json">Summary and exact bindings</a> · <a href="../current-audio-pipeline-review-4052/">Measured timing requirement</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue6</a></p><details><summary>Metrics</summary><pre>'''+html.escape(json.dumps(summary,indent=2))+'</pre></details>'
    (out/'index.html').write_text(body)
    paths=[Path(__file__),first/'report.json',qualification/'report.json',audio/'report.json',audio/'native-audio.wav']
    report=dict(summary=summary,sources={str(p):sha(p) for p in paths},
        artifacts={p.name:sha(p) for p in out.iterdir()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('first','qualification','audio','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
