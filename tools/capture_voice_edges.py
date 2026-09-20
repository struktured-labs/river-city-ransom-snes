"""Read-only all-voice source/mixer observation around previously selected replay edges."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def windows(report, radius=128):
    selected = sorted(e['replay_peak']['sample'] for e in report['events'] if e['mapped']['covered'])
    if not selected or radius < 1:
        raise ValueError('Need prior covered events and a positive fixed radius')
    result = []
    for sample in selected:
        if sample <= radius:
            raise ValueError('Edge too near initialization')
        first,last = sample-radius,sample+radius+1
        if result and first <= result[-1][1]:
            result[-1][1] = max(last,result[-1][1])
        else:
            result.append([first,last])
    return result


def capture(core, fixture, review, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    prior = bound_report(review/'report.json')
    if prior['sources'].get(str(fixture/'manifest.json')) != sha(fixture/'manifest.json'):
        raise ValueError('Different command fixture from reviewed edges')
    selected = windows(prior)
    plan = out.with_name(out.name+'-windows.txt')
    trace = out.with_name(out.name+'-edges.csv')
    if plan.exists() or trace.exists():
        raise ValueError('Fresh trace/plan required')
    paths = [Path(__file__),Path('tools/snes9x_voice_edge.inc'),Path('tools/capture_pulse_onset.py'),
        Path('tools/snes9x_pulse_onset.inc'),Path('tools/snes9x_dsp_latency.inc'),
        core,core.parent.parent/'apu/bapu/dsp/SPC_DSP.cpp',review/'report.json',
        fixture/'manifest.json',fixture/'player.sfc']
    sources = {str(p):sha(p) for p in paths}
    plan.write_text(''.join(f'{a} {b}\n' for a,b in selected))
    env = dict(os.environ,RCR_VOICE_EDGE_WINDOWS=str(plan.resolve()),RCR_VOICE_EDGE_TRACE=str(trace.resolve()))
    subprocess.run([sys.executable,'-m','tools.capture_pulse_onset','--core',str(core),
        '--fixture',str(fixture),'--out',str(out)],env=env,check=True)
    if sources != {str(p):sha(p) for p in paths} or not trace.stat().st_size:
        raise ValueError('Changed source or missing voice trace')
    sources.update({str(p):sha(p) for p in (plan,trace,out/'report.json',out/'onset-observer.json')})
    result = dict(windows=selected,trace=str(trace),radius=128,sources=sources,scope=__doc__)
    (out/'voice-edge-observer.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(windows=len(selected),samples=sum(b-a for a,b in selected),trace=str(trace))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','fixture','review','out'):
        p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
