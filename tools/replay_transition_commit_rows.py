"""Exact-state text/HUD guard for candidate3502, not a substitute for its boot checks."""
import argparse
import json
from pathlib import Path

from tools import replay_row_scan_checkpoint as base
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.early_oam_final_slack import patch as early_patch
from tools.build_transition_commit_direct import patch as commit_patch
from tools.build_transition_display_commit import assemble


def patch(image):
    early,_=early_patch(image)
    return commit_patch(early,assemble())


def replay(**args):
    control=bound_report(args['resume_control']/'report.json')
    initial_pc=control['initial_full_state']['registers']['pc']&0x3fffff
    original=(args['candidate']/'native-cpu.sfc').read_bytes()
    expected,_=patch(original)
    if expected!=(args['trial']/'native-cpu.sfc').read_bytes():raise ValueError('Changed candidate composition')
    # Do not resume in a changed instruction/operand or the inserted helper.
    if any(original[i]!=expected[i] for i in range(max(0,initial_pc-4),min(len(original),initial_pc+5))):
        raise ValueError('Checkpoint overlaps patched code')
    manifest=json.loads((args['trial']/'manifest.json').read_text())
    dependencies=manifest['experimental_transition_display_commit']['sources']
    if any(sha(Path(p))!=h for p,h in dependencies.items()):raise ValueError('Changed transition patch dependency')
    old=base.patch
    try:
        base.patch=patch
        result=base.replay(**args)
    finally:base.patch=old
    p=args['out']/'report.json';report=json.loads(p.read_text())
    report['sources'].update(dependencies)
    for path in (Path(__file__),Path('tools/early_oam_final_slack.py'),Path('tools/early_oam_palette.py'),Path('tools/early_oam_scan.py')):
        report['sources'][str(path)]=sha(path)
    report['row_scan_trial'].update(early_oam=True,explicit_palette_mode_bank=True,row_cutoff=249,
        final_palette_cutoff=254,atomic_transition_commit=True,direct_page_readiness=True)
    report['scope']=(__doc__+' Exact pinned composition3502 from3408. Complete initial CPU/WRAM/VRAM equality and '
        'authenticated same-ROM uninterrupted control required. All cross-ROM primary differences retained; '
        'not a claim of original-game speed or unchanged sound. No restored historical observers.')
    p.write_text(json.dumps(report,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('core','candidate','normal','checkpoint-report','out','trial','resume-control'):
        p.add_argument('--'+k,type=Path,required=True)
    for k in ('frame','frames'):p.add_argument('--'+k,type=int,required=True)
    raise SystemExit(0 if replay(**vars(p.parse_args())) else 1)
