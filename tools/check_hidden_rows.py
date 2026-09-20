"""Execute hidden-load row budgets, unchanged visible budgets, and mutations."""
import argparse
import hashlib
import json
from pathlib import Path

try:
    from .check_rows import check, ROOT
except ImportError:
    from check_rows import check, ROOT


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    positives=[]
    for budget in (4,8,16):
        for state in (0,1,2):
            folder=out/f'rows-{budget}-state-{state}'
            check(core,folder,attribute_lookup=True,hidden_rows=budget,transition_state=state)
            positives.append(dict(budget=budget,state=state,cases=8))
    source=(ROOT/'snes/native_prepare.asm').read_text()
    anchor='    lda $1CA0\n    cmp #2\n    bne :+\n    lda #HIDDEN_ROW_BUDGET'
    if source.count(anchor)!=1:raise ValueError('Ambiguous hidden-budget guard')
    negatives=[]
    for name,state,replacement in (
        ('visible-budget-leak',0,anchor.replace('cmp #2','cmp #0')),
        ('wrong-hidden-budget',2,anchor.replace('lda #HIDDEN_ROW_BUDGET','lda #2'))):
        folder=out/name;folder.mkdir()
        (folder/'row_test.asm').write_bytes((ROOT/'snes/row_test.asm').read_bytes())
        (folder/'native_prepare.asm').write_text(source.replace(anchor,replacement))
        try:
            check(core,folder,source=folder/'row_test.asm',attribute_lookup=True,hidden_rows=8,transition_state=state)
        except RuntimeError as error:
            if 'First-batch flags differ' not in str(error):raise
            negatives.append(dict(name=name,failure=str(error)))
        else:raise ValueError('Hidden-budget mutation was not rejected')
    report=dict(passed=True,positive=positives,negative_controls=negatives,
        scope='72 emulated row-conversion cases across pattern/mirroring/task/transition budgets; all 3840 visible tile words checked per case. Not frame timing or full-game certification.',
        files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.sfc','.ram','.asm')},
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=72,negative_controls=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
