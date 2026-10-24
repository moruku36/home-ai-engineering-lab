import contextlib
from datetime import date, datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import github_history as h

NOW = datetime(2026, 10, 24, 0, tzinfo=timezone.utc).timestamp()
def snapshot(day="2026-10-24", count=2):
    d = date.fromisoformat(day)
    end = datetime.combine(d, datetime.min.time(), h.JST)
    from datetime import timedelta
    return {"schema":1, "generated_at":end.isoformat(),
      "activity":{"collected_at":end.isoformat(),
      "window":{"start":(end-timedelta(days=1)).isoformat(),"end":end.isoformat()},
      "metrics":{n:{"status":"ok","keys":["private/repo#"+str(i) for i in range(count)]} for n in h.METRICS}}}
class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def put(self, day, value): (self.root/(day+".json")).write_text(json.dumps(value),encoding="utf-8")
    def test_activity_day_not_collection_day(self):
        self.put("2026-10-24",snapshot())
        row=h.history(self.root,NOW)["days"][0]
        self.assertEqual(row["day"],"2026-10-23"); self.assertEqual(row["prs_merged"],2)
    def test_latest_excluded(self):
        self.put("latest",snapshot()); self.assertEqual(h.history(self.root,NOW)["days"],[])
    def test_same_day_replacement_no_accumulation(self):
        self.put("2026-10-24",snapshot(count=1)); self.put("2026-10-24",snapshot(count=3))
        self.assertEqual(h.history(self.root,NOW)["days"][0]["prs_opened"],3)
    def test_keys_dedup_and_privacy(self):
        s=snapshot(); s["activity"]["metrics"]["prs_opened"]["keys"]=["private/repo#1"]*3
        self.put("2026-10-24",s); result=h.history(self.root,NOW)
        self.assertEqual(result["days"][0]["prs_opened"],1); self.assertNotIn("private/repo",json.dumps(result))
    def test_gap_null_only_inside_range(self):
        self.put("2026-10-22",snapshot("2026-10-22")); self.put("2026-10-24",snapshot())
        result=h.history(self.root,NOW)
        self.assertEqual(len(result["days"]),3); self.assertIsNone(result["days"][1]["prs_merged"])
        self.assertEqual(result["meta"][0]["missing_days"],1)
    def test_old_history_keeps_values_stale_badge(self):
        self.put("2026-10-20",snapshot("2026-10-20"))
        result=h.history(self.root,NOW)
        self.assertEqual(result["days"][0]["prs_merged"],2); self.assertEqual(result["meta"][0]["quality"],3)
    def test_partial_zero_distinct_failed(self):
        s=snapshot(count=0); m=s["activity"]["metrics"]
        m["prs_opened"]["status"]="incomplete"; m["prs_merged"]["status"]="failed"
        r=h.parse_day(s,date(2026,10,24),NOW)
        self.assertEqual((r["prs_opened"],r["prs_opened_quality"]),(0,2))
        self.assertIsNone(r["prs_merged"]); self.assertEqual(r["prs_merged_quality"],4)
    def test_missing_activity_unknown(self):
        s=snapshot(); del s["activity"]
        self.assertIsNone(h.parse_day(s,date(2026,10,24),NOW)["prs_opened"])
    def test_window_mismatch_rejected(self):
        s=snapshot(); s["activity"]["window"]["start"]=s["generated_at"]
        with self.assertRaises(ValueError): h.parse_day(s,date(2026,10,24),NOW)
    def test_invalid_latest_does_not_reuse_security(self):
        self.put("2026-10-23",snapshot("2026-10-23")); self.put("2026-10-24",{})
        result=h.history(self.root,NOW)
        self.assertEqual(result["meta"][0]["quality"],4); self.assertEqual(result["security"][0]["quality"],0)
    def test_calendar_bound(self):
        self.put("2025-01-01",snapshot("2025-01-01")); self.put("2026-10-24",snapshot())
        self.assertEqual(h.history(self.root,NOW)["days"],[])
    def test_sidekick_never_inferred(self):
        self.assertEqual(h.security_view(snapshot(),NOW)[1]["quality"],0)
    def security(self, amount=0, unknown=False, complete=True):
        s=snapshot()
        severity={"high":amount}
        if unknown: severity["unknown"]=1
        s["dependabot"]={"private/repo":{"available":True,"open":sum(severity.values()),"by_severity":severity}}
        s["coverage_detail"]={"passes":{"Dependabot alerts":{"total":1,"done":1,"failed":0,"stopped":None if complete else "budget"}}}
        return h.security_view(s,NOW)[0]
    def test_security_complete_zero_green(self): self.assertEqual(self.security()["risk"],1)
    def test_security_partial_zero_unknown(self): self.assertEqual(self.security(complete=False)["risk"],0)
    def test_security_high_partial_red(self): self.assertEqual(self.security(2,complete=False)["risk"],3)
    def test_unknown_severity_not_green(self): self.assertEqual(self.security(unknown=True)["risk"],0)

class DashboardTests(unittest.TestCase):
    def test_new_uid_and_unique_panels(self):
        root=Path(__file__).resolve().parents[1]
        d=json.loads((root/'stacks/observability/proposals/home-lab-unified.json').read_text(encoding='utf-8'))
        self.assertEqual(d['uid'],'home-lab-unified')
        self.assertEqual(len(d['panels']),16)
        self.assertEqual(len({p['id'] for p in d['panels']}),16)
        target=next(p for p in d['panels'] if p['targets'] and p['targets'][0].get('root_selector')=='$.days')['targets'][0]
        self.assertIn({'selector':'time','type':'timestamp','text':'time'},target['columns'])
        self.assertNotIn('rate(',json.dumps(target))
    def test_service_template_not_autoprovisioned(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'stacks/observability/proposals/compose.history.yaml.example').read_text(encoding='utf-8')
        self.assertNotIn('ports:',source)
        self.assertNotIn('/var/run/docker.sock',source)
        self.assertIn('read_only: true',source)
        self.assertIn('owner must verify snapshots subdirectory only',source)
    def test_only_two_services_share_isolated_network(self):
        root=Path(__file__).resolve().parents[1]
        s=(root/'stacks/observability/proposals/compose.history.yaml.example').read_text(encoding="utf-8")
        self.assertIn('networks: [default, monitor, history-only]',s)
        self.assertIn('networks: [history-only]',s)
        self.assertIn('internal: true',s)
        self.assertIn('attachable: false',s)
        self.assertIn('enable_ipv6: false',s)
        self.assertIn('target: /snapshots',s)
        self.assertIn('create_host_path: false',s)
        self.assertNotIn('target: /state',s)
        self.assertNotIn('pending_updates.py',s)
    def test_history_no_update_dependency_or_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(set(h.history(directory,NOW)),{'schema','meta','days','security'})
        root=Path(__file__).resolve().parents[1]
        source=(root/'scripts/github_history.py').read_text(encoding='utf-8')
        self.assertNotIn('pending_updates',source)
        self.assertNotIn('--updates-dir',source)
    def test_pinned_query_contract(self):
        root=Path(__file__).resolve().parents[1]
        p=root/'stacks/observability/proposals'
        lock=json.loads((p/'infinity-version.json').read_text(encoding='utf-8'))
        self.assertEqual(lock['version'],'4.1.3')
        self.assertEqual(lock['grafana_target'],'12.4.3')
        dash=json.loads((p/'home-lab-unified.json').read_text(encoding='utf-8'))
        for panel in dash['panels']:
            for target in panel['targets']:
                if target.get('type')!='json': continue
                self.assertEqual(target['parser'],'backend')
                self.assertEqual(target['url'],'http://github-history:8081/history')
                self.assertEqual(target['url_options']['method'],'GET')
                self.assertIn(target['root_selector'],lock['query_review']['roots'])
                self.assertIn(target['format'],lock['query_review']['formats'])
                self.assertEqual(target['datasource']['uid'],'homelab-history')
                for column in target['columns']:
                    self.assertIn(column['type'],lock['query_review']['column_types'])
        ds=(p/'datasource.history.yaml.example').read_text(encoding='utf-8')
        self.assertIn('auth_method: none',ds)
        self.assertIn('proxy_type: none',ds)
        self.assertIn('editable: false',ds)
        self.assertIn('isDefault: false',ds)
        self.assertNotIn('https://',ds)
if __name__=="__main__": unittest.main()

