"""Strict, aggregate-only security summaries; no collectors or network clients."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

MAX_BYTES = 16384
SOURCES = ('dependabot', 'sidekick_defender')
COMMON = {'schema', 'source', 'observed_utc', 'model_status'}
DEPENDABOT = COMMON | {'quality','reason','checked','expected','unavailable',
    'critical','high','medium','low','unknown','page_limit_reached'}
DEFENDER = COMMON | {'status_quality','history_quality','service_enabled',
    'antivirus_enabled','realtime_enabled','definitions_updated_utc',
    'quick_scan_utc','full_scan_utc','window_start_utc','window_end_utc',
    'detections_24h','latest_detection_utc'}
STAMP = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,7})?(?:Z|\+00:00)$')


def timestamp(value):
    if not isinstance(value, str) or len(value)>40 or not STAMP.fullmatch(value):
        raise ValueError('timestamp')
    dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None or dt.year<2000:
        raise ValueError('timestamp')
    return dt.timestamp()


def number(value, maximum=1000000):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError('count')
    return value


def validate(data, now):
    if not isinstance(data,dict) or type(data.get('schema')) is not int or data['schema']!=1:
        raise ValueError('schema')
    source=data.get('source')
    if source not in SOURCES or set(data)!=(DEPENDABOT if source=='dependabot' else DEFENDER):
        raise ValueError('fields')
    if data['model_status']!='not_used': raise ValueError('model')
    at=timestamp(data['observed_utc'])
    if at>now+300: raise ValueError('future')
    if source=='dependabot':
        if data['quality'] not in ('complete','partial','unavailable','failed','not_collected'):
            raise ValueError('quality')
        if data['reason'] not in ('two_targets_complete','page_limit','mixed_coverage',
            'access_or_feature_unavailable','authentication_failed','api_failed','no_token'):
            raise ValueError('reason')
        if type(data['expected']) is not int or data['expected']!=2: raise ValueError('scope')
        checked=number(data['checked'],2); unavailable=number(data['unavailable'],2)
        if checked+unavailable>2 or type(data['page_limit_reached']) is not bool:
            raise ValueError('scope')
        counts=[data[k] for k in ('critical','high','medium','low','unknown')]
        if checked:
            for value in counts: number(value,200)
            if sum(counts)>200: raise ValueError('bound')
        elif any(value is not None for value in counts): raise ValueError('missing_counts')
        if data['quality']=='complete' and (checked!=2 or unavailable or data['page_limit_reached'] or data['unknown']):
            raise ValueError('incomplete')
        if (data['quality']=='complete') != (data['reason']=='two_targets_complete'):
            raise ValueError('reason')
        if data['quality']=='not_collected' and (checked or unavailable or data['reason']!='no_token'):
            raise ValueError('uncollected')
        if data['reason']=='no_token' and data['quality']!='not_collected': raise ValueError('reason')
    else:
        if data['status_quality'] not in ('complete','unavailable','failed') or data['history_quality'] not in (
            'available_retention_unknown','truncated_retention_unknown','unavailable','failed'):
            raise ValueError('quality')
        for key in ('service_enabled','antivirus_enabled','realtime_enabled'):
            if data[key] is not None and type(data[key]) is not bool: raise ValueError('flag')
            if data['status_quality']=='complete' and data[key] is None: raise ValueError('flag')
            if data['status_quality']!='complete' and data[key] is not None: raise ValueError('missing_flag')
        for key in ('definitions_updated_utc','quick_scan_utc','full_scan_utc','latest_detection_utc'):
            if data[key] is not None and timestamp(data[key])>at+300: raise ValueError('future')
        if data['status_quality']!='complete' and any(data[k] is not None for k in ('definitions_updated_utc','quick_scan_utc','full_scan_utc')):
            raise ValueError('missing_status_dates')
        start=timestamp(data['window_start_utc']); end=timestamp(data['window_end_utc'])
        if end!=at or end-start!=86400: raise ValueError('window')
        if data['history_quality'] in ('available_retention_unknown','truncated_retention_unknown'):
            number(data['detections_24h'],1001)
            if data['detections_24h']==0 and data['latest_detection_utc'] is not None: raise ValueError('count_time')
            if data['detections_24h']>0 and data['latest_detection_utc'] is None: raise ValueError('count_time')
        elif data['detections_24h'] is not None or data['latest_detection_utc'] is not None:
            raise ValueError('missing_history')
        if data['latest_detection_utc'] is not None and not start<=timestamp(data['latest_detection_utc'])<end:
            raise ValueError('window')
    return data


def _no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate')
        result[key]=value
    return result


def load(path,now):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError('file')
    raw=path.read_bytes()
    if len(raw)>MAX_BYTES: raise ValueError('size')
    return parse(raw,now)


def parse(raw,now):
    if len(raw)>MAX_BYTES: raise ValueError('size')
    # Flat schema only: constrain JSON nesting independently of Python recursion limits.
    depth=0; quoted=False; escaped=False
    for c in raw.decode('utf-8-sig'):
        if quoted:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c=='"': quoted=False
        elif c=='"': quoted=True
        elif c in '{[':
            depth+=1
            if depth>2: raise ValueError('depth')
        elif c in '}]': depth-=1
    data=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_no_duplicates,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('constant')))
    return validate(data,now)


def save_new(directory,data,now):
    validate(data,now)
    directory=Path(directory)
    if directory.is_symlink() or not directory.is_dir(): raise ValueError('directory')
    stamp=datetime.fromtimestamp(timestamp(data['observed_utc']),timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path=directory/(data['source']+'-'+stamp+'.json')
    body=json.dumps(data,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()
    if len(body)>MAX_BYTES: raise ValueError('size')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return path


def view(data,now):
    validate(data,now)
    at=timestamp(data['observed_utc'])
    row={'scope':data['source'],'quality':0,'risk':0,'reason':'not_collected',
        'critical_high':None,'medium_low':None,'checked':None,'expected':None,
        'unavailable':None,'possible_truncation':None,'last_success_utc':None,
        'observed_utc':data['observed_utc'],'age_seconds':max(0,round(now-at)),
        'coverage_scope':'two_selected_public_repositories' if data['source']=='dependabot' else 'defender_status_and_retained_detections_only',
        'model_status':'not_used','detections_24h':None,'latest_detection_utc':None,
        'service_enabled':None,'antivirus_enabled':None,'realtime_enabled':None,
        'definitions_updated_utc':None,'last_scan_utc':None,'history_quality':None,
        'latest_job_attempt':'not_observable_after_saved_summary'}
    if data['source']=='dependabot':
        row.update(quality={'complete':1,'partial':2,'unavailable':5,'failed':4,'not_collected':0}[data['quality']],
            reason=data['reason'],checked=data['checked'],expected=2,unavailable=data['unavailable'],
            possible_truncation=int(data['page_limit_reached']))
        if data['checked']:
            row.update(critical_high=data['critical']+data['high'],medium_low=data['medium']+data['low'])
            row['risk']=3 if row['critical_high'] else 2 if row['medium_low'] else 1 if data['quality']=='complete' else 0
        if data['quality']=='complete': row['last_success_utc']=data['observed_utc']
    else:
        for key in ('service_enabled','antivirus_enabled','realtime_enabled','definitions_updated_utc','detections_24h','latest_detection_utc','history_quality'):
            row[key]=data[key]
        scans=[s for s in (data['quick_scan_utc'],data['full_scan_utc']) if s is not None]
        row['last_scan_utc']=max(scans,key=timestamp) if scans else None
        row['quality']=1 if data['status_quality']=='complete' and data['history_quality']=='available_retention_unknown' else 2
        row['reason']='retained_history_only_not_a_clean_scan_result'
        if data['status_quality']=='failed' and data['history_quality']=='failed': row['quality']=4
        if data['status_quality']=='unavailable' and data['history_quality']=='unavailable': row['quality']=5
        if data['detections_24h'] is not None and data['detections_24h']>0:
            row.update(risk=3,reason='detections_observed_remediation_unreviewed')
        elif data['status_quality']=='complete':
            if not all(data[k] for k in ('service_enabled','antivirus_enabled','realtime_enabled')):
                row.update(risk=2,reason='defender_protection_disabled_other_av_unknown')
            elif data['definitions_updated_utc'] is None or row['last_scan_utc'] is None:
                row.update(risk=0,reason='protection_dates_unconfirmed')
            elif at-timestamp(data['definitions_updated_utc'])>48*3600 or at-timestamp(row['last_scan_utc'])>7*86400:
                row.update(risk=2,reason='definition_or_scan_age_attention')
            elif data['history_quality']!='available_retention_unknown':
                row.update(risk=0,reason='history_collection_unconfirmed')
            else:
                row.update(risk=1,reason='protection_fields_ok_history_coverage_unknown')
        if row['quality']==1: row['last_success_utc']=data['observed_utc']
    if now-at>26*3600:
        row.update(quality=3,risk=0,reason='stale_summary',critical_high=None,medium_low=None,detections_24h=None,
            service_enabled=None,antivirus_enabled=None,realtime_enabled=None)
    return row


def read_views(directory,now):
    """No fallback from invalid newest input to an older green report."""
    directory=Path(directory)
    if directory.is_symlink() or not directory.is_dir(): raise ValueError('directory')
    names=list(directory.iterdir())
    if len(names)>64: raise ValueError('file_bound')
    result={}
    for source in SOURCES:
        files=sorted(p for p in names if re.fullmatch(re.escape(source)+r'-\d{8}T\d{6}Z\.json',p.name))
        if not files: continue
        try:
            latest=load(files[-1],now)
            if latest['source']!=source: raise ValueError('source')
            expected=source+'-'+datetime.fromtimestamp(timestamp(latest['observed_utc']),timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json'
            if files[-1].name!=expected: raise ValueError('filename_time')
            result[source]=view(latest,now)
            for path in reversed(files):
                try:
                    previous=load(path,now)
                    if previous['source']!=source: continue
                    expected=source+'-'+datetime.fromtimestamp(timestamp(previous['observed_utc']),timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json'
                    if path.name!=expected: continue
                    candidate=view(previous,now)
                    if candidate['last_success_utc'] is not None:
                        result[source]['last_success_utc']=candidate['last_success_utc']; break
                except (ValueError,OSError,TypeError,OverflowError): pass
        except (ValueError,OSError,TypeError,OverflowError):
            result[source]={'scope':source,'quality':4,'risk':0,'reason':'invalid_newest_summary',
                'model_status':'not_used','critical_high':None,'medium_low':None,'detections_24h':None,
                'observed_utc':None,'last_success_utc':None}
    return result
