"""Retain every short replay gap and its actual DSP gate/packet context.

No cross-system waveform alignment: NES callbacks are joined by source frame.
Physical gameplay command identity is explicitly not inferred.
"""
import argparse
from bisect import bisect_right
import csv
import json
from pathlib import Path
import wave

import numpy as np

from tools.analyze_game_silence import voice_state
from tools.audit_main_display_latency import bound_report
from tools.audit_nes_filter import reconstruct, window
from tools.audit_pulse_onset import load
from tools.audit_recorded_transients import zero_runs
from tools.benchmark_report import sha
from tools.replay_nes_apu_stimulus import pack_writes, publication_writes
from tools.replay_spc_packets import packets as pack_packets


def gate(regs):
    """Register command state only; this does not emulate internal DSP latches."""
    return dict(voice_mask=sum(1 << v for v in range(8)
        if regs[16*v] or regs[16*v+1]),
        master_muted=not (regs[0x0c] or regs[0x1c]),
        echo_muted=not (regs[0x2c] or regs[0x3c]),
        global_muted=bool(regs[0x6c] & 0xc0))


def gate_segments(writes, first, last):
    if not 0 <= first < last:
        raise ValueError('Invalid sample interval')
    regs, cursor, segments = [0]*128, first, []
    def append(end):
        nonlocal cursor
        if end > cursor:
            state = gate(regs)
            state['zero_output_commanded'] = (state['global_muted'] or
                (state['echo_muted'] and (state['master_muted'] or not state['voice_mask'])))
            if segments and all(segments[-1][key] == value for key, value in state.items()):
                segments[-1]['last'] = end
            else:
                segments.append(dict(first=cursor, last=end, **state))
            cursor = end
    for write in writes:
        # First DAC emission at or after this actual register write. Internal
        # volume latching can differ by a DSP sample; retain this limitation.
        sample = max(0, (write['tick']-28+31)//32)
        if sample >= last:
            break
        if sample > cursor:
            append(sample)
        regs[write['register']] = write['value']
    append(last)
    return segments


def gap_gate_context(pcm, rate, segments):
    ends = [s['last'] for s in segments]
    results, censored = [], []
    for first, last in zero_runs(pcm):
        if (last-first)*1000 < rate*5:
            continue
        if not segments[0]['first'] <= first < last <= ends[-1]:
            censored.append(dict(first=first, last=last, reason='outside complete source coverage'))
            continue
        overlaps = [dict(s, first=max(first, s['first']), last=min(last, s['last']))
            for s in segments[bisect_right(ends, first):bisect_right(ends, last-1)+1]]
        if sum(s['last']-s['first'] for s in overlaps) != last-first:
            raise ValueError('Incomplete gate coverage')
        ungated = sum(s['last']-s['first'] for s in overlaps if not s['zero_output_commanded'])
        results.append(dict(first=first, last=last, milliseconds=(last-first)*1000/rate,
            zero_output_command_samples=last-first-ungated,
            active_command_samples=ungated, active_command_ms=ungated*1000/rate,
            gate_segments=overlaps))
    return results, censored


def command_segments(payload, ready, first, last):
    cursor, packet, position, quiet = first, 0, 0, None
    result = []
    while position < len(payload):
        count = payload[position]
        position += 1
        if count not in (0, 1):
            raise ValueError('Invalid packet count')
        if not count:
            continue
        data = payload[position:position+23]
        position += 23
        if len(data) != 23:
            raise ValueError('Incomplete packet')
        packet += 1
        sample = max(0, (ready[packet]['tick']-28+31)//32)
        if sample > cursor:
            result.append(dict(first=cursor, last=min(sample, last),
                zero_output_commanded=quiet is True, packet=packet-1,
                state_known=quiet is not None))
            cursor = min(sample, last)
        quiet = voice_state(data.hex())[1]
        if cursor == last:
            break
    if cursor < last:
        result.append(dict(first=cursor, last=last, zero_output_commanded=quiet is True,
            packet=packet, state_known=quiet is not None))
    return result


def read_pcm(path):
    with wave.open(str(path)) as f:
        if f.getsampwidth() != 2 or f.getnchannels() != 2:
            raise ValueError('Need stereo PCM16')
        return f.getframerate(), np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)


def audit(observed, normal, fixture, game, nes, filtered, out):
    onset, _, writes, ready = load(observed, normal, fixture)
    reference = bound_report(nes/'report.json')
    filt = bound_report(filtered/'report.json')
    fm = bound_report(fixture/'manifest.json')
    game_manifest = json.loads((game/'manifest.json').read_text())
    game_image = (game/'native-cpu.sfc').read_bytes()
    at = game_manifest['sweep_driver_rom_offset']
    length = game_manifest['sweep_driver_layout']['engine_bytes']
    if (sha(game/'native-cpu.sfc') != game_manifest['rom_sha256'] or
            game_image[at:at+length] != (fixture/'engine.bin').read_bytes()):
        raise ValueError('Replay does not use the specified game engine')
    source = Path(fm['source_capture'])
    receipt = json.loads((source/'capture.json').read_text())
    bus = Path(receipt['audio_bus_trace']['path'])
    if reference['sources'].get(str(bus)) != sha(bus) or reference['timing'] != 'publication-frame':
        raise ValueError('Different NES source commands/scheduling')
    with bus.open() as f:
        records = list(csv.reader(f))
    frames = fm['source_frames']
    _, payload = pack_packets(records, frames)
    nes_payload, _ = pack_writes(publication_writes(records)[0], frames, banked=True)
    if payload != (fixture/'stream.bin').read_bytes() or nes_payload != (nes/'stimulus.bin').read_bytes():
        raise ValueError('Stimulus differs from actual common bus')
    if any(sha(filtered/name) != sha(nes/name) for name in ('audio.wav', 'timeline.json', 'memory.ram')):
        raise ValueError('Nonneutral NES filter observer')
    nr, npc = read_pcm(filtered/'audio.wav')
    raw = np.fromfile(filt['traces']['samples'], '<i4').reshape(-1, 2)
    with Path(filt['traces']['blocks']).open() as f:
        checked = reconstruct(raw, list(csv.reader(f)), npc, nr)
    rate, pcm = read_pcm(normal/'audio.wav')
    rows = json.loads((normal/'timeline.json').read_text())
    nrows = json.loads((nes/'timeline.json').read_text())
    if len(rows) != frames or len(nrows) != frames:
        raise ValueError('Different source frame coverage')
    starts = [r['start_sample'] for r in rows]
    ends = [r['end_sample'] for r in rows]
    if any(r['source_frame'] != i+1 or nrows[i]['source_frame'] != i+1 for i, r in enumerate(rows)):
        raise ValueError('Missing source frame')
    segments = gate_segments(writes, starts[0], ends[-1])
    results, censored = gap_gate_context(pcm, rate, segments)
    commands = command_segments(payload, ready, starts[0], ends[-1])
    command_gaps, _ = gap_gate_context(pcm, rate, commands)
    if [(g['first'],g['last']) for g in results] != [(g['first'],g['last']) for g in command_gaps]:
        raise ValueError('Different command coverage')
    for gap, context in zip(results, command_gaps):
        gap['packet_command_context'] = context
    for gap in results:
        first, last = gap['first'], gap['last']
        lo, hi = bisect_right(starts, first), bisect_right(starts, last-1)
        contexts = []
        for index in range(lo-1, hi):
            nrow = nrows[index]
            metrics = window(raw, nrow['start_sample'], nrow['end_sample'])
            contexts.append(dict(source_frame=index+1, complete_snes_callback=(
                first <= starts[index] < ends[index] <= last),
                packet=rows[index]['packets'], packet_state=voice_state(rows[index]['packet']), **metrics))
        gap.update(first_frame=lo, last_frame=hi, reference_context=contexts)
    # Full measured silence is a sensitivity control; nonzero sound under open
    # gate must not become "explained" by a nearby quiet packet.
    active = next(s for s in segments if not s['zero_output_commanded'] and
                  s['last']-s['first'] >= rate//100 and np.any(pcm[s['first']:s['last']]))
    cut_first = active['first']
    cut_last = cut_first+rate//100
    damaged = pcm.copy()
    damaged[cut_first:cut_last] = 0
    injected, _ = gap_gate_context(damaged, rate, segments)
    caught = any(g['first'] <= cut_first and g['last'] >= cut_last and
                 g['active_command_samples'] >= cut_last-cut_first for g in injected)
    if not caught:
        raise ValueError('Open-gate silence control escaped')
    held = next(s for s in commands if s['state_known'] and not s['zero_output_commanded'] and
        s['last']-s['first'] >= rate//100 and np.any(pcm[s['first']:s['first']+rate//100]))
    damaged = pcm.copy()
    damaged[held['first']:held['first']+rate//100] = 0
    command_negative, _ = gap_gate_context(damaged, rate, commands)
    command_caught = any(g['first'] <= held['first'] and g['last'] >= held['first']+rate//100 and
        g['active_command_samples'] >= rate//100 for g in command_negative)
    if not command_caught:
        raise ValueError('Command-active injected silence escaped')
    result = dict(gaps=results, censored=censored, checked_nes_filter_samples=checked,
        observer_neutral=True, shared_command_stream_verified=True,
        game_rom_sha256=game_manifest['rom_sha256'], engine_matches_game=True,
        received_packets=onset['received_packets'], source_frames=frames,
        short_gap_count=len(results),
        max_open_volume_gate_ms=max(g['active_command_ms'] for g in results),
        gaps_over_2ms_open_volume_gate=sum(g['active_command_ms'] > 2 for g in results),
        max_packet_unproven_ms=max(g['active_command_ms'] for g in command_gaps),
        packet_unproven_over_2ms=sum(g['active_command_ms'] > 2 for g in command_gaps),
        complete_silent_callbacks_with_varying_nes_input=sum(
            c['complete_snes_callback'] and not c['constant_input'] for g in results for c in g['reference_context']),
        complete_silent_callbacks=sum(c['complete_snes_callback'] for g in results for c in g['reference_context']),
        open_gate_control_detected=caught,
        injected_10ms_silence=dict(first=cut_first, last=cut_last),
        packet_active_control_detected=command_caught,
        packet_injected_10ms=dict(first=held['first'], last=held['first']+rate//100),
        physical_gaps_resolved=False, pop_free_verified=False, release_ready=False,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/audit_pulse_onset.py'),
            Path('tools/audit_nes_filter.py'), Path('tools/audit_recorded_transients.py'),
            Path('tools/analyze_game_silence.py'),
            Path('tools/replay_nes_apu_stimulus.py'), Path('tools/replay_spc_packets.py'),
            observed/'onset-observer.json', normal/'report.json', fixture/'manifest.json',
            game/'manifest.json', game/'native-cpu.sfc',
            nes/'report.json', filtered/'report.json', bus)},
        scope='Every >=5ms exact-zero replay interval retained, including boundary cases. '
            'Actual DSP register commands joined through validated clock epoch; internal '
            'volume latch/voice envelope is not inferred. An open volume gate is NOT proof '
            'of an active voice (e.g. triangle release). Packet quiet state is measured at '
            'actual ready; tails and onset latency remain, not a sample-equivalent oracle. '
            'NES prefilter activity joined by '
            'source callback, not sample-equivalent phase. Both players batch publication '
            'writes; game subframe scheduling and physical gameplay commands remain separate.')
    out.mkdir(parents=True, exist_ok=False)
    selections = [max(results, key=lambda g: max((c['output_ac_rms'] for c in g['reference_context']
                  if c['complete_snes_callback']), default=0)),
                  min((g for g in results if g['milliseconds'] < 20), key=lambda g: g['first']),
                  max(results, key=lambda g: g['packet_command_context']['active_command_ms'])]
    examples, players = [], []
    for i, gap in enumerate(selections, 1):
        first_frame, last_frame = max(1,gap['first_frame']-30), min(frames,gap['last_frame']+30)
        clips = {}
        for label, hz, data, timeline in [('snes',rate,pcm,rows),('nes',nr,npc,nrows)]:
            begin, end = timeline[first_frame-1]['start_sample'], timeline[last_frame-1]['end_sample']
            path = out/f'example-{i}-{label}.wav'
            with wave.open(str(path), 'wb') as f:
                f.setparams((2,2,hz,0,'NONE','not compressed'))
                f.writeframes(data[begin:end].tobytes())
            clips[label] = dict(path=path.name, sha256=sha(path), first=begin, last=end, rate=hz)
        examples.append(dict(first_frame=first_frame,last_frame=last_frame, gap_first_frame=gap['first_frame'], clips=clips))
        players.append(f'<h3>Example {i}: source frames {first_frame}–{last_frame}; gap starts frame {gap["first_frame"]}</h3>'+
            ''.join(f'<p>{label.upper()} · {clip["rate"]} Hz, native samples, original gain</p>'
                    f'<audio controls src="{clip["path"]}"></audio>' for label,clip in clips.items()))
    result['listening_examples'] = examples
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    table = ''.join(f'<tr><td>{g["first_frame"]}–{g["last_frame"]}</td><td>{g["milliseconds"]:.3f}</td>'
        f'<td>{g["packet_command_context"]["active_command_ms"]:.3f}</td><td>'
        f'{sum(c["complete_snes_callback"] for c in g["reference_context"])}</td></tr>' for g in results)
    (out/'index.html').write_text(('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Short silences · same-command NES/SNES replay</title><style>body{background:#101821;color:#eef;font:17px/1.5 system-ui;max-width:1100px;margin:auto;padding:24px}a{color:#9df}audio{width:100%}td,th{border:1px solid #567;padding:8px}table{border-collapse:collapse}.open{color:#ffd68b}</style>
<h1>Short silences: actual commands versus NES filter tails</h1>
<p>September 18, 2026 · exact engine from test build @ROM@. Offline diagnosis only: no new cartridge or Rival inputs.</p>
<p>Both replay payloads were reconstructed from the same original captured bus and checked byte-for-byte.
All @PACKETS@ received SNES packets and complete observer neutrality remain verified.
The NES observer leaves PCM, timeline and RAM unchanged; all @FILTER@ filter outputs are reconstructed exactly.</p>
<h2>What this run establishes</h2>
<p>All @GAPS@ exact-zero intervals of at least 5 ms are retained. Across each interval, at most @UNPROVEN@ ms lies
outside a packet-commanded quiet state at actual SPC ready. Of @CALLBACKS@ completely silent SNES callbacks,
@VARYING@ have varying NES pre-filter input in the corresponding source callback. NES output may still vary
because of its filter state. These observations are diagnostics, not a synthesis-fidelity pass.</p>
<p class="open">Partial-frame NES boundaries remain visible in the JSON; different system scheduling prevents
sample-exact equivalence. Initial uncaptured-source silence is censored explicitly. The two actual gameplay
silences on Rival remain unclassified: this replay does not identify their commands.</p>
<p>The volume-register-only check cannot classify these gaps: triangle volume can remain open during release.
Its unfavorable measurements remain in the report. Packet quiet commands are independent evidence,
not a replacement assertion that an open volume gate means audible output.</p>
<p>Two independently injected 10 ms PCM dropouts are detected by the volume-gate and packet-state checks.
These are waveform mutations with unchanged command logs, not executed damaged cartridges.</p>
<h2>Listen at original gain and sample rates</h2>
<p>Selections: largest NES filter-tail variation in a complete silent callback; first sub-20 ms gap;
largest packet-unproven boundary. Windows use identical source-frame numbers, no waveform alignment,
gain matching, resampling or time warping. Player startup and within-frame timing differ.</p>'''+''.join(players)+'''
<p class="open">This does not certify pop-free playback or analog NES fidelity. Abrupt cutoff/tail differences
remain a synthesis-fidelity question. No game code or audio engine changed in this investigation.</p>
<h2>Every gap, including short boundary cases</h2><table><tr><th>Source frames</th><th>Gap ms</th>
<th>Outside packet-quiet ms</th><th>Complete silent callbacks</th></tr>'''+table+'''</table>
<p><a href="report.json">Commands, filter observations, controls and provenance</a> ·
<a href="../pulse-onset-rival-review-1363/">Current Rival test build and physical recording</a></p>''')
        .replace('@ROM@', result['game_rom_sha256'][:12])
        .replace('@PACKETS@', str(result['received_packets']))
        .replace('@FILTER@', str(checked))
        .replace('@GAPS@', str(len(results)))
        .replace('@UNPROVEN@', f'{result["max_packet_unproven_ms"]:.6f}')
        .replace('@CALLBACKS@', str(result['complete_silent_callbacks']))
        .replace('@VARYING@', str(result['complete_silent_callbacks_with_varying_nes_input'])))
    print(json.dumps({k: v for k, v in result.items() if k not in ('gaps', 'sources', 'scope')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('observed', 'normal', 'fixture', 'game', 'nes', 'filtered', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
