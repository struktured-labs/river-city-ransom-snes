"""Refuse controller replay when the observed paused game differs from its reference.

Requires a manually audited, OSD-closed paused-street reference from this setup.
This conservative image guard is not a universal pause/OSD recognizer and cannot
exclude a state change after the last observation. Original evidence is untouched.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from tools import capture_mister_dual_audio as coordinator
from tools.capture_mister_scroll import run as scroll
from tools.benchmark_report import sha
from tools.read_obs_audio_provenance import read

# Game display, HUD and pause labels in the audited OBS scene. Excludes chat,
# controller illustrations and branding outside the game. No scale/lag fitting.
ROI = (596, 66, 3240, 2096)
GEOMETRY = (2160, 3840, 3)
MAX_CHANGED_FRACTION = .005
MAX_RMS = 10.0
PIXEL_THRESHOLD = 40


def compare(reference, observed):
    if reference.shape != GEOMETRY or observed.shape != GEOMETRY:
        raise ValueError('Unexpected OBS image geometry; no input is safe')
    x0, y0, x1, y1 = ROI
    delta = observed[y0:y1, x0:x1].astype(np.int16)-reference[y0:y1, x0:x1].astype(np.int16)
    fraction = float(np.mean(np.max(np.abs(delta), axis=2) > PIXEL_THRESHOLD))
    rms = float(np.sqrt(np.mean(delta.astype(np.float64)**2)))
    return dict(passed=fraction <= MAX_CHANGED_FRACTION and rms <= MAX_RMS,
                changed_fraction=fraction, rms=rms, roi=list(ROI),
                limits=dict(changed_fraction=MAX_CHANGED_FRACTION, rms=MAX_RMS,
                            pixel_threshold=PIXEL_THRESHOLD))


def check(reference, out, *, recording=False, url='ws://127.0.0.1:4455'):
    if out.exists():
        raise ValueError('Need fresh guard evidence')
    out.mkdir(parents=True, exist_ok=False)
    reference_hash = sha(reference)
    started = time.monotonic()
    state = read(url, 'blackmage', out/'observed.png')
    elapsed = time.monotonic()-started
    try:
        with Image.open(reference) as image:
            original = np.asarray(image.convert('RGB'))
        with Image.open(out/'observed.png') as image:
            current = np.asarray(image.convert('RGB'))
        result = compare(original, current)
    except (ValueError, OSError) as error:
        # Retain a machine-readable refusal, including wrong-resolution frames.
        result = dict(passed=False, image_error=str(error))
    result.update(state=state, observation_seconds=elapsed,
        settings_passed=(state['scene'] == 'river city ransom' and
                         state['recording_active'] == recording and not state['replay_active'] and
                         not state['blackmagic']['mute']),
        reference_unchanged=sha(reference) == reference_hash,
        no_controller_input_sent=True, checked_utc=datetime.now(timezone.utc).isoformat(),
        scope=__doc__, sources={str(p): sha(p) for p in (
            Path(__file__), Path('tools/read_obs_audio_provenance.py'), reference, out/'observed.png')})
    result['passed'] = (result['passed'] and result['settings_passed'] and
                        result['reference_unchanged'] and elapsed <= 3.0)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    if not result['passed']:
        raise ValueError('Game-screen precondition failed; controller input refused')
    return result


@contextmanager
def guarded_input(reference, guard_out):
    original = coordinator.run
    calls = []
    def send(*args, **kwargs):
        if calls:
            raise ValueError('Unexpected second controller sequence')
        calls.append(True)
        check(reference, guard_out/'at-input', recording=True)
        return original(*args, **kwargs)
    coordinator.run = send
    try:
        yield
    finally:
        coordinator.run = original


def capture(reference, out, remote_out, guard_out):
    if out.exists() or remote_out.exists() or guard_out.exists():
        raise ValueError('Need fresh capture and guard paths')
    # Refuse before creating a recorder. Recheck after its ready handshake,
    # immediately before the only controller call. Old coordinator owns cleanup.
    check(reference, guard_out/'before-recording')
    try:
        with guarded_input(reference, guard_out):
            scroll(out, remote_out)
    finally:
        report_path = out/'report.json'
        if report_path.exists():
            report = json.loads(report_path.read_text())
            report['screen_guard'] = str(guard_out)
            report['sources'].update({str(p): sha(p) for p in (
                Path(__file__), reference, *sorted(guard_out.glob('*/report.json')))})
            report_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    observe = sub.add_parser('check')
    for name in ('reference', 'out'):
        observe.add_argument('--'+name, type=Path, required=True)
    observe.add_argument('--recording', action='store_true')
    cap = sub.add_parser('capture')
    for name in ('reference', 'out', 'remote-out', 'guard-out'):
        cap.add_argument('--'+name, type=Path, required=True)
    args = vars(parser.parse_args()); command = args.pop('command')
    (check if command == 'check' else capture)(**args)
