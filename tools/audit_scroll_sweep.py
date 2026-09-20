"""Dense fixed-band camera sweep, selected by game state rather than pixels."""
import argparse
import html
import json
from pathlib import Path
import shutil

try:
    from .benchmark_report import verify_capture, sha
    from .audit_scroll_publication import frame_path, mismatch, BACKGROUND_REGION
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit_scroll_publication import frame_path, mismatch, BACKGROUND_REGION

ROOMS = (0, 1, 2, 3)
MIN_COMMON = 64


def state(row):
    raw = bytes.fromhex(row['game_ram_hex'])
    if len(raw) != 2048:
        raise ValueError('Need original 2 KiB RAM')
    mask = row['native']['ppu_mask'] if 'native' in row else row['nes_ppu']['mask']
    valid = (bool(mask & 8) and raw[0x100] == 0xc0 and not raw[0x107] & 0x80
             and not raw[0x3e] & 0x80 and not raw[0x3f] & 0x20
             and not row.get('native', {}).get('transition_state', 0))
    return valid, (raw[0x42], int.from_bytes(raw[0xdc:0xde], 'little'))


def observations(rows, post_fade=False):
    first, stable, publications = {}, {}, []
    previous = None
    gameplay_started=False
    for row in rows:
        if row.get('phase')=='settle_street':gameplay_started=True
        valid, key = state(row)
        if not valid or key[0] not in ROOMS:
            previous = None
            continue
        native = row.get('native')
        if native:
            raw = bytes.fromhex(row['game_ram_hex'])
            expected = raw[0xf6] | ((raw[0x3d] & 1) << 8)
            if native['hdma_street_scroll_x'] != expected:
                publications.append(dict(frame=row['frame'], room=key[0], camera=key[1],
                    expected=expected, actual=native['hdma_street_scroll_x']))
        if post_fade:
            raw = bytes.fromhex(row['game_ram_hex'])
            # Original E343..E39E ends fade-in at level 4 and clears bit 1.
            # Exclude phase-mixed black/fading samples without inspecting
            # pixels. Keep publication checks above active during fades too.
            if not gameplay_started or raw[0x3e]&2 or raw[0x692]!=4:
                previous=None
                continue
        first.setdefault(key, row)
        if previous is not None and previous[0] == key and previous[1]+1 == row['frame']:
            stable.setdefault(key, row)
        previous = key, row['frame']
    return first, stable, publications


def audit(reference, candidate, out, post_fade=False):
    data = [verify_capture(p) for p in (reference, candidate)]
    for system, (r, rows) in zip(('nes', 'snes'), data):
        if (r['system'] != system or not r['capture_complete'] or not r['frame_images']
                or any(x['fault'] or x['input_requested'] != x['input_delivered'] for x in rows)):
            raise ValueError('Need complete fault-free exact-frame ordinary-input captures')
    if (data[0][0]['scenario_sha256'] != data[1][0]['scenario_sha256']
            or data[0][0]['rom_sha256'] != data[1][0]['templates']['menu']['source_rom']):
        raise ValueError('Mismatched input scenario or original ROM')
    a_first, a_stable, _ = observations(data[0][1],post_fade)
    b_first, b_stable, publications = observations(data[1][1],post_fade)
    common = sorted(a_stable.keys() & b_stable.keys())
    out.mkdir(parents=True, exist_ok=False)
    comparisons = []
    cards = []
    for room, camera in common:
        key = room, camera
        a, b = a_stable[key], b_stable[key]
        paths = frame_path(reference, a), frame_path(candidate, b)
        different, _ = mismatch(*paths, BACKGROUND_REGION)
        comparison = dict(room=room, camera=camera, nes_frame=a['frame'], snes_frame=b['frame'],
            nes_settle=a['frame']-a_first[key]['frame'], snes_settle=b['frame']-b_first[key]['frame'],
            mismatch_pixels=different)
        comparisons.append(comparison)
        # Every failed comparison is visible. Passing fixed 9-bit/boundary
        # checkpoints are included without searching for a pretty frame.
        if different or camera in (0, 64, 128, 254, 255, 256, 258, 384, 510, 511, 512):
            cards.append(f'<h2>Room {room}, camera {camera}: {different} differing pixels</h2><section>')
            for label, path in zip(('NES', 'SNES'), paths):
                target = f'room-{room}-camera-{camera:03d}-{label.lower()}.png'
                shutil.copyfile(path, out/target)
                cards.append(f'<figure><img loading="lazy" src="{target}"><figcaption>{label}</figcaption></figure>')
            cards.append('</section>')
    coverage = {str(room):dict(common=sum(k[0] == room for k in common),
        nes_only=[k[1] for k in sorted(a_stable.keys()-b_stable.keys()) if k[0] == room],
        snes_only=[k[1] for k in sorted(b_stable.keys()-a_stable.keys()) if k[0] == room]) for room in ROOMS}
    gates = dict(at_least_64_common_camera_positions_per_room=all(x['common'] >= MIN_COMMON for x in coverage.values()),
        all_fixed_background_bands_exact=bool(comparisons) and all(not x['mismatch_pixels'] for x in comparisons),
        no_late_scroll_publications=not publications,
        stable_samples_no_later_than_original=bool(comparisons) and all(x['snes_settle'] <= x['nes_settle'] for x in comparisons))
    report = dict(passed=all(gates.values()), gates=gates, region=BACKGROUND_REGION,post_fade=post_fade,
        coverage=coverage, comparisons=comparisons, late_publications=publications,
        sources={system:dict(capture_sha256=sha(p/'capture.json'),rom_sha256=r['rom_sha256'])
                 for system,p,(r,_) in zip(('nes','snes'),(reference,candidate),data)},
        audit_sha256=sha(Path(__file__)),
        scope='First second-consecutive rendering-enabled eligible sample at every common room/camera position, '
              'with all missing positions retained. Fixed y=32..79 RGB555 band, no image alignment '
              'or dynamically masked pixels. Checks camera publication on every eligible SNES frame. '
              'Enemy states differ; not actor, whole-game speed, or gameplay audio certification.'+
              (' Post-fade variant additionally requires the verified street-arrival phase, original fade bit 1 clear and level 4. '
               'Publication checks still cover fading frames; fixed-offset fade timing remains a separate gate.'
               if post_fade else ' Legacy selection includes black/fading samples and can mix fade phases at camera zero.'))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Dense scrolling audit</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;max-width:1200px;margin:30px auto}a{color:#9df}section{display:flex}figure{margin:12px}img{width:512px;image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        f'<h1>Dense scrolling: {"PASS" if report["passed"] else "FAIL"}</h1><p>'+html.escape(report['scope'])+
        '</p><p><a href="report.json">All camera observations, missing positions and hashes</a></p><pre>'+
        html.escape(json.dumps(dict(gates=gates,coverage=coverage,late_publications=len(publications)),indent=2))+
        '</pre>'+''.join(cards))
    print(json.dumps(dict(passed=report['passed'],gates=gates,positions=len(comparisons),
        differing_positions=sum(bool(x['mismatch_pixels']) for x in comparisons),late_publications=len(publications)),indent=2))
    return report['passed']


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--post-fade',action='store_true',help='Compare completed fade-in scenery; retain all-frame scroll publication checks')
    args=p.parse_args()
    raise SystemExit(0 if audit(args.reference,args.candidate,args.out,args.post_fade) else 1)
