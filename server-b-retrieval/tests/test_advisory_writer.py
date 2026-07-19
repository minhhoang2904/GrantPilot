from __future__ import annotations

import json
import unittest

from advisory_writer import write_advisory_answer
from policy_discovery import DIGITAL_TRANSFORMATION_POLICY_ID, discover_policies


class FakeFpt:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.payload = None

    def advise(self, payload):
        self.payload = payload
        if self.error:
            raise self.error
        return self.response


class RetryFpt:
    def __init__(self):
        self.calls = 0

    def advise(self, payload):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("first call timed out")
        return "- Ưu tiên kiểm tra nhu cầu chuyển đổi số."


class AdvisoryWriterTest(unittest.TestCase):
    def setUp(self):
        self.scope = discover_policies("Tư vấn hỗ trợ chuyển đổi số")
        self.company = {
            "email": "secret@example.test",
            "company_name": "Tên doanh nghiệp bí mật",
            "sector": "thuong_mai_dich_vu",
            "primary_business_activity_group": "services",
            "business_description": "Cung cấp phần mềm quản trị bán hàng.",
        }
        self.requirement = "Giải pháp phải được công bố trên cổng thông tin hợp lệ."
        self.eligibility = {
            "eligibility_results": [
                {
                    "policy_id": DIGITAL_TRANSFORMATION_POLICY_ID,
                    "policy_name": "Hỗ trợ thuê hoặc mua giải pháp chuyển đổi số",
                    "status": "eligible",
                    "reasons": ["Đạt điều kiện is_sme == True."],
                    "application_requirements": [self.requirement],
                    "benefit_calculator": {"type": "Hỗ trợ chi phí thuê hoặc mua"},
                    "sources": [{"document_number": "06/2022/TT-BKHĐT", "article": "7"}],
                }
            ],
            "derived_facts": {"enterprise_size": "small", "is_sme": True},
        }

    def test_llm_suggestion_is_appended_after_deterministic_decision(self):
        fpt = FakeFpt("- Ưu tiên kiểm tra giải pháp doanh nghiệp định mua.")

        written = write_advisory_answer(
            "Tư vấn hỗ trợ chuyển đổi số",
            self.company,
            self.scope,
            self.eligibility,
            fpt=fpt,
        )

        self.assertEqual(written.writer, "fpt_llm")
        self.assertIsNone(written.fallback_reason)
        self.assertIn("Hồ sơ hiện tại đáp ứng", written.answer)
        self.assertIn("Gợi ý dành cho doanh nghiệp", written.answer)
        self.assertIn("Ưu tiên kiểm tra", written.answer)
        serialized = json.dumps(fpt.payload, ensure_ascii=False)
        self.assertNotIn("secret@example.test", serialized)
        self.assertNotIn("Tên doanh nghiệp bí mật", serialized)
        self.assertNotIn("Đạt điều kiện is_sme", serialized)
        self.assertIn("thương mại và dịch vụ", serialized)
        self.assertIn(self.requirement, serialized)

    def test_llm_failure_keeps_deterministic_fallback(self):
        fpt = FakeFpt(error=TimeoutError("late"))

        written = write_advisory_answer(
            "Tư vấn hỗ trợ chuyển đổi số",
            self.company,
            self.scope,
            self.eligibility,
            fpt=fpt,
        )

        self.assertEqual(written.writer, "deterministic_fallback")
        self.assertEqual(written.fallback_reason, "TimeoutError")
        self.assertIn("Hồ sơ hiện tại đáp ứng", written.answer)
        self.assertNotIn("Gợi ý dành cho doanh nghiệp", written.answer)

    def test_transient_llm_failure_is_retried_once(self):
        fpt = RetryFpt()

        written = write_advisory_answer(
            "Tư vấn hỗ trợ chuyển đổi số",
            self.company,
            self.scope,
            self.eligibility,
            fpt=fpt,
        )

        self.assertEqual(fpt.calls, 2)
        self.assertEqual(written.writer, "fpt_llm")
        self.assertIn("Ưu tiên kiểm tra", written.answer)

    def test_disabled_llm_keeps_deterministic_fallback(self):
        written = write_advisory_answer(
            "Tư vấn hỗ trợ chuyển đổi số",
            self.company,
            self.scope,
            self.eligibility,
            fpt=FakeFpt(response=None),
        )

        self.assertEqual(written.writer, "deterministic_fallback")
        self.assertEqual(written.fallback_reason, "llm_disabled_or_empty")


if __name__ == "__main__":
    unittest.main()
