"""Bind stable physical command exports to guarded video and complete native PCM.

This qualifies evidence, not playback quality, logging overhead, or sub-frame
command/sample alignment. It deliberately does not inherit a cadence verdict.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from tools.audit_hardware_packet_episode import episode
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_mister_game_review import validate_handoff
from tools.capture_mister_boot import remote
from tools.read_mister_packet_export import validate


def stable_export(path):
    report = bound_report(path/'report.json')
    rows = report['snapshots']
    if not report['passed'] or len(rows) < 2:
        raise ValueError('Need two complete stable exports')
    for row in rows[-2:]:
        name = row['file']
        if Path(name).name != name or not row.get('valid'):
            raise ValueError('Invalid stable snapshot')
        data = (path/name).read_bytes()
        result = validate(data, report['minimum_total'], report['expected_sha256'])
        if (result['sha256'] != row['sha256'] or result['total'] != row['total'] or
                result['sha256'] != report['sha256'] or result['total'] != report['total'] or
                report['artifacts'].get(name) != result['sha256']):
            raise ValueError('Changed stable snapshot')
    if report['accepted_file'] != rows[-1]['file']:
        raise ValueError('Different accepted snapshot')
    return report, data


def gaps(pcm, rate):
    if pcm.ndim != 2 or pcm.shape[1] != 2 or rate != 48000 or pcm.dtype != np.int16:
        raise ValueError('Need native S16 stereo 48k PCM')
    edges = np.diff(np.r_[False, np.all(pcm == 0, axis=1), False].astype(np.int8))
    return [dict(first=int(a), last=int(b), duration_ms=(b-a)*1000/rate)
            for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))
            if b-a >= rate//100]


def audit(manifest, out):
    if out.exists():
        raise ValueError('Fresh output required')
    paths = {k: Path(v) for k, v in json.loads(manifest.read_text()).items()}
    sources = {}
    def bind(p):
        sources[str(p)] = sha(p)
    def load(p):
        result = bound_report(p)
        bind(p)
        sources.update(result['sources'])
        return result
    candidate = paths['candidate']
    rom = candidate/'native-cpu.sfc'
    meta = json.loads((candidate/'manifest.json').read_text())
    boot = load(paths['boot'])
    if sha(rom) != meta['rom_sha256'] or meta['rom_sha256'] != boot['rom_sha256']:
        raise ValueError('Different diagnostic cartridge')
    coverage = load(paths['coverage'])
    if (coverage['sources'].get(str(rom)) != sha(rom) or
            not all(coverage['observer_neutral'].values()) or
            coverage['selected'] != coverage['retained_matched'] or
            not coverage['actual_wrong_receiver_mutation_rejected']):
        raise ValueError('Different/unqualified emulator command logger')
    exports, data = {}, {}
    for name in ('before', 'after', 'repeat'):
        exports[name], data[name] = stable_export(paths[name])
        r = load(paths[name]/'report.json')
        if (r['expected_launcher'] != boot['launcher'] or
                r['remote'] != '/media/fat/saves/SNES/RCR-SNES-'+boot['rom_sha256'][:12]+'.sav'):
            raise ValueError('Different exported cartridge')
        for row in r['snapshots']:
            bind(paths[name]/row['file'])
    log = episode(data['before'], data['after'], data['repeat'])
    coord = load(paths['coordinator'])
    if coord.get('error') or coord['recorder_returncode']:
        raise ValueError('Failed recording/input coordinator')
    recorder_path = Path(coord['remote_out'])/'report.json'
    recorder = load(recorder_path)
    if (sha(recorder_path) != coord['recording_report_sha256'] or
            not all(recorder[k] for k in ('debug_removed', 'adapter_properties_restored',
                                         'links_unchanged', 'obs_audio_settings_unchanged'))):
        raise ValueError('Recorder identity/cleanup differs')
    input_path = paths['coordinator'].parent/'input.json'
    inputs = json.loads(input_path.read_text())
    if sha(input_path) != coord['input_sha256']:
        raise ValueError('Changed physical input')
    seconds = lambda value: datetime.fromisoformat(value).timestamp()
    start, stop = map(seconds, (recorder['recording_started_utc'], recorder['recording_stopped_utc']))
    times = {}
    for name in ('presave', 'postsave', 'reexport'):
        receipt = json.loads(paths[name].read_text())
        if any(receipt[k] != boot['config_before'] for k in ('settings_before', 'settings_after')):
            raise ValueError('Configuration changed during save')
        times[name] = (receipt['events'][0]['utc_epoch'],
                       receipt['events'][-1]['utc_epoch']+receipt['events'][-1]['seconds'])
    guards = [load(Path(coord['screen_guard'])/name/'report.json')
              for name in ('before-recording', 'at-input')]
    if (not all(g['passed'] for g in guards) or
            not times['presave'][1] < seconds(guards[0]['checked_utc']) < start <
                inputs['events'][0]['utc_epoch'] < inputs['events'][-1]['utc_epoch'] < stop <
                times['postsave'][0] < times['postsave'][1] < times['reexport'][0]):
        raise ValueError('Recording/export/screen-guard order differs')
    # These monotonic clocks are from the same local reader/coordinator host.
    if exports['before']['snapshots'][-1]['monotonic'] >= coord['ready_received_monotonic']:
        raise ValueError('Baseline was not validated before input')
    decoded = load(paths['decoded']/'report.json')
    capture = load(paths['capture']/'report.json')
    if (not decoded['input_common_exact_conversion'] or capture['returncode'] or
            not capture['same_obs_process'] or not capture['sources_unchanged'] or
            not seconds(capture['started_utc']) < start < stop < seconds(capture['finished_utc']) or
            decoded['sources'].get(str(paths['capture']/'report.json')) != sha(paths['capture']/'report.json')):
        raise ValueError('Incomplete/mismatched native PCM capture')
    for name, digest in decoded['artifacts'].items():
        p = paths['decoded']/name
        if sha(p) != digest:
            raise ValueError('Changed decoded PCM')
        bind(p)
    rate, pcm = wavfile.read(paths['decoded']/'input.wav')
    cr, common = wavfile.read(paths['decoded']/'common.wav')
    if cr != rate or not np.array_equal(pcm.astype(np.float32)/32768, common):
        raise ValueError('Native/common sample conversion differs')
    initial = json.loads(paths['initial'].read_text())
    handoff = json.loads(paths['handoff'].read_text())
    validate_handoff(initial, handoff)
    restored = load(paths['restore'])
    process = remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    config = remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    if (restored['launcher'] not in process or config != boot['config_before'] or
            config != restored['saved_config_sha256'] or
            remote('sha256sum '+restored['rom']).split()[0] != restored['rom_sha256']):
        raise ValueError('Regular cartridge/settings not restored')
    for p in (manifest, Path(__file__), Path('tools/audit_hardware_packet_episode.py'),
              Path('tools/read_mister_packet_export.py'), Path('tools/build_mister_game_review.py'),
              Path('tools/audit_main_display_latency.py'), rom, candidate/'manifest.json',
              input_path, Path(recorder['recorded']['outputPath']), *[paths[k] for k in
              ('initial', 'handoff', 'presave', 'postsave', 'reexport', 'snac_screenshot', 'handoff_screenshot')]):
        bind(p)
    result = dict(diagnostic_rom_sha256=boot['rom_sha256'], log=log,
        physical_export_verified=True, physical_receiver_readback_verified=False,
        sample_exact_command_alignment_verified=False, physical_timing_neutral_verified=False,
        release_ready=False, pop_free_verified=False, packets=decoded['packets'],
        native_frames=len(pcm), rate=rate, native_common_exact=True,
        gaps_at_least_10ms=gaps(pcm, rate), peak=int(np.abs(pcm.astype(np.int32)).max()),
        max_adjacent_step=int(np.abs(np.diff(pcm.astype(np.int32), axis=0)).max()),
        restored_rom_sha256=restored['rom_sha256'], restored_process=process,
        saved_config_sha256=config, scope=__doc__, sources=sources)
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('diagnostic_rom_sha256', 'packets', 'native_frames',
                     'gaps_at_least_10ms', 'peak', 'max_adjacent_step')}))
    print(json.dumps({k: log[k] for k in ('episode_records', 'timeouts', 'nmi_intervals')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    audit(**vars(parser.parse_args()))
