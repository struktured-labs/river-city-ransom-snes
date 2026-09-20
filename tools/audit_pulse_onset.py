"""Check actual DSP voice pitch after KON startup against its packet's ready state."""
import argparse
import csv
import json
from pathlib import Path
import wave

import numpy as np

from tools.audit_dsp_latency import raw_identity, validate_trace
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha


def parse_voice(records, writes):
    events, active, serials = [], {}, [0, 0]
    keyons = [(w, v) for w in writes if w['register'] == 0x4c
              for v in (0, 1) if w['value'] & (1 << v)]
    matched = set()
    last_tick = -1
    for raw in records:
        if raw[0] == 'K' and len(raw) == 5:
            voice, serial, tick, packet = map(int, raw[1:])
            if voice not in (0, 1) or serial != serials[voice]+1 or tick <= last_tick:
                raise ValueError('Invalid/reordered DSP restart')
            if voice in active and len(active[voice]['samples']) != 96:
                raise ValueError('Interrupted startup observation')
            candidates = [(i, w) for i, (w, v) in enumerate(keyons) if v == voice and
                w['packet'] == packet and 0 <= tick-w['tick'] <= 67 and i not in matched]
            if len(candidates) != 1:
                raise ValueError('DSP KON consumption lacks exactly one actual write')
            i, write = candidates[0]
            matched.add(i)
            serials[voice] = serial
            event = dict(voice=voice, serial=serial, tick=tick, packet=packet,
                         keyon_write=write, write_to_latch_clocks=tick-write['tick'], samples=[])
            events.append(event)
            active[voice] = event
        elif raw[0] == 'V' and len(raw) == 16:
            values = list(map(int, raw[1:]))
            fields = ('voice', 'serial', 'index', 'tick', 'packet', 'delay', 'pitch',
                      'register_pitch', 'srcn', 'brr', 'env', 'output', 'left', 'right', 'noise')
            row = dict(zip(fields, values))
            voice, tick = row['voice'], row['tick']
            event = active.get(voice)
            if (event is None or row['serial'] != event['serial'] or row['packet'] != event['packet'] or
                    row['index'] != len(event['samples']) or row['index'] >= 96 or tick <= last_tick or
                    tick != event['tick']+1+32*row['index'] or row['delay'] != max(0, 5-row['index'])):
                raise ValueError('Missing/reordered/wrong-clock voice sample')
            if not (0 <= row['pitch'] <= 0x3fff and 0 <= row['register_pitch'] <= 0x3fff and
                    0 <= row['env'] <= 0x7ff and -32768 <= row['output'] <= 32767 and
                    0 <= row['brr'] <= 65535 and all(0 <= row[k] <= 255 for k in ('srcn', 'left', 'right', 'noise'))):
                raise ValueError('Invalid internal voice value')
            event['samples'].append(row)
        else:
            raise ValueError('Malformed voice trace')
        last_tick = tick
    if len(matched) != len(keyons) or not events or any(len(e['samples']) != 96 for e in events):
        raise ValueError('Incomplete restart/sample coverage')
    return events


def characterize(events, ready):
    measured, startup = [], []
    for event in events:
        if event['packet'] == 0:
            startup.append(event)
            continue
        state = ready[event['packet']]
        voice = event['voice']
        regs = state['registers']
        base = voice*16
        pitch = regs[base+2] | (regs[base+3] & 63) << 8
        eligible = bool(regs[base] or regs[base+1]) and not regs[0x6c] & 0xc0 and bool(regs[0x0c] or regs[0x1c])
        # Index0 is the trigger cycle; indices1..5 are hardware startup.
        # The next cycle is the first that advances the restarted oscillator.
        samples = event['samples'][6:]
        first = samples[0]
        stale = [s for s in samples if s['tick'] < state['tick'] and s['pitch'] != pitch and
                 s['env'] and s['output'] and (s['left'] or s['right'])]
        measured.append(dict(**event, ready_tick=state['tick'], target_pitch=pitch,
            target_srcn=regs[base+4], target_volumes=[regs[base], regs[base+1]], eligible=eligible,
            first_oscillator_pitch=first['pitch'], first_pitch_matches=(first['pitch'] == pitch),
            stale_nonzero_voice_samples=stale))
    eligible = [e for e in measured if e['eligible']]
    return dict(events=measured, startup=startup, restarts=len(measured), eligible=len(eligible),
        wrong_first_pitch=sum(not e['first_pitch_matches'] for e in eligible),
        stale_nonzero_onsets=sum(bool(e['stale_nonzero_voice_samples']) for e in measured),
        stale_nonzero_samples=sum(len(e['stale_nonzero_voice_samples']) for e in measured),
        max_stale_samples=max((len(e['stale_nonzero_voice_samples']) for e in measured), default=0))


def load(observed, normal, fixture):
    binding = bound_report(observed/'onset-observer.json')
    report = bound_report(observed/'report.json')
    baseline = bound_report(normal/'report.json')
    fixture_report = bound_report(fixture/'manifest.json')
    if not report['passed'] or not baseline['passed']:
        raise ValueError('Incomplete replay')
    if report['sources'].get(str(fixture/'player.sfc')) != fixture_report['rom_sha256']:
        raise ValueError('Different fixture')
    for filename in ('audio.wav', 'timeline.json', 'memory.ram', 'last.png'):
        if sha(observed/filename) != sha(normal/filename):
            raise ValueError('Voice observer changed '+filename)
    paths = {k: Path(v) for k, v in binding['traces'].items()}
    with wave.open(str(observed/'audio.wav')) as f:
        if f.getnchannels() != 2 or f.getsampwidth() != 2:
            raise ValueError('Need stereo PCM16')
        pcm = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)
    raw_identity(np.fromfile(paths['RCR_DSP_DAC_PCM'], '<i2').reshape(-1, 2), pcm)
    with paths['RCR_DSP_LATENCY_TRACE'].open() as f:
        records = list(csv.reader(f))
    # Replay stores source-frame rather than every host callback. Validate
    # every B record independently against raw PCM continuity and clock math.
    callbacks = [r for r in records if r[0] == 'B']
    rows = [dict(frame=i+1, audio_start_sample=int(r[2]), audio=dict(samples=int(r[3])))
            for i, r in enumerate(callbacks)]
    packets, writes, _ = validate_trace(records, rows, len(pcm))
    ready, regs = {}, [0]*128
    for row in records:
        if row[0] == 'D':
            regs[int(row[5])] = int(row[6])
        elif row[0] == 'R' and int(row[1]):
            packet = int(row[1])
            if packet in ready:
                raise ValueError('Duplicate ready')
            ready[packet] = dict(tick=int(row[2]), registers=regs.copy())
    if set(ready) != set(range(1, len(packets)+1)):
        raise ValueError('Missing ready')
    # Actual receive stores must equal every byte of the fixture stream.
    raw = (fixture/'stream.bin').read_bytes()
    cursor, payload = 0, []
    for _ in range(fixture_report['source_frames']):
        count = raw[cursor]; cursor += 1
        if count not in (0, 1):
            raise ValueError('Unsupported stream packet count')
        if count:
            payload.extend(raw[cursor:cursor+23]); cursor += 23
    with paths['RCR_SPC_RECEIVE_TRACE'].open() as f:
        received = list(csv.reader(f))
    if cursor != len(raw) or len(received) != len(payload) or len(payload) != len(packets)*23:
        raise ValueError('Incomplete receive coverage')
    for i, (r, value) in enumerate(zip(received, payload)):
        if len(r) != 3 or int(r[0]) != i % 23 or int(r[1]) != value or int(r[2], 16) != (0x32f1 if i % 23 & 1 else 0x32e5):
            raise ValueError('Wrong actual received byte/site')
    with paths['RCR_PULSE_ONSET_TRACE'].open() as f:
        voice_records = list(csv.reader(f))
    events = parse_voice(voice_records, writes)
    result = characterize(events, ready)
    result.update(observer_neutral=True, raw_dac_identical=True, received_packets=len(packets),
        sources={str(p): sha(p) for p in (observed/'onset-observer.json', normal/'report.json', fixture/'manifest.json')})
    return result, voice_records, writes, ready


def audit(baseline, normal_baseline, original_fixture, candidate, normal_candidate, changed_fixture, out):
    if sha(original_fixture/'stream.bin') != sha(changed_fixture/'stream.bin'):
        raise ValueError('Restart comparison requires identical complete packet streams')
    before, _, _, _ = load(baseline, normal_baseline, original_fixture)
    after, records, writes, ready = load(candidate, normal_candidate, changed_fixture)
    # Independently damage exact voice observations; no emulated-ROM mutation.
    broken = [r.copy() for r in records]
    index = next(i for i, r in enumerate(broken) if r[0] == 'V' and r[3] == '6' and int(r[5]) > 0)
    broken[index][7] = str(int(broken[index][7]) ^ 1)
    bad = characterize(parse_voice(broken, writes), ready)
    wrong_pitch = bad['wrong_first_pitch'] > after['wrong_first_pitch']
    missing = records[:index] + records[index+1:]
    try:
        parse_voice(missing, writes)
    except ValueError:
        missing_rejected = True
    else:
        missing_rejected = False
    if not wrong_pitch or not missing_rejected:
        raise ValueError('Voice observation mutation survived')
    result = dict(baseline=before, candidate=after,
        passed=bool(after['eligible']) and not after['wrong_first_pitch'] and not after['stale_nonzero_onsets'],
        controls=dict(wrong_pitch_detected=wrong_pitch, missing_sample_rejected=missing_rejected),
        physical_audio_verified=False, original_nes_waveform_verified=False, pop_free_verified=False,
        sources={str(p): sha(p) for p in map(Path, (__file__, 'tools/audit_dsp_latency.py',
            'tools/audit_main_display_latency.py', 'tools/snes9x_pulse_onset.inc'))},
        scope='Actual DSP KON latches and all96 following V4 voice samples. Exact32-clock sample '
        'spacing, hardware startup delay and one-to-one KON-write consumption checked. Target '
        'is the same packet final DSP pitch at ready, not an independently synthesized NES '
        'waveform. Nonzero stale samples require voice output, envelope and volume. Global '
        'perceptual clicks, BRR start-pointer fidelity and analog hardware remain separate.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({s: {k: result[s][k] for k in ('restarts', 'eligible', 'wrong_first_pitch',
        'stale_nonzero_onsets', 'stale_nonzero_samples', 'max_stale_samples')} for s in ('baseline', 'candidate')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'normal-baseline', 'original-fixture', 'candidate', 'normal-candidate', 'changed-fixture', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
