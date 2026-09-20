"""Reject stale observer binaries that do not honor the requested trace window."""
import csv


def validate(records,first,last,frames):
    if first<1 or last<first or frames<1:raise ValueError('Invalid NES trace window')
    count=0;previous=None;observed_first=None
    for raw in records:
        if len(raw)!=6:raise ValueError('NES scroll trace needs six columns')
        frame,line,clock=map(int,raw[:3]);pc,address=[int(x,16) for x in raw[3:5]];value=int(raw[5])
        if not first<=frame<=min(last,frames):raise ValueError('NES observer ignored requested frame window')
        if clock<0 or not 0<=pc<=65535 or address not in (0xf6,0x3d,0x2005,0x2000) or not 0<=value<=255:
            raise ValueError('Invalid NES scroll event')
        if previous and (frame<previous[0] or clock<=previous[1]):raise ValueError('Nonmonotonic NES scroll events')
        if observed_first is None:observed_first=frame
        previous=frame,clock;count+=1
    if not count:raise ValueError('Empty NES scroll observation')
    return dict(records=count,observed_first=observed_first,observed_last=previous[0])


def validate_file(path,first,last,frames):
    with path.open() as stream:return validate(csv.reader(stream),first,last,frames)
