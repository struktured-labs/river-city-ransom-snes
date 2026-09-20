"""Bind phase96 execution and inherited camera execution to the exact candidate."""
import argparse
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_phase_balance_trial import patch, PHASE
from tools.build_main_phase_trial import SIZE
from tools.build_retained_producer_guard import symbols
from tools.check_main_phase_reprobe import relocated_body


def audit(parent,candidate,oracle,camera_proof,out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(oracle/'report.json')
    camera = bound_report(camera_proof)
    if (not proof['passed'] or proof['phase'] != PHASE or len(proof['cases']) != 50 or
            {r['name'] for r in proof['mutants']} !=
            {'wrong-target','lost-high-bit','lost-pause','lost-flags','masked-nmi'} or
            not camera['passed'] or camera['sources'].get(str(parent/'native-cpu.sfc')) != sha(parent/'native-cpu.sfc')):
        raise ValueError('Incomplete or unbound phase/camera execution')
    sources = {**proof['sources'],**camera['sources']}
    for folder in (parent,candidate):
        if sha(folder/'native-cpu.sfc') != json.loads((folder/'manifest.json').read_text())['rom_sha256']:
            raise ValueError('Unbound cartridge')
    for name in ('native_boot.lbl','native_runtime.lbl'):
        if (parent/name).read_bytes() != (candidate/name).read_bytes():
            raise ValueError('Existing symbols moved')
    labels = symbols(candidate/'native_runtime.lbl')
    expected, sites = patch((parent/'native-cpu.sfc').read_bytes(),labels['gameplay_phase_start'])
    image = (candidate/'native-cpu.sfc').read_bytes()
    if image != expected:
        raise ValueError('Different cartridge patch')
    for case in proof['cases']:
        for name,digest in case['sources'].items():
            if sha(Path(name)) != digest:
                raise ValueError('Changed executed fixture')
        sources.update(case['sources'])
        binaries = [Path(p) for p in case['sources'] if p.endswith('/test.bin')]
        if len(binaries) != 1 or str(binaries[0].with_suffix('.lbl')) not in case['sources']:
            raise ValueError('Missing fixture bytes/labels')
        binary = binaries[0]
        body = relocated_body(binary,binary.with_suffix('.lbl'),labels)
        for bank in range(1,9):
            at = bank*65536+labels['gameplay_phase_start']
            if image[at:at+SIZE] != body:
                raise ValueError('Production differs from executed phase96 helper')
    paths = [Path(__file__),Path('tools/build_phase_balance_trial.py'),
             Path('tools/check_main_phase_reprobe.py'),Path('tools/build_retained_producer_guard.py'),
             oracle/'report.json',camera_proof]
    paths += [p/n for p in (parent,candidate) for n in ('manifest.json','native-cpu.sfc','native_runtime.lbl','native_boot.lbl')]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(passed=True,phase=PHASE,cases=50,mutants=proof['mutants'],camera_cases=len(camera['cases']),
                  camera_mutants=len(camera['mutants']),sites=sites,sources=sources,release_ready=False,
                  scope=__doc__+' Only eight immediates plus checksum differ from the camera-qualified parent. '
                  'Not a game timing, scrolling, latency or sound-quality certificate.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('passed','phase','cases','camera_cases')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','oracle','camera-proof','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
