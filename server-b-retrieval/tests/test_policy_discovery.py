from __future__ import annotations

import unittest

from policy_discovery import (
    DIGITAL_TRANSFORMATION_POLICY_ID,
    GOLDEN_POLICY_IDS,
    INFORMATION_POLICY_ID,
    IN_PERSON_TRAINING_POLICY_ID,
    ONLINE_TRAINING_POLICY_ID,
    discover_policies,
)


class PolicyDiscoveryTest(unittest.TestCase):
    def test_tax_question_is_not_covered(self):
        result = discover_policies("Tôi có đủ điều kiện nhận ưu đãi thuế TNDN không?")

        self.assertEqual(result.coverage_status, "not_covered")
        self.assertEqual(result.policy_ids, ())
        self.assertIn("thuế thu nhập doanh nghiệp", result.unsupported_topics[0])

    def test_rent_digital_solution_is_not_mistaken_for_tax(self):
        result = discover_policies("Có hỗ trợ thuê hoặc mua giải pháp chuyển đổi số không?")

        self.assertEqual(result.coverage_status, "supported")
        self.assertEqual(result.policy_ids, (DIGITAL_TRANSFORMATION_POLICY_ID,))
        self.assertEqual(result.unsupported_topics, ())

    def test_natif_is_not_covered(self):
        result = discover_policies("Doanh nghiệp có được vay vốn NATIF không?")

        self.assertEqual(result.coverage_status, "not_covered")
        self.assertIn("NATIF", result.unsupported_topics[0])

    def test_multi_intent_selects_digital_and_both_training_policies(self):
        result = discover_policies("Tư vấn hỗ trợ chuyển đổi số và đào tạo cho công ty tôi")

        self.assertEqual(result.coverage_status, "supported")
        self.assertEqual(
            result.policy_ids,
            (
                ONLINE_TRAINING_POLICY_ID,
                IN_PERSON_TRAINING_POLICY_ID,
                DIGITAL_TRANSFORMATION_POLICY_ID,
            ),
        )
        self.assertNotIn(INFORMATION_POLICY_ID, result.policy_ids)

    def test_generic_profile_scan_selects_all_golden_policies(self):
        result = discover_policies("Công ty tôi có được hỗ trợ không?")

        self.assertEqual(result.coverage_status, "profile_scan")
        self.assertEqual(result.policy_ids, GOLDEN_POLICY_IDS)

    def test_mixed_supported_and_unsupported_question_is_partial(self):
        result = discover_policies("Tôi muốn biết về ưu đãi thuế TNDN và khóa đào tạo")

        self.assertEqual(result.coverage_status, "partial_coverage")
        self.assertEqual(
            result.policy_ids,
            (ONLINE_TRAINING_POLICY_ID, IN_PERSON_TRAINING_POLICY_ID),
        )
        self.assertTrue(result.unsupported_topics)

    def test_known_retrieval_candidate_is_safe_fallback(self):
        result = discover_policies("Chính sách này áp dụng thế nào?", [INFORMATION_POLICY_ID, "unknown"])

        self.assertEqual(result.coverage_status, "supported")
        self.assertEqual(result.policy_ids, (INFORMATION_POLICY_ID,))


if __name__ == "__main__":
    unittest.main()
