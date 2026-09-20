"""Qualify the direct receiver dispatch trial without claiming whole-game speed."""
import argparse
import csv
import json
from pathlib import Path
import shutil

from scipy.io import wavfile

from tools.audit_alley_fade_schedule import neutral
from tools.audit_alley_entry_work import return_index
from tools.audit_main_display_latency import bound_report
from tools.audit_mall_fade_timing import audio_sections
from tools.audit_park_instructions import parse
from tools.audit_postpublish_keyon import load
from tools.audit_room_entry import entries
from tools.audit_scroll_publication import frame_path
from tools.benchmark_report import sha, verify_capture
from tools.build_receiver_dispatch_trial import patch
from tools.check_word_pitch_trial import compare_game


def audit(out):
    parent=Path('build/word-pitch-1699/game');candidate=Path('build/receiver-dispatch-1916')
    before=Path('build/receiver-dispatch-baseline-1920');normal=Path('build/receiver-dispatch-normal-1918')
    dsp=Path('build/receiver-dispatch-dsp-1919')
    entry=Path('build/receiver-dispatch-entry-1921/report.json')
    cadence=Path('build/receiver-dispatch-cadence-1927/report.json')
    checker=Path('build/receiver-dispatch-check-1917/report.json')
    sources=[Path(__file__),Path('tools/build_receiver_dispatch_trial.py'),
        Path('tools/audit_mall_fade_timing.py'),Path('tools/audit_alley_fade_schedule.py'),
        Path('tools/audit_park_instructions.py'),Path('tools/audit_alley_entry_work.py'),
        Path('tools/audit_postpublish_keyon.py'),Path('tools/check_word_pitch_trial.py'),
        parent/'manifest.json',parent/'native-cpu.sfc',candidate/'manifest.json',candidate/'native-cpu.sfc',
        before/'capture.json',normal/'capture.json',dsp/'capture.json',entry,cadence,checker]
    pm=json.loads((parent/'manifest.json').read_text());cm=json.loads((candidate/'manifest.json').read_text())
    original=(parent/'native-cpu.sfc').read_bytes();changed=(candidate/'native-cpu.sfc').read_bytes()
    if sha(parent/'native-cpu.sfc')!=pm['rom_sha256'] or sha(candidate/'native-cpu.sfc')!=cm['rom_sha256']:
        raise ValueError('Changed cartridge')
    at=pm['sweep_driver_rom_offset'];size=pm['sweep_driver_layout']['engine_bytes']
    engine,metadata=patch(original[at:at+size],pm['sweep_driver_layout'],pm['receiver_poll'])
    if changed[at:at+size]!=engine:raise ValueError('Different patch')
    differences=[i for i,(a,b) in enumerate(zip(original,changed)) if a!=b]
    if len(original)!=len(changed) or any(not(at<=i<at+size or 0xffdc<=i<0xffe0) for i in differences):
        raise ValueError('CPU/graphics changes outside patch')
    transport,_,_=load(dsp,normal,candidate)
    clock=bound_report(checker);pace=bound_report(cadence)
    visibility=json.loads(entry.read_text())
    if (visibility['audit_sha256']!=sha(Path('tools/audit_room_entry.py')) or
            visibility['sources']['snes']['capture_sha256']!=sha(normal/'capture.json')):
        raise ValueError('Changed room-entry audit')
    base,base_rows=verify_capture(before);trial,trial_rows=verify_capture(normal)
    if base['core_sha256']!=trial['core_sha256'] or base['scenario_sha256']!=trial['scenario_sha256']:
        raise ValueError('Different baseline execution setup')
    state=compare_game(base_rows,trial_rows)
    profiles={}
    for name,root,reference,rom in (
        ('baseline',Path('build/receiver-dispatch-baseline-instructions-1923'),before,parent),
        ('trial',Path('build/receiver-dispatch-trial-instructions-1924'),normal,candidate)):
        receipt,timeline=neutral(root,reference)
        binding=receipt['instruction_trace'];trace=Path(binding['path'])
        if sha(trace)!=binding['sha256']:raise ValueError('Changed instructions')
        with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
        labels=rom/'native_boot.lbl'
        symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
        enable=timeline[entries(timeline)[2]]['frame']
        audio=[dict(entry=r,**audio_sections(rows,i,return_index(rows,i,0x6b),symbols))
            for i,r in enumerate(rows) if enable<=r['frame']<enable+10 and r['pc']==0xc00000+symbols['audio_publish_bridge']]
        if len(audio)!=10 or not all(r['packet'] for r in audio):raise ValueError('Incomplete audio bridge window')
        profiles[name]=dict(enable=enable,audio=audio,summary={k:dict(
            minimum=min(r[k] for r in audio),maximum=max(r[k] for r in audio),mean=sum(r[k] for r in audio)/10)
            for k in ('bridge_clocks','sender_clocks','wait_clocks')})
        sources.extend((root/'capture.json',trace,labels))
    out.mkdir(parents=True,exist_ok=False)
    # Show actual same-frame differences, not an aligned or interpolated collage.
    frames=[338,1542,5964+7,7522]
    figures=[];clips=[]
    for frame in frames:
        figures.append(f'<h3>Actual frame {frame}</h3><div class="grid">')
        for name,root,rows in (('baseline',before,base_rows),('trial',normal,trial_rows)):
            source=frame_path(root,rows[frame-1]);target=f'{name}-{frame}.png'
            shutil.copyfile(source,out/target);sources.append(source)
            figures.append(f'<figure><img src="{target}"><figcaption>{name}</figcaption></figure>')
        figures.append('</div>')
    for name,root,rows in (('baseline',before,base_rows),('trial',normal,trial_rows)):
        rate,pcm=wavfile.read(root/'audio.wav');sources.append(root/'audio.wav')
        for label,first,last in (('mall',5964,6084),('park',7522,7642)):
            a=rows[first-1]['audio_start_sample'];last_row=rows[last-1]
            b=last_row['audio_start_sample']+last_row['audio']['samples'];target=f'{name}-{label}.wav'
            wavfile.write(out/target,rate,pcm[a:b]);clips.append(dict(file=target,source=str(root/'audio.wav'),first=a,last=b))
    saved=100*(1-profiles['trial']['summary']['bridge_clocks']['mean']/profiles['baseline']['summary']['bridge_clocks']['mean'])
    report=dict(rom_sha256=cm['rom_sha256'],changed_rom_bytes=len(differences),patch_scope_verified=True,
        clock_passed=clock['passed'],transport=transport,entry_gates=visibility['gates'],
        cadence_passed=pace['passed'],profiles=profiles,measured_bridge_reduction_percent=saved,
        full_game_comparison=state,clips=clips,release_ready=False,deployed=False,
        observer_neutral=True,physical_speed_verified=False,audible_improvement_verified=False,
        sources={str(p):sha(p) for p in sources},
        scope='Only SPC dispatch target and checksum changed. Ten actual mall audio bridges; '
              'different sub-frame timings, not a whole-game or equal-work speed ratio. '
              'Full parent/trial timeline differences retained. Existing cadence/entry gates '
              'unchanged. No physical or perceptual certification.')
    text='''<!doctype html><meta charset="utf-8"><title>SPC receiver dispatch trial</title>
<style>body{background:#101821;color:#eee;font:18px system-ui;max-width:1100px;margin:2rem auto}
a{color:#8df}.grid{display:grid;grid-template-columns:1fr 1fr}img{width:100%;image-rendering:pixelated}audio{width:100%}</style>
<h1>SPC receiver: remove a redundant polling jump</h1>'''
    text+=f'<p>Ten mall audio bridges: mean {profiles["baseline"]["summary"]["bridge_clocks"]["mean"]:.1f} → {profiles["trial"]["summary"]["bridge_clocks"]["mean"]:.1f} SNES master clocks ({saved:.2f}% less). Individual calls can be slower; all are retained.</p>'
    text+='<p>This is a measured audio-bridge saving, not 4.3% faster gameplay or an audio-pop fix. Sixteen SPC clock cases pass. Actual full-game receiver byte matching and restart ordering pass. Room-entry gates and sampled cadence: see linked reports. Not deployed.</p>'
    text+=f'<p>Full parent/trial equality does NOT pass: {len(state["state_errors"])} frame-state differences and {len(state["callback_changes"])} audio callback-boundary differences retained. Within each trial observer pair, complete timeline and PCM are identical. Earlier/later actor frames need broader validation before promotion.</p>'
    text+=''.join(figures)+'<h2>Native-rate, unchanged audio excerpts</h2>'
    for clip in clips:text+=f'<p>{clip["file"]}<br><audio controls preload="none" src="{clip["file"]}"></audio></p>'
    for name,source in (('cadence.json',cadence),('entry.json',entry),('clock.json',checker)):
        shutil.copyfile(source,out/name);text+=f'<p><a href="{name}">{name}</a></p>'
    text+='<p><a href="report.json">Every measurement, difference and source binding</a> · <a href="../receiver-dispatch-entry-1921/">Original NES room-entry collage</a></p>'
    (out/'index.html').write_text(text)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),bridge_reduction_percent=saved,cadence=pace['passed'],entry=visibility['passed'],bytes=transport['transport']['bytes_compared'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
