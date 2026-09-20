"""Bind complete SPC event traces to an observer-neutral game waveform."""
import argparse
import csv
import json
from pathlib import Path

from tools.analyze_audio_bus import analyze as analyze_bus
from tools.analyze_game_keyons import analyze as analyze_keyons
from tools.analyze_spc_receive import compare as compare_received
from tools.benchmark_report import sha, verify_capture


def validate_headers(rows, packets):
    headers = [row for row in rows if row[0] == 'P']
    if len(headers) != len(packets):
        raise ValueError('SPC header and full bus packet counts differ')
    for number, (header, packet) in enumerate(zip(headers, packets), 1):
        data = bytes.fromhex(packet['bytes'])
        if len(header) != 7 or len(data) != 23:
            raise ValueError('Malformed complete packet/header')
        if int(header[1]) != number or list(map(int, header[2:6])) != [data[22], data[21], data[0], data[4]]:
            raise ValueError('SPC header differs from actual received bytes')
    return len(headers)


def validate_synthesis(rows, packet_count, *, triple=False, receiver_pc=None, ready_pc=0x0474):
    if receiver_pc is None:receiver_pc=0x300c if triple else 0x3008
    last_tick = -1
    pending = None
    ready = []
    startup = []
    for row in rows:
        if len(row) != 4 or row[0] not in ('P', 'R'):
            raise ValueError('Malformed SPC completion event')
        kind, number, tick, pc = row[0], int(row[1]), int(row[2]), int(row[3], 16)
        if tick <= last_tick:
            raise ValueError('Nonmonotonic SPC ticks')
        last_tick = tick
        if number == 0:
            if kind != 'R' or ready or pending or pc not in (0xffe2, ready_pc):
                raise ValueError('Invalid startup ready event')
            startup.append(dict(tick=tick, pc=pc))
            continue
        if kind == 'P':
            if pending is not None or number != len(ready)+1 or pc != receiver_pc:
                raise ValueError('Missing ready or out-of-order SPC packet')
            pending = (number, tick)
        else:
            if pending is None or pending[0] != number or pc != ready_pc:
                raise ValueError('Unexpected SPC ready event')
            ready.append(dict(packet=number, received_tick=pending[1], ready_tick=tick,
                              processing_ticks=tick-pending[1]))
            pending = None
    if pending is not None or len(ready) != packet_count or not ready:
        raise ValueError('Incomplete SPC processing coverage')
    if not startup or startup[-1]['pc'] != ready_pc:
        raise ValueError('Missing engine startup ready')
    return dict(startup=startup, packets=ready,
                minimum_processing_ticks=min(r['processing_ticks'] for r in ready),
                maximum_processing_ticks=max(r['processing_ticks'] for r in ready))


def validate_bindings(receipt, traces):
    for field, path in traces.items():
        binding = receipt.get(field, {})
        if binding.get('path') != str(path.resolve()) or binding.get('sha256') != sha(path):
            raise ValueError('Missing or changed capture-bound trace: '+field)


def splash_ident_model(capture, receipt):
    """Called only after verify_capture authenticates the boot manifest/handoff."""
    if not receipt.get('boot_fault_policy'):
        return False
    path = capture/'boot-manifest.json'
    if sha(path) != receipt['candidate_manifest_sha256']:
        raise ValueError('Changed splash manifest')
    splash = json.loads(path.read_text())['splash']
    ident = splash.get('ident_audio', False)
    if ident and splash.get('ident_spc_sha256') != 'acd06820ac015f15cbaba5f73a86d7348cf1fff0d8cfdae64ac970e5774621a5':
        raise ValueError('Unknown splash ident key-on program')
    return ident


def audit(capture, normal, keyons, synth, bus, out, triple=False, received=None):
    receipt, rows = verify_capture(capture)
    control, baseline = verify_capture(normal)
    if (receipt['system'] != 'snes' or control['system'] != 'snes' or not receipt['capture_complete']
            or not control['capture_complete'] or rows != baseline
            or any(row['fault'] or row['input_requested'] != row['input_delivered'] for row in rows)
            or any(receipt[k] != control[k] for k in ('rom_sha256', 'scenario_sha256', 'audio_sha256'))):
        raise ValueError('Need complete fault-free observer-neutral replay')
    validate_bindings(receipt, dict(game_keyon_trace=keyons, spc_synth_trace=synth, audio_bus_trace=bus))
    if triple and received is None:
        raise ValueError('Triple qualification requires all physical SPC receive stores')
    if received is not None:
        validate_bindings(receipt, dict(spc_receive_trace=received))
    def read(path):
        with path.open() as stream:
            return list(csv.reader(stream))
    keyon_rows, bus_rows, synth_rows = map(read, (keyons, bus, synth))
    receiver = None
    if received is not None:
        receiver = compare_received(bus_rows, read(received), paired=not triple, triple=triple)
        if not receiver['passed']:
            raise ValueError('Actual SPC receive bytes differ from sent bytes')
    splash_ident = splash_ident_model(capture, receipt)
    schedule = analyze_keyons(keyon_rows, fast=True, triple=triple, splash_ident=splash_ident)
    transport = analyze_bus(bus_rows, length_gate=True)
    if not schedule['passed'] or transport['mismatches'] or transport['unflushed_cpu_writes']:
        raise ValueError('SPC key-on schedule or transport failed')
    count = validate_headers(keyon_rows, transport['packets'])
    completion = validate_synthesis(synth_rows, count, triple=triple)
    out.mkdir(parents=True, exist_ok=False)
    for name, value, trace in (('keyon-report', schedule, keyons), ('bus-report', transport, bus)):
        (out/(name+'.json')).write_text(json.dumps(value | dict(trace_sha256=sha(trace)), indent=2)+'\n')
    report = dict(passed=True, frames=receipt['frames'], packets=count, observer_neutral=True,
        transport='triple' if triple else 'paired',
        receiver=receiver,
        rom_sha256=receipt['rom_sha256'], audio_sha256=receipt['audio_sha256'],
        keyon_schedule=schedule, spc_completion=completion,
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/benchmark_capture.py'),
            Path('tools/benchmark_report.py'), Path('tools/analyze_audio_bus.py'),
            Path('tools/analyze_game_keyons.py'), Path('tools/analyze_spc_receive.py'), capture/'capture.json', normal/'capture.json',
            keyons, synth, bus, out/'keyon-report.json', out/'bus-report.json')},
        scope='Contemporaneously capture-bound host traces, full replay neutrality, CPU packet '
              'bytes and four SPC header fields cross-checked, pulse key-on schedule, and '
              'last-logical-byte-to-ready SPC ticks. '+
              ('All physical receiver stores independently checked, including triple padding. '
               if received is not None else 'No complete physical receive-store trace supplied. ')+
              'IPL acknowledgements are separate from engine ready events. Not DSP sample latency, '
              'waveform fidelity, perceptual click detection or physical audio certification.')
    if received is not None:
        report['sources'][str(received)] = sha(received)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, frames=receipt['frames'], packets=count,
        processing_ticks=[completion['minimum_processing_ticks'], completion['maximum_processing_ticks']])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'normal', 'keyons', 'synth', 'bus', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--triple', action='store_true', help='Require the pinned three-byte receiver PC')
    p.add_argument('--received', type=Path, help='Capture-bound actual SPC packet stores; required for triple')
    audit(**vars(p.parse_args()))
