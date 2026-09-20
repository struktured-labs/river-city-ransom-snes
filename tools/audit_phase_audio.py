"""Compare complete input-phase PCM without fitting a time or gain alignment."""
import argparse
import html
import json
from pathlib import Path
import shutil
import wave

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


def phase_rows(rows, phase):
    selected=[r for r in rows if r['phase']==phase]
    if not selected or [r['frame'] for r in selected] != list(range(selected[0]['frame'],selected[-1]['frame']+1)):
        raise ValueError('Need one contiguous nonempty phase')
    return selected


def build(reference,candidate,phase,out):
    captures=[]
    for system,path in zip(('nes','snes'),(reference,candidate)):
        receipt,rows=verify_capture(path)
        if receipt['system']!=system or not receipt['capture_complete'] or any(r['fault'] for r in rows):
            raise ValueError('Need complete fault-free NES/SNES captures')
        if system=='nes' and receipt['rom_sha256']!=receipt['templates']['menu']['source_rom']:
            raise ValueError('Wrong original NES source')
        selected=phase_rows(rows,phase)
        if any(r['input_requested']!=r['input_delivered'] for r in selected):
            raise ValueError('Phase input delivery failed')
        captures.append((system,path,receipt,selected))
    if captures[0][2]['scenario']!=captures[1][2]['scenario']:
        raise ValueError('Different input scenarios')
    out.mkdir(parents=True,exist_ok=False)
    report=dict(schema='rcr-phase-audio-v1',release_ready=False,phase=phase,
                scope='Complete same-input-phase PCM, no time or gain fitting; not a synthesis-fidelity or equal-scene-timing verdict',captures=[])
    page=['<!doctype html><meta charset="utf-8"><title>Phase audio comparison</title>',
          '<style>body{background:#121923;color:white;font:16px system-ui;margin:24px}audio{width:90%}img{image-rendering:pixelated;width:512px}</style>',
          f'<h1>{html.escape(phase)} audio</h1>',
          '<p>Full input phase on each platform, without gain or time alignment. Scene events can occur at different offsets. Not a waveform-fidelity verdict.</p>']
    for system,path,receipt,rows in captures:
        with wave.open(str(path/'audio.wav')) as source:
            params=source.getparams()
            raw=source.readframes(source.getnframes())
        start=rows[0]['audio_start_sample']
        end=rows[-1]['audio_start_sample']+rows[-1]['audio']['samples']
        width=params.nchannels*params.sampwidth
        clip=out/f'{system}.wav'
        with wave.open(str(clip),'wb') as target:
            target.setparams(params)
            target.writeframes(raw[start*width:end*width])
        shutil.copyfile(path/f'{phase}.png',out/f'{system}.png')
        metrics=[dict(offset=i,frame=r['frame'],**r['audio']) for i,r in enumerate(rows)]
        report['captures'].append(dict(system=system,capture_sha256=sha(path/'capture.json'),
                                      full_pcm_sha256=sha(path/'audio.wav'),clip_sha256=sha(clip),
                                      sample_rate=params.framerate,start_sample=start,end_sample=end,
                                      frame_metrics=metrics))
        page.append(f'<h2>{system}</h2><audio controls src="{system}.wav"></audio><p>End-of-phase screenshot:</p><img src="{system}.png">')
    page.append('<p><a href="report.json">Every frame’s measurements and source hashes</a></p>')
    (out/'index.html').write_text('\n'.join(page))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--phase',required=True)
    a=p.parse_args()
    build(a.reference,a.candidate,a.phase,a.out)
