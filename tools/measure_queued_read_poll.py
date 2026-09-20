"""Measure complete ring-read wrappers in executed active-display ABI fixtures."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def measure(before, after, core, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh isolated output required')
    proofs = [bound_report(p/'report.json') for p in (before, after)]
    if not all(p['passed'] for p in proofs):
        raise ValueError('Failed fixture oracle')
    sources = {}
    for proof in proofs:
        sources.update(proof['sources'])
    out.mkdir(parents=True)
    records = []
    for index, original in enumerate(proofs[0]['cases']):
        case = original['case']
        if case['EVENTS'] or not case['READ_KIND'] or case['TAIL_PENDING']:
            continue
        if case != proofs[1]['cases'][index]['case']:
            raise ValueError('Different fixture inputs')
        arms = {}
        for name, root, proof in zip(('before','after'), (before,after), proofs):
            fixture = root/f'case-{index:03}'
            rom = fixture/'test.sfc'
            for path, digest in proof['cases'][index]['artifacts'].items():
                if sha(Path(path)) != digest:
                    raise ValueError('Changed fixture artifact')
                sources[path] = digest
            candidates = [Path(p).parent for p in proof['sources'] if p.endswith('/queued-vblank.lbl')]
            if len(candidates)!=1:
                raise ValueError('Ambiguous assembled queue helper')
            production = candidates[0]
            entry = symbols(production/'queued-vblank.lbl')[
                'ring_read_long' if case['READ_KIND']==1 else 'ring_read_short']
            sources[str(production/'queued-vblank.lbl')] = sha(production/'queued-vblank.lbl')
            folder = out/f'{index}-{name}'
            folder.mkdir()
            trace = folder/'instructions.csv'
            env = dict(os.environ, RCR_INSTRUCTION_TRACE=str(trace.resolve()),
                       RCR_PROFILE_FIRST='1',RCR_PROFILE_LAST='6')
            command = [sys.executable,'-m','tools.smoke_libretro','--core',str(core),
                '--rom',str(rom),'--kind','adapter','--frames','120']
            for observed in (False,True):
                ram = folder/('observed.ram' if observed else 'normal.ram')
                run = subprocess.run(command+['--ram',str(ram),'--receipt',str(ram.with_suffix('.json'))],
                    env=env if observed else dict(os.environ),capture_output=True,text=True,timeout=30)
                (folder/('observed.log' if observed else 'normal.log')).write_text(run.stdout+run.stderr)
                run.check_returncode()
            if ((folder/'normal.ram').read_bytes() != (folder/'observed.ram').read_bytes() or
                    (folder/'normal.ram').read_bytes() != (fixture/'memory.ram').read_bytes()):
                raise ValueError('Changed complete fixture RAM')
            with trace.open() as stream:
                rows = list(csv.reader(stream))
            bank = 0xc1 if case['READ_KIND']==1 else case['BANK']
            starts = [i for i,r in enumerate(rows) if int(r[4],16)==bank*65536+entry]
            if len(starts)!=1:
                raise ValueError('Missing or duplicate read-wrapper entry')
            start = starts[0]
            # No nested RTS occurs on the qualified active-display fast path.
            # For the old wrapper, find its own return PC from the assembled
            # body, not the first nested collector RTS.
            image = rom.read_bytes()
            load = bytes.fromhex('bf4505006b' if case['READ_KIND']==1 else 'bd450560')
            body = image[(bank&0x3f)*65536+entry:(bank&0x3f)*65536+entry+32]
            if body.count(load)!=1:
                raise ValueError('Changed read/return layout')
            return_pc = bank*65536+entry+body.index(load)+len(load)-1
            ends = [i+1 for i in range(start+1,len(rows)-1) if int(rows[i][4],16)==return_pc]
            if len(ends)!=1:
                raise ValueError('Missing or duplicate actual return')
            end = ends[0]
            if not all(int(r[1])<240 for r in rows[start:end+1]):
                raise ValueError('Timing case crossed VBlank')
            arms[name] = dict(entry=rows[start],after_return=rows[end],
                             clocks=int(rows[end][3])-int(rows[start][3]),instructions=end-start)
        records.append(dict(case=case,arms=arms,saved_clocks=arms['before']['clocks']-arms['after']['clocks']))
    if len(records)!=24:
        raise ValueError('Missing active-display read cases')
    paths = [Path(__file__),before/'report.json',after/'report.json',core,
             Path('tools/smoke_libretro.py'),Path('tools/snes9x_instruction_trace.inc')]
    sources.update({str(p):sha(p) for p in paths})
    report = dict(cases=records,sources=sources,observer_neutral=True,release_ready=False,
        artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},
        scope=__doc__+' Trace-on/off and original oracle fixture full WRAM match. '
        'Savings exclude the unchanged caller JSL/JSR; not a whole-game speedup claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=len(records),saved_clocks=sorted(set(r['saved_clocks'] for r in records)))))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('before','after','core','out'):
        parser.add_argument('--'+key,type=Path,required=True)
    measure(**vars(parser.parse_args()))
