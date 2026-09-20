"""Two bounded hardware recordings of the qualified SPC player, then reload game."""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.capture_mister_boot import capture, remote, stamp
from tools.read_obs_audio_provenance import read


def trial(fixture, qualification, visual, out, remote_prefix, tail_only=False):
    q = bound_report(qualification); v = bound_report(visual)
    f = bound_report(fixture/'manifest.json')
    if not q['passed'] or not v['passed'] or q['replay_rom_sha256'] != f['rom_sha256']:
        raise ValueError('Unqualified replay')
    if v['sources'].get(str(fixture/'manifest.json')) != sha(fixture/'manifest.json'):
        raise ValueError('Unrelated visual proof')
    before = remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
    launchers = re.findall(r'/media/fat/RCR-SNES-[a-f0-9]{12}\.mgl',before)
    if len(launchers) != 1:raise ValueError('Cannot identify original game launcher')
    original = launchers[0]
    config = remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
    boot_path = Path(str(remote_prefix)+'-boot'); tail_path = Path(str(remote_prefix)+'-tail')
    if out.exists() or boot_path.exists() or tail_path.exists():raise ValueError('Need fresh output paths')
    out.mkdir(parents=True)
    stage = out/'staged'; stage.mkdir()
    shutil.copyfile(fixture/'player.sfc',stage/'native-cpu.sfc')
    helper = Path('tools/capture_blackmagic_raw.py')
    remote_helper = '/tmp/rcr-raw-boot-'+sha(helper)[:16]+'.py'
    result = dict(started_utc=stamp(), original_launcher=original, config_before=config,
        tail_only=tail_only,
        replay_rom_sha256=f['rom_sha256'], release_ready=False, snac_restoration_verified=False,
        sources={str(p):sha(p) for p in (Path(__file__),fixture/'manifest.json',fixture/'player.sfc',
            qualification,visual,Path('tools/capture_mister_boot.py'),helper)})
    try:
        if tail_only:
            state=read('ws://127.0.0.1:4458','blackmage')
            if state['recording_active'] or state['replay_active']:raise ValueError('OBS is busy')
            target='/media/fat/games/SNES/RCR-SNES-'+f['rom_sha256'][:12]+'.sfc'
            launcher='/media/fat/RCR-SNES-'+f['rom_sha256'][:12]+'.mgl'
            if remote('sha256sum '+target).split()[0]!=f['rom_sha256']:
                raise ValueError('Existing replay cartridge differs')
            launch_text=remote('cat '+launcher)
            if target not in launch_text or '_Console/SNES_20260603' not in launch_text:
                raise ValueError('Existing replay launcher differs')
            result['launch_requested_utc']=stamp()
            remote("printf '%s\\n' "+shlex.quote('load_core '+launcher)+' > /dev/MiSTer_cmd')
            time.sleep(25)
            result['replay_process']=remote('ps -ef | grep "[M]iSTer /media/fat/_Console/"')
            if launcher not in result['replay_process']:raise ValueError('Different running cartridge')
        else:
            capture(stage,out/'boot',boot_path)
            # StopRecord can acknowledge while OBS still flushes the output.
            # Observe idle; never stop a recording we do not own.
            for _ in range(8):
                state=read('ws://127.0.0.1:4458','blackmage')
                if not state['recording_active'] and not state['replay_active']:break
                time.sleep(.5)
            else:raise ValueError('OBS did not become idle after owned recording')
        command = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','blackmage',
            '/home/struktured/.local/bin/python3',remote_helper,'--seconds','30','--out',str(tail_path)]
        tail = subprocess.run(command,text=True,capture_output=True,timeout=50)
        result['tail_stdout']=tail.stdout;result['tail_stderr']=tail.stderr
        tail.check_returncode()
        result['recordings']={str(p/'report.json'):sha(p/'report.json') for p in
                              ((tail_path,) if tail_only else (boot_path,tail_path))}
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        try:
            remote("printf '%s\\n' "+shlex.quote('load_core '+original)+' > /dev/MiSTer_cmd')
            result['game_reload_requested_utc']=stamp()
            result['config_after']=remote('sha256sum /media/fat/config/SNES.CFG').split()[0]
            if result['config_after']!=config:raise ValueError('Saved configuration changed')
        finally:
            result['finished_utc']=stamp()
            (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','qualification','visual','out','remote-prefix'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--tail-only',action='store_true',help='Replay an already hash-verified staged cartridge; record seconds25..55')
    trial(**vars(p.parse_args()))
