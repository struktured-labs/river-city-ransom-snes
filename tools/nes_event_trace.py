"""Validate host-only NES exact-PC events against requested points and bounds."""
import csv


def validate(records,first,last,frames,points):
    points={int(k):int(v,16) for k,v in points.items()}
    if first<1 or last<first or not points or len(set(points.values()))!=len(points):
        raise ValueError('Invalid NES event window or points')
    if any(not 0<=k<8 or not 0<=v<=65535 for k,v in points.items()):
        raise ValueError('Invalid NES event point')
    count=0;previous=None;seen=set();observed_first=None
    for row in records:
        if len(row)!=50:raise ValueError('NES exact-PC event requires fifty columns')
        frame,line,clock,event=map(int,row[:4]);pc=int(row[4],16)
        if not first<=frame<=min(last,frames):raise ValueError('NES event outside requested window')
        if not -1<=line<=261 or clock<0 or points.get(event)!=pc:
            raise ValueError('Wrong NES event PC or timestamp')
        if any(not 0<=int(v)<=255 for v in row[5:]):raise ValueError('Invalid NES register/RAM byte')
        if previous and (frame<previous[0] or clock<=previous[1]):raise ValueError('Nonmonotonic NES events')
        if observed_first is None:observed_first=frame
        seen.add(event);count+=1;previous=(frame,clock)
    if not count or seen!=set(points):raise ValueError('Missing requested NES events')
    return dict(records=count,observed_first=observed_first,observed_last=previous[0])


def validate_file(path,first,last,frames,points):
    with path.open() as stream:return validate(csv.reader(stream),first,last,frames,points)
