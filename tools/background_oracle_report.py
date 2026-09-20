"""Recheck the executed observer oracle, not only its saved pass flag."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SOURCE_NAMES=('tools/check_background_observer.py','snes/background_observer_test.asm',
              'tools/snes9x_background.inc','.deps/snes9x/gfx.cpp',
              'tools/smoke_libretro.py','tools/background_observer.py')
FILES=('test.sfc','screen.png','background.png','background.valid','receipt.json')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path,core_sha):
    report=json.loads(path.read_text())
    if (report.get('core_sha256')!=core_sha or report.get('passed') is not True or
        report.get('sources')!={name:sha(ROOT/name) for name in SOURCE_NAMES}):
        raise ValueError('Unbound observer oracle core or sources')
    cases=report.get('cases',[])
    if len(cases)!=80:raise ValueError('Incomplete observer oracle')
    expected=[dict(SC_SIZE=s,SCROLL_X=x,SCROLL_Y=y,CHR_BASE=b,BRIGHTNESS=v,
                   BG_MODE=0,COLOR_MATH=0,WINDOW_ENABLE=0,WINDOW_LEFT=0,WINDOW_RIGHT=255)
              for s in range(4) for x,y in ((0,0),(1,7),(255,255),(256,256),(511,511),(257,17))
              for b,v in ((0,15),(4,7),(15,15))]
    for enable,left,right in ((2,0,7),(3,0,7),(2,64,192),(3,64,192),(2,0,255),(3,0,255)):
        expected.append(dict(expected[0],WINDOW_ENABLE=enable,WINDOW_LEFT=left,WINDOW_RIGHT=right))
    expected.extend([dict(expected[0],BG_MODE=1),dict(expected[0],COLOR_MATH=1)])
    for i,(case,config) in enumerate(zip(cases,expected)):
        folder=path.parent/f'case-{i:02d}'
        if (case.get('config')!=config or case.get('files')!={name:sha(folder/name) for name in FILES}):
            raise ValueError('Changed/missing oracle case or artifacts')
        receipt=json.loads((folder/'receipt.json').read_text())
        if (receipt['core_sha256']!=core_sha or receipt['rom_sha256']!=sha(folder/'test.sfc') or
            case['rom_sha256']!=receipt['rom_sha256'] or receipt['screenshot_sha256']!=sha(folder/'screen.png') or
            receipt['emulated_frames']!=120 or receipt['video_frames']!=120 or receipt['status']!='passed'):
            raise ValueError('Unbound executed oracle receipt')
        screen=np.asarray(Image.open(folder/'screen.png').convert('RGB'))
        bg=np.asarray(Image.open(folder/'background.png').convert('RGB'))
        flags=(folder/'background.valid').read_bytes()
        if screen.shape!=(239,256,3) or bg.shape!=(240,256,3) or len(flags)!=240:
            raise ValueError('Bad oracle video geometry')
        diff=int(np.any(screen!=bg[:239],axis=2).sum())
        supported=i<78
        passed=diff==0 and flags[:239]==bytes([1])*239 if supported else not any(flags)
        if (case['differing_pixels']!=diff or case['valid_lines']!=sum(flags[:239]) or
            case['supported']!=supported or case['passed'] is not True or not passed):
            raise ValueError('False oracle pass or unsupported-row claim')
    return report
