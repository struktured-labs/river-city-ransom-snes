"""Bind ROM patch scope to exact unmodified-route video/RAM/audio equivalence."""
import argparse
import html
import json
import os
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
except ImportError:
    from benchmark_report import verify_capture, sha


SHOP_PROMPT_OFFSETS = (0x9634, 0x9639, 0x963e, 0x9643, 0x9648,
                       0x964d, 0x9652, 0x9657, 0x965c, 0x9661)


def patch_scope(old_rom, new_rom, old_manifest, new_manifest, offsets=SHOP_PROMPT_OFFSETS):
    before, after = old_rom.read_bytes(), new_rom.read_bytes()
    if len(before) != len(after) or len(before) != 2097152:
        raise ValueError('Not the expected equal-size 2 MiB SNES ROM pair')
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    allowed = set(range(0xffdc, 0xffe0))
    for offset in offsets:
        allowed.update(range(0x30000+offset, 0x30000+offset+3))
    old, new = (json.loads(p.read_text()) for p in (old_manifest, new_manifest))
    old_patches = {p['offset']: p for p in old['patches']}
    new_patches = {p['offset']: p for p in new['patches']}
    additions = set(new_patches) - set(old_patches)
    if (changed != allowed or additions != set(offsets)
            or any(new_patches[offset] != patch for offset, patch in old_patches.items())
            or new['spc_sha256'] != old['spc_sha256']
            or old['source_rom_sha256'] != new['source_rom_sha256']
            or old['rom_sha256'] != sha(old_rom) or new['rom_sha256'] != sha(new_rom)):
        raise ValueError('ROM has edits outside the expected NES shop hardware accesses and checksum')
    return sorted(changed)


def compare(old, new, old_rom, new_rom):
    old_receipt, before = verify_capture(old)
    new_receipt, after = verify_capture(new)
    if (old_receipt['system'] != new_receipt['system'] or old_receipt['system'] != 'snes'
            or old_receipt['scenario_name'] != new_receipt['scenario_name']
            or old_receipt['scenario_name'] != 'traversal-shop-exit'
            or old_receipt['scenario_sha256'] != new_receipt['scenario_sha256']
            or old_receipt['rom_sha256'] != sha(old_rom)
            or new_receipt['rom_sha256'] != sha(new_rom)
            or not old_receipt['capture_complete'] or not new_receipt['capture_complete']
            or len(before) != len(after) or len(before) < 7000):
        raise ValueError('Not complete same-scenario candidate ROM captures')
    gates = dict(
        every_frame_video_hash=all(a['video_sha256'] == b['video_sha256'] for a, b in zip(before, after)),
        every_frame_game_ram_hash=all(a['ram_sha256'] == b['ram_sha256'] for a, b in zip(before, after)),
        every_frame_inputs=all(a['input_delivered'] == b['input_delivered'] == a['input_requested']
                               == b['input_requested'] for a, b in zip(before, after)),
        every_frame_audio_callback=all(a['audio'] == b['audio'] and a['audio_start_sample'] == b['audio_start_sample']
                                       for a, b in zip(before, after)),
        full_wav_bytes=sha(old/'audio.wav') == sha(new/'audio.wav'),
        no_adapter_faults=all(not a['fault'] and not b['fault'] for a, b in zip(before, after)),
    )
    return dict(frames=len(before), scenario_sha256=old_receipt['scenario_sha256'], gates=gates)


def audit(old_rom, new_rom, old_capture, new_capture, shop_report, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    changed = patch_scope(old_rom, new_rom, old_rom.parent/'manifest.json', new_rom.parent/'manifest.json')
    route = compare(old_capture, new_capture, old_rom, new_rom)
    shop = json.loads(shop_report.read_text())
    if (shop.get('schema') != 'rcr-shop-confirm-audit-v1' or shop.get('passed') is not True
            or shop['captures']['snes']['rom_sha256'] != sha(new_rom)
            or shop['captures']['previous']['rom_sha256'] != sha(old_rom)):
        raise ValueError('Shop negative control is not bound to these two ROMs')
    gates = dict(ten_executed_sites_only=len(changed) == 34, **route['gates'],
                 new_shop_prompt_fixed=shop['gates']['prompt_pixels_and_shadow_match'],
                 old_shop_prompt_rejected=shop['gates']['regression_control_rejected'])
    report = dict(schema='rcr-candidate-route-equivalence-v1', passed=all(gates.values()),
                  roms=dict(previous=dict(path=str(old_rom), sha256=sha(old_rom)),
                            corrected=dict(path=str(new_rom), sha256=sha(new_rom))),
                  captures=dict(previous=dict(path=str(old_capture), sha256=sha(old_capture/'capture.json')),
                                corrected=dict(path=str(new_capture), sha256=sha(new_capture/'capture.json'))),
                  shop_prompt_audit=dict(path=str(shop_report), sha256=sha(shop_report)),
                  changed_rom_bytes=[hex(x) for x in changed], route=route, gates=gates,
                  scope='Same input route through shop exit, no purchase. The new shop-confirm path is separately compared with NES. Physical MiSTer audio remains unverified.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    rows = ''.join(f'<tr><td>{"PASS" if value else "FAIL"}</td><td>{html.escape(name)}</td></tr>'
                   for name, value in gates.items())
    def link(target):
        return os.path.relpath(target, out)
    images = ''.join(f'<figure><figcaption>{label}</figcaption><img src="{link(folder/"observe_shop.png")}"></figure>'
                     for label, folder in (('Before', old_capture), ('After', new_capture)))
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>RCR shop prompt candidate regression</title>'
        '<style>body{background:#0e1720;color:#f1f8ff;font:16px system-ui;padding:24px}'
        'a{color:#5fe0ff}table{border-collapse:collapse}td{border:1px solid #687786;padding:9px}'
        'figure{display:inline-block}img{width:512px;image-rendering:pixelated}</style>'
        f'<h1>Corrected candidate: {"PASS" if report["passed"] else "FAIL"}</h1>'
        f'<p>{route["frames"]} complete frames, six exact route/audio checks, and a separate '
        f'<a href="{link(shop_report.parent/"index.html")}">original-NES YES/NO comparison</a>.</p>'
        f'<table>{rows}</table><div>{images}</div>'
        '<p>The MiSTer/OBS HDMI recording chain is silent; this is not a physical-audio verdict.</p>'
        '<a href="report.json">Machine-readable hashes and exact changed ROM offsets</a>')
    print(json.dumps({'passed': report['passed'], 'frames': route['frames'], 'gates': gates}, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('old_rom', 'new_rom', 'old_capture', 'new_capture', 'shop_report', 'out'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.old_rom, args.new_rom, args.old_capture,
                                 args.new_capture, args.shop_report, args.out) else 1)
