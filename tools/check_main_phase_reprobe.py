"""Bind an immediate-only phase revision to every executed eligibility fixture."""
import argparse
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_main_phase_trial import patch, PHASE, SIZE
from tools.build_retained_producer_guard import symbols


def relocated_body(binary, labels, target):
    source = symbols(labels)
    highs = [int(row.split()[1], 16) for row in labels.read_text().splitlines()
             if len(row.split()) == 3 and row.split()[2] == '.@high']
    begin = source['gameplay_phase_start']
    if len(highs) != 1 or highs[0]+2-begin != SIZE:
        raise ValueError('Wrong executed helper extent')
    body = bytearray(binary.read_bytes()[begin-0x8000:begin-0x8000+SIZE])
    if (body[:3] != bytes.fromhex('084820') or body[5:8] != bytes.fromhex('68284c')
            or body[-3:] != bytes.fromhex('606860')):
        raise ValueError('Wrong executed wrapper')
    for offset, name in ((3, 'gameplay_phase_wait'), (8, 'gameplay_iteration_start')):
        if int.from_bytes(body[offset:offset+2], 'little') != source[name]:
            raise ValueError('Unexpected fixture relocation')
        body[offset:offset+2] = target[name].to_bytes(2, 'little')
    return bytes(body)


def validate_images(old, new, start, body):
    expected, sites = patch(old, start)
    if new != expected or len(body) != SIZE:
        raise ValueError('Not the exact immediate-only patch')
    for bank in range(1, 9):
        offset = bank*65536+start
        if new[offset:offset+SIZE] != body:
            raise ValueError('Production helper differs from executed fixture')
    if sum(new)&65535 != int.from_bytes(new[0xffde:0xffe0], 'little'):
        raise ValueError('Wrong checksum')
    return sites


def audit(parent, candidate, oracle, out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(oracle/'report.json')
    if (not proof['passed'] or proof['phase'] != PHASE or len(proof['cases']) != 50
            or {r['name'] for r in proof['mutants']} !=
            {'wrong-target', 'lost-high-bit', 'lost-pause', 'lost-flags', 'masked-nmi'}):
        raise ValueError('Incomplete eligibility/NMI oracle')
    paths = [Path(__file__), Path('tools/build_main_phase_trial.py'),
             Path('tools/build_retained_producer_guard.py'),
             Path('tools/build_inline_pitch_trial.py'), oracle/'report.json']
    sources = dict(proof['sources'])
    images = []
    for folder in (parent, candidate):
        meta = json.loads((folder/'manifest.json').read_text())
        if sha(folder/'native-cpu.sfc') != meta['rom_sha256']:
            raise ValueError('Unbound cartridge')
        images.append((folder/'native-cpu.sfc').read_bytes())
        paths += [folder/name for name in ('manifest.json', 'native-cpu.sfc',
                                          'native_runtime.lbl', 'native_boot.lbl')]
    for name in ('native_runtime.lbl', 'native_boot.lbl'):
        if (parent/name).read_bytes() != (candidate/name).read_bytes():
            raise ValueError('Existing symbols moved')
    target = symbols(candidate/'native_runtime.lbl')
    for case in proof['cases']:
        for name, digest in case['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed executed fixture: '+name)
        sources.update(case['sources'])
        binaries = [Path(p) for p in case['sources'] if p.endswith('/test.bin')]
        if len(binaries) != 1 or str(binaries[0].with_suffix('.lbl')) not in case['sources']:
            raise ValueError('Missing bound fixture bytes/labels')
        binary = binaries[0]
        body = relocated_body(binary, binary.with_suffix('.lbl'), target)
        sites = validate_images(*images, target['gameplay_phase_start'], body)
    sources.update({str(p): sha(p) for p in paths})
    report = dict(passed=True, phase=PHASE, helper_size=SIZE, sites=sites,
                  cases=len(proof['cases']), mutants=proof['mutants'],
                  changed_bytes=sum(a != b for a,b in zip(*images)), sources=sources,
                  release_ready=False,
                  scope='Only eight immediates and checksum change. Every production bank matches '
                        'each executed fixture after two verified address relocations. This proves '
                        'eligibility and ABI, not speed, scrolling cadence or sound fidelity.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed', 'cases', 'changed_bytes', 'phase')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'candidate', 'oracle', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
