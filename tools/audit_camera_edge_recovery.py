"""Compare actual native NMI and sound-return events in the pinned combat window."""
import csv
import json
from pathlib import Path
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed
from tools.two_player_combat import installed_policy


def audit():
    out=Path('build/camera-edge-recovery-3825')
    if out.exists():raise ValueError('Fresh output required')
    sources={};results={}
    for key,obs,control in (
        ('before','palette-combat-instructions-3816','palette-combat-instruction-control-3815'),
        ('after','camera-edge-instructions-3822','camera-edge-instruction-control-3821')):
        obs=Path('build')/obs;control=Path('build')/control
        for folder in (obs,control):
            for name in ('instruction-control.json','two-player-instructions.json'):
                proof=bound_report(folder/name);sources.update(proof['sources'])
                sources[str(folder/name)]=sha(folder/name)
        with installed_policy(),installed('sustained-attacks'):
            receipt,rows=verify_capture(obs);plain,baseline=verify_capture(control)
        equivalent(receipt,rows,plain,baseline)
        trace=obs.with_suffix('.csv')
        if sha(trace)!=receipt['instruction_trace']['sha256']:raise ValueError('Changed trace')
        events=[]
        for r in csv.reader(trace.open()):
            pc=int(r[4],16)
            if pc==0x80fb or (pc>>16 in range(0xc1,0xc9) and pc&65535==0xfa64):
                events.append(dict(frame=int(r[0]),line=int(r[1]),cycle=int(r[2]),
                    clock=int(r[3]),pc=pc,kind='nmi' if pc==0x80fb else 'sound_return'))
        nmis=[r['frame'] for r in events if r['kind']=='nmi']
        audio=[r for r in events if r['kind']=='sound_return']
        gaps=[dict(first=a['frame'],last=b['frame'],clocks=b['clock']-a['clock'])
              for a,b in zip(audio,audio[1:])]
        recovered=nmis==list(range(1837,1841)) and [r['frame'] for r in audio]==list(range(1837,1841))
        results[key]=dict(rom_sha256=receipt['rom_sha256'],events=events,gaps=gaps,
                          missing_frame_recovered=recovered)
        for p in (trace,obs/'timeline.json',obs/'audio.wav'):sources[str(p)]=sha(p)
    if results['before']['missing_frame_recovered'] or not results['after']['missing_frame_recovered']:
        raise ValueError('Recovery or actual-negative gate failed')
    sources[str(Path(__file__))]=sha(Path(__file__))
    out.mkdir()
    report=dict(runs=results,sources=sources,release_ready=False,observer_neutral=True,
        scope='Same-core full4930-frame/nativePCM neutrality for each cartridge. '
              'Actual original bad build fails the missing-NMI/audio-call gate. '
              'Every event in the four-frame window retained; not acoustic-pop proof or whole-game speed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(recovered=v['missing_frame_recovered'],gaps=v['gaps']) for k,v in results.items()}))


if __name__=='__main__':audit()
