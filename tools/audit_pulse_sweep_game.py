"""Qualify the sweep candidate's actual game cadence and publish narrow evidence."""
import argparse
import csv
from html import escape
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.analyze_audio_bus import analyze
from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_route_loop_cadence import measure
from tools.benchmark_report import sha,verify_capture
from tools.correct_pulse_sweep import correct
from tools.prepare_audio import paired_engine,nearest_clock_engine,triangle_dac_release_engine


def audit(candidate,normal,main,baseline,provenance,holds,arithmetic,old_stem,new_stem,nes_stem,out):
    sources={}
    def bind(path):sources[str(path)]=sha(path)
    for path in (Path(__file__),Path('tools/audit_main_store_latency.py'),
                 Path('tools/audit_route_loop_cadence.py'),Path('tools/correct_pulse_sweep.py')):bind(path)
    control,rows=verify_capture(normal);observed,traced=verify_capture(main)
    if rows!=traced or any(control[k]!=observed[k] for k in ('rom_sha256','audio_sha256','frames')):
        raise ValueError('Main observer not neutral')
    binding=observed['main_store_observer']
    for path,digest in binding['sources'].items():
        if sha(Path(path))!=digest:raise ValueError('Changed sparse observer source')
    sources.update(binding['sources']);trace=Path(binding['trace']['path'])
    if sha(trace)!=binding['trace']['sha256']:raise ValueError('Changed main trace')
    rom=candidate/'native-cpu.sfc'
    if sha(rom)!=control['rom_sha256']:raise ValueError('Different candidate ROM')
    points={int(k):int(v,16) for k,v in binding['points'].items()}
    with trace.open() as stream:loops,censored=parse(csv.reader(stream),points,control['frames'],rom.read_bytes())
    for loop in loops:
        loop['nmi_advances']=(loop['finish']['nmi']-loop['start']['nmi'])&65535
    cadence=measure(loops,rows)
    old,old_rows=verify_capture(baseline)
    proofs={}
    for label,path in (('transport',provenance),('holds',holds),('arithmetic',arithmetic)):
        proof=json.loads(path.read_text())
        for source,digest in proof['sources'].items():
            if sha(Path(source))!=digest:raise ValueError('Changed '+label+' source: '+source)
        proofs[label]=proof
    if proofs['transport']['rom_sha256']!=control['rom_sha256'] or not proofs['transport']['passed']:
        raise ValueError('Different/failed transport')
    if not proofs['arithmetic']['passed']:raise ValueError('Arithmetic correction not qualified')
    raw=Path('.deps/upernes/source/asm/Memblers_2a03.bin')
    engine=triangle_dac_release_engine(nearest_clock_engine(paired_engine(raw.read_bytes(),
        reset_notes=True,fast_reset=True)),attack=True,in_place=True)
    old_rom=Path('build/triangle-game-inplace-branded-890/native-cpu.sfc')
    before=old_rom.read_bytes();after=rom.read_bytes();offset=before.find(engine)
    if before.count(engine)!=1 or after[offset:offset+len(engine)]!=correct(engine):
        raise ValueError('Candidate does not contain exactly the intended engine correction')
    changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
    allowed=set(range(offset+0x60b,offset+0x618))|{offset+0x641}|set(range(0xffdc,0xffe0))
    if len(before)!=len(after) or not set(changed)<=allowed or len(changed)!=17:
        raise ValueError('Unexpected non-audio ROM changes')
    # Comparison frames are fixed from the game's first pulse-1 sweep passage.
    first,last=960,1150
    packet_sources={}
    for label,directory in (('old',Path('build/triangle-game-inplace-spc-892')),
                             ('new',Path('build/pulse-sweep-spc-1061'))):
        receipt,_=verify_capture(directory);bus=Path(receipt['audio_bus_trace']['path'])
        if sha(bus)!=receipt['audio_bus_trace']['sha256']:raise ValueError('Changed packet source')
        with bus.open() as stream:packets=analyze(list(csv.reader(stream)),True)['packets']
        packet_sources[label]=[(p['frame'],p['bytes']) for p in packets if first<=p['frame']<=last]
        bind(bus);bind(directory/'capture.json')
    if [p[1] for p in packet_sources['old']]!=[p[1] for p in packet_sources['new']]:
        raise ValueError('Listening window packet bytes/order differ')
    publication_differences=[dict(packet_in_window=i,old_frame=a[0],new_frame=b[0])
        for i,(a,b) in enumerate(zip(packet_sources['old'],packet_sources['new'])) if a[0]!=b[0]]
    out.mkdir(parents=True,exist_ok=False);clips=[]
    for label,directory,expected_rows in (('old',old_stem,old_rows),('corrected',new_stem,rows),
                                           ('nes',nes_stem,None)):
        if label=='nes':
            reference=bound_report(directory/'report.json')
            if reference['timing']!='publication-frame':raise ValueError('Different NES stimulus timing')
            timeline=json.loads((directory/'timeline.json').read_text())
            a=timeline[first-1]['start_sample'];b=timeline[last-1]['end_sample']
            bind(directory/'report.json')
        else:
            receipt,timeline=verify_capture(directory)
            if receipt['audio_stem']['mode']!='pulse1':raise ValueError('Wrong isolated voice')
            if len(timeline)!=len(expected_rows) or any(
                    {k:v for k,v in x.items() if k!='audio'}!={k:v for k,v in y.items() if k!='audio'}
                    for x,y in zip(timeline,expected_rows)):
                raise ValueError('Stem changed game timeline')
            a=timeline[first-1]['audio_start_sample'];end=timeline[last-1]
            b=end['audio_start_sample']+end['audio']['samples'];bind(directory/'capture.json')
        rate,pcm=wavfile.read(directory/'audio.wav');path=out/(label+'-pulse1.wav')
        wavfile.write(path,rate,pcm[a:b]);rr,clip=wavfile.read(path)
        if rr!=rate or not np.array_equal(clip,pcm[a:b]):raise ValueError('Changed audio excerpt')
        clips.append(dict(path=path.name,sha256=sha(path),source=str(directory/'audio.wav'),first=a,last=b,rate=rate))
        for name in ('timeline.json','audio.wav'):bind(directory/name)
    divergences={}
    for field in ('video_sha256','game_ram_hex','nmi_counter','input_delivered','audio_start_sample'):
        divergences[field]=next((i+1 for i,(a,b) in enumerate(zip(old_rows,rows)) if a[field]!=b[field]),None)
    for path in (rom,old_rom,raw,trace,normal/'capture.json',main/'capture.json',baseline/'capture.json',
                 provenance,holds,arithmetic,Path('tools/capture_pulse_stem.py')):bind(path)
    result=dict(rom_sha256=control['rom_sha256'],changed_rom_bytes=len(changed),changed_offsets=changed,
        arithmetic=proofs['arithmetic']['cases'],spc_packets=proofs['transport']['packets'],
        cadence=cadence,censored=censored,holds=proofs['holds']['runs'],
        observer_neutral=True,comparison_frames=[first,last],identical_comparison_packet_bytes=len(packet_sources['old']),
        comparison_publication_frame_differences=publication_differences,
        old_frames=old['frames'],candidate_frames=control['frames'],first_divergence=divergences,
        clips=clips,sources=sources,hardware_deployed=False,release_ready=False,pop_free_verified=False,
        scope='Corrected pulse-1 sweep target arithmetic. Actual game loop cadence and renderer checks; '
        'different encounters, not an equal-work speed ratio. Listening clips retain native samples '
        'and publication-frame NES timing, without alignment/gain fits. Divider timing and combat sputter remain open.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    table=''.join(f'<tr><td>{room}</td><td>{len(v["iterations"])}</td><td>{escape(str(v["nmi_advances"]))}</td>'
                  f'<td>{escape(str(v["start_frame_spans"]))}</td></tr>' for room,v in cadence['rooms'].items())
    panels=[]
    for label,directory in (('Before',baseline),('Candidate',normal)):
        for phase in ('settle_street','observe_shop','park_00_east_settle'):
            path=directory/(phase+'.png')
            if not path.exists():raise ValueError('Missing original game panel')
            panels.append(f'<figure><a href="../{directory.name}/{path.name}"><img src="../{directory.name}/{path.name}" alt="{label} {phase}"></a><figcaption>{label} · {phase}</figcaption></figure>')
    audio=''.join(f'<h3>{c["path"]}</h3><audio controls src="{c["path"]}"></audio>' for c in clips)
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RCR · pulse sweep arithmetic correction</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}a{color:#9df}td,th{padding:9px;border:1px solid #567}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}figure{margin:0}img,audio{width:100%}img{image-rendering:pixelated}.open{color:#ffd68b}</style>
<h1>A real sound-engine arithmetic bug, corrected experimentally</h1>
<p>The legacy pulse-1 sweep subtracts one from the shifted amount before both directions. The NES rule is unchanged positive amount; negative amount plus one. Example: period 172, shift 4 should become 182 for period increase or 161 for period decrease; the old engine gives 181 or 163. See the <a href="https://www.nesdev.org/wiki/APU_Sweep">NESdev hardware reference</a>.</p>
<p>The actual SPC interpreter executes all 28,560 input combinations: 28,560 legacy mismatches, zero corrected mismatches, and zero cycle-count differences. Three executed mutants—restored old adjustment, omitted borrow and incorrect padding timing—are caught. Correction is behind the default-off <code>--experimental-pulse-sweep</code> flag.</p>
<p>Disabling the flag reproduces Rival's existing ROM byte-for-byte. The branded candidate changes only 13 embedded SPC bytes and four checksum bytes. Graphics, controller mappings, splash and game code are unchanged.</p>
<h2>Game validation</h2><p>Candidate route: '''+str(control['frames'])+''' frames, '''+str(proofs['transport']['packets'])+''' actual received SPC packets, no transport mismatch. Instrumented replay is frame/RAM/WAV-neutral to the candidate's normal replay. Run duration is not a speedup/slowdown claim: encounters diverge.</p>
<table><tr><th>Room</th><th>Stable complete loops</th><th>NMI ticks → count</th><th>Start spacing → count</th></tr>'''+table+'''</table>
<p>Renderer audit retains all stops and finds zero short 1/3/4-frame uniform-endpoint irregular holds in either park direction. This does not certify full-game or physical timing.</p>
<h2>Native pulse-1 listening clips</h2><p>Source frames 960–1150; all 192 old/new packet byte sequences match, but 10 packet publication frame labels differ by one frame near the end. Those differences are retained in the report, not aligned away. NES receives the old build's ordered writes at publication-frame cadence. No resampling, gain fit or time warp. Sweep-divider timing remains different; arithmetic correctness is not complete waveform fidelity.</p>'''+audio+'''
<h2>Unaltered game captures</h2><p>Same named scenario checkpoints, not identical encounter states or a pixel-equivalence assertion.</p><div class="grid">'''+''.join(panels)+'''</div>
<p class="open">Not deployed to Rival. Intermittent combat sputtering, sweep-divider timing, full-game qualification and physical audio validation remain open. No restart was made.</p>
<p><a href="report.json">Measurements, exclusions and source hashes</a> · <a href="../pulse-sweep-executed-1055/report.json">All arithmetic cases and mutants</a> · <a href="../pulse-sweep-holds-1069/">Scrolling holds</a> · <a href="../main-phase-rival-review-819/">Evidence hub</a></p></html>''')
    print(json.dumps(dict(cadence_passed=cadence['sampled_two_tick_cadence'],
        rooms={k:dict(loops=len(v['iterations']),ticks=v['nmi_advances']) for k,v in cadence['rooms'].items()},
        compared_packets=len(packet_sources['old']),divergences=divergences)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','normal','main','baseline','provenance','holds','arithmetic',
                 'old-stem','new-stem','nes-stem','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
