from __future__ import annotations

import unittest

import config
from policy_discovery import load_manifest, select_policies


class PolicyDiscoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policies = load_manifest(config.POLICY_DISCOVERY_PATH)

    def test_supported_questions_select_only_relevant_policy(self):
        scenarios = {
            "Doanh nghiệp tôi có được hỗ trợ chuyển đổi số không?": "sme_digital_solution_rent_purchase",
            "DNNVV có được đào tạo trực tuyến không?": "sme_online_training",
            "DNNVV có được đào tạo online không?": "sme_online_training",
            "Doanh nghiệp sản xuất được hỗ trợ đào tạo trực tiếp thế nào?": "sme_direct_training_manufacturing_processing",
            "Tôi cần hỗ trợ thông tin cho doanh nghiệp nhỏ và vừa": "sme_information_support",
        }
        for question, topic_id in scenarios.items():
            with self.subTest(question=question):
                result = select_policies(question, self.policies)
                self.assertEqual(result["coverage_status"], "covered")
                self.assertEqual(result["topic_ids"], [topic_id])
                self.assertEqual(len(result["policy_ids"]), 1)

    def test_out_of_scope_questions_are_not_covered(self):
        for question in (
            "Tôi có được ưu đãi thuế TNDN không?",
            "Có thể xin quỹ NATIF không?",
            "Doanh nghiệp tôi có được hỗ trợ không?",
        ):
            with self.subTest(question=question):
                result = select_policies(question, self.policies)
                self.assertEqual(result["coverage_status"], "not_covered")
                self.assertEqual(result["policy_ids"], [])

    def test_profile_scan_selects_exactly_four_golden_policies(self):
        result = select_policies("", self.policies, scope="profile_scan")
        self.assertEqual(result["coverage_status"], "covered")
        self.assertEqual(len(result["policy_ids"]), 4)
        self.assertEqual(len(result["topic_ids"]), 4)


if __name__ == "__main__":
    unittest.main()
