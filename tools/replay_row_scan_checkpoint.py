"""Exact-state row-scan probe with authenticated same-ROM audio/video restoration."""
import argparse
import ctypes as C
import json
from pathlib import Path
import time

from tools import replay_route_checkpoint as base
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_full_row_scan import patch, SITE


def replay(core, candidate, normal, checkpoint_report, frame, frames, out,
           trial=None, resume_control=None):
    started = time.monotonic()
    if frames > 120:
        raise ValueError('Focused replay capped at 120 frames')
    if trial:
        for file in ('native_boot.lbl', 'native_runtime.lbl'):
            if (candidate/file).read_bytes() != (trial/file).read_bytes():
                raise ValueError('Linked code moved')
        proof = bound_report(resume_control/'report.json')
        if proof['sources'].get(str(Path(__file__))) != sha(Path(__file__)):
            raise ValueError('Resume control used another wrapper')
        meta = json.loads((trial/'manifest.json').read_text())['experimental_full_row_scan']
        if any(sha(Path(p)) != h for p, h in meta['sources'].items()):
            raise ValueError('Changed scan-patch dependency')
    snapshots, initial, loaded = [], {}, []
    original_loader, original_patch = C.CDLL, base.budget_patch

    def guarded(image, start, end, old, new):
        if old != 16 or new != 16:
            raise ValueError('Hidden budget must remain unchanged')
        expected, _ = patch(image)
        return expected, SITE+1

    def loader(path, *args, **kwargs):
        lib = original_loader(path, *args, **kwargs)
        if Path(path).resolve() != core.resolve():
            return lib
        if loaded:
            raise ValueError('Multiple core instances')
        loaded.append(lib)
        run, restore = lib.retro_run, lib.retro_unserialize

        def state():
            if lib.retro_get_memory_size(2) != 131072 or lib.retro_get_memory_size(3) != 65536:
                raise ValueError('Wrong memory geometry')
            wram = C.string_at(lib.retro_get_memory_data(2), 131072)
            vram = C.string_at(lib.retro_get_memory_data(3), 65536)
            regs = {k: lib.retro_rcr_cpu_register(i) for i,k in enumerate(('pc','a','x','y','s','p','db','dp'))}
            return wram, vram, regs

        def restore_state(data, size):
            # The base sets ctypes declarations on this wrapper, not its saved
            # underlying function, so specify the native ABI explicitly here.
            restore.argtypes = [C.c_void_p, C.c_size_t]; restore.restype = C.c_bool
            ok = restore(data, size)
            if ok:
                wram, vram, regs = state()
                if abs((regs['pc'] & 0x3fffff)-SITE) <= 4:
                    raise ValueError('Checkpoint overlaps changed instruction')
                (out/'initial.vram').write_bytes(vram)
                initial.update(registers=regs, wram_sha256=base.digest(wram), vram_sha256=base.digest(vram))
            return ok

        def step():
            run()
            wram, vram, regs = state()
            n = frame+len(snapshots)+1
            rows = {}
            for r in (2, 25):
                rows[str(r)] = dict(shadow=wram[0x12000+r*32:0x12000+(r+1)*32].hex(),
                    staged=wram[0x3000+r*64:0x3000+(r+1)*64].hex(),
                    vram=vram[0x4000+r*64:0x4000+(r+1)*64].hex())
            snapshots.append(dict(frame=n, rows=rows, flags=wram[0x1d00:0x1d80].hex(),
                                  registers=regs, sprite_source=wram[0x1000:0x1100].hex(),
                                  sprite_staging=wram[0x5000:0x5220].hex()))
        lib.retro_run, lib.retro_unserialize = step, restore_state
        return lib
    try:
        C.CDLL, base.budget_patch = loader, guarded
        passed = base.replay(core, candidate, normal, checkpoint_report, frame, frames, out,
                             budget_trial=trial, resume_control=resume_control)
    finally:
        C.CDLL, base.budget_patch = original_loader, original_patch
    report = json.loads((out/'report.json').read_text())
    if len(snapshots) != frames or not initial:
        raise ValueError('Incomplete publication observer')
    (out/'row-publication.json').write_text(json.dumps(snapshots)+'\n')
    report['initial_full_state'] = initial
    if trial:
        initial_equal = initial == proof['initial_full_state']
        if not initial_equal:
            passed = False
        report['initial_full_state_matches_control'] = initial_equal
        report['same_state_comparison_valid'] &= initial_equal
        report['cross_rom_restore_verified'] &= initial_equal
        report['row_scan_trial'] = dict(report.pop('budget_trial'), before=32, after=128)
    report['sources'].update({str(p): sha(p) for p in
        (Path(__file__), Path('tools/build_full_row_scan.py'), Path('tools/replay_route_checkpoint.py'))})
    report['artifacts'].update({str(p.relative_to(out)): sha(p) for p in
                               (out/'initial.vram', out/'row-publication.json')})
    report['seconds'] = time.monotonic()-started
    report['scope'] = (__doc__+' Trial permits only ROM$838E 32→128 and checksum; hidden budget unchanged. '
        'All initial CPU registers, full WRAM and VRAM must match. Same-ROM control must match '
        'uninterrupted game RAM, PC/P/DB, video, delivered input and native PCM including callback boundaries. '
        'No historical trace counters or instruction clocks used after restoration. Full later differences retained; '
        'trial comparison validity is not an equality/release verdict.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(valid=passed, seconds=report['seconds'], frames=frames)))
    return passed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out'):
        p.add_argument('--'+k, type=Path, required=True)
    for k in ('frame','frames'):
        p.add_argument('--'+k, type=int, required=True)
    for k in ('trial','resume-control'):
        p.add_argument('--'+k, type=Path)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
