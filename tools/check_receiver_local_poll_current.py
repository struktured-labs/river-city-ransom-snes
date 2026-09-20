"""Current-engine receiver qualification, including relocated volume-writer ownership."""
import argparse
import json
from pathlib import Path
import tempfile
from tools import check_receiver_poll_trial as receiver
from tools.check_receiver_local_poll import check as original_check
from tools.check_interleaved_volume_state import VolumeDriver
from tools.benchmark_report import sha


def check(parent,candidate,core,out):
    if out.exists():raise ValueError('Fresh output required')
    previous=receiver.Driver
    try:
        receiver.Driver=VolumeDriver
        with tempfile.TemporaryDirectory(prefix='rcr-current-receiver-') as temp:
            scratch=Path(temp)/'proof'
            original_check(parent,candidate,core,scratch)
            report=json.loads((scratch/'report.json').read_text())
        meta=json.loads((candidate/'manifest.json').read_text());image=(candidate/'native-cpu.sfc').read_bytes()
        at=meta['sweep_driver_rom_offset'];size=meta['sweep_driver_layout']['engine_bytes']
        bad=bytearray(image[at:at+size])
        if bad[0x177]!=0xac:raise ValueError('Changed suppressed legacy writer')
        bad[0x177]=0xf3
        legacy=receiver.stream(core,bytes(bad),meta['sweep_driver_layout'],0,2048)
        if not legacy['bad_volume_writes']:raise ValueError('Legacy writer mutant escaped')
    finally:receiver.Driver=previous
    report.update(legacy_writer_mutant=legacy,legacy_writer_rejected=True,
        volume_writer_interval=[meta['sweep_driver_layout']['driver']['publish'],0x3540],
        fixture_correction='Use the existing current interleaved-volume ownership range; retain timer-drop and legacy-writer negative controls.')
    for p in (Path(__file__),Path('tools/check_interleaved_volume_state.py')):report['sources'][str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in report['sources'].items()):raise ValueError('Changed source')
    out.mkdir();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],legacy_writer_rejected=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('parent','candidate','core','out'):p.add_argument('--'+k,type=Path,required=True)
    check(**vars(p.parse_args()))
