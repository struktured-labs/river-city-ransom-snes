"""Bind the observed late interrupt-return wait to a missed native NMI."""
import argparse
import csv
import json
from pathlib import Path

from tools.benchmark_report import sha,verify_capture


def audit(candidate,normal,capture,out):
    n,rows=verify_capture(normal);s,seen=verify_capture(capture)
    if not s['capture_complete'] or rows!=seen or any(n[k]!=s[k] for k in
            ('rom_sha256','audio_sha256','frames','scenario_sha256')):
        raise ValueError('Incomplete/non-neutral instruction observation')
    rom=candidate/'native-cpu.sfc';labels=candidate/'native_runtime.lbl';boot=candidate/'native_boot.lbl'
    if sha(rom)!=n['rom_sha256']:raise ValueError('Wrong ROM')
    image=rom.read_bytes();binding=s['instruction_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256']:raise ValueError('Changed instruction trace')
    def symbols(path):return {r.split()[2].lstrip('.'):int(r.split()[1],16) for r in path.read_text().splitlines()}
    runtime=symbols(labels);native=symbols(boot);wait=runtime['@outside_vblank'];entry=runtime['nmi_rti_return']
    pattern=bytes.fromhex('ad124230fbce0a1cad201c29808d00426840')
    if image[0x10000+wait:0x10000+wait+len(pattern)]!=pattern:raise ValueError('Different return wait')
    records=[]
    with trace.open() as f:
        for raw in csv.reader(f):
            if len(raw)!=10:raise ValueError('Malformed instruction row')
            r=dict(zip(('frame','line','cycle','clock','pc','opcode','a','x','y','stack'),
                       (int(v,16 if i in (4,5) else 10) for i,v in enumerate(raw))))
            offset=(r['pc']>>16&63)*65536+(r['pc']&65535)
            if image[offset]!=r['opcode'] or (records and r['clock']<=records[-1]['clock']):
                raise ValueError('Wrong instruction or clock order')
            r['bytes']=image[offset:offset+3].hex();records.append(r)
    enabled=None;start=None;intervals=[]
    for i,r in enumerate(records):
        if r['bytes'] not in ('9c0042','8d0042'):continue
        value=0 if r['opcode']==0x9c else r['a']&255
        if not value&128 and enabled!=0:start=i
        if value&128 and enabled==0 and start is not None:
            block=records[start:i+1]
            waits=[x for x in block if x['pc']&65535==wait and x['pc']>>16 in range(0xc1,0xc9)]
            late=[x for x in block if x['pc']&65535==entry and 240<=x['line']<262]
            if waits and late:
                native_entries=[x for x in block if x['pc'] in (native['nmi'],0xc00000+native['nmi'])]
                flag_reads=[x for x in block if x['bytes']=='ad1042']
                if (not block[0]['line']<240 or not 240<=waits[0]['line']<262 or
                        r['line']!=0 or native_entries or flag_reads or len(waits)<2):
                    raise ValueError('Not the fresh masked-edge return-wait failure')
                intervals.append(dict(masked=block[0],return_entry=late[0],wait_first=waits[0],
                    wait_last=waits[-1],enabled=r,wait_reads=len(waits),native_nmi_entries=0,
                    nmi_flag_reads=0,masked_master_clocks=r['clock']-block[0]['clock']))
        enabled=value&128
    if not intervals:raise ValueError('No observed late-return lost edge')
    paths=[Path(__file__),Path('tools/benchmark_report.py'),Path('tools/snes9x_instruction_trace.inc'),
        Path('snes/native_runtime.asm'),Path('snes/native_boot.asm'),rom,labels,boot,trace,
        normal/'capture.json',capture/'capture.json',normal/'timeline.json',normal/'audio.wav']
    result=dict(observed_failure=True,observer_neutral=True,intervals=intervals,
        sources={str(p):sha(p) for p in paths},fixed=False,
        scope='Actual opcode/clock trace: NMI masked before VBlank, retained return reaches it '
        'late, no native NMI or NMI-flag read inside interval, repeated $4212 polling until line '
        'zero before re-enable. Specific observed lost-service case; no global no-wait fix validated.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(observed_failure=True,intervals=len(intervals),wait_reads=[r['wait_reads'] for r in intervals])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','normal','capture','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
