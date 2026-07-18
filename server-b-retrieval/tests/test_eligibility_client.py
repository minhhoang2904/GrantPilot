from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import eligibility_client


class EligibilityClientTest(unittest.TestCase):
    def test_empty_candidate_list_requests_full_server_c_decision_set(self):
        response = Mock()
        response.json.return_value = {
            "eligibility_results": [{"policy_id": "golden-1"}],
            "diagnostics": {"evaluated_policy_count": 4},
        }

        with patch.object(eligibility_client.httpx, "post", return_value=response) as post:
            result = eligibility_client.evaluate_company({"is_sme": True}, [])

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(result["diagnostics"]["evaluated_policy_count"], 4)
        self.assertEqual(post.call_args.kwargs["json"]["candidate_policy_ids"], [])


if __name__ == "__main__":
    unittest.main()
