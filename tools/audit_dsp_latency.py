"""Join actual SPC receipt/DSP writes to raw DAC samples and host callbacks.

Requires exact raw-DAC/WAV equality and an unchanged complete game timeline.
Clock origin is checked algebraically at every DSP write, never fitted to PCM.
"""
import argparse
from bisect import bisect_right
from collections import Counter
import csv
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_stimulus_audio import verify_sources
from tools.benchmark_report import sha, verify_capture


def dac_tick(sample):
    # DSP phase starts at zero. echo_27 emits sample zero at completed tick28.
    return 32*sample+28


def next_dac_sample(tick):
    return max(0,(tick-28+31)//32)


def callback_frame(starts,ends,sample):
    at=bisect_right(starts,sample)-1
    return at+1 if 0<=at<len(starts) and sample<ends[at] else None


def validate_trace(trace, timeline, sample_count):
    packets=[];writes=[];callbacks=[];last_tick=-1;last_sample=0
    for row in trace:
        kind=row[0]
        if kind=='B' and len(row)==4:
            generated,start,count=map(int,row[1:])
            index=len(callbacks)
            if index>=len(timeline):raise ValueError('Extra callback')
            expected=timeline[index]
            if (expected['frame']!=index+1 or count<=0 or start!=expected['audio_start_sample']
                    or count!=expected['audio']['samples'] or generated!=start+count
                    or start!=(callbacks[-1]['end'] if callbacks else 0)):
                raise ValueError('Callback mapping/backlog mismatch')
            callbacks.append(dict(frame=index+1,start=start,end=generated))
            continue
        if kind not in ('P','R','D') or len(row)!=(7 if kind=='D' else 5):
            raise ValueError('Malformed DSP trace')
        packet,tick,samples,phase_or_pending=map(int,row[1:5])
        if tick<=last_tick or samples<last_sample or min(tick,samples,packet)<0:
            raise ValueError('DSP clock moved backwards')
        last_tick,last_sample=tick,samples
        if kind=='D':
            phase=phase_or_pending;addr,data=map(int,row[5:])
            if (not 0<=phase<32 or not 0<=addr<128 or not 0<=data<=255 or
                    tick!=32*(samples-int(phase>=28))+phase or packet!=len(packets)):
                raise ValueError('DSP write clock/packet/register mismatch')
            writes.append(dict(packet=packet,tick=tick,sample=samples,phase=phase,register=addr,value=data))
        else:
            pending=phase_or_pending
            if pending<0 or samples!=(tick-pending+4)//32:
                raise ValueError('Unsynchronized DSP count/pending-clock mismatch')
            if kind=='P':
                if packet!=len(packets)+1:raise ValueError('Missing/reordered packet')
                packets.append(dict(packet=packet,received_tick=tick+1,
                                    observed_sample=samples,pending_clocks=pending))
            elif packet!=len(packets):raise ValueError('Ready packet mismatch')
    if not writes or not packets or len(callbacks)!=len(timeline) or callbacks[-1]['end']!=sample_count:
        raise ValueError('Incomplete DSP/callback coverage')
    return packets,writes,callbacks


def raw_identity(raw, pcm):
    if (raw.dtype!=np.dtype('<i2') or pcm.dtype!=np.dtype('<i2') or raw.ndim!=2 or
            raw.shape[1]!=2 or raw.shape!=pcm.shape or not np.array_equal(raw,pcm)):
        raise ValueError('Raw DAC is not exactly the delivered PCM')


def audit(capture, normal, provenance, silence, out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    proof=verify_sources(provenance/'report.json')
    binding=receipt['dsp_latency_observer']
    for name,digest in binding['sources'].items():
        if sha(Path(name))!=digest:raise ValueError('Observer source changed: '+name)
    traces={k:Path(v['path']) for k,v in binding['traces'].items()}
    for key,path in traces.items():
        if sha(path)!=binding['traces'][key]['sha256']:raise ValueError('Trace changed: '+key)
    if (not receipt['capture_complete'] or not control['capture_complete'] or rows!=baseline or
            receipt['rom_sha256']!=control['rom_sha256'] or receipt['audio_sha256']!=control['audio_sha256'] or
            not proof['observer_neutral'] or proof['audio_sha256']!=receipt['audio_sha256'] or
            proof['sources'].get(str(capture/'capture.json'))!=sha(capture/'capture.json')):
        raise ValueError('Need complete bound observer-neutral capture')
    with wave.open(str(capture/'audio.wav')) as f:
        if f.getnchannels()!=2 or f.getsampwidth()!=2:raise ValueError('Need stereo PCM16')
        rate=f.getframerate();pcm=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)
    raw=np.fromfile(traces['RCR_DSP_DAC_PCM'],dtype='<i2').reshape(-1,2)
    raw_identity(raw,pcm)
    with traces['RCR_DSP_LATENCY_TRACE'].open() as f:
        packets,writes,callbacks=validate_trace(list(csv.reader(f)),rows,len(pcm))
    offered=json.loads((provenance/'bus-report.json').read_text())['packets']
    if len(packets)!=len(offered):raise ValueError('Packet coverage mismatch')
    starts=[r['start'] for r in callbacks];ends=[r['end'] for r in callbacks]
    for packet,bus in zip(packets,offered):
        sample=next_dac_sample(packet['received_tick'])
        frame=callback_frame(starts,ends,sample)
        packet.update(publication_frame=bus['frame'],first_possible_sample=sample,
            dac_callback_frame=frame,callback_frame_difference=frame-bus['frame'] if frame else None,
            bytes=bus['bytes'])
    # This prior diagnostic contains same-PCM gaps, not hardware APU events.
    gaps=json.loads(silence.read_text())
    for name,digest in gaps['sources'].items():
        if sha(Path(name))!=digest:raise ValueError('Silence source changed: '+name)
    if (gaps['rom_sha256']!=receipt['rom_sha256'] or
            not any(name.endswith('/audio.wav') and digest==receipt['audio_sha256']
                    for name,digest in gaps['sources'].items())):
        raise ValueError('Silence report has different PCM')
    contexts=[];ticks=[p['received_tick'] for p in packets]
    for gap in gaps['gaps']:
        if not gap['longest_active_reference_run']:continue
        end=gap['end_sample'];begin=gap['first_sample']
        if not 0<=begin<end<len(pcm) or np.any(pcm[begin:end]) or not np.any(pcm[end]):
            raise ValueError('Gap does not match raw PCM')
        at=bisect_right(ticks,dac_tick(end))-1
        if at<0:raise ValueError('No preceding receipt')
        packet=packets[at]
        relevant=[w for w in writes if w['packet']==packet['packet'] and w['tick']<=dac_tick(end)]
        contexts.append(dict(first_frame=gap['first_frame'],last_frame=gap['last_frame'],
            first_sample=begin,first_nonzero_sample=end,first_nonzero_tick=dac_tick(end),
            nonzero_callback=callback_frame(starts,ends,end),preceding_packet=packet,
            receipt_to_first_nonzero_ticks=dac_tick(end)-packet['received_tick'],
            milliseconds_at_nominal_dac_rate=(dac_tick(end)-packet['received_tick'])*1000/(32*rate),
            dsp_writes_before_sound=relevant,
            nes_active_source_frames=[r['source_frame'] for r in gap['reference_frames'] if r['reference_active']]))
    sources=[Path(__file__),Path('tools/benchmark_report.py'),Path('tools/audit_stimulus_audio.py'),
        capture/'capture.json',normal/'capture.json',capture/'timeline.json',normal/'timeline.json',
        capture/'audio.wav',provenance/'report.json',provenance/'bus-report.json',silence,*traces.values()]
    result=dict(observer_neutral=True,raw_dac_equals_delivered_pcm=True,dac_samples=len(raw),
        checked_dsp_writes=len(writes),checked_callbacks=len(callbacks),packets=packets,
        callback_frame_difference_histogram=dict(Counter(str(p['callback_frame_difference']) for p in packets)),
        short_reference_gap_contexts=contexts,nominal_dac_rate=rate,
        release_ready=False,physical_gaps_correlated=False,synthesis_fidelity_verified=False,
        sources={**binding['sources'],**{str(p):sha(p) for p in sources}},
        scope='DSP sample counter clock epoch validated at every write; no waveform fit or added '
              'emulated synchronization. Every raw DAC sample equals callback PCM. Packet arrival '
              'after a host audio callback can label its sound with the next callback frame. '
              'Gap contexts use the nearest preceding received packet, not automatic proof of '
              'which voice causes onset. SPC ticks are primary; milliseconds use nominal DAC rate. '
              'No physical capture latency, full NES waveform equivalence or pop-free verdict.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('observer_neutral','dac_samples','checked_dsp_writes',
        'checked_callbacks','callback_frame_difference_histogram')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','provenance','silence','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
