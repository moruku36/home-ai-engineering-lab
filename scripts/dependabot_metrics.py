#!/usr/bin/env python3
"""Explicit, single-run GET collector. Fixed public targets, no job or scheduler."""
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import sys

TARGETS=('home-ai-engineering-lab','local-ai-sidekick')
MAX_BODY=1024*1024


def request(repo,token):
    if repo not in TARGETS: raise ValueError('target')
    connection=http.client.HTTPSConnection('api.github.com',timeout=10)
    try:
        connection.request('GET','/repos/moruku36/'+repo+'/dependabot/alerts?state=open&per_page=100',
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                'X-GitHub-Api-Version':'2022-11-28','User-Agent':'home-lab-security-aggregate/1'})
        response=connection.getresponse()
        if response.status!=200: return response.status,None
        raw=response.read(MAX_BODY+1)
        if len(raw)>MAX_BODY: raise ValueError('body_bound')
        return 200,json.loads(raw)
    finally:
        connection.close()


def collect(token,now=None,transport=request):
    now=datetime.now(timezone.utc) if now is None else now
    row=dict(schema=1,source='dependabot',observed_utc=now.astimezone(timezone.utc).isoformat(),
        model_status='not_used',quality='not_collected',reason='no_token',checked=0,expected=2,
        unavailable=0,critical=None,high=None,medium=None,low=None,unknown=None,page_limit_reached=False)
    if not token: return row
    totals={key:0 for key in ('critical','high','medium','low','unknown')}
    failed=False
    for repo in TARGETS:
        try:
            status,items=transport(repo,token)
            if status in (403,404):
                row['unavailable']+=1; continue
            if status==401:
                row.update(quality='failed',reason='authentication_failed'); failed=True; break
            if status!=200: raise ValueError('http')
            if not isinstance(items,list) or len(items)>100: raise ValueError('schema')
            subtotal={key:0 for key in totals}
            for item in items:
                if not isinstance(item,dict): raise ValueError('schema')
                vulnerability=item.get('security_vulnerability') or {}
                advisory=item.get('security_advisory') or {}
                if not isinstance(vulnerability,dict) or not isinstance(advisory,dict): raise ValueError('schema')
                severity=vulnerability.get('severity') or advisory.get('severity') or 'unknown'
                severity=severity.lower() if isinstance(severity,str) else 'unknown'
                subtotal[severity if severity in totals else 'unknown']+=1
            for key in totals: totals[key]+=subtotal[key]
            row['checked']+=1
            row['page_limit_reached'] |= len(items)==100
        except Exception:
            row.update(quality='failed',reason='api_failed'); failed=True; break
    if row['checked']:
        row.update(totals)
        if not failed:
            if row['checked']==2 and not row['page_limit_reached'] and not row['unknown']:
                row.update(quality='complete',reason='two_targets_complete')
            else:
                row.update(quality='partial',reason='page_limit' if row['page_limit_reached'] else 'mixed_coverage')
    elif not failed:
        row.update(quality='unavailable',reason='access_or_feature_unavailable')
    return row


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    args=p.parse_args(argv)
    # No generic GITHUB_TOKEN fallback. No command-line token or remote URL.
    token=os.environ.get('DEPENDABOT_TOKEN','').strip()
    if token and (not token.startswith('github_pat_') or len(token)<30 or any(c.isspace() for c in token)):
        print('{"status":"stopped","reason":"dedicated_credential_format"}')
        return 2
    try:
        import security_summary
        row=collect(token)
        security_summary.save_new(args.output_dir,row,datetime.now(timezone.utc).timestamp())
        print(json.dumps({'status':'aggregate_saved','source':'dependabot','quality':row['quality'],
            'reason':row['reason'],'checked':row['checked'],'expected':2,'model_status':'not_used'}))
        return 0 if row['quality']=='complete' else 2
    except Exception:
        print('{"status":"stopped","reason":"collection_or_exclusive_save_failed"}')
        return 2


if __name__=='__main__': sys.exit(main())
