import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compare_saved_model_outputs as comparison
import security_log_pipeline as pipeline


class ComparisonTest(unittest.TestCase):
    def test_valid_invalid_refusal_missing_and_unknown_cases(self):
        cases = [{"id": str(i), "logs": ["synthetic log"]} for i in range(4)]
        entry = pipeline.parse_and_preprocess_logs(cases[0]["logs"])[0]
        event = {"event_id": "rule-synthetic-12345678", "source": "synthetic_test",
                 "timestamp": "2026-10-19T05:00:00Z", "event_type": "generic_anomaly",
                 "severity": "low", "summary": "Synthetic finding for validation",
                 "evidence_refs": [{"line_no": 1, "raw_hash": entry["raw_hash"], "log_excerpt": "synthetic"}],
                 "suspected_cause": "Synthetic cause", "recommended_actions": ["Review synthetic evidence"],
                 "needs_human_review": True}
        invalid = copy.deepcopy(event)
        invalid["evidence_refs"][0]["raw_hash"] = "deadbeef"
        run = {"model": "example", "responses": [
            {"case_id": "0", "status": "response", "events": [event]},
            {"case_id": "1", "status": "response", "events": [invalid]},
            {"case_id": "2", "status": "refusal"}]}
        result = comparison.compare(cases, [run])["models"][0]
        self.assertEqual(result["counts"], {"valid": 1, "invalid": 1, "refusal": 1, "missing": 1})
        event["needs_human_review"] = False
        self.assertEqual(comparison.compare(cases, [run])["models"][0]["counts"]["invalid"], 2)
        run["responses"].append({"case_id": "unknown", "status": "refusal"})
        with self.assertRaises(ValueError):
            comparison.compare(cases, [run])


if __name__ == "__main__":
    unittest.main()
