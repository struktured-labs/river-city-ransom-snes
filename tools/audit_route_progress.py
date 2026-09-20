"""Compare observed room visits, with unaltered checkpoint images for review."""
import argparse
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


def visits(rows):
    result = []
    for row in rows:
        memory = bytes.fromhex(row['game_ram_hex'])
        if len(memory) != 2048:
            raise ValueError('Room observation requires complete original game RAM')
        room = memory[0x42]
        if not result or result[-1]['room'] != room:
            result.append(dict(room=room, frame=row['frame'], phase=row['phase']))
    if not result:
        raise ValueError('Empty route')
    return result


def compare(reference, candidate):
    a, b = visits(reference), visits(candidate)
    return dict(reference_visits=a, candidate_visits=b,
                room_sequence_matches=[x['room'] for x in a] == [x['room'] for x in b],
                scope='Observed room byte sequence only; not speed, collision, visual or audio equivalence')


def build(reference, candidate, out):
    evidence = [verify_capture(p) for p in (reference, candidate)]
    for system, (receipt, rows) in zip(('nes', 'snes'), evidence):
        if receipt['system'] != system or not receipt['capture_complete']:
            raise ValueError('Need complete NES reference and SNES candidate captures')
        if any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in rows):
            raise ValueError('Capture faults or input delivery mismatch')
    if evidence[0][0]['scenario_name'] != evidence[1][0]['scenario_name']:
        raise ValueError('Different input scenarios')
    if evidence[0][0]['rom_sha256'] != evidence[0][0]['templates']['menu']['source_rom']:
        raise ValueError('Reference does not match original template ROM')
    scoped = []
    for _, rows in evidence:
        starts = [row['frame'] for row in rows if row['phase'] == 'settle_street']
        if not starts:
            raise ValueError('Need recognized street followed by settle_street phase')
        scoped.append([row for row in rows if row['frame'] >= starts[0]])
    result = compare(*scoped)
    result['observation_start'] = 'settle_street; excludes uninitialized boot RAM'
    result['capture_hashes'] = [sha(p/'capture.json') for p in (reference, candidate)]
    out.mkdir(parents=True, exist_ok=False)
    page = ['<!doctype html><meta charset="utf-8"><title>Route progress audit</title>',
            '<style>body{background:#141923;color:#eee;font:16px system-ui;padding:24px}'
            'section{display:flex;gap:24px;flex-wrap:wrap}img{width:512px;image-rendering:pixelated}</style>',
            '<h1>Observed route progress</h1><p>'+html.escape(result['scope'])+'</p>',
            '<p>Room sequence matches: '+str(result['room_sequence_matches'])+'</p>',
            '<pre>'+html.escape(json.dumps(result, indent=2))+'</pre>']
    for phase in ('align_alley', 'enter_alley', 'observe_alley_exit', 'observe_shop'):
        if not all(any(row['phase'] == phase for row in rows) for _, rows in evidence):
            continue
        page.append('<h2>'+phase+'</h2><section>')
        for name, directory in zip(('nes', 'snes'), (reference, candidate)):
            filename = f'{phase}-{name}.png'
            shutil.copyfile(directory/(phase+'.png'), out/filename)
            page.append(f'<figure><figcaption>{name}</figcaption><img src="{filename}" alt="{name} {phase}"></figure>')
        page.append('</section>')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'index.html').write_text('\n'.join(page))
    (out/'bundle.json').write_text(json.dumps({p.name: sha(p) for p in sorted(out.iterdir())}, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result['room_sequence_matches']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'candidate', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if build(args.reference, args.candidate, args.out) else 1)
