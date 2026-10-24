from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import security_summary as codec
import dependabot_metrics as collector

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)

class PrivateLibrariesTests(unittest.TestCase):
    def collect(self, callback):
        return collector.collect("synthetic", NOW, callback)

    def test_fixed_public_scope(self):
        seen=[]
        def get(repo, token):
            seen.append(repo)
            return 200, []
        row=self.collect(get)
        self.assertEqual(seen, ["home-ai-engineering-lab", "local-ai-sidekick"])
        self.assertEqual((row["checked"], row["expected"]), (2,2))
        self.assertEqual(row["quality"], "complete")

    def test_missing_credential_skips_all_requests(self):
        row=collector.collect("", NOW, lambda *a: self.fail("request"))
        self.assertEqual(row["reason"], "no_token")
        self.assertIsNone(row["high"])

    def test_normal_zero_has_two_successful_targets(self):
        self.assertEqual(codec.view(self.collect(lambda *a:(200,[])), NOW.timestamp())["risk"],1)

    def test_permission_or_feature_unavailable_not_zero(self):
        for status in (403,404):
            row=self.collect(lambda *a:(status,None))
            self.assertEqual(row["unavailable"],2)
            self.assertIsNone(row["high"])
            self.assertEqual(codec.view(row,NOW.timestamp())["quality"],5)

    def test_authentication_error_stops_without_retry(self):
        seen=[]
        def get(*a):
            seen.append(1)
            return 401,None
        row=self.collect(get)
        self.assertEqual(len(seen),1)
        self.assertEqual(row["reason"],"authentication_failed")

    def test_redirect_or_server_error_not_retried(self):
        for status in (302,429,500):
            seen=[]
            def get(*a):
                seen.append(1)
                return status,None
            self.assertEqual(self.collect(get)["quality"],"failed")
            self.assertEqual(len(seen),1)

    def test_payload_names_and_details_not_exported(self):
        row=self.collect(lambda *a:(200,[{"security_vulnerability":{"severity":"high"},"Resources":"PRIVATE","body":"PRIVATE"}]))
        self.assertEqual(row["high"],2)
        self.assertNotIn("PRIVATE",json.dumps(row))

    def test_page_cap_is_partial(self):
        row=self.collect(lambda *a:(200,[{"security_vulnerability":{"severity":"high"}}]*100))
        self.assertEqual(row["quality"],"partial")
        self.assertTrue(row["page_limit_reached"])

    def test_unknown_severity_not_green(self):
        row=self.collect(lambda *a:(200,[{"security_vulnerability":{"severity":"unclassified"}}]))
        self.assertEqual(row["quality"],"partial")
        self.assertEqual(codec.view(row,NOW.timestamp())["risk"],0)

    def test_partial_positive_is_visible(self):
        def get(repo, token):
            return (200,[{"security_vulnerability":{"severity":"critical"}}]) if repo==collector.TARGETS[0] else (403,None)
        row=self.collect(get)
        self.assertEqual(row["quality"],"partial")
        self.assertEqual(codec.view(row,NOW.timestamp())["risk"],3)

    def test_invalid_response_has_no_invented_counts(self):
        row=self.collect(lambda *a:(200,["PRIVATE"]))
        self.assertEqual(row["quality"],"failed")
        self.assertIsNone(row["high"])

    def test_other_github_credential_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(collector.os,"environ",{"GITHUB_TOKEN":"PRIVATE"}), patch("builtins.print"):
                self.assertEqual(collector.main(["--output-dir",folder]),2)
            data=json.loads(next(Path(folder).iterdir()).read_text())
            self.assertEqual(data["reason"],"no_token")

    def test_exclusive_save_prevents_overwrite(self):
        row=self.collect(lambda *a:(200,[]))
        with tempfile.TemporaryDirectory() as folder:
            path=codec.save_new(folder,row,NOW.timestamp())
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):codec.save_new(folder,row,NOW.timestamp())
            self.assertEqual(path.read_bytes(),original)

    def test_stale_current_counts_hidden(self):
        row=codec.view(self.collect(lambda *a:(200,[])),NOW.timestamp()+27*3600)
        self.assertEqual(row["quality"],3)
        self.assertIsNone(row["critical_high"])

    def test_extra_fields_duplicate_keys_and_depth_rejected(self):
        row=self.collect(lambda *a:(200,[]))
        with self.assertRaises(ValueError):codec.validate(dict(row,Resources="PRIVATE"),NOW.timestamp())
        with self.assertRaises(ValueError):codec.parse(b'{"schema":1,"schema":1}',NOW.timestamp())
        with self.assertRaises(ValueError):codec.parse(("["*3000+"]"*3000).encode(),NOW.timestamp())

    def test_corrupt_newest_not_replaced_by_older_green(self):
        with tempfile.TemporaryDirectory() as folder:
            codec.save_new(folder,self.collect(lambda *a:(200,[])),NOW.timestamp())
            (Path(folder)/"dependabot-20261024T120001Z.json").write_text("{}")
            self.assertEqual(codec.read_views(folder,NOW.timestamp())["dependabot"]["quality"],4)

if __name__=="__main__":
    unittest.main()
