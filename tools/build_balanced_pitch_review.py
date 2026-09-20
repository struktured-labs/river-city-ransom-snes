"""Publish the cycle-balanced pitch candidate and retained rejected experiments."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import wave

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_pitch_pair_review import transactions


def windows(path,centers):
    found=[[] for _ in centers]
    with path.open() as stream:
        for row in csv.reader(stream):
            tick,voice=int(row[0]),int(row[1])
            for i,(v,center) in enumerate(centers):
                if voice==v and -192<=tick-center<192:
                    found[i].append(dict(tick=tick,pitch=int(row[4])))
    if any(len(rows)!=12 or any(b['tick']-a['tick']!=32 for a,b in zip(rows,rows[1:])) for rows in found):
        raise ValueError('Incomplete fixed-clock plot')
    return found


def build(out):
    paths={name:Path('build')/directory/'report.json' for name,directory in (
        ('before','inline-pitch-base-audit-1488'),('after','balanced-pitch-audit-1500'),
        ('executed','balanced-pitch-executed-1505'),('timing','balanced-pitch-timing-1508'),
        ('onsets','balanced-pitch-onsets-1501'),('game_audio','balanced-pitch-game-audio-1502'),
        ('cadence','balanced-pitch-game-cadence-1506'),('renderer','balanced-pitch-game-render-audit-1507'))}
    reports={name:bound_report(path) for name,path in paths.items()}
    observed=[Path('build/inline-pitch-base-observed-1481'),Path('build/balanced-pitch-observed-1495')]
    main_paths=[Path('build/receiver-poll-index-main-1442.csv'),Path('build/balanced-pitch-game-main-1503.csv')]
    if sha(main_paths[0])!=sha(main_paths[1]):raise ValueError('Main instruction trace changed')
    bindings=[bound_report(p/'onset-observer.json') for p in observed];keyed=[transactions(b) for b in bindings]
    if set(keyed[0][0])!=set(keyed[1][0]):raise ValueError('Different pitch publications')
    if any(keyed[0][0][k]['high']['tick']!=keyed[1][0][k]['high']['tick'] for k in keyed[0][0]):
        raise ValueError('Publication completion moved')
    events=sorted((e for e in reports['before']['events'] if e['nonzero_output']),
        key=lambda e:-min(abs(e['pitch']-e['update'][v]) for v in ('old','new')))
    selected=[]
    for e in events:
        key=keyed[0][1][e['voice'],e['update']['low']['tick']]
        if key not in selected:selected.append(key)
        if len(selected)==3:break
    if len(selected)!=3:raise ValueError('Need three distinct actual transactions')
    centers=[(k[0],keyed[0][0][k]['high']['tick']) for k in selected]
    traces=[windows(Path(b['traces']['RCR_PULSE_PITCH_TRACE']),centers) for b in bindings]
    out.mkdir(parents=True,exist_ok=False);sources={str(p):sha(p) for p in (Path(__file__),
        Path('tools/build_pitch_pair_review.py'),*paths.values(),*main_paths,*[p/'onset-observer.json' for p in observed])}
    for name,path in paths.items():shutil.copyfile(path,out/(name+'.json'))
    sections=[];clips=[]
    for i,key in enumerate(selected):
        voice,packet,old,new,ordinal=key;center=centers[i][1]
        maximum=max([old,new]+[r['pitch'] for side in traces for r in side[i]]) or 1
        svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300">',
            '<rect width="1000" height="300" fill="white"/><g font-family="sans-serif" font-size="15" fill="#123">']
        players=[];first=None;last=None
        for s,label in enumerate(('Current Rival engine','Balanced candidate')):
            left=30+s*500;x=lambda tick:left+(tick-center+192)*1.1;y=lambda pitch:240-170*pitch/maximum
            points=[]
            for j,r in enumerate(traces[s][i]):
                if j:points.append(f'{x(r["tick"])},{y(traces[s][i][j-1]["pitch"])}')
                points.append(f'{x(r["tick"])},{y(r["pitch"])}')
            svg.append(f'<text x="{left}" y="25">{label}: voice {voice}, packet {packet}</text>')
            for value,color in ((old,'#aaa'),(new,'#d80')):
                svg.append(f'<line x1="{left}" x2="{left+422}" y1="{y(value)}" y2="{y(value)}" stroke="{color}"/>')
            svg.append('<polyline fill="none" stroke="#1670b0" stroke-width="2" points="'+' '.join(points)+'"/>')
            svg.append(f'<text x="{left}" y="278">Old {old}, new {new}; same absolute clock window</text>')
            src=observed[s]/'audio.wav'
            with wave.open(str(src)) as wav:
                params=wav.getparams();rate=wav.getframerate()
                if first is None:first=max(0,(center-28)//32-int(rate*.3));last=first+int(rate*.8)
                if last>wav.getnframes():raise ValueError('Incomplete listening window')
                wav.setpos(first);pcm=wav.readframes(last-first)
            name=f'pair-{i}-{s}.wav'
            with wave.open(str(out/name),'wb') as wav:wav.setparams(params);wav.writeframes(pcm)
            clips.append(dict(file=name,source=str(src),first=first,last=last,pcm_sha256=hashlib.sha256(pcm).hexdigest()))
            sources[str(src)]=sha(src);players.append(f'<p>{label}<br><audio controls preload="none" src="{name}"></audio></p>')
        svg.append('</g></svg>');name=f'pair-{i}.svg';(out/name).write_text(''.join(svg))
        sections.append(f'<section><img src="{name}" alt="Actual pitch samples before and after">'+''.join(players)+'</section>')
    summary=("The new pitch publisher reduces the two-byte write gap from 17 to 8 SPC clocks, with "
        "no additional total publication cost. Both engines replay the same 2,512 packets and 13,203 "
        "pitch transactions; every high-byte completion time is identical. All 3,482,203 measured "
        "pulse samples are reconstructed from real DSP writes. Split-byte samples fall from 122 to 51; "
        "those with nonzero voice output fall from 37 to 19. Residual errors remain: this is not atomic, "
        "an audible-pop count, a hardware test, or original-NES waveform certification.")
    limits=("50,265 executed state cases preserve final DP/DSP state and exact call cost; a wrong-high-byte "
        "mutant fails 4,082 cases. Continuous delayed-transfer tests pass. The complete game retains every "
        "video/RAM/input/NMI state across 9,406 frames and an identical main instruction trace. Room fades, "
        "3,823 stable main loops, renderer coverage and 1,638 restart orderings pass. All 379,784 DSP "
        "commands retain their values and order: 47,588 low-pitch writes move nine clocks later, and "
        "all other write times and packet/ready records are unchanged.")
    caveat=("The original strict callback-equality check remains FAILED: two adjacent callback pairs "
        "redistribute one sample (frames 2382/2383 and 6341/6342). Each raw DAC stream equals its own "
        "concatenated WAV exactly, and total sample counts match; audio has not been retimed to hide "
        "this difference. The first, unbalanced trial also failed room fades and is not promoted. "
        "Neither trial is deployed. Rival remains on 339d2b220a3a. The physical 17 ms gap and popping "
        "remain open. Splash audio, art and controls are unchanged.")
    page='<!doctype html><meta charset="utf-8"><title>Balanced pitch update trial</title>'
    page+='<style>body{max-width:1100px;margin:30px auto;font:18px sans-serif;background:#101821;color:#eee}a{color:#8df}img{width:100%}section{margin:35px 0}audio{width:500px;max-width:100%}</style>'
    page+='<h1>Balanced pitch update — not deployed</h1>'+''.join('<p>'+html.escape(t)+'</p>' for t in (summary,limits,caveat))
    page+='<p>Below: three largest baseline pitch deviations. Plots and unchanged stereo clips use the same absolute sample window on both sides; no gain, phase or time alignment.</p>'+''.join(sections)
    page+='<p>'+' · '.join(f'<a href="{name}.json">{name}</a>' for name in paths)+'</p>'
    page+='<p><a href="../balanced-pitch-game-entry-1499/">Passing room-entry collages</a> · <a href="../inline-pitch-game-entry-1491/">Rejected first trial collages</a> · <a href="../receiver-poll-rival-review-1479/">Current Rival hardware recording</a></p>'
    (out/'index.html').write_text(page)
    report=dict(sources=sources,clips=clips,write_gaps=[k[2] for k in keyed],
        matched_transactions=len(keyed[0][0]),strict_callback_equality_passed=False,
        deployed=False,pop_free_verified=False,artifacts={p.name:sha(p) for p in out.iterdir()})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),artifacts=len(report['artifacts']),matched_transactions=report['matched_transactions'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
