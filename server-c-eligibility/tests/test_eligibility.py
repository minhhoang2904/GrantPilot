"""
Test lõi eligibility. Chạy: python -m tests.test_eligibility

Không dùng pytest để khỏi thêm phụ thuộc — hackathon, chạy thẳng bằng python là đủ.
Chỉ test phần sai ÂM THẦM (không crash, chỉ ra kết quả sai): logic 4 giá trị + engine 2 tầng.
"""

from datetime import date

from grantpilot import benefit, classifier, engine, logic, operators
from grantpilot.logic import EvalContext
from grantpilot.models.eligibility_result import EligibilityStatus
from grantpilot.models.rule import RuleResult, UnknownReason

PASS, FAIL, UNKNOWN, REVIEW = (
    RuleResult.PASS, RuleResult.FAIL, RuleResult.UNKNOWN, RuleResult.NEEDS_REVIEW,
)

_checks = []


def check(name, actual, expected):
    ok = actual == expected
    _checks.append((ok, name, actual, expected))
    print(f"  {'✅' if ok else '❌'} {name}"
          + ("" if ok else f"\n       thực tế: {actual!r}\n       kỳ vọng: {expected!r}"))


def leaf(rule_id, field, op, value, **kw):
    """Rule mẫu ĐÃ review — để test logic chứ không test cổng review."""
    return {
        "rule_id": rule_id, "field": field, "operator": op, "value": value,
        "description": kw.get("description", rule_id),
        "hard": kw.get("hard", False),
        "evaluation": kw.get("evaluation", "auto"),
        "source_document": "Luật 04/2017/QH14", "article": "Điều 17",
        "source_url": "https://example", "interpretation_note": "",
        "review_status": kw.get("review_status", "manually_reviewed"),
        "effective_from": kw.get("effective_from", "2018-01-01"),
        "effective_to": kw.get("effective_to"),
    }


def ctx(**kw):
    return EvalContext(evaluated_at=kw.get("evaluated_at", date(2026, 7, 17)),
                       require_reviewed=kw.get("require_reviewed", True))


# ─────────────────────────────────────────────────────────────
print("\n[1] operators — None ≠ False")

check("None → UNKNOWN/MISSING_FIELD (chưa khai, KHÔNG phải trượt)",
      operators.apply(None, "<=", 5), (UNKNOWN, UnknownReason.MISSING_FIELD))
check("ngưỡng null → UNKNOWN/THRESHOLD_UNVERIFIED (lỗi của đội)",
      operators.apply(3, "<=", None), (UNKNOWN, UnknownReason.THRESHOLD_UNVERIFIED))
check("0 là giá trị THẬT, không nhầm với None",
      operators.apply(0, "<=", 5), (PASS, None))
check("False là giá trị THẬT",
      operators.apply(False, "==", False), (PASS, None))
check("2 <= 5 → PASS", operators.apply(2, "<=", 5), (PASS, None))
check("7 <= 5 → FAIL", operators.apply(7, "<=", 5), (FAIL, None))
check("'software' in [...] → PASS",
      operators.apply("software", "in", ["software", "ai"]), (PASS, None))
check("contains: DN có list, rule cho 1 giá trị",
      operators.apply(["training"], "contains", "training"), (PASS, None))
check("so chuỗi với số → UNKNOWN/TYPE_ERROR (không crash)",
      operators.apply("abc", "<=", 5), (UNKNOWN, UnknownReason.TYPE_ERROR))

try:
    operators.apply(1, "≤", 5)
    check("toán tử lạ phải NỔ", "không nổ", "UnknownOperatorError")
except operators.UnknownOperatorError:
    check("toán tử lạ → nổ (lỗi data, không nuốt)", "nổ", "nổ")


# ─────────────────────────────────────────────────────────────
print("\n[2] logic.combine — thứ tự ưu tiên")

check("all: FAIL thắng UNKNOWN (Case 3 sống nhờ dòng này)",
      logic.combine([FAIL, UNKNOWN, PASS], "all"), FAIL)
check("all: UNKNOWN thắng NEEDS_REVIEW (hỏi user trước, escalate sau)",
      logic.combine([UNKNOWN, REVIEW, PASS], "all"), UNKNOWN)
check("all: NEEDS_REVIEW thắng PASS", logic.combine([REVIEW, PASS], "all"), REVIEW)
check("all: toàn PASS → PASS", logic.combine([PASS, PASS], "all"), PASS)
check("any: PASS thắng tất cả", logic.combine([FAIL, PASS, UNKNOWN], "any"), PASS)
check("any: UNKNOWN thắng FAIL", logic.combine([FAIL, UNKNOWN], "any"), UNKNOWN)
check("any: toàn FAIL → FAIL", logic.combine([FAIL, FAIL], "any"), FAIL)

check("⚠️ group RỖNG → UNKNOWN, KHÔNG phải PASS (vacuous truth = thảm họa)",
      logic.combine([], "all"), UNKNOWN)


# ─────────────────────────────────────────────────────────────
print("\n[3] logic.evaluate_node — cây lồng nhau + các cổng lọc")

tree = {"all": [
    leaf("age", "company_age_years", "<=", 5, hard=True),
    {"any": [
        leaf("product", "product_type", "in", ["software", "ai"]),
        leaf("innovative", "is_innovative", "==", True, evaluation="human_review"),
    ]},
]}

r, conds = logic.evaluate_node(tree, {"company_age_years": 2, "product_type": "software"}, ctx())
check("cây lồng: tuổi PASS + any[product PASS] → PASS", r, PASS)
check("any dừng ở nhánh auto, KHÔNG kéo human_review lên",
      [c["result"] for c in conds], ["PASS", "PASS", "NEEDS_REVIEW"])

r, _ = logic.evaluate_node(tree, {"company_age_years": 7, "product_type": None}, ctx())
check("Case 3: quá tuổi → FAIL dù nhánh kia UNKNOWN", r, FAIL)

r, _ = logic.evaluate_node(tree, {"company_age_years": 2, "product_type": None}, ctx())
check("Case 2: thiếu product_type → UNKNOWN (không đoán)", r, UNKNOWN)

r, conds = logic.evaluate_node(
    {"all": [leaf("innovative", "is_innovative", "==", True, evaluation="human_review")]},
    {"is_innovative": True}, ctx())
check("human_review: có sẵn giá trị vẫn KHÔNG tự quyết", r, REVIEW)

# --- cổng review ---
c = ctx()
r, _ = logic.evaluate_node({"all": [leaf("x", "a", "==", 1, review_status="draft")]}, {"a": 1}, c)
check("⚠️ rule draft bị lọc → group rỗng → UNKNOWN (không tự tuyên đủ điều kiện)", r, UNKNOWN)
check("rule bị lọc phải hiện trong warnings, không biến mất âm thầm",
      any("draft" in w for w in c.warnings), True)

r, _ = logic.evaluate_node({"all": [leaf("x", "a", "==", 1, review_status="draft")]},
                           {"a": 1}, ctx(require_reviewed=False))
check("tắt cổng review (chỉ khi test) → xét bình thường", r, PASS)

# --- cổng hiệu lực ---
c = ctx()
r, _ = logic.evaluate_node(
    {"all": [leaf("x", "a", "==", 1, effective_to="2020-01-01")]}, {"a": 1}, c)
check("rule hết hiệu lực → bị lọc → UNKNOWN", r, UNKNOWN)
check("hết hiệu lực phải vào warnings",
      any("hết hiệu lực" in w for w in c.warnings), True)

r, _ = logic.evaluate_node({"all": [leaf("x", "a", "==", 1, effective_from="<TODO>")]},
                           {"a": 1}, ctx())
check("effective_from='<TODO>' → vẫn xét (cổng review đã lo), chỉ cảnh báo", r, PASS)


# ─────────────────────────────────────────────────────────────
print("\n[4] classifier — chưa biết ≠ không đạt")

TABLE = {
    "article": "Điều 5", "source_document": "NĐ 80/2021/NĐ-CP",
    "sector_to_linh_vuc": {"information_technology": "thuong_mai_dich_vu"},
    "criteria": {"thuong_mai_dich_vu": {
        "sieu_nho": {"max_social_insurance_employees": 10,
                     "max_annual_revenue_vnd": 3_000_000_000,
                     "max_total_capital_vnd": 3_000_000_000},
        "nho": {"max_social_insurance_employees": 50,
                "max_annual_revenue_vnd": 50_000_000_000,
                "max_total_capital_vnd": 50_000_000_000},
        "vua": {"max_social_insurance_employees": 100,
                "max_annual_revenue_vnd": 300_000_000_000,
                "max_total_capital_vnd": 100_000_000_000},
    }},
}
# ⚠️ Ngưỡng trên là SỐ BỊA để test thuật toán. Bảng thật ở data/sme_classification.json
#    còn null — Thành phải điền từ NĐ 80. Đừng copy số này ra data.

GREEN = {"sector": "information_technology", "social_insurance_employees": 18,
         "annual_revenue_vnd": 6_000_000_000, "total_capital_vnd": None}

check("GreenVision: 18 LĐ, 6 tỷ → hạng nhỏ",
      classifier.classify_sme_size(GREEN, TABLE)["value"], "nho")
check("trace phải giải thích được, không hộp đen",
      "18 ≤ 50" in classifier.classify_sme_size(GREEN, TABLE)["trace"], True)

check("thiếu sector → UNKNOWN (không phải khong_thuoc_dnnvv)",
      classifier.classify_sme_size({**GREEN, "sector": None}, TABLE)["value"], None)
check("thiếu sector → hỏi đúng 'sector'",
      classifier.classify_sme_size({**GREEN, "sector": None}, TABLE)["missing_fields"], ["sector"])
check("thiếu CẢ doanh thu lẫn vốn → UNKNOWN",
      classifier.classify_sme_size(
          {**GREEN, "annual_revenue_vnd": None}, TABLE)["missing_fields"],
      ["annual_revenue_vnd", "total_capital_vnd"])
check("có vốn dù thiếu doanh thu → vẫn tra được (luật dùng HOẶC)",
      classifier.classify_sme_size(
          {**GREEN, "annual_revenue_vnd": None, "total_capital_vnd": 2_000_000_000},
          TABLE)["value"], "nho")  # 18 LĐ > ngưỡng sieu_nho (10) → rơi xuống nho
check("hạng chặn bởi số LĐ, không phải tiền: 8 LĐ + vốn nhỏ → sieu_nho",
      classifier.classify_sme_size(
          {**GREEN, "social_insurance_employees": 8, "annual_revenue_vnd": None,
           "total_capital_vnd": 2_000_000_000}, TABLE)["value"], "sieu_nho")

EMPTY_TABLE = {**TABLE, "criteria": {"thuong_mai_dich_vu": {
    "sieu_nho": {"max_social_insurance_employees": None,
                 "max_annual_revenue_vnd": None, "max_total_capital_vnd": None},
    "nho": {}, "vua": {}}}}
check("⚠️ ngưỡng chưa xác minh → UNKNOWN, TUYỆT ĐỐI không 'khong_thuoc_dnnvv'",
      classifier.classify_sme_size(GREEN, EMPTY_TABLE)["value"], None)

check("DN to thật → khong_thuoc_dnnvv (kết luận thật, không phải UNKNOWN)",
      classifier.classify_sme_size(
          {**GREEN, "social_insurance_employees": 500,
           "annual_revenue_vnd": 900_000_000_000}, TABLE)["value"], "khong_thuoc_dnnvv")

check("map lĩnh vực còn <TODO> → UNKNOWN",
      classifier.classify_sme_size(
          GREEN, {**TABLE, "sector_to_linh_vuc": {"information_technology": "<TODO>"}})["value"],
      None)


# ─────────────────────────────────────────────────────────────
print("\n[5] benefit — không bịa số")

def prog(**kw):
    return {"program_id": "p", "name": "P", "benefit": {
        "type": kw.get("type", "percentage_of_cost"),
        "basis": "chi phí thuê", "basis_field": kw.get("basis_field", "coworking_monthly_cost_vnd"),
        "cap_period": "month",
        "tiers": {"nho": {"rate": kw.get("rate"), "cap_amount": kw.get("cap"),
                          "max_duration_months": kw.get("months")}},
    }}

P = {"sme_size_category": "nho", "coworking_monthly_cost_vnd": 10_000_000}

check("rate chưa xác minh → computable=False",
      benefit.estimate(prog(cap=5_000_000), P)["computable"], False)
check("note phải chỉ rõ ĐỘI phải làm, không đổ cho user",
      "việc của đội" in benefit.estimate(prog(cap=5_000_000), P)["note"], True)
check("DN chưa khai chi phí → computable=False",
      benefit.estimate(prog(rate=0.5, cap=5_000_000),
                       {**P, "coworking_monthly_cost_vnd": None})["computable"], False)
check("chưa khai chi phí → đưa vào missing_fields để chatbot hỏi",
      benefit.estimate(prog(rate=0.5, cap=5_000_000),
                       {**P, "coworking_monthly_cost_vnd": None})["missing_fields"],
      ["coworking_monthly_cost_vnd"])
check("đủ số → 50% × 10tr = 5tr, đúng trần",
      benefit.estimate(prog(rate=0.5, cap=5_000_000), P)["amount_vnd"], 5_000_000)
check("vượt trần → áp trần",
      benefit.estimate(prog(rate=0.9, cap=5_000_000), P)["amount_vnd"], 5_000_000)
check("tier_used ghi lại hạng đã tra",
      benefit.estimate(prog(rate=0.5, cap=5_000_000), P)["tier_used"], "nho")
check("in_kind → KHÔNG quy ra tiền",
      benefit.estimate(prog(type="in_kind"), P)["computable"], False)
check("chưa biết hạng → không tra tier được",
      benefit.estimate(prog(rate=0.5, cap=5_000_000),
                       {**P, "sme_size_category": None})["computable"], False)


# ─────────────────────────────────────────────────────────────
print("\n[6] engine — 2 tầng + availability là lớp phủ")

QUAL = {"qualification_id": "dnnvv_knst", "ruleset_version": "test-1",
        "rules": {"all": [
            leaf("is_dnnvv", "sme_size_category", "in", ["sieu_nho", "nho", "vua"]),
            leaf("age", "company_age_years", "<=", 5, hard=True,
                 description="Thành lập không quá 5 năm"),
        ]}}

def program(av_status="open", **kw):
    return {
        "program_id": "coworking", "name": "Hỗ trợ thuê coworking",
        "requires_qualification": "dnnvv_knst",
        "rules": {"all": [leaf("has_contract", "has_coworking_contract", "==", True)]},
        "required_documents": [{"doc_id": "lease", "name": "Hợp đồng thuê",
                                "profile_field": "has_coworking_contract"}],
        "benefit": {"type": "percentage_of_cost", "basis": "chi phí thuê",
                    "basis_field": "coworking_monthly_cost_vnd", "cap_period": "month",
                    "tiers": {"nho": {"rate": 0.5, "cap_amount": 5_000_000,
                                      "max_duration_months": 12}}},
        "availability": {"scope": "province",
                         "by_province": {"hanoi": {"status": av_status, "deadline": kw.get("deadline")}},
                         "default": {"status": "unknown"}},
        "submission": {"agency": "Sở KH&ĐT", "deadline": "2026-12-31"},
        "conflicts_with": [],
    }

BASE = {"company_name": "GreenVision AI", "province": "hanoi", "company_age_years": 2,
        "sector": "information_technology", "social_insurance_employees": 18,
        "annual_revenue_vnd": 6_000_000_000, "total_capital_vnd": None,
        "product_type": "software", "has_coworking_contract": True,
        "coworking_monthly_cost_vnd": 10_000_000}

def run(profile, av="open", c=None):
    c = c or ctx()
    q = engine.check_qualification(profile, QUAL, TABLE, c)
    q["ruleset_version"] = "test-1"
    return q, engine.check_program(q["profile"], program(av), q, c)

# --- CASE 1: đủ điều kiện rõ ràng ---
q, r = run(BASE)
check("Case 1: tầng 1 LIKELY_ELIGIBLE", q["status"], "LIKELY_ELIGIBLE")
check("Case 1: hạng nhỏ, có trace", q["sme_size_category"]["value"], "nho")
check("Case 1: program LIKELY_ELIGIBLE", r["status"], "LIKELY_ELIGIBLE")
check("Case 1: tính được tiền 5tr", r["benefit_estimate"]["amount_vnd"], 5_000_000)
check("Case 1: mọi điều kiện có trích dẫn",
      all(c_["source"] for c_ in r["conditions"]), True)

# --- CASE 2: thiếu thông tin → không kết luận bừa ---
q, r = run({**BASE, "social_insurance_employees": None})
check("Case 2: thiếu LĐ BHXH → NEED_MORE_INFO (không đoán)", r["status"], "NEED_MORE_INFO")
check("Case 2: hỏi ĐÚNG field thiếu, không hỏi sme_size_category",
      q["missing_fields"], ["social_insurance_employees"])

# --- CASE 3: trượt điều kiện cứng ---
q, r = run({**BASE, "company_age_years": 7, "annual_revenue_vnd": None,
            "total_capital_vnd": None})
check("Case 3: 7 tuổi → NOT_ELIGIBLE dù thiếu doanh thu (FAIL thắng UNKNOWN)",
      q["status"], "NOT_ELIGIBLE")
check("Case 3: program kế thừa NOT_ELIGIBLE", r["status"], "NOT_ELIGIBLE")
check("Case 3: nêu rào chắn + trích dẫn",
      "Thành lập không quá 5 năm" in (r["blocking_reason"] or ""), True)
check("Case 3: không khắc phục được", r["fixable"], False)

# --- CASE 4: đủ tư cách nhưng thiếu hồ sơ ---
q, r = run({**BASE, "has_coworking_contract": None})
check("Case 4: tầng 1 vẫn đạt", r["qualification"]["status"], "LIKELY_ELIGIBLE")
check("Case 4: program NEED_MORE_INFO", r["status"], "NEED_MORE_INFO")
check("Case 4: checklist hồ sơ thiếu",
      [d["name"] for d in r["missing_documents"]], ["Hợp đồng thuê"])

# --- CASE 5: đủ điều kiện nhưng chương trình chưa rõ mở ---
q, r = run(BASE, av="unknown")
check("Case 5: status = PROGRAM_UNAVAILABLE", r["status"], "PROGRAM_UNAVAILABLE")
check("⭐ Case 5: legal_status VẪN giữ LIKELY_ELIGIBLE → hiện được căn cứ pháp lý",
      r["legal_status"], "LIKELY_ELIGIBLE")
check("Case 5: có căn cứ để hiển thị (không rỗng)", len(r["conditions"]) > 0, True)
check("Case 5: chỉ ra bước xác minh", r["submission"]["agency"], "Sở KH&ĐT")

q, r = run({**BASE, "province": None})
check("thiếu province → NEED_MORE_INFO + hỏi province",
      (r["status"], "province" in r["missing_fields"]), ("NEED_MORE_INFO", True))

q, r = run(BASE, av="closed")
check("chương trình đóng → PROGRAM_UNAVAILABLE + cảnh báo",
      (r["status"], any("đóng" in w for w in r["warnings"])),
      ("PROGRAM_UNAVAILABLE", True))

# --- tái lập ---
q, r = run(BASE)
check("kết quả ghi evaluated_at", r["evaluated_at"], "2026-07-17")
check("kết quả ghi ruleset_version", r["ruleset_version"], "test-1")


# ─────────────────────────────────────────────────────────────
print("\n[7] Dữ liệu THẬT hiện tại (mọi rule còn draft)")

import json
from pathlib import Path

# parents[2] = gốc repo → shared/ (khớp volume mount ./shared của docker-compose).
# Rulebook là của Thành (server-a ghi), Hoàng chỉ đọc → để ở shared/, không nhân bản vào server-c.
RULEBOOK = Path(__file__).resolve().parents[2] / "shared" / "rulebook"
real_qual = json.loads((RULEBOOK / "qualification.json").read_text(encoding="utf-8"))
real_table = json.loads((RULEBOOK / "sme_classification.json").read_text(encoding="utf-8"))

c = ctx()
q = engine.check_qualification(BASE, real_qual, real_table, c)
check("⭐ data thật (rule draft + ngưỡng null) → NEED_MORE_INFO, KHÔNG tuyên đủ điều kiện",
      q["status"], "NEED_MORE_INFO")
check("và nói rõ vì sao trong warnings", len(c.warnings) > 0, True)


# ─────────────────────────────────────────────────────────────
failed = [c_ for c_ in _checks if not c_[0]]
print(f"\n{'─' * 60}")
print(f"{len(_checks) - len(failed)}/{len(_checks)} PASS" + (f", {len(failed)} FAIL" if failed else " — tất cả xanh ✅"))
raise SystemExit(1 if failed else 0)
