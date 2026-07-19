from __future__ import annotations

import json
import unittest

from advisory_writer import write_advisory_answer


class FakeFpt:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.payload = None
        self.calls = 0

    def advise(self, payload):
        self.calls += 1
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
        return "- Kiểm tra giải pháp doanh nghiệp dự định thuê."


class AdvisoryWriterTest(unittest.TestCase):
    def setUp(self):
        self.selection = {
            "advisory_scope": "question",
            "coverage_status": "covered",
            "policy_ids": ["technology"],
            "topic_ids": ["sme_digital_solution_rent_purchase"],
        }
        self.company = {
            "email": "secret@example.test",
            "company_name": "Tên doanh nghiệp bí mật",
            "created_at": "2026-07-01",
            "sector": "thuong_mai_dich_vu",
            "primary_business_activity_group": "services",
            "business_description": "Cung cấp phần mềm quản trị bán hàng.",
        }
        self.requirement = "Giải pháp phải được công bố trên cổng thông tin hợp lệ."
        self.eligibility = {
            "eligibility_results": [{
                "policy_id": "technology",
                "policy_name": "Hỗ trợ thuê hoặc mua giải pháp chuyển đổi số",
                "status": "eligible",
                "reasons": ["Đạt điều kiện is_sme == True."],
                "application_requirements": [self.requirement],
                "required_documents": ["Hợp đồng thuê giải pháp"],
                "benefit_calculator": {"type": "Hỗ trợ chi phí thuê hoặc mua"},
                "sources": [{
                    "document_number": "06/2022/TT-BKHĐT",
                    "article": "7",
                    "clause": "1",
                }],
            }],
            "derived_facts": {"enterprise_size": "small", "is_sme": True},
        }
        self.deterministic = "Kết luận: Có. Theo hồ sơ hiện tại, doanh nghiệp phù hợp."

    def write(self, fpt, *, selection=None):
        return write_advisory_answer(
            "Tư vấn hỗ trợ chuyển đổi số",
            self.company,
            selection or self.selection,
            self.eligibility,
            self.deterministic,
            fpt=fpt,
        )

    def test_suggestion_is_appended_without_exposing_pii_or_internal_reason(self):
        fpt = FakeFpt("- Kiểm tra giải pháp doanh nghiệp dự định mua.")

        written = self.write(fpt)

        self.assertEqual(written.writer, "fpt_llm")
        self.assertTrue(written.answer.startswith(self.deterministic))
        self.assertIn("Gợi ý dành cho doanh nghiệp", written.answer)
        serialized = json.dumps(fpt.payload, ensure_ascii=False)
        self.assertNotIn("secret@example.test", serialized)
        self.assertNotIn("Tên doanh nghiệp bí mật", serialized)
        self.assertNotIn("Đạt điều kiện is_sme", serialized)
        self.assertIn("Tư vấn hỗ trợ chuyển đổi số", serialized)
        self.assertIn("thương mại và dịch vụ", serialized)
        self.assertIn(self.requirement, serialized)
        self.assertIn("06/2022/TT-BKHĐT", serialized)

    def test_failure_retries_once_then_keeps_deterministic_answer(self):
        fpt = FakeFpt(error=TimeoutError("late"))

        written = self.write(fpt)

        self.assertEqual(fpt.calls, 2)
        self.assertEqual(written.answer, self.deterministic)
        self.assertEqual(written.writer, "deterministic_fallback")
        self.assertEqual(written.fallback_reason, "TimeoutError")

    def test_transient_failure_succeeds_on_second_attempt(self):
        fpt = RetryFpt()

        written = self.write(fpt)

        self.assertEqual(fpt.calls, 2)
        self.assertEqual(written.writer, "fpt_llm")
        self.assertIn("Kiểm tra giải pháp", written.answer)

    def test_disabled_or_empty_llm_keeps_deterministic_answer(self):
        written = self.write(FakeFpt(response=None))

        self.assertEqual(written.answer, self.deterministic)
        self.assertEqual(written.writer, "deterministic_fallback")
        self.assertEqual(written.fallback_reason, "llm_disabled_or_empty")

    def test_not_covered_never_calls_llm(self):
        fpt = FakeFpt("should not be used")
        selection = dict(self.selection, coverage_status="not_covered")

        written = self.write(fpt, selection=selection)

        self.assertEqual(fpt.calls, 0)
        self.assertEqual(written.answer, self.deterministic)
        self.assertEqual(written.writer, "deterministic_not_covered")


if __name__ == "__main__":
    unittest.main()
