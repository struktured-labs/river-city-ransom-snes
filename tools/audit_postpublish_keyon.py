"""Audit restart ordering in actual DSP writes, not just CPU packet shadows."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import wave

import numpy as np

from tools.analyze_audio_bus import analyze as analyze_bus
from tools.analyze_spc_receive import compare
from tools.audit_dsp_latency import raw_identity, validate_trace
from tools.benchmark_report import sha, verify_capture


def ordering(writes, ready):
    regs, groups = {}, {}
    for write in writes:
        register = write['register']
        item = dict(write, previous_value=regs.get(register))
        regs[register] = write['value']
        if write['packet'] and write['tick'] < ready[write['packet']]:
            groups.setdefault(write['packet'], []).append(item)
    events = []
    for packet, group in groups.items():
        for keyon in (w for w in group if w['register'] == 0x4c):
            for voice in (0, 1):
                if not keyon['value'] & (1 << voice):
                    continue
                # SRCN, full pitch, and both volume registers. Idle sweep
                # writes after this packet's ready are deliberately separate.
                config = [w for w in group if w['register'] in [voice*16+i for i in (0, 1, 2, 3, 4)]]
                late = [w for w in config if w['tick'] > keyon['tick'] and w['value'] != w['previous_value']]
                events.append(dict(packet=packet, voice=voice, keyon=keyon,
                    ready_tick=ready[packet], configuration=config,
                    changed_configuration_after_restart=late,
                    last_configuration_minus_restart=max((w['tick'] for w in config), default=keyon['tick'])-keyon['tick']))
    return dict(restarts=len(events), late_restarts=sum(bool(e['changed_configuration_after_restart']) for e in events),
                events=events, passed=bool(events) and not any(e['changed_configuration_after_restart'] for e in events))


def load(capture, normal, candidate):
    receipt, rows = verify_capture(capture)
    control, baseline = verify_capture(normal)
    if (not receipt['capture_complete'] or not control['capture_complete'] or rows != baseline or
            any(receipt[k] != control[k] for k in ('rom_sha256', 'audio_sha256', 'frames', 'scenario_sha256'))):
        raise ValueError('Incomplete or non-neutral DSP observer')
    manifest = json.loads((candidate/'manifest.json').read_text())
    if manifest['rom_sha256'] != receipt['rom_sha256'] or sha(candidate/'native-cpu.sfc') != receipt['rom_sha256']:
        raise ValueError('Different candidate')
    binding = receipt['dsp_latency_observer']
    sources = dict(binding['sources'])
    traces = {}
    for name, value in binding['traces'].items():
        path = Path(value['path'])
        sources[str(path)] = value['sha256']
        if not name.endswith('_PCM'):
            with path.open() as f:
                traces[name] = list(csv.reader(f))
    for path, digest in sources.items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed observer source: '+path)
    with wave.open(str(capture/'audio.wav')) as f:
        if f.getsampwidth() != 2 or f.getnchannels() != 2:
            raise ValueError('Need stereo PCM16')
        rate = f.getframerate()
        pcm = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)
    raw_identity(np.fromfile(binding['traces']['RCR_DSP_DAC_PCM']['path'], '<i2').reshape(-1, 2), pcm)
    dsp = traces['RCR_DSP_LATENCY_TRACE']
    packets, writes, callbacks = validate_trace(dsp, rows, len(pcm))
    ready = {}
    for row in dsp:
        if row[0] == 'R' and int(row[1]):
            packet = int(row[1])
            if packet in ready:
                raise ValueError('Multiple ready acknowledgements')
            ready[packet] = int(row[2])
    if set(ready) != set(range(1, len(packets)+1)):
        raise ValueError('Incomplete ready coverage')
    bus = analyze_bus(traces['RCR_AUDIO_BUS_TRACE'], length_gate=True)
    if bus['mismatches'] or bus['unflushed_cpu_writes']:
        raise ValueError('CPU bus mismatch')
    # Receiver itself is unchanged by this prototype; bind both instructions.
    image = (candidate/'native-cpu.sfc').read_bytes()
    at = manifest['sweep_driver_rom_offset']
    engine = image[at:at+manifest['sweep_driver_layout']['engine_bytes']]
    import hashlib
    if hashlib.sha256(engine).hexdigest() != manifest['spc_sha256']:
        raise ValueError('Wrong SPC image')
    labels = manifest['sweep_driver_layout']['driver']
    block = engine[labels['receiver']-0x400:labels['receiver_tail']-0x400]
    pcs = []
    for port in (0xf5, 0xf6):
        pattern = bytes((0xe4, port, 0xd4, 0x40))
        if block.count(pattern) != 1:
            raise ValueError('Nonunique receiver')
        pcs.append(labels['receiver']+block.index(pattern)+4)
    transport = compare(traces['RCR_AUDIO_BUS_TRACE'], traces['RCR_SPC_RECEIVE_TRACE'], paired=True, receiver_pcs=pcs)
    if not transport['passed'] or transport['packets'] != len(packets):
        raise ValueError('Actual received packets differ')
    observed = {}
    for w in writes:
        if w['packet'] and w['register'] == 0x4c:
            observed.setdefault(w['packet'], []).append(w['value'])
    prior_duty = [0, 0]
    post = bool(manifest.get('experimental_postpublish_keyon'))
    for number, packet in enumerate(bus['packets'], 1):
        data = bytes.fromhex(packet['bytes'])
        reset = data[22] & data[21] & 3
        duty = 0
        for voice in (0, 1):
            if data[21] & (1 << voice):
                current = data[voice*4] >> 6
                if current != prior_duty[voice]:
                    duty |= 1 << voice
                prior_duty[voice] = current
        expected = ([reset | duty] if reset | duty else []) if post or reset else [bit for bit in (1, 2) if bit & duty]
        if observed.get(number, []) != expected:
            raise ValueError(f'Missing/extra restart on packet {number}')
    result = ordering(writes, ready)
    for p in (capture/'capture.json', normal/'capture.json', candidate/'manifest.json', candidate/'native-cpu.sfc'):
        sources[str(p)] = sha(p)
    result.update(observer_neutral=True, raw_dac_matches_wav=True, transport=transport,
        packets=len(packets), writes=len(writes), pcm_samples=len(pcm), sample_rate=rate,
        pcm_peak=int(np.abs(pcm.astype(np.int32)).max()), clipped_samples=int((np.abs(pcm.astype(np.int32)) >= 32767).sum()),
        sources=sources, restart_schedule_verified=True)
    return result, writes, ready


def audit(baseline, normal_baseline, parent, candidate, normal_candidate, rom, out):
    original, _, _ = load(baseline, normal_baseline, parent)
    changed, writes, ready = load(candidate, normal_candidate, rom)
    # Damage the actual candidate observation: move one changed pitch write
    # past its KON but keep it inside the same ready interval. This tests the
    # ordering oracle; it is not an executed damaged ROM.
    target = next(e for e in changed['events'] if any(w['register'] % 16 in (2, 3) and
                  w['value'] != w['previous_value'] for w in e['configuration']))
    late = next(w for w in target['configuration'] if w['register'] % 16 in (2, 3) and w['value'] != w['previous_value'])
    mutated = [dict(w) for w in writes]
    entry = next(w for w in mutated if w['tick'] == late['tick'])
    entry['tick'] = target['keyon']['tick']+1
    mutated.sort(key=lambda w: w['tick'])
    rejected = not ordering(mutated, ready)['passed']
    if not rejected:
        raise ValueError('Late configuration mutation survived')
    report = dict(baseline=original, candidate=changed, late_write_mutation_rejected=rejected,
        passed=changed['passed'], physical_audio_verified=False, pop_free_verified=False,
        sources={str(p): sha(p) for p in map(Path, (__file__, 'tools/analyze_audio_bus.py',
            'tools/analyze_spc_receive.py', 'tools/audit_dsp_latency.py', 'tools/benchmark_report.py'))},
        scope='Complete actual DSP writes, received packet bytes, inferred reset/duty schedule, '
        'ready boundaries and exact DAC/WAV equality. Ordering failure means a changed voice '
        'setting was written after restart and before ready. Idle sweep writes are retained '
        'in source traces but are not packet setup failures. Not proof of DSP internal latch '
        'contents, audibility, waveform improvement or original-NES equivalence.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], baseline_late=original['late_restarts'],
        candidate_late=changed['late_restarts'], restarts=changed['restarts'],
        mutation_rejected=rejected)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'normal-baseline', 'parent', 'candidate', 'normal-candidate', 'rom', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
