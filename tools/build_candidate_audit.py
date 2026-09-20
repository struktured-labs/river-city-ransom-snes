"""Build one hash-bound web dashboard from the independent release gates."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def all_named_gates(report):
    gates = report.get('gates')
    if isinstance(gates, list):
        return bool(gates) and all(gate.get('passed') is True for gate in gates)
    if isinstance(gates, dict):
        return bool(gates) and all(value is True for value in gates.values())
    return False


def assess(reports):
    bus, ack, keyon = reports['bus'], reports['ack'], reports['keyon']
    packet_count = bus.get('packet_count')
    gates = [
        dict(gate='pause/resume interrupt liveness', passed=reports['pause'].get('passed') is True),
        dict(gate='rightward movement no slower than NES', passed=reports['movement'].get('passed') is True),
        dict(gate='content-adjusted school transition cadence', passed=reports['transition'].get('passed') is True),
        dict(gate='long route room progression', passed=reports['route'].get('room_sequence_matches') is True),
        dict(gate='mixed-gameplay audio discontinuity bound', passed=reports['gameplay_audio'].get('passed') is True),
        dict(gate='isolated pulse-1 phase/transient', passed=reports['pulse1'].get('passed') is True),
        dict(gate='isolated pulse-2 phase/transient', passed=reports['pulse2'].get('passed') is True),
        dict(gate='audio CPU/SPC transport and ACK count',
             passed=(packet_count == keyon.get('packets') == ack.get('acknowledged_packets')
                     and packet_count > 0 and not bus.get('mismatches')
                     and bus.get('unflushed_cpu_writes') == 0
                     and keyon.get('passed') is True and keyon.get('mismatch_count') == 0
                     and ack.get('paired_transfer') is True)),
        dict(gate='room-2 scroll publication', passed=reports['scroll2'].get('passed') is True),
        dict(gate='room-3 scroll publication/boundary', passed=reports['scroll3'].get('passed') is True),
        dict(gate='cafe menu pixels and CHR state', passed=all_named_gates(reports['shop'])),
        dict(gate='mall NPC CHR bank state', passed=reports['mall'].get('mall_chr_banks_match') is True),
    ]
    return gates


def _report(path):
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise ValueError(f'Non-object report: {path}')
    return result


def _link(out, path):
    target = path.parent/'index.html'
    if not target.exists():
        target = path
    return os.path.relpath(target, out).replace(os.sep, '/')


def build(rom, report_paths, captures, out):
    if out.exists():
        raise ValueError('Output directory already exists')
    reports = {name: _report(path) for name, path in report_paths.items()}
    rom_hash = sha(rom)
    capture_hashes = set()
    capture_rows = []
    for root in captures:
        path = root/'capture.json'
        receipt = _report(path)
        if (receipt.get('schema') != 'rcr-benchmark-capture-v1' or receipt.get('system') != 'snes'
                or not receipt.get('capture_complete') or receipt.get('rom_sha256') != rom_hash):
            raise ValueError(f'Capture is not complete or bound to candidate ROM: {root}')
        digest = sha(path)
        capture_hashes.add(digest)
        capture_rows.append(dict(path=str(root), report_sha256=digest,
                                 scenario=receipt['scenario_name'], frames=receipt['frames']))

    expected_hashes = [
        reports['pause'].get('candidate_capture_sha256'),
        reports['movement'].get('capture_sha256', [None, None])[1],
        reports['transition'].get('capture_sha256', {}).get('snes'),
        reports['route'].get('capture_hashes', [None, None])[1],
        reports['gameplay_audio'].get('capture', {}).get('report_sha256'),
        reports['scroll2'].get('capture_sha256', [None, None])[1],
        reports['scroll3'].get('capture_sha256', [None, None])[1],
        reports['shop'].get('capture_sha256', [None, None])[1],
        reports['mall'].get('capture_sha256', [None, None])[1],
    ]
    if any(digest not in capture_hashes for digest in expected_hashes):
        raise ValueError('An audit is not bound to one of the supplied candidate captures')

    gates = assess(reports)
    passed = all(gate['passed'] for gate in gates)
    out.mkdir(parents=True)
    sources = {name: dict(path=str(path), sha256=sha(path), link=_link(out, path))
               for name, path in report_paths.items()}
    result = dict(
        schema='rcr-candidate-audit-dashboard-v1', passed=passed,
        hardware_test_ready=passed, release_ready=False,
        candidate_rom=dict(path=str(rom), sha256=rom_hash), captures=capture_rows,
        gates=gates, sources=sources,
        unresolved=[
            'Analog MiSTer output and subjective listening still require a hardware pass.',
            'Coverage reaches the cafe, exits it, and crosses into the next scrolling room; it is not a whole-game completion proof.',
            'Mixed audio is bounded for discontinuities and transport loss, not declared sample-identical to NES synthesis.',
        ])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')

    gate_rows = ''.join(
        f'<tr><td class="{str(g["passed"]).lower()}">{"PASS" if g["passed"] else "FAIL"}</td><td>{html.escape(g["gate"])}</td></tr>'
        for g in gates)
    source_rows = ''.join(
        f'<tr><td>{html.escape(name)}</td><td><a href="{html.escape(item["link"])}">open evidence</a></td>'
        f'<td><code>{item["sha256"][:16]}…</code></td></tr>' for name, item in sources.items())
    def rel(path):
        return os.path.relpath(path, out).replace(os.sep, '/')
    panels = [
        ('Movement', report_paths['movement'].parent/'snes.png'),
        ('Room 2 scroll', report_paths['scroll2'].parent/'camera-110-collage.png'),
        ('Room 3 boundary', report_paths['scroll3'].parent/'camera-068-collage.png'),
        ('Café', report_paths['shop'].parent/'snes.png'),
        ('Mall NPC scene', report_paths['mall'].parent/'snes.png'),
    ]
    visual = ''.join(f'<figure><figcaption>{html.escape(label)}</figcaption><a href="{rel(path)}"><img src="{rel(path)}"></a></figure>'
                     for label, path in panels if path.exists())
    audio = report_paths['gameplay_audio'].parent/'full.wav'
    unresolved = ''.join(f'<li>{html.escape(item)}</li>' for item in result['unresolved'])
    (out/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>River City Ransom SNES candidate audit</title>'
        '<style>body{background:#0b1018;color:#e8f0fa;font:16px system-ui;max-width:1500px;margin:auto;padding:24px}'
        'h1{color:#55e6ff}a{color:#55e6ff}table{border-collapse:collapse;width:100%;margin:16px 0}'
        'th,td{border:1px solid #465465;padding:.5em;text-align:left}.true{color:#55f09a;font-weight:bold}.false{color:#ff647c;font-weight:bold}'
        '.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px}figure{margin:0;background:#131c28;padding:12px}'
        'img{width:100%;image-rendering:pixelated}audio{width:100%}code{font-size:.85em}</style>'
        f'<h1>Candidate audit: {"hardware-test ready" if passed else "blocked"}</h1>'
        f'<p>ROM SHA-256: <code>{rom_hash}</code>. This dashboard is an index over independent hash-bound reports; it does not replace them.</p>'
        f'<table><tr><th>Status</th><th>Gate</th></tr>{gate_rows}</table>'
        '<h2>Visual evidence</h2><div class="gallery">'+visual+'</div>'
        f'<h2>Complete mixed-gameplay recording</h2><audio controls src="{rel(audio)}"></audio>'
        f'<p><a href="{sources["gameplay_audio"]["link"]}">Open the seekable top-20 transient audit</a>.</p>'
        f'<h2>Evidence index</h2><table><tr><th>Audit</th><th>Review</th><th>Report hash</th></tr>{source_rows}</table>'
        f'<h2>Deliberate limits</h2><ul>{unresolved}</ul><p><a href="report.json">Machine-readable dashboard</a></p>')
    print(json.dumps(dict(passed=passed, hardware_test_ready=passed,
                          rom_sha256=rom_hash, gates=gates), indent=2))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--capture', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    for name in ('pause', 'movement', 'transition', 'route', 'gameplay_audio', 'pulse1',
                 'pulse2', 'bus', 'ack', 'keyon', 'scroll2', 'scroll3', 'shop', 'mall'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = vars(parser.parse_args())
    rom, captures, out = args.pop('rom'), args.pop('capture'), args.pop('out')
    raise SystemExit(0 if build(rom, args, captures, out) else 1)
