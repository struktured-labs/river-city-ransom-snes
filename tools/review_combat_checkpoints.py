"""Same-start-state transition comparison, without excusing cadence failures."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import shutil

import numpy as np

from tools.audit_main_display_latency import bound_report
from tools.audit_scroll_publication import rgb555, BACKGROUND_REGION
from tools.benchmark_report import sha


def transition(rows):
    if len(rows)<50 or any(b['frame']!=a['frame']+1 for a,b in zip(rows,rows[1:])):
        raise ValueError('Incomplete or nonconsecutive transition window')
    game=[bytes.fromhex(r['game_ram_hex']) for r in rows]
    native=[bytes.fromhex(r['native_ram_hex']) for r in rows]
    change=next((i for i in range(1,len(rows)) if game[i][0x42]!=game[i-1][0x42]),None)
    off=next((i for i in range(1,len(rows)) if not native[i][0x21]&8 and native[i-1][0x21]&8),None)
    if change is None or off is None:
        raise ValueError('Missing first room/off edges')
    enable=next((i for i in range(off+1,len(rows)) if native[i][0x21]&8),None)
    if enable is None or enable+40>len(rows) or any(game[i][0x42]!=game[change][0x42] for i in range(change,enable+40)):
        raise ValueError('Incomplete first entry/fade; refusing later fallback')
    completions=[]
    for i in range(1,len(rows)):
        delta=(game[i][0x52b]-game[i-1][0x52b])&255
        if delta not in (0,1):
            raise ValueError('Completion counter skipped/reset; not a single-loop observation')
        if delta:
            completions.append(rows[i]['frame'])
    spans=[dict(first=a,last=b,frames=b-a) for a,b in zip(completions,completions[1:])]
    return dict(room=game[change][0x42],change_frame=rows[change]['frame'],
        off_frame=rows[off]['frame'],enable_frame=rows[enable]['frame'],enable_index=enable,
        completion_frame_spans=dict(Counter(s['frames'] for s in spans)),
        off_cadence_completion_intervals=[s for s in spans if s['frames']!=2],
        completion_frames=completions,
        completion_scope='Frame-end original052B increment observations, not exact-PC instruction endpoints. '
                         'First/last incomplete intervals are not measured; every interior counter change retained.')


def load(root):
    report=bound_report(root/'report.json')
    if not report['same_state_comparison_valid'] or not all(report['initial_checks'].values()):
        raise ValueError('Invalid resume state or inputs')
    for p,d in report['artifacts'].items():
        if sha(root/p)!=d:
            raise ValueError('Changed replay artifact')
    rows=json.loads((root/'timeline.json').read_text())
    if len(rows)!=report['replayed_frames'] or rows[0]['frame']!=report['restored_frame']+1:
        raise ValueError('Replay window disagrees with receipt')
    for r in rows:
        if hashlib.sha256(bytes.fromhex(r['game_ram_hex'])).hexdigest()!=r['ram_sha256']:
            raise ValueError('Changed raw game RAM')
    return report,rows


def build(out):
    if out.exists():raise ValueError('Fresh review required')
    cases={'school':[('parent',2129),('shift',2131),('active',2132),('both',2133)],
           'alley':[('parent',2130),('shift',2134),('active',2135),('both',2136)]}
    out.mkdir(parents=True)
    sources={str(Path(p)):sha(Path(p)) for p in (__file__,'tools/replay_combat_checkpoint.py',
        'tools/capture_combat_checkpoints.py','tools/audit_scroll_publication.py')}
    result={};cards=[]
    x0,y0,x1,y1=BACKGROUND_REGION
    for location,variants in cases.items():
        entries=[];pictures=[];reference=None;control=None
        cards.append(f'<h2>{location}: same initial state, four cartridges</h2>')
        for variant,number in variants:
            root=Path('build')/f'{location}-{variant}-resume-{number}'
            report,rows=load(root)
            if variant=='parent':
                if not report['passed'] or report['trial'] is not None:
                    raise ValueError('Parent control not exact')
                control=(report,rows,root)
            else:
                if (report['trial']['variant']!=variant or
                        Path(report['trial']['resume_control'])!=control[2] or
                        report['initial_registers']!=control[0]['initial_registers'] or
                        (root/'initial.ram').read_bytes()!=(control[2]/'initial.ram').read_bytes() or
                        [r['input_requested'] for r in rows]!=[r['input_requested'] for r in control[1]]):
                    raise ValueError('Variants do not share exact initial state and physical input')
            measured=transition(rows);index=measured['enable_index']
            pixels=[rgb555(root/r['frame_image'])[y0:y1,x0:x1] for r in rows[index:index+40]]
            if reference is None:reference=pixels
            visible=next((i for i,p in enumerate(pixels) if np.any(p)),None)
            measured.update(variant=variant,first_nonblack_offset=visible,
                change_to_visible=None if visible is None else measured['enable_frame']+visible-measured['change_frame'],
                off_to_visible=None if visible is None else measured['enable_frame']+visible-measured['off_frame'],
                fixed_offset_mismatch_pixels=[int(np.any(a!=b,axis=2).sum()) for a,b in zip(reference,pixels)],
                exact_same_frame_video=sum(a['video_sha256']==b['video_sha256'] for a,b in zip(control[1],rows)),
                exact_same_frame_pcm=sum(a['audio_sha256']==b['audio_sha256'] for a,b in zip(control[1],rows)),
                source=str(root),all_initial_checks=report['initial_checks'])
            entries.append(measured)
            audio=f'{location}-{variant}.wav';shutil.copyfile(root/'audio.wav',out/audio)
            measured['audio']=dict(file=audio,sha256=sha(out/audio),source=str(root/'audio.wav'),unchanged_whole_replay=True)
            selected=[]
            for offset in (0,7,8,14,24,39):
                r=rows[index+offset];source=root/r['frame_image']
                if sha(source)!=r['frame_image_sha256']:raise ValueError('Changed screenshot')
                name=f'{location}-{variant}-{offset}.png';shutil.copyfile(source,out/name)
                selected.append((offset,name))
            pictures.append((variant,selected))
            sources.update(report['sources'])
            for name in ('report.json','timeline.json','initial.ram','audio.wav'):
                sources[str(root/name)]=sha(root/name)
        result[location]=entries
        cards.append('<table><tr><th>Patch</th><th>Room→visible</th><th>Off→visible</th><th>On→visible</th><th>Fade offsets differing from parent</th><th>Completion intervals ≠2</th></tr>')
        for r in entries:
            cards.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in (
                r['variant'],r['change_to_visible'],r['off_to_visible'],r['first_nonblack_offset'],
                [i for i,n in enumerate(r['fixed_offset_mismatch_pixels']) if n],r['off_cadence_completion_intervals']))+'</tr>')
        cards.append('</table>')
        for offset in (0,7,8,14,24,39):
            cards.append(f'<h3>First rendering-enable +{offset}</h3><div class="grid">')
            for variant,files in pictures:
                filename=dict(files)[offset]
                cards.append(f'<figure><img src="{filename}"><figcaption>{variant}</figcaption></figure>')
            cards.append('</div>')
        for variant,_ in variants:
            cards.append(f'<p>{location} / {variant}: whole native replay, no normalization or time fitting</p><audio controls src="{location}-{variant}.wav"></audio>')
    report=dict(comparisons=result,sources=sources,same_start_state_verified=True,release_ready=False,
        original_speed_verified=False,physical_audio_verified=False,
        scope='Each180-frame branch starts from the identical complete128KiB WRAM and saved CPU registers. '
        'Same-ROM fresh-process controls exactly reproduce uninterrupted video/RAM/input/PCM. '
        'Only source-assembled shift shortcut and/or exact active-row patch allowed. '
        'Fixed40-frame fade comparisons anchor at first observed rendering-enable, not selected best matches. '
        'Different outputs are retained, not equality failures waived. This is SNES-versus-SNES, '
        'not an original-NES school-return benchmark, precise interrupt profile or acoustic certification.')
    page='<!doctype html><meta charset="utf-8"><title>Same-state combat transitions</title><style>body{background:#101820;color:#eef;font:16px system-ui;max-width:1300px;margin:30px auto}a{color:#8df}td,th{border:1px solid #567;padding:8px}.grid{display:grid;grid-template-columns:repeat(4,1fr)}img,audio{width:100%}figure{margin:8px}</style>'
    page+='<h1>Same-state school/alley transition experiments</h1><p>'+html.escape(report['scope'])+'</p><p><a href="report.json">Complete measurements and source hashes</a></p>'+''.join(cards)
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:[{n:r[n] for n in ('variant','change_to_visible','off_to_visible','first_nonblack_offset','off_cadence_completion_intervals')} for r in v] for k,v in result.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
