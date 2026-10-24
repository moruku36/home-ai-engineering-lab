import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT))
import github_security_history as display
import security_summary as codec
NOW=1792846200

def aggregate(at=NOW,**updates):
    row=dict(schema=1,source='dependabot',observed_utc=display.base.utc(at),model_status='not_used',
             quality='complete',reason='two_targets_complete',checked=2,expected=2,unavailable=0,
             critical=0,high=0,medium=0,low=0,unknown=0,page_limit_reached=False)
    row.update(updates)
    return row

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.snap=self.root/'snap';self.snap.mkdir()
        self.inputs=self.root/'input';self.inputs.mkdir()

    def save(self, row):
        return codec.save_new(self.inputs,row,NOW)

    def view(self):
        return display.history(self.snap,self.inputs,NOW)['security'][0]

    def test_complete_zero_and_sidekick_unknown(self):
        self.save(aggregate());result=display.history(self.snap,self.inputs,NOW)
        self.assertEqual(result['security'][0]['risk'],1)
        self.assertEqual(result['security'][0]['checked'],2)
        side=result['security'][1]
        self.assertEqual((side['quality'],side['risk'],side['critical_high']),(0,0,None))

    def test_partial_zero_never_green_or_prior_success(self):
        self.save(aggregate(NOW-60))
        self.save(aggregate(quality='partial',reason='mixed_coverage',checked=1,unavailable=1))
        row=self.view()
        self.assertEqual((row['quality'],row['risk'],row['checked']),(2,0,1))
        self.assertEqual(row['last_success_utc'],display.base.utc(NOW-60))

    def test_stale_hides_counts(self):
        self.save(aggregate(NOW-26*3600-1));row=self.view()
        self.assertEqual((row['quality'],row['risk'],row['critical_high']),(3,0,None))
        self.assertIsNotNone(row['observed_utc'])

    def test_uncollected_and_unavailable_not_zero(self):
        self.assertEqual((self.view()['quality'],self.view()['critical_high']),(0,None))
        self.save(aggregate(quality='unavailable',reason='access_or_feature_unavailable',checked=0,
                            unavailable=2,critical=None,high=None,medium=None,low=None,unknown=None))
        self.assertEqual((self.view()['quality'],self.view()['critical_high']),(5,None))

    def test_invalid_latest_never_falls_back_green(self):
        self.save(aggregate(NOW-60));path=self.save(aggregate())
        path.write_text('{"secret":"synthetic_sensitive"}',encoding='utf-8')
        row=self.view();self.assertEqual((row['quality'],row['risk']),(4,0))
        self.assertNotIn('synthetic_sensitive',json.dumps(row))

    def test_input_unavailable(self):
        self.inputs.rmdir()
        self.assertEqual(self.view()['reason'],'security_input_unavailable')

    def test_existing_history_and_codec_kept(self):
        sentinel={'schema':1,'meta':[{'quality':2}],'days':[{'day':'2026-10-18'}], 'security':[]}
        with patch.object(display.base,'history',return_value=copy.deepcopy(sentinel)):
            result=display.history(self.snap,self.inputs,NOW)
        self.assertEqual(result['meta'],sentinel['meta']);self.assertEqual(result['days'],sentinel['days'])
        import hashlib
        self.assertEqual(hashlib.sha256((ROOT/'scripts/security_summary.py').read_bytes()).hexdigest(),
                         'aabea7b97a5766e869fa712d3164d7b1f9280091d9988b19cda97fa84cd61c87')

    def test_overlay_has_no_credential_or_network_changes(self):
        d=json.loads((ROOT/'stacks/observability/proposals/compose.security-display.json.example').read_text(encoding='utf-8'))
        self.assertEqual(set(d),{'services'});self.assertEqual(set(d['services']),{'github-history'})
        svc=d['services']['github-history'];self.assertEqual(set(svc),{'command','volumes'})
        for mount in svc['volumes']:
            self.assertTrue(mount['read_only']);self.assertFalse(mount['bind']['create_host_path'])
            self.assertNotIn('token',mount['source'])
        self.assertEqual({m['target'] for m in svc['volumes']},
                         {'/security-input','/app/github_security_history.py','/app/security_summary.py'})

    def test_dashboard_only_security_panel_changes(self):
        import hashlib
        new=json.loads((ROOT/'stacks/observability/proposals/home-lab-unified.json').read_text(encoding='utf-8'))
        self.assertEqual(new['uid'],'home-lab-unified')
        digest=hashlib.sha256(json.dumps([p for p in new['panels'] if p['id']!=16],sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest,'79774516e4cf24fcfa4479602965d9139e2e9610660eaa31cd5f1e9b8f70e913')
        self.assertEqual(next(p for p in new['panels'] if p['id']==16)['targets'][0]['url'],'http://github-history:8081/history')

if __name__=='__main__':unittest.main()
