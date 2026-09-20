"""Source-to-picture diagnosis and full-scan experiment, retaining unequal encounters."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from scipy.io import wavfile

from tools.audit_main_display_latency import bound_report
from tools.audit_main_store_latency import parse
from tools.audit_ordinary_route_timing import cadence
from tools.audit_postpublish_keyon import load
from tools.audit_pulse_onset import parse_voice, characterize
from tools.audit_startup_pitch_game import note_windows
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.frame_audit import verify_frame
from tools.review_restart_volume import first_volume_failures


def generations(samples, row):
    """Retain all observed tile generations, including superseded/censored ones."""
    result = []
    decoded = [{k: bytes.fromhex(v) for k, v in s['rows'][str(row)].items()} for s in samples]
    for i in range(1, len(samples)):
        if samples[i]['frame'] != samples[i-1]['frame']+1:
            continue
        for col, (old, value) in enumerate(zip(decoded[i-1]['shadow'], decoded[i]['shadow'])):
            if old == value:
                continue
            end = i+1
            while (end < len(samples) and samples[end]['frame'] == samples[end-1]['frame']+1
                   and decoded[end]['shadow'][col] == value):
                end += 1
            contiguous_end = end < len(samples) and samples[end]['frame'] == samples[end-1]['frame']+1
            record = dict(row=row, col=col, previous=old, value=value, source_frame=samples[i]['frame'],
                          last_observed_frame=samples[end-1]['frame'], superseded=contiguous_end)
            for name in ('staged', 'vram'):
                found = next((j for j in range(i, end) if decoded[j][name][col*2] == value), None)
                record[name+'_frame'] = samples[found]['frame'] if found is not None else None
                record[name+'_latency'] = samples[found]['frame']-samples[i]['frame'] if found is not None else None
            record['status'] = ('published' if record['vram_frame'] is not None else
                                'superseded_without_publication' if contiguous_end else 'right_censored')
            result.append(record)
    return result


def health_gate(event, limit):
    return event['status'] == 'published' and event['vram_latency'] <= limit


def old_samples(root):
    proof = bound_report(root/'publication-state.json')
    result = []
    for key, artifact in sorted(proof['samples'].items(), key=lambda kv: int(kv[0])):
        raw = Path(artifact['path']).read_bytes()
        if len(raw) != 196608:
            raise ValueError('Incomplete memory image')
        rows = {}
        for r in (2, 25):
            rows[str(r)] = dict(shadow=raw[0x12000+r*32:0x12000+(r+1)*32].hex(),
                staged=raw[0x3000+r*64:0x3000+(r+1)*64].hex(),
                vram=raw[0x24000+r*64:0x24000+(r+1)*64].hex())
        result.append(dict(frame=int(key), rows=rows, flags=raw[0x1d00:0x1d80].hex()))
    return proof, result


def audio_and_cadence(candidate, normal, observed):
    proof = bound_report(observed/'startup-game.json')
    receipt, rows = verify_capture(observed)
    plain, control = verify_capture(normal)
    equivalent(receipt, rows, plain, control)
    bus, writes, _ = load(observed, normal, candidate)
    ready, regs, groups = {}, [0]*128, defaultdict(list)
    for raw in csv.reader(Path(receipt['dsp_latency_observer']['traces']['RCR_DSP_LATENCY_TRACE']['path']).open()):
        if raw[0] == 'D':
            regs[int(raw[5])] = int(raw[6])
        elif raw[0] == 'R' and int(raw[1]):
            ready[int(raw[1])] = dict(tick=int(raw[2]), registers=regs.copy())
    for w in writes:
        groups[w['packet']].append(w)
    onsets = characterize(parse_voice(list(csv.reader(Path(proof['onset']).open())), writes), ready)
    windows, inactive, volume_failures = [], [], []
    for e in onsets['events']:
        # Existing window functions filter by packet. Supplying that exact group
        # avoids repeated scans over unrelated packets without changing results.
        w, skip = note_windows([e], groups[e['packet']], ready)
        windows.extend(w); inactive.extend(skip)
        selected = [x for x in groups[e['packet']] if x['register'] in (16*e['voice'], 16*e['voice']+1)
                    and x['tick'] < ready[e['packet']]['tick']]
        if not selected or any(not e['tick']+32 < x['tick'] < e['samples'][6]['tick'] for x in selected):
            volume_failures.append(dict(packet=e['packet'], voice=e['voice'], writes=selected))
    loops, censored = parse(csv.reader(Path(proof['main']).open()), {int(k): v for k, v in proof['points'].items()},
                            len(rows), (candidate/'native-cpu.sfc').read_bytes())
    for loop in loops:
        loop['nmi_advances'] = (loop['finish']['nmi']-loop['start']['nmi']) & 65535
    timing = cadence(loops, rows)
    rate, pcm = wavfile.read(normal/'audio.wav')
    if rate != 32040 or pcm.dtype != np.int16 or pcm.shape[1] != 2:
        raise ValueError('Not native stereo PCM16')
    x = pcm.astype(np.int32)
    audio = dict(restarts=onsets['restarts'], packets=bus['packets'], windows=windows,
        inactive=inactive, failed_pitch=[w for w in windows if not w['passed']], failed_volume=volume_failures,
        wrong_first_pitch=onsets['wrong_first_pitch'], stale_nonzero=onsets['stale_nonzero_onsets'],
        late_volume=first_volume_failures(onsets['events']), kon_phases=sorted({w['kon_tick'] % 64 for w in windows}),
        samples=len(pcm), peak=int(np.abs(x).max()), max_adjacent_step=int(np.abs(np.diff(x, axis=0)).max()),
        rms=float(np.sqrt(np.mean(x.astype(float)**2))), clipped=int(np.count_nonzero(np.abs(x) >= 32767)))
    audio['passed'] = bool(windows) and not any(audio[k] for k in
        ('failed_pitch', 'failed_volume', 'wrong_first_pitch', 'stale_nonzero', 'late_volume', 'clipped'))
    return dict(audio=audio, cadence=timing, censored=censored, frames=len(rows)), dict(proof['sources'], **bus['sources'])


def review(candidate, control_state, parent_state, trial_rows, normal, observed, out):
    started = time.monotonic()
    if out.exists():
        raise ValueError('Fresh report required')
    sources, arms, cards = {}, {}, []
    rowproof = bound_report(trial_rows/'row-observer.json')
    groups = []
    for name, root in (('equal_upload_control', control_state), ('audio_parent', parent_state)):
        proof, samples = old_samples(root)
        groups.append((name, root, proof, samples))
    groups.append(('full_scan_trial', trial_rows, rowproof, json.loads(Path(rowproof['samples']).read_text())))
    out.mkdir()
    targets = {}
    for name, root, proof, samples in groups:
        receipt, timeline = verify_capture(root)
        sources.update(proof['sources'])
        events = generations(samples, 2)+generations(samples, 25)
        for e in events:
            row = timeline[e['source_frame']-1]; ram = bytes.fromhex(row['game_ram_hex'])
            e['source_stable'] = (ram[0x100] == 192 and ram[0x692] == 4 and not ram[0x3e]&130
                                  and not ram[0x3f]&32 and row['native']['transition_state'] == 0)
            e['room'] = ram[0x42]
        choices = [e for e in events if e['row'] == 2 and e['col'] == 9 and e['previous'] == 190
                   and e['value'] == 191 and e['source_stable'] and e['room'] == 3]
        if len(choices) != 1:
            raise ValueError('Ambiguous park health-tile change')
        target = choices[0]; targets[name] = target
        source, visible = target['source_frame'], target['vram_frame']
        if visible is None:
            raise ValueError('Missing target publication')
        crops = []
        for f in (source, visible-1, visible):
            path = verify_frame(root, timeline[f-1]); sources[str(path)] = sha(path)
            full = Image.open(path).convert('RGB')
            file = f'{name}-{f}.png'; full.save(out/file)
            hud = full.crop((64, 8, 96, 32)); hud.save(out/(file[:-4]+'-hud.png'))
            crops.append(np.array(full.crop((72, 16, 80, 24))))
            cards.append(f'<figure><img src="{file}"><img class="hud" src="{file[:-4]}-hud.png">'
                         f'<figcaption>{name}: frame {f}, source +{f-source}</figcaption></figure>')
        target['picture_edge_verified'] = not np.array_equal(crops[0], crops[-1]) and not np.array_equal(crops[-2], crops[-1])
        if not target['picture_edge_verified']:
            raise ValueError('VRAM event not confirmed by rendered health tile')
        arms[name] = dict(rom_sha256=receipt['rom_sha256'], frames=len(timeline), events=events, target=target,
            snapshots=len(samples), stable_latencies={str(r): dict(Counter(str(e['vram_latency']) for e in events
                if e['row'] == r and e['source_stable'])) for r in (2, 25)},
            missing=[e for e in events if e['status'] != 'published'], initial_generation_left_censored=True)
    qualified, bindings = audio_and_cadence(candidate, normal, observed)
    sources.update(bindings)
    limit = targets['equal_upload_control']['vram_latency']
    health = {k: health_gate(v, limit) for k, v in targets.items()}
    if health['audio_parent']:
        raise ValueError('Known delayed health update escaped regression gate')
    for p in (Path(__file__), Path('tests/test_row_publication.py'), Path('tools/capture_row_publication.py'),
              Path('tools/capture_text_publication_state.py'), Path('tools/build_full_row_scan.py'),
              Path('tools/audit_startup_pitch_game.py'), Path('tools/review_startup_pitch_trial.py'),
              Path('tools/audit_pulse_onset.py'), Path('tools/review_restart_volume.py'),
              candidate/'manifest.json', candidate/'native-cpu.sfc', trial_rows/'row-observer.json',
              control_state/'publication-state.json', parent_state/'publication-state.json', observed/'startup-game.json'):
        sources[str(p)] = sha(p)
    result = dict(arms=arms, qualification=qualified, health_latency_limit=limit, health_gate=health,
        known_bad_rejected=not health['audio_parent'], sources=sources, release_ready=False,
        passed=health['full_scan_trial'] and qualified['audio']['passed'] and qualified['cadence']['passed'],
        matched_encounter=False, scope=__doc__+' Source-to-render delays are measured per observed tile generation. '
        'The full-scan route has different encounter/input timing; it is not equal-work speed or pixel equivalence. '
        'Initial generations and unpublished/superseded generations remain explicit. Tile-ID measurements '
        'do not prove palette or whole-game correctness. Only the selected health event has a rendered-pixel edge check.')
    lines = ''.join(f'<tr><td>{k}</td><td>{v["source_frame"]}</td><td>{v["staged_frame"]}</td>'
                    f'<td>{v["vram_frame"]}</td><td>{v["vram_latency"]}</td></tr>' for k,v in targets.items())
    (out/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Row publication experiment</title>
<style>body{{background:#14202b;color:#eef;font:17px system-ui;max-width:1150px;margin:30px auto}}a{{color:#9ef}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr)}}figure{{margin:8px}}img{{width:100%;image-rendering:pixelated}}
img.hud{{width:192px}}td,th{{padding:8px;border-bottom:1px solid #456}}</style>
<h1>Health update delay reduced; original-control target still {"met" if health['full_scan_trial'] else "unmet"}</h1>
<p>One scan-budget operand changes from 32 to 128. DMA byte budget, VBlank guards and staged ownership remain unchanged.
Offline experiment only; not deployed. Different encounters—these are source-to-picture measurements, not aligned replays.</p>
<table><tr><th>Build</th><th>Source</th><th>Staged</th><th>Visible/VRAM</th><th>Delay</th></tr>{lines}</table>
<p>Health delay gate ≤{limit} frames: {health}. The known slow parent fails. Initial and superseded generations are retained in JSON.</p>
<h2>Original full pictures and diagnostic HUD crops</h2><p>Each row: source change, last stale picture, first updated picture.</p>
<div class="cards">{''.join(cards)}</div>
<h2>Timing and sound guards</h2><p>Busy-inclusive four-room cadence: {qualified['cadence']['passed']}.
Actual DSP restart timing: {qualified['audio']['passed']}, {qualified['audio']['restarts']} restarts.
Native audio peak {qualified['audio']['peak']}, maximum adjacent step {qualified['audio']['max_adjacent_step']}.
These do not certify pop-free sound or original-NES equivalence.</p>
<audio controls src="../{normal.name}/audio.wav"></audio>
<p><a href="report.json">All generations, timing, failures, source hashes and scope</a></p>''')
    result['seconds'] = time.monotonic()-started
    result['artifacts'] = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'], health_gate=health, audio=qualified['audio']['passed'],
                         cadence=qualified['cadence']['passed'], seconds=result['seconds'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','control-state','parent-state','trial-rows','normal','observed','out'):
        p.add_argument('--'+k, type=Path, required=True)
    review(**vars(p.parse_args()))
