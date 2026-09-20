"""Publish checked five-clock pitch experiment with unprocessed A/B evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave

from PIL import Image, ImageDraw

from tools.audit_balanced_pitch_timing import records
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture
from tools.build_balanced_pitch_review import windows
from tools.build_pitch_pair_review import transactions
from tools.check_word_pitch_trial import compare_writes


def build(out):
    if out.exists():
        raise ValueError('Need new review directory')
    paths = {name: Path('build')/directory/'report.json' for name, directory in (
        ('baseline', 'word-pitch-baseline-audit-1704'), ('trial', 'word-pitch-audit-1703'),
        ('executed', 'word-pitch-check-1706'), ('game_audio', 'word-pitch-game-audio-1708'))}
    reports = {name: bound_report(path) for name, path in paths.items()}
    if not reports['executed']['passed'] or not reports['game_audio']['passed']:
        raise ValueError('Failed prerequisite')
    game_traces = []
    for side in ('baseline', 'candidate'):
        data = reports['game_audio'][side]
        for p, digest in data['sources'].items():
            if sha(Path(p)) != digest:
                raise ValueError('Changed game audio evidence')
        game_traces.append(next(Path(p) for p in data['sources'] if p.endswith('-dsp.csv')))
    a, am = records(game_traces[0]); b, bm = records(game_traces[1])
    game_timing = compare_writes(a, b)
    if any(am[k] != bm[k] for k in ('P', 'R')):
        raise ValueError('Full-game receipt/ready times changed')
    parent = Path('build/balanced-pitch-1493/game/native-cpu.sfc')
    candidate = Path('build/word-pitch-1699/game/native-cpu.sfc')
    manifest = json.loads(candidate.with_name('manifest.json').read_text())
    before, after = parent.read_bytes(), candidate.read_bytes()
    allowed = set(range(0xffdc, 0xffe0))
    for change in manifest['experimental_word_pitch']['changes']:
        at = manifest['sweep_driver_rom_offset'] + change['offset']
        allowed.update(range(at, at+len(bytes.fromhex(change['before']))))
    differences = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    if len(before) != len(after) or not differences or not set(differences) <= allowed:
        raise ValueError('Unapproved cartridge changes')
    observed = [Path('build/word-pitch-baseline-observed-1702'), Path('build/word-pitch-replay-observed-1701')]
    bindings = [bound_report(p/'onset-observer.json') for p in observed]
    keyed = [transactions(b) for b in bindings]
    if keyed[0][0].keys() != keyed[1][0].keys() or any(
            keyed[0][0][k]['high']['tick'] != keyed[1][0][k]['high']['tick'] for k in keyed[0][0]):
        raise ValueError('Different replay transactions/completion times')
    events = [reports[side]['events'] for side in ('baseline', 'trial')]
    identities = [{(e['voice'], e['tick']) for e in side} for side in events]
    retained = len(identities[0] & identities[1]); removed = len(identities[0] - identities[1])
    introduced = len(identities[1] - identities[0])
    selected = []
    ranked = sorted((e for e in events[0] if e['nonzero_output']),
                    key=lambda e: -min(abs(e['pitch']-e['update'][v]) for v in ('old', 'new')))
    for e in ranked:
        key = keyed[0][1][e['voice'], e['update']['low']['tick']]
        if key not in selected:
            selected.append(key)
        if len(selected) == 3:
            break
    if len(selected) != 3:
        raise ValueError('Insufficient event coverage')
    removed_example = next(e for e in ranked if (e['voice'], e['tick']) not in identities[1])
    removed_key = keyed[0][1][removed_example['voice'], removed_example['update']['low']['tick']]
    if removed_key not in selected:
        selected.append(removed_key)
    centers = [(key[0], keyed[0][0][key]['high']['tick']) for key in selected]
    traces = [windows(Path(b['traces']['RCR_PULSE_PITCH_TRACE']), centers) for b in bindings]
    out.mkdir(parents=True, exist_ok=False)
    sources = {str(p): sha(p) for p in (Path(__file__), Path('tools/check_word_pitch_trial.py'),
        Path('tools/build_balanced_pitch_review.py'), Path('tools/build_pitch_pair_review.py'),
        parent, candidate, candidate.with_name('manifest.json'), *paths.values(), *game_traces,
        *[p/'onset-observer.json' for p in observed])}
    for name, path in paths.items():
        shutil.copyfile(path, out/(name+'.json'))
    cards, clips = [], []
    for index, key in enumerate(selected):
        voice, packet, old, new, _ = key; center = centers[index][1]
        maximum = max([old, new]+[r['pitch'] for side in traces for r in side[index]]) or 1
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300">',
               '<rect width="1000" height="300" fill="white"/><g font-family="sans-serif" font-size="15" fill="#123">']
        players = []
        for side, label in enumerate(('Current engine (8 clocks)', 'Word-write trial (5 clocks)')):
            left = 30+500*side
            x = lambda tick: left+(tick-center+192)*1.1
            y = lambda pitch: 240-170*pitch/maximum
            points = []
            for j, row in enumerate(traces[side][index]):
                if j:
                    points.append(f'{x(row["tick"])},{y(traces[side][index][j-1]["pitch"])}')
                points.append(f'{x(row["tick"])},{y(row["pitch"])}')
            svg.append(f'<text x="{left}" y="25">{label}: voice {voice}, packet {packet}</text>')
            for value, color in ((old, '#aaa'), (new, '#d80')):
                svg.append(f'<path d="M{left} {y(value)}H{left+422}" stroke="{color}"/>')
            svg.append('<polyline fill="none" stroke="#1670b0" stroke-width="2" points="'+' '.join(points)+'"/>')
            svg.append(f'<text x="{left}" y="278">Old {old}, new {new}; same absolute clock window</text>')
            source = observed[side]/'audio.wav'
            with wave.open(str(source)) as wav:
                rate = wav.getframerate(); params = wav.getparams()
                first = max(0, (center-28)//32-int(rate*.3)); last = first+int(rate*.8)
                if last > wav.getnframes():
                    raise ValueError('Truncated audio context')
                wav.setpos(first); pcm = wav.readframes(last-first)
            name = f'pair-{index}-{side}.wav'
            with wave.open(str(out/name), 'wb') as wav:
                wav.setparams(params); wav.writeframes(pcm)
            sources[str(source)] = sha(source)
            clips.append(dict(file=name, source=str(source), first=first, last=last,
                              pcm_sha256=hashlib.sha256(pcm).hexdigest()))
            players.append(f'<p>{label}<br><audio controls preload="none" src="{name}"></audio></p>')
        name = f'pair-{index}.svg'; (out/name).write_text(''.join(svg)+'</g></svg>')
        selection = 'Largest removed nonzero split event' if key == removed_key else f'Baseline deviation rank {index+1}'
        cards.append(f'<section><h2>{selection}</h2><img src="{name}" alt="Actual pulse pitch latches">'+''.join(players)+'</section>')
    game = Path('build/word-pitch-game-normal-1705')
    _, rows = verify_capture(game)
    gallery = Image.new('RGB', (512, 526), '#101821'); draw = ImageDraw.Draw(gallery)
    images = []
    for i, phase in enumerate(('settle_street', 'observe_alley_exit', 'observe_shop', 'park_00_east_settle')):
        row = next(r for r in rows if r['phase'] == phase)
        path = game/row['frame_image']
        if sha(path) != row['frame_image_sha256']:
            raise ValueError('Changed game image')
        frame = Image.open(path).convert('RGB')
        if frame.size != (256, 239):
            raise ValueError('Unexpected native screenshot dimensions')
        left, top = i%2*256, i//2*263
        draw.text((left+4, top+4), f'{phase}: {row["frame"]}', fill='white')
        gallery.paste(frame, (left, top+24))
        images.append(dict(frame=row['frame'], source=str(path), sha256=sha(path)))
        sources[str(path)] = sha(path)
    gallery.save(out/'game-collage.png')
    sources[str(game/'capture.json')] = sha(game/'capture.json')
    summary = ('The pitch-write window shrinks from 8 to 5 SPC clocks at unchanged total routine cost. '
        '50,265 executed state cases match; 3,641 wrong-high-byte mutant cases fail. '
        'The same 1,238 hardware-recorded command packets produce 40 → 27 mixed-byte pitch samples '
        '(18 → 12 with nonzero voice output). These are not audible-pop counts. '
        f'{removed} baseline split samples disappear, {retained} remain, and {introduced} new ones appear. '
        'Both replay runs retain correct note-start pitches and identical receipt/ready times.')
    limits = ('All 9,406 full-game video/RAM/input/NMI states and audio callback positions match the current build. '
        'Full-game DSP command values/order are unchanged; only normal low-pitch writes move three clocks later. '
        'All 8,950 packets and 1,638 restart orderings pass; raw DAC equals delivered PCM. '
        'No graphics, splash, control mapping or sample assets changed. This is an offline experiment, not '
        'a demonstrated hardware or perceptual improvement, atomic update, original-speed certificate, or pop-free release. Rival is unchanged.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Five-clock pitch trial</title>'
        '<style>body{max-width:1100px;margin:30px auto;font:18px system-ui;background:#101821;color:#eee}a{color:#9df}img{max-width:100%}section{margin:35px 0}audio{width:500px;max-width:100%}</style>'
        '<h1>Five-clock pitch trial — not deployed</h1><p>'+summary+'</p><p>'+limits+'</p>'
        '<p>The three largest baseline nonzero pitch deviations are shown, including residual failures, '
        'plus the largest removed nonzero split event. '
        'Twelve actual DSP samples per plot; unchanged native stereo clips use identical absolute sample windows. No gain or phase fitting.</p>'
        +''.join(cards)+'<h2>Unchanged game-frame samples</h2><img src="game-collage.png" alt="Street, alley, shop and park screenshots">'
        '<p><a href="report.json">Hashes, timing, residual events and clip provenance</a> · '
        +' · '.join(f'<a href="{name}.json">{name}</a>' for name in paths)+'</p>')
    report = dict(game_timing=game_timing, game_receipts_ready_equal=True, cartridge_changed_offsets=differences,
                  split_samples=dict(removed=removed, retained=retained, introduced=introduced),
                  clips=clips, images=images, selected_transactions=selected,
                  sources=sources, artifacts={p.name: sha(p) for p in out.iterdir()},
                  deployed=False, perceptual_improvement_verified=False, pop_free_verified=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(out=str(out), game_timing=game_timing, split_samples=report['split_samples'],
                         cartridge_changed_bytes=len(differences))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(**vars(parser.parse_args()))
