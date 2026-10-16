"""Reviewed capacity calculation using the explicitly uploaded retained captures."""
import json
from collections import Counter
from datetime import datetime, timedelta
import numpy as np
from book_labs.runtime import ROOT
from book_labs.upload import verify
DATA=ROOT/'data/raw/capacity-upload'
FLOW=DATA/'joined_flow.json'
def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def response(name):
    r=json.loads((DATA/(name+'.json')).read_text())
    return r.get('response',r)
def rows(name):
    r=response(name)
    if r.get('isError'): raise ValueError(name+': source error')
    r=r['structuredContent']
    if r['meta']['next_cursor'] is not None: raise ValueError('Incomplete capture')
    return r['data']
def select_capacity(rr,f,indicator):
    matches=[r for r in rr if r['indicator']==indicator and all(r[k]==f[k] for k in ('point_key','direction','operator_key')) and dt(r['valid_from_utc'])<=dt(f['ts_utc']) and dt(f['period_end_utc'])<=dt(r['valid_to_utc'])]
    if not matches:raise ValueError('Missing full-hour capacity coverage')
    newest=max(dt(r['valid_from_utc']) for r in matches)
    chosen=[r for r in matches if dt(r['valid_from_utc'])==newest]
    if len(chosen)!=1:raise ValueError('Ambiguous newest-start capacity')
    r=chosen[0]
    if r['unit']!='kWh/h' or r['is_unlimited'] or r['value'] is None or not np.isfinite(r['value']) or r['value']<0:raise ValueError('Unusable denominator contract')
    return r,len(matches)
def capacity():
    verify();flow=json.loads(FLOW.read_text())['response'];snapshot=flow['meta']['snapshot_id']
    feeds=('capacity-technical','capacity-available','firm-booked','interruptible')
    rr=[];audits={}
    for feed in feeds:
        latest=rows(feed);prior=rows('asof_'+feed)
        for name in (feed,'asof_'+feed):
            if response(name)['structuredContent']['meta']['snapshot_id']!=snapshot:raise ValueError('Mixed snapshots')
        keys=[tuple(r[k] for k in ('indicator','point_key','direction','operator_key','valid_from_utc')) for r in latest]
        if len(set(keys))!=len(keys):raise ValueError('Duplicate interval key')
        if any(dt(r['retrieved_utc'])>dt('2026-10-10T04:00:00Z') for r in prior):raise ValueError('Capacity cutoff leakage')
        if latest!=prior:raise ValueError('Retained vintage comparison changed')
        audits[feed]={'rows':len(latest),'collector_asof_equal':True};rr.extend(latest)
    indicators=sorted({r['indicator'] for r in rr});result={}
    for direction in ('entry','exit'):
        ff=sorted([r for r in flow['data'] if r['direction']==direction],key=lambda r:r['ts_utc'])
        expected=[dt('2026-10-10T04:00:00Z')+timedelta(hours=i) for i in range(72)]
        if [dt(r['ts_utc']) for r in ff]!=expected:raise ValueError('Incomplete or duplicate flow hours')
        if any(r['unit']!='kWh/h' or dt(r['period_end_utc'])-dt(r['ts_utc'])!=timedelta(hours=1) for r in ff):raise ValueError('Flow unit or duration mismatch')
        selected=[[select_capacity(rr,f,ind) for ind in indicators] for f in ff]
        values={ind:np.array([s[j][0]['value'] for s in selected],float) for j,ind in enumerate(indicators)}
        f=np.array([r['value'] for r in ff],float)
        if not np.isfinite(f).all():raise ValueError('Missing flow')
        ratio=np.full(72,np.nan);np.divide(f,values['Firm Technical'],out=ratio,where=values['Firm Technical']>0)
        result[direction]={'times':expected,'flow':f,'values':values,'ratio':ratio,'overlap_hours':sum(any(n>1 for r,n in s) for s in selected),
            'status':dict(Counter(r['flow_status'] for r in ff))}
    return {'directions':result,'audit':audits,'narrow_query_rows':len(rows('narrow_technical'))}
