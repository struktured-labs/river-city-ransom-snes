"""Bind a lost camera-completion NMI to an observer-neutral instruction trace."""
import argparse
import csv
import json
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
    from .audit_park_instructions import parse as instructions
    from .audit_park_spans import parse as spans
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit_park_instructions import parse as instructions
    from audit_park_spans import parse as spans


def audit(capture,control,candidate,frame,out):
    receipt,frames=verify_capture(capture);normal,_=verify_capture(control)
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=normal[key]:raise ValueError('Observer changed '+key)
    if not receipt['capture_complete'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in frames):
        raise ValueError('Incomplete/faulty capture')
    rom=candidate/'native-cpu.sfc';labels=candidate/'native_runtime.lbl';binary=candidate/'native_runtime.bin'
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Wrong ROM')
    image=rom.read_bytes()
    if any(image[b*65536+0x2000:b*65536+0x6000]!=binary.read_bytes() for b in range(1,9)):
        raise ValueError('Runtime not linked into all game banks')
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in labels.read_text().splitlines()}
    paths=[capture.with_name(capture.name+suffix) for suffix in ('-instructions.csv','-spans.csv')]
    for p,key in zip(paths,('instruction_trace','span_trace')):
        if sha(p)!=receipt[key]['sha256']:raise ValueError('Unbound trace')
    binding=receipt['instruction_trace'];rows=instructions(csv.reader(paths[0].open()),binding['first'],binding['last'])
    events=spans(csv.reader(paths[1].open()),receipt['span_trace'])
    cameras=[r for r in events if r['event']==8 and r['frame']==frame]
    if len(cameras)!=1 or cameras[0]['pending']!=0:raise ValueError('Need one unretained camera completion')
    start=cameras[0]
    end=next(r for r in rows if r['clock']>start['clock'] and r['pc']&65535==symbols['camera_deferred_nmi_quick_return'])
    selected=[r for r in rows if start['clock']<=r['clock']<=end['clock']]
    mask=[r for r in selected if image[r['pc']&0x3fffff:(r['pc']&0x3fffff)+3]==bytes.fromhex('9c0042')]
    waits=[r for r in selected if r['pc']&65535==symbols['@enable_outside_vblank']]
    if len(mask)!=1 or not waits or mask[0]['line']!=239 or waits[0]['line']!=240 or waits[-1]['line']!=0:
        raise ValueError('Trace does not reproduce the fresh-edge crossing')
    if any(r['event']==0 and start['clock']<=r['clock']<=end['clock'] for r in events):
        raise ValueError('An NMI serviced the allegedly lost edge')
    next_nmi=next(r for r in events if r['event']==0 and r['clock']>end['clock'])
    if next_nmi['frame']!=frame+1:raise ValueError('Unexpected subsequent NMI frame')
    report=dict(observer_equivalent=True,frame=frame,camera=start,mask_instruction=mask[0],
        first_wait=waits[0],last_wait=waits[-1],wait_iterations=len(waits),return_instruction=end,next_nmi=next_nmi,
        sources={str(p):sha(p) for p in (capture/'capture.json',control/'capture.json',rom,labels,binary,*paths,Path(__file__))},
        scope='Exact unretained camera call crosses line 239 into VBlank with NMI masked; old wait spans line 240 through wrap to line zero. '
              'No hardware NMI entry occurs in that interval; next entry is next frame. Full timeline and PCM match normal core. '
              'This diagnoses one concrete lost edge, not every audio glitch.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observer_equivalent=True,frame=frame,wait_iterations=len(waits),next_nmi_frame=next_nmi['frame'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','control','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--frame',type=int,required=True);a=p.parse_args();audit(a.capture,a.control,a.candidate,a.frame,a.out)
