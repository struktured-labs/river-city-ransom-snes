"""Prove actual flag acknowledgment, FIFO service and audio publication ordering."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_restored_clock import decode,reconstruct,expired_events
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def event_order(rows,entries,boot,image,initial_id,final_id):
    ins=[r for r in rows if r['kind']=='I']
    acknowledgments=[];services=[];pending=[];audio=[];packets=[]
    for i,r in enumerate(ins):
        pc,low,bank=r['pc'],r['pc']&65535,r['pc']>>16
        if bank in (0,0xc0) and low==boot['audio_publish_bridge']:
            ends=[j for j in range(i+1,len(ins)-1) if ins[j]['opcode']==0x6b and
                  ins[j]['s']==r['s'] and ins[j]['pc']>>16 in (0,0xc0)]
            if not ends:raise ValueError('Incomplete audio bridge in trace')
            audio.append(dict(event=r['nmi_count'],entry=r,returned=ins[ends[0]+1]))
        if bank in (0,0xc0) and low==boot['spc_frame']:
            packets.append(r)
        if not 0xc1<=bank<=0xc8:continue
        if entries['collect_vblank']<=low<entries['ring_read_long'] and image[pc&0x3fffff:(pc&0x3fffff)+3]==bytes.fromhex('ad1042'):
            if i+1==len(ins):raise ValueError('Missing actual flag-read result')
            following=ins[i+1]
            if not following['a']&128:continue
            if (r['enable']&128 or r['depth']!=1 or following['rdnmi']&128 or
                    r['nmi_count']!=following['nmi_count']):
                raise ValueError('Invalid acknowledgment or early active-event identity change')
            acknowledgment=dict(read=r,after=following)
            acknowledgments.append(acknowledgment);pending.append(acknowledgment)
        if low==entries['queued_entry']:
            if not pending:raise ValueError('Queued service without a real acknowledged event')
            acknowledged=pending.pop(0)
            completed=[a for a in audio if a['event']==r['nmi_count'] and a['returned']['clock']<r['clock']]
            if len(completed)!=1:raise ValueError('Prior sound publication not complete before queued service')
            later=[]
            for n in ins[i+1:]:
                nlow,nbank=n['pc']&65535,n['pc']>>16
                if n['pc']==boot['nmi'] or 0xc1<=nbank<=0xc8 and nlow==entries['queued_entry']:break
                if 0xc1<=nbank<=0xc8 and nlow==0xff4f:later.append(n)
            if len(later)!=1 or later[0]['nmi_count']!=(r['nmi_count']+1)&65535:
                raise ValueError('Missing/duplicate actual original interrupt dispatch')
            services.append(dict(acknowledgment=acknowledged,entry=r,original_body=later[0],
                                 old_audio=completed[0]))
    if pending:raise ValueError('Unserved collected event at trace boundary')
    wanted=[(initial_id+i)&65535 for i in range(1,((final_id-initial_id)&65535)+1)]
    if not wanted or [p['nmi_count'] for p in packets]!=wanted or [a['event'] for a in audio]!=wanted:
        raise ValueError('Missing/duplicate or reordered audio event publication')
    return dict(acknowledgments=acknowledgments,services=services,audio=audio,packets=packets,
        packet_intervals_clocks=[b['clock']-a['clock'] for a,b in zip(packets,packets[1:])])


def audit(candidate,capture,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(capture/'report.json')
    if not proof['passed'] or not proof['observed'] or not proof['queue_accounting']:
        raise ValueError('Non-neutral/unbalanced replay')
    for name,d in proof['artifacts'].items():
        if sha(capture/name)!=d:raise ValueError('Changed replay artifact')
    rom=candidate/'native-cpu.sfc'
    if proof['sources'].get(str(rom))!=sha(rom):raise ValueError('Different cartridge')
    queue=json.loads((capture/'queue.json').read_text())
    with (capture/'instructions.csv').open() as stream:rows=[decode(r) for r in csv.reader(stream)]
    clock=reconstruct(rows,proof['first'],proof['last'],rom.read_bytes())
    q=symbols(candidate/'queued-vblank.lbl');boot=symbols(candidate/'native_boot.lbl')
    last=next(r for r in queue['frames'] if r['frame']==proof['last'])
    if queue['initial']['pending'] or queue['initial']['collected'] or queue['initial']['served']:
        raise ValueError('Nonempty starting queue')
    order=event_order(rows,q,boot,rom.read_bytes(),queue['initial']['native_id'],last['native_id'])
    if len(order['acknowledgments'])!=last['collected'] or len(order['services'])!=last['served']:
        raise ValueError('Trace collection/service differs from actual WRAM counters')
    expires=expired_events(rows,boot['nmi'])
    if expires:raise ValueError('Unserviced flag expiry remains in qualified window')
    sources=dict(proof['sources'])
    paths=[Path(__file__),Path('tools/audit_restored_clock.py'),Path('tools/build_retained_producer_guard.py'),
        capture/'report.json',capture/'queue.json',capture/'instructions.csv',candidate/'queued-vblank.lbl',
        candidate/'native_boot.lbl',Path('tests/test_queued_event_order.py')]
    sources.update({str(p):sha(p) for p in paths})
    report=dict(passed=True,clock=clock,order=order,queue=queue,expired=expires,sources=sources,
        release_ready=False,pop_free_verified=False,scope=__doc__+
        ' Actual CPU SPC sender entries, not a DSP waveform-fidelity guarantee. '
        'A once-per-event packet can still arrive late; all publication intervals are retained.')
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,acknowledgments=len(order['acknowledgments']),
        services=len(order['services']),packets=len(order['packets']),intervals=order['packet_intervals_clocks'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','capture','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
