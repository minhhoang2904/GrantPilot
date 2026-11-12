from __future__ import annotations

import unittest
from unittest.mock import patch

import main


class EvaluateContractCompatibilityTest(unittest.TestCase):
    def test_accepts_canonical_facts(self):
        payload = main.EvaluateIn(facts={"sector": "services"})
        self.assertEqual(payload.direct_facts, {"sector": "services"})

    def test_accepts_legacy_profile(self):
        payload = main.EvaluateIn(profile={"sector": "services"})
        self.assertEqual(payload.direct_facts, {"sector": "services"})

    def test_response_exposes_transitional_results_alias(self):
        canonical = {"eligibility_results": [{"policy_id": "p1"}]}
        with patch.object(main, "_evaluate", return_value=canonical):
            response = main.evaluate_eligibility(main.EvaluateIn(facts={}))

        self.assertEqual(response["results"], response["eligibility_results"])


if __name__ == "__main__":
    unittest.main()
