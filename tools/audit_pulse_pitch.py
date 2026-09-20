"""Reconstruct every DSP pulse pitch latch and detect split-byte intermediate values."""
import argparse
from bisect import bisect_left
import csv
import json
from pathlib import Path
import wave

from tools.audit_pulse_onset import load
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def pitch_updates(writes,voice):
    selected=[w for w in writes if w['register'] in (voice*16+2,voice*16+3)]
    if len(selected)%2:raise ValueError('Incomplete pitch-byte pair')
    updates=[];old=0
    for low,high in zip(selected[::2],selected[1::2]):
        if low['register']!=voice*16+2 or high['register']!=voice*16+3 or high['tick']<=low['tick']:
            raise ValueError('Pitch writes are not complete low/high pairs')
        new=low['value']|((high['value']&63)<<8)
        updates.append(dict(old=old,new=new,low=low,high=high));old=new
    return updates


def value_before(ticks,values,tick):
    i=bisect_left(ticks,tick)-1
    return values[i] if i>=0 else 0


def sample_expectation(tick,voice,previous_delay,updates,low_ticks,high_ticks,low_values,high_values):
    # Actual GEN_DSP_TIMING: voice0 V2/V3a are ten/nine clocks before V4;
    # voice1 V2/V3a are two/one clocks before V4. Writes at completed clock N
    # affect a read at observer tick N+1, not the read that already ran at N.
    low_tick=tick-(10 if voice==0 else 2)
    high_tick=tick-(9 if voice==0 else 1)
    expected=value_before(low_ticks,low_values,low_tick)|(
        (value_before(high_ticks,high_values,high_tick)&63)<<8)
    if previous_delay:expected=0 # V3c forcibly clears pitch during KON startup.
    current=value_before(low_ticks,low_values,tick)|((value_before(high_ticks,high_values,tick)&63)<<8)
    i=bisect_left(low_ticks,high_tick)-1
    update=updates[i] if i>=0 else None
    allowed={0} if update is None else ({update['new']} if update['high']['tick']<low_tick else
                                       {update['old'],update['new']})
    return dict(expected=expected,registers=current,update_index=i,
                split_byte=not previous_delay and expected not in allowed,
                allowed=sorted(allowed),low_read_tick=low_tick,high_read_tick=high_tick)


def audit(observed,normal,fixture,out):
    onset,_,writes,ready=load(observed,normal,fixture)
    binding=bound_report(observed/'onset-observer.json')
    path=Path(binding['traces']['RCR_PULSE_PITCH_TRACE'])
    if any(w['register']==0x2d and w['value']&2 for w in writes):
        raise ValueError('Pulse pitch modulation needs a different oracle')
    updates=[pitch_updates(writes,v) for v in (0,1)]
    for voice in updates:
        if any(b['low']['tick']-a['low']['tick']<32 for a,b in zip(voice,voice[1:])):
            raise ValueError('Multiple pitch transactions inside one sample need separate accounting')
    tables=[([u['low']['tick'] for u in us],[u['high']['tick'] for u in us],
             [u['low']['value'] for u in us],[u['high']['value'] for u in us]) for us in updates]
    counts=[0,0];last=[0,0];delays=[0,0];events=[];global_tick=0;nonzero=[0,0]
    with path.open() as stream:
        for raw in csv.reader(stream):
            if len(raw)!=13:raise ValueError('Need complete thirteen-column pitch samples')
            tick,voice,packet,delay,pitch,regs,srcn,brr,env,output,left,right,noise=map(int,raw)
            if voice not in (0,1) or tick<=global_tick or tick!=(32 if voice==0 else 3)+counts[voice]*32:
                raise ValueError('Missing/reordered pulse sample or wrong DSP phase')
            if delay not in (max(0,delays[voice]-1),5) or not 0<=pitch<=16383 or not 0<=env<=2047:
                raise ValueError('Invalid pitch or startup progression')
            expected=sample_expectation(tick,voice,delays[voice],updates[voice],*tables[voice])
            if pitch!=expected['expected'] or regs!=expected['registers']:
                raise ValueError(f'Unexplained pitch latch at voice{voice} tick{tick}: '
                                 f'{pitch}/{regs} expected{expected}')
            active=bool(env and output and (left or right) and not noise&(1<<voice))
            nonzero[voice]+=active
            if expected['split_byte']:
                events.append(dict(tick=tick,voice=voice,packet=packet,pitch=pitch,
                    delay=delay,env=env,output=output,volumes=[left,right],nonzero_output=active,
                    update=updates[voice][expected['update_index']],**expected))
            counts[voice]+=1;last[voice]=tick;delays[voice]=delay;global_tick=tick
    with wave.open(str(observed/'audio.wav')) as f:
        samples=f.getnframes();rate=f.getframerate()
    last_dac_tick=(samples-1)*32+28
    if not last_dac_tick<=global_tick<last_dac_tick+32 or counts!=[
            (global_tick-32)//32+1,(global_tick-3)//32+1]:
        raise ValueError('Truncated pulse coverage relative to delivered DAC samples')
    report=dict(observer_neutral=True,raw_dac_identical=True,received_packets=onset['received_packets'],
        samples_by_voice=counts,nonzero_samples_by_voice=nonzero,rate=rate,
        pitch_pairs_by_voice=[len(u) for u in updates],split_samples=len(events),
        nonzero_split_samples=sum(e['nonzero_output'] for e in events),events=events,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_pulse_onset.py'),
            Path('tools/audit_dsp_latency.py'),Path('tools/snes9x_pulse_pitch.inc'),
            observed/'onset-observer.json',normal/'report.json',fixture/'manifest.json',path)},
        scope='Every actual pulse V4 sample reconstructed from DSP byte writes at its exact V2/V3a '
              'read clocks, including hardware KON startup. Split values are neither complete old nor '
              'complete new pitch; nonzero means measured voice contribution, not proof of an audible '
              'click or physical defect. Packet replay retains its known publication-frame quantization. '
              'No waveform alignment, ROM change, or perceptual/hardware pass.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('samples_by_voice','pitch_pairs_by_voice','split_samples','nonzero_split_samples')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('observed','normal','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
