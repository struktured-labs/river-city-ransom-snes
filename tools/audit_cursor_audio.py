"""Bound isolated pause-selector cues without confusing filter tails with dropouts."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.io import wavfile

from tools.analyze_audio_bus import analyze
from tools.analyze_spc_receive import compare
from tools.audit_main_display_latency import bound_report
from tools.audit_recorded_transients import zero_runs
from tools.audit_spc_event_provenance import validate_bindings
from tools.benchmark_report import sha, verify_capture
from tools.capture_mister_cursor_audio import episode


def cues(pcm, rate, threshold=.0005, separation=.2):
    """Fixed full-scale threshold and separation, never fitted to expected count."""
    if (pcm.ndim != 2 or pcm.shape[1] != 2 or rate <= 0 or
            not np.isfinite(pcm).all() or threshold <= 0 or separation <= 0):
        raise ValueError('Need finite stereo PCM and positive detection parameters')
    envelope = np.max(np.abs(pcm), axis=1)
    active = np.flatnonzero(envelope > threshold)
    if not len(active):
        return []
    splits = np.flatnonzero(np.diff(active) > rate * separation)
    spans = zip(np.r_[active[0], active[splits+1]], np.r_[active[splits]+1, active[-1]+1])
    result = []
    for first, last in spans:
        peak = float(envelope[first:last].max())
        strong = np.flatnonzero(envelope[first:last] > peak * .1)
        lo, hi = first + strong[0], first + strong[-1] + 1
        gaps = zero_runs(pcm[lo:hi])
        result.append(dict(first=int(first), last=int(last), seconds=float(first/rate),
            duration_ms=float((last-first)*1000/rate), peak=peak,
            strong_duration_ms=float((hi-lo)*1000/rate),
            longest_internal_exact_zero_ms=max((b-a)*1000/rate for a,b in gaps) if gaps else 0.0))
    return result


def checks(events, expected_times):
    count = len(events) == len(expected_times) and bool(events)
    residuals = ([((event['seconds']-events[0]['seconds'])-(t-expected_times[0]))*1000
                  for event,t in zip(events,expected_times)] if count else [])
    gates = dict(expected_cue_count=count,
        relative_onset_timing=count and max(map(abs,residuals)) <= 50,
        no_internal_2ms_exact_zero=count and all(e['longest_internal_exact_zero_ms'] < 2 for e in events),
        strong_duration_45_to_100ms=count and all(45 <= e['strong_duration_ms'] <= 100 for e in events))
    return dict(passed=all(gates.values()), gates=gates, relative_onset_residual_ms=residuals)


def normalized(path):
    rate, pcm = wavfile.read(path)
    if pcm.dtype == np.int16:
        return rate, pcm.astype(float)/32768
    if pcm.dtype == np.int32:
        return rate, pcm.astype(float)/2147483648
    if pcm.dtype == np.float32:
        return rate, pcm.astype(float)
    raise ValueError('Unexpected PCM encoding')


def audit(nes, snes, observer, coordinator, aac, out):
    sources = {}
    def bind(path):
        sources[str(path)] = sha(path)
    for path in (Path(__file__), Path('tools/analyze_audio_bus.py'), Path('tools/analyze_spc_receive.py'),
                 Path('tools/benchmark_report.py'), Path('tools/audit_recorded_transients.py')):
        bind(path)
    runs = {}
    captures = {}
    clips = []
    out.mkdir(parents=True, exist_ok=False)
    for label, directory in (('nes', nes), ('snes', snes), ('observer', observer)):
        receipt, rows = verify_capture(directory)
        if not receipt['capture_complete'] or receipt['scenario_name'] != 'pause-cursor-return':
            raise ValueError('Need completed pause-selector capture')
        captures[label] = (receipt, rows)
        for filename in ('capture.json', 'timeline.json', 'audio.wav'):
            bind(directory/filename)
        if label == 'observer':
            continue
        rate, pcm = normalized(directory/'audio.wav')
        events = []
        times = []
        for index in range(1,5):
            selected = [row for row in rows if row['phase'] in
                        (f'pause_right_{index}', f'pause_right_visible_{index}')]
            first = selected[0]['audio_start_sample']
            last = selected[-1]['audio_start_sample'] + selected[-1]['audio']['samples']
            detected = cues(pcm[first:last], rate)
            if len(detected) != 1:
                raise ValueError('Expected one isolated emulator cue per navigation segment')
            event = detected[0]
            event.update(first=event['first']+first, last=event['last']+first,
                         seconds=event['seconds']+first/rate, segment=index)
            events.append(event)
            times.append(first/rate)
            if index == 1:
                native_rate, native = wavfile.read(directory/'audio.wav')
                path = out/(label+'-cue.wav')
                wavfile.write(path, native_rate, native[first:last])
                clips.append(dict(path=path.name, source=str(directory/'audio.wav'), first=first,
                                  last=last, channels=[0,1], sha256=sha(path)))
        runs[label] = dict(rate=rate, events=events, **checks(events,times))
    control, baseline = captures['snes']
    observed, traced = captures['observer']
    if (baseline != traced or any(control[k] != observed[k] for k in
            ('rom_sha256','audio_sha256','scenario_sha256')) or
            any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in baseline)):
        raise ValueError('Observer is not neutral')
    bus = Path(observed['audio_bus_trace']['path'])
    received = Path(observed['spc_receive_trace']['path'])
    validate_bindings(observed,dict(audio_bus_trace=bus,spc_receive_trace=received))
    with bus.open() as stream:
        bus_rows = list(csv.reader(stream))
    with received.open() as stream:
        transport = compare(bus_rows,list(csv.reader(stream)),paired=True)
    offered = analyze(bus_rows,length_gate=True)
    if not transport['passed'] or offered['mismatches'] or offered['unflushed_cpu_writes']:
        raise ValueError('SPC packet transport failed')
    bind(bus); bind(received)
    coord = bound_report(coordinator)
    if coord.get('declared_events') != episode() or coord.get('recorder_returncode') != 0:
        raise ValueError('Different or failed hardware episode')
    bind(coordinator)
    sources.update(coord['sources'])
    receipt_path = Path(coord['remote_out'])/'report.json'
    input_path = coordinator.parent/'input.json'
    if sha(receipt_path) != coord['recording_report_sha256'] or sha(input_path) != coord['input_sha256']:
        raise ValueError('Changed hardware receipts')
    recording = json.loads(receipt_path.read_text())
    commands = json.loads(input_path.read_text())['events']
    if [dict(keys=e['keys'],seconds=e['seconds']) for e in commands] != episode():
        raise ValueError('Hardware input differs from declared episode')
    start = datetime.fromisoformat(recording['recording_started_utc']).timestamp()
    end = datetime.fromisoformat(recording['recording_stopped_utc']).timestamp()
    if not start <= commands[0]['utc_epoch'] < commands[-1]['utc_epoch']+commands[-1]['seconds'] <= end:
        raise ValueError('Input not covered by recording')
    if not all(recording[k] for k in ('debug_removed','adapter_properties_restored',
                                     'links_unchanged','obs_audio_settings_unchanged')):
        raise ValueError('Hardware capture did not restore state')
    raw = receipt_path.parent/'raw-monitor.wav'
    if recording['artifacts'].get(str(raw)) != sha(raw):
        raise ValueError('Raw capture changed')
    rate, native = wavfile.read(raw)
    if rate != 48000 or native.dtype != np.int32 or native.ndim != 2 or native.shape[1] != 4 or np.any(native[:,2:]):
        raise ValueError('Unexpected pre-mute stream')
    media = Path(recording['recorded']['outputPath'])
    ar, decoded = wavfile.read(aac)
    exact = subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(media),
        '-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-'])
    if ar != rate or decoded.dtype != np.float32 or decoded.tobytes() != exact:
        raise ValueError('AAC excerpt differs from source decode')
    times = [e['utc_epoch'] for e in commands if e['keys']]
    arrays = dict(raw=native[:,:2].astype(float)/2147483648, aac=decoded.astype(float))
    for label, pcm in arrays.items():
        events = cues(pcm,rate)
        runs[label] = dict(rate=rate,events=events,**checks(events,times))
    # Actual retained-capture mutations: original media never changes.
    events = runs['raw']['events']
    if len(events) != 8:
        raise ValueError('Need eight raw cues to exercise capture mutations')
    mutants = {}
    for kind in ('missing_cue','extra_cue','internal_10ms_cut','100ms_delay','stretched_cue'):
        pcm = arrays['raw'].copy()
        e = events[2]; first,last = e['first'],e['last']
        if kind == 'missing_cue':
            pcm[first-rate//10:last+rate//5] = 0
        elif kind == 'extra_cue':
            pcm[first+rate//2:last+rate//2] = pcm[first:last]
        elif kind == 'internal_10ms_cut':
            pcm[first+rate//50:first+rate//50+rate//100] = 0
        elif kind == '100ms_delay':
            saved = pcm[first:last].copy(); pcm[first:last] = 0
            pcm[first+rate//10:last+rate//10] = saved
        else:
            saved = np.repeat(pcm[first:last],2,axis=0); pcm[first:last] = 0
            pcm[first:first+len(saved)] = saved
        checked = checks(cues(pcm,rate),times)
        mutants[kind] = dict(synthetic=True,detected=not checked['passed'],**checked)
    for label, original in (('raw',native[:,:2]),('aac',decoded)):
        first = max(0,runs[label]['events'][0]['first']-rate//10)
        last = runs[label]['events'][0]['first']+rate//2
        path = out/(label+'-cue.wav'); wavfile.write(path,rate,original[first:last])
        clips.append(dict(path=path.name, source=str(raw if label=='raw' else aac), first=first,
                          last=last,channels=[0,1],sha256=sha(path)))
    for path in (receipt_path,input_path,raw,aac,media):
        bind(path)
    for path,digest in recording['sources'].items():
        # Executed helpers are remote; bind corresponding local content explicitly.
        matching = [p for p in map(Path,('tools/capture_blackmagic_raw.py',
                    'tools/capture_blackmagic_monitor.py','tools/obs_hardware_probe.py')) if sha(p)==digest]
        if len(matching) != 1:
            raise ValueError('Different remote recorder helper')
        bind(matching[0])
    result = dict(runs=runs,observer_neutral=True,spc_packets=transport['packets'],
        spc_receive_mismatches=transport['mismatch_count'],mutations=mutants,clips=clips,
        rom_sha256=control['rom_sha256'],media=str(media),sources=sources,
        isolated_cue_checks_passed=all(r['passed'] for r in runs.values()),
        mutations_detected=all(m['detected'] for m in mutants.values()),
        physical_command_identity_verified=False,pop_free_verified=False,release_ready=False,
        scope='Four Right cues in each emulator and four Right/four Left cues on paused Rival. '
        'Fixed 0.0005 full-scale detection, 200ms separation, relative onset tolerance 50ms, '
        'strong duration 45..100ms, no internal exact-zero run >=2ms within 10%-peak bounds. '
        'These coarse missing/repeated/stalled cue gates are not waveform fidelity or a pop detector. '
        'No gain fitting, resampling or time warping; native clips unchanged. '
        'Different filters and capture paths retain different tails. Hardware APU commands not traced.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('isolated_cue_checks_passed','mutations_detected',
                                          'spc_packets','spc_receive_mismatches')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('nes','snes','observer','coordinator','aac','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
