"""Diagnose fixed failed samples using actual renderer scroll provenance.

This never selects replacement frames, shifts pixels, or promotes a candidate.
Fresh-process observer runs must match every normal timeline field and PCM.
"""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.benchmark_report import verify_capture, sha


def nes_offset(row):
    group, address, next_address, fine = (row[k] for k in
        ('group', 'older_address', 'newer_address', 'fine_x'))
    if not 0 <= group < 32 or not 0 <= fine < 8 or not row['mask'] & 8:
        raise ValueError('Unsupported NES pixel group')
    following = address ^ 0x41f if address & 31 == 31 else address + 1
    if next_address != following:
        raise ValueError('Nonconsecutive NES shifter fetches')
    return (((address & 31) * 8) + ((address >> 10) & 1) * 256 + fine - group * 8) & 511


def load_lines(path, system, frames):
    selected = {frame: {} for frame in frames}
    with path.open() as stream:
        for raw in csv.DictReader(stream):
            row = {key: int(value) for key, value in raw.items()}
            if row['frame'] not in selected:
                continue
            line = row['line']
            if not 32 <= line < 192:
                raise ValueError('Unexpected renderer line')
            group = row['group'] if system == 'nes' else 0
            if system == 'nes':
                offset = nes_offset(row)
            else:
                if row['mode'] != 0 or not row['main_screen'] & 1 or row['forced_blank']:
                    raise ValueError('Unsupported SNES rendering state')
                offset = row['h_offset'] & 511
            key = (line, group)
            if key in selected[row['frame']]:
                raise ValueError('Duplicate renderer observation')
            selected[row['frame']][key] = offset
    result = {}
    for frame, pixels in selected.items():
        expected = {(y, g) for y in range(32, 192)
                    for g in range(32 if system == 'nes' else 1)}
        if pixels.keys() != expected:
            raise ValueError('Missing renderer observations')
        lines = {}
        for y in range(32, 192):
            offsets = {v for (line, group), v in pixels.items() if line == y}
            if len(offsets) != 1:
                raise ValueError('Horizontal within-line scroll change; inspect raw trace')
            lines[y] = offsets.pop()
        result[frame] = lines
    return result


def bands(lines):
    result = []
    for y, value in sorted(lines.items()):
        if result and result[-1]['scroll_x'] == value and result[-1]['last_line'] + 1 == y:
            result[-1]['last_line'] = y
        else:
            result.append(dict(first_line=y, last_line=y, scroll_x=value))
    return result


def audit(nes, snes, normal_nes, normal_snes, failures, out, spans=None):
    if out.exists():
        raise ValueError('Use a fresh output directory')
    roots = dict(nes=nes, snes=snes, normal_nes=normal_nes, normal_snes=normal_snes)
    data = {name: verify_capture(root) for name, root in roots.items()}
    for system in ('nes', 'snes'):
        observed, rows = data[system]
        normal, baseline = data['normal_' + system]
        if (observed['system'] != system or normal['system'] != system or
            observed['rom_sha256'] != normal['rom_sha256'] or
            observed['scenario_sha256'] != normal['scenario_sha256'] or
            observed['audio_sha256'] != normal['audio_sha256'] or rows != baseline):
            raise ValueError('Renderer observer is not neutral')
    failed = json.loads((failures / 'report.json').read_text())
    for system in ('nes', 'snes'):
        if failed['sources'][system]['rom_sha256'] != data[system][0]['rom_sha256']:
            raise ValueError('Different failed ROM')
    samples = [r for r in failed['comparisons'] if r['background_playfield_differences']]
    if not samples:
        raise ValueError('No failed samples to diagnose')
    traces = {s: roots[s].with_suffix('.csv') for s in ('nes', 'snes')}
    rendered = {s: load_lines(traces[s], s, [r[s + '_frame'] for r in samples])
                for s in ('nes', 'snes')}
    comparisons = []
    for sample in samples:
        entry = dict(sample)
        for system in ('nes', 'snes'):
            frame = sample[system + '_frame']
            row = data[system][1][frame - 1]
            raw = bytes.fromhex(row['game_ram_hex'])
            if (raw[0x42], int.from_bytes(raw[0xdc:0xde], 'little')) != (sample['room'], sample['camera']):
                raise ValueError('Failed sample game state changed')
            entry[system + '_rendered_bands'] = bands(rendered[system][frame])
            entry[system + '_frame_end_camera'] = raw[0xf6] | ((raw[0x3d] & 1) << 8)
            if system == 'snes':
                entry['snes_frame_end_hdma_table'] = row['native']['hdma_street_scroll_x']
        comparisons.append(entry)
    span_sources = []
    if spans is not None:
        receipt, rows = verify_capture(spans)
        normal, baseline = data['normal_snes']
        if (receipt['rom_sha256'] != normal['rom_sha256'] or rows != baseline or
                receipt['audio_sha256'] != normal['audio_sha256']):
            raise ValueError('CPU span observer is not neutral')
        metadata = json.loads((spans / 'span-points.json').read_text())
        for source, digest in metadata['sources'].items():
            if sha(Path(source)) != digest:
                raise ValueError('CPU span source changed')
        point, = [p for p in metadata['points'] if p['label'] == 'camera_exit']
        trace_path = spans.with_name(spans.name + '-spans.csv')
        exits = {}
        with trace_path.open() as stream:
            for record in csv.reader(stream):
                if int(record[0]) == point['index']:
                    if int(record[5], 16) & 65535 != int(point['pc'], 16):
                        raise ValueError('CPU camera hook PC mismatch')
                    exits.setdefault(int(record[1]), []).append(dict(line=int(record[2]),
                        cycle=int(record[3]), clock=int(record[4]), pc=record[5]))
        for entry in comparisons:
            matching, = exits[entry['snes_frame']]
            entry['snes_camera_hook_entry'] = matching
            entry['camera_hook_after_street_deadline'] = matching['line'] > 32
        span_sources = [trace_path, spans / 'span-points.json', spans / 'capture.json']
    sources = [Path(__file__), Path('tools/fceumm_raster_scroll.inc'),
        Path('tools/snes9x_raster_scroll.inc'),
        Path('.deps/fceumm-raster/src/ppu.c'), Path('.deps/fceumm-raster/src/pputile.h'),
        Path('.deps/fceumm-raster/src/drivers/libretro/libretro.c'),
        Path('.deps/snes9x-raster/gfx.cpp'), Path('.deps/snes9x-raster/libretro/libretro.cpp')]
    result = dict(scope='Diagnosis only. Exact pre-existing failed frames, unchanged images. '
        'All original normal-core timeline fields and PCM identical. No scrolling pass or deployment.',
        observer_neutral=dict(nes=True, snes=True), comparisons=comparisons,
        sources={str(p): sha(p) for p in sources + list(traces.values()) + span_sources + [failures / 'report.json']},
        captures={s: dict(receipt_sha256=sha(roots[s] / 'capture.json'),
            rom_sha256=data[s][0]['rom_sha256'], core_sha256=data[s][0]['core_sha256']) for s in roots})
    out.mkdir(parents=True)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    cards = []
    for sample in comparisons:
        cards.append(f'<h2>Room {sample["room"]}, camera {sample["camera"]}</h2>')
        cards.append('<pre>' + html.escape(json.dumps(sample, indent=2)) + '</pre><section>')
        for system in ('nes', 'snes'):
            name = f'{system}-{sample["room"]}-{sample["camera"]}-background.png'
            shutil.copyfile(failures / name, out / name)
            cards.append(f'<figure><img src="{name}"><figcaption>{system}: unchanged background</figcaption></figure>')
        cards.append('</section>')
    (out / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Renderer scroll diagnosis</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;max-width:1200px;margin:30px auto}'
        'a{color:#9df}section{display:flex}img{width:512px;image-rendering:pixelated}figure{margin:8px}</style>'
        '<h1>Confirmed mid-frame scrolling error — not fixed</h1><p>' + html.escape(result['scope']) +
        '</p><a href="report.json">Bound renderer evidence</a>' + ''.join(cards))
    print(json.dumps(comparisons, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes', 'snes', 'normal-nes', 'normal-snes', 'failures', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--spans', type=Path)
    args = parser.parse_args()
    audit(args.nes, args.snes, args.normal_nes, args.normal_snes, args.failures, args.out, args.spans)
