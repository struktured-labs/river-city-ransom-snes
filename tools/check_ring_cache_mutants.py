"""Execute damaged production ring helpers against the independent memory oracle."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_inline_pitch_trial import checksum
from tools.check_ring_stride import independent


def mutate(image, needle, replacement, helper, size):
    if len(needle) != len(replacement) or len(image) != 0x200000:
        raise ValueError('Mutation extent changed')
    result = bytearray(image)
    for bank in range(1,9):
        start = bank*65536+helper
        body = image[start:start+size]
        if body.count(needle) != 1:
            raise ValueError('Ambiguous mutation preimage')
        at = start+body.index(needle)
        result[at:at+len(needle)] = replacement
    checksum(result)
    return bytes(result)


def audit(candidate, oracle, core, out):
    if out.exists():
        raise ValueError('Fresh output required')
    proof = bound_report(oracle/'report.json')
    if not proof['passed'] or proof['sources'].get(str(candidate/'native-cpu.sfc')) != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Wrong qualified cartridge')
    meta = json.loads((candidate/'manifest.json').read_text())['experimental_ring_dirty_cache']
    cases = [('vertical-alias',0,'4940','4920'),('horizontal-alias',1,'4920','4940'),
             ('lost-dirty-flag',0,'a9018d851c','a901eaeaea'),
             ('lost-shadow-write',0,'8700','eaea'),('lost-write-count',0,'ee091c','eaeaea')]
    out.mkdir(parents=True)
    results = []
    sources = dict(proof['sources'])
    for name,index,needle,replacement in cases:
        record = proof['cases'][index]
        source = oracle/f'case-{index:03}'/'after'/'test.sfc'
        if record['artifacts'].get(str(source)) != sha(source):
            raise ValueError('Changed executed fixture')
        folder = out/name
        folder.mkdir()
        rom = folder/'test.sfc'
        rom.write_bytes(mutate(source.read_bytes(),bytes.fromhex(needle),bytes.fromhex(replacement),
                               meta['helper'],meta['size']))
        run = subprocess.run([sys.executable,'-m','tools.smoke_libretro','--core',str(core),
            '--rom',str(rom),'--kind','adapter','--frames','120','--ram',str(folder/'memory.ram'),
            '--receipt',str(folder/'receipt.json')],check=True,capture_output=True,text=True,timeout=30)
        (folder/'execution.log').write_text(run.stdout+run.stderr)
        try:
            checked = independent((folder/'memory.ram').read_bytes(),record['case'])
        except ValueError as exc:
            rejected,reason = True,str(exc)
        else:
            raise ValueError('Corrupt helper survived oracle: '+str((name,checked)))
        results.append(dict(name=name,case=record['case'],rejected=rejected,reason=reason,
                            needle=needle,replacement=replacement))
        sources[str(source)] = sha(source)
    paths = [Path(__file__),Path('tools/check_ring_stride.py'),Path('tools/build_inline_pitch_trial.py'),
             Path('tools/smoke_libretro.py'),core,oracle/'report.json',candidate/'manifest.json']
    sources.update({str(p):sha(p) for p in paths})
    report = dict(passed=True,mutants=results,sources=sources,
                  artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
                  scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,rejected=len(results))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','oracle','core','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
