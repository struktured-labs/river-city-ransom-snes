"""Bind targeted production calls to executed helper bytes and exact full-ROM reconstruction."""
import argparse
import json
from pathlib import Path
import tempfile

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_ppu_targeted_trial import build
from tools.build_ppu_register_trial import HELPER,SIZE
from tools.build_retained_producer_guard import symbols


def audit(parent,candidate,qualified,oracle,edges,out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(oracle/'report.json')
    extra = bound_report(edges/'report.json')
    expected = sha(qualified/'native-cpu.sfc')
    if any(not r['passed'] or r['sources'].get(str(qualified/'native-cpu.sfc'))!=expected for r in (proof,extra)):
        raise ValueError('Different executed helper cartridge')
    meta = json.loads((candidate/'manifest.json').read_text())
    target = (candidate/'native-cpu.sfc').read_bytes()
    original = (qualified/'native-cpu.sfc').read_bytes()
    if sha(candidate/'native-cpu.sfc')!=meta['rom_sha256']:
        raise ValueError('Changed candidate')
    with tempfile.TemporaryDirectory(prefix='rcr-targeted-proof-') as directory:
        fresh = Path(directory)/'trial'
        build(parent,fresh)
        if (fresh/'native-cpu.sfc').read_bytes()!=target:
            raise ValueError('Unrelated cartridge difference')
    labels = symbols(qualified/'native_runtime.lbl')
    for bank in range(1,9):
        base = bank*65536
        if (target[base+HELPER:base+HELPER+SIZE]!=original[base+HELPER:base+HELPER+SIZE] or
                target[base+labels['dispatch_write']+3:base+labels['mark_ppu_dirty']] !=
                original[base+labels['dispatch_write']+3:base+labels['mark_ppu_dirty']]):
            raise ValueError('Different executed helper or fallback')
    for report in (proof,extra):
        for case in report['cases']:
            for name,digest in case['artifacts'].items():
                if sha(Path(name))!=digest:
                    raise ValueError('Changed executed fixture')
    sources = {**proof['sources'],**extra['sources'],**meta['experimental_ppu_targeted']['sources']}
    paths = [Path(__file__),Path('tools/build_ppu_targeted_trial.py'),Path('tools/build_ppu_register_trial.py'),
             oracle/'report.json',edges/'report.json',candidate/'manifest.json',candidate/'native-cpu.sfc',
             qualified/'native-cpu.sfc',qualified/'native_runtime.lbl']
    sources.update({str(p):sha(p) for p in paths})
    for name,digest in sources.items():
        if sha(Path(name))!=digest:
            raise ValueError('Changed source: '+name)
    report = dict(passed=True,target_stubs=len(meta['experimental_ppu_targeted']['targets']),
        mirrored_calls=len(meta['experimental_ppu_targeted']['sites']),
        helper_cases=len(proof['cases'])+len(extra['cases']),
        independent_cases=sum(r['independent_oracle'] for r in proof['cases'])+len(extra['cases']),
        executed_mutants=len(proof['mutants']),sources=sources,release_ready=False,
        scope=__doc__+' Helper executions are inherited by byte identity; targeted callers are proven '
        'to differ only in JSL target. This does not independently execute every coroutine return path.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','scope')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','candidate','qualified','oracle','edges','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
