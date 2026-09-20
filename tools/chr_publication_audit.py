"""Check CHR job identity through retired flags AND actual source-equal VRAM bytes."""
from hashlib import sha256


def inspect(raw,rom):
    if len(raw)!=196608:raise ValueError('Need complete WRAM+VRAM snapshot')
    jobs=[]
    for slot in range(24):
        descriptor=raw[0x1500+slot*8:0x1508+slot*8]
        flag=raw[0x1d80+slot];count=int.from_bytes(descriptor[6:8],'little')
        job=dict(slot=slot,flag=flag,descriptor=descriptor.hex(),count=count,source_equal=None)
        if count:
            source=int.from_bytes(descriptor[:3],'little');destination=int.from_bytes(descriptor[4:6],'little')*2
            offset=source&0x3fffff
            if count not in (1024,2048) or source<0xc00000 or offset+count>len(rom) or destination+count>65536:
                raise ValueError('Unsupported CHR descriptor')
            desired=rom[offset:offset+count];actual=raw[131072+destination:131072+destination+count]
            job.update(source=source,destination=destination,source_equal=actual==desired,
                expected_sha256=sha256(desired).hexdigest(),actual_sha256=sha256(actual).hexdigest(),
                mismatched_bytes=sum(a!=b for a,b in zip(desired,actual)))
        elif flag:raise ValueError('Pending zero-length descriptor')
        jobs.append(job)
    return jobs


def episodes(samples,limit=4):
    if not samples or [s['frame'] for s in samples]!=list(range(samples[0]['frame'],samples[-1]['frame']+1)):
        raise ValueError('Missing CHR observation frame')
    result=[]
    for slot in range(24):
        last=None
        for i,s in enumerate(samples):
            job=s['jobs'][slot]
            identity=job['descriptor']
            if job['flag'] and (last is None or identity!=last['descriptor'] or not samples[i-1]['jobs'][slot]['flag']):
                end=i+1
                while end<len(samples) and samples[end]['jobs'][slot]['descriptor']==identity:
                    if end>i+1 and samples[end]['jobs'][slot]['flag'] and not samples[end-1]['jobs'][slot]['flag']:break
                    end+=1
                group=samples[i:end]
                clear=next((t for t in group if not t['jobs'][slot]['flag']),None)
                published=next((t for t in group if not t['jobs'][slot]['flag'] and t['jobs'][slot]['source_equal']),None)
                latency=published['frame']-s['frame'] if published else None
                result.append(dict(slot=slot,descriptor=identity,source_frame=s['frame'],
                    source=s['jobs'][slot].get('source'),destination=s['jobs'][slot].get('destination'),
                    visible_source=s['visible'],left_censored=i==0,
                    initial_mismatched_bytes=job.get('mismatched_bytes'),
                    first_clear=clear['frame'] if clear else None,
                    clear_matches_source=clear['jobs'][slot]['source_equal'] if clear else None,
                    first_publication=published['frame'] if published else None,latency=latency,
                    last_observed_frame=group[-1]['frame'],
                    status='published' if published else 'superseded_without_publication' if end<len(samples) else 'right_censored',
                    passed=published is not None and latency<=limit and clear['jobs'][slot]['source_equal']))
            last=job
    visible=[e for e in result if e['visible_source']]
    return dict(episodes=result,visible_cohort=visible,limit=limit,
                passed=bool(visible) and all(e['passed'] and not e['left_censored'] for e in visible))


def pending_runs(rows,limit=4):
    runs=[];active=None
    for r in rows:
        n=r['native'];eligible=n['task']&192==192 and n['transition_state']==0 and bool(n['ppu_mask']&8)
        pending=n['chr_jobs_pending']
        if eligible and pending:
            if active is None:active=dict(first=r['frame'],last=r['frame'],counts=[])
            active['last']=r['frame'];active['counts'].append(pending)
        elif active:
            active.update(frames=active['last']-active['first']+1,ended_by='cleared' if eligible else 'transition_or_hidden')
            runs.append(active);active=None
    if active:
        active.update(frames=active['last']-active['first']+1,ended_by='right_censored');runs.append(active)
    return dict(runs=runs,limit=limit,max_pending_frames=max((r['frames'] for r in runs),default=0),
                passed=all(r['frames']<=limit and r['ended_by']=='cleared' for r in runs),
                scope='Every visible pending span retained, including spans ended by transition or capture end. '
                      'Aggregate liveness guard, not per-generation source-to-VRAM proof.')
