"""
engine.py — Bộ máy xét điều kiện, HAI TẦNG. (chủ: Hoàng) ⭐

Xem docs/contracts.md mục A (hai tầng) + C (logic 4 giá trị).

--- API chính ---
check_qualification(profile, qualification, classification) -> QualificationResult
    TẦNG 0 rồi TẦNG 1:
      0. classifier.classify_sme_size(profile, classification)
         → profile.sme_size_category + SizeCategoryTrace
         PHẢI chạy trước, vì rule `is_dnnvv` của tầng 1 đọc trường này.
      1. logic.evaluate_node(qualification.rules, profile)

check_program(profile, program, qualification_result, evaluated_at) -> EligibilityResult
    Xét TẦNG 2 cho một program.

    Trình tự:
      1. Nếu qualification_result.status != LIKELY_ELIGIBLE
         → kế thừa status đó luôn, KHÔNG xét tiếp (giải thích "vì sao tắt")
      2. Lọc rule theo hiệu lực tại `evaluated_at`:
         effective_from > evaluated_at, hoặc effective_to < evaluated_at → BỎ
         → ghi log + warnings. KHÔNG được biến mất âm thầm.
      3. logic.evaluate_node(program.rules, profile) → RuleResult + chi tiết từng điều kiện
      4. Kiểm required_documents → thiếu giấy tờ nào (profile_field is None/False)
         → gộp vào NEED_MORE_INFO + missing_documents (Case 4)
      5. Ánh xạ RuleResult → `legal_status` (xem logic.py)
      6. Tra availability THEO TỈNH → phủ lên `legal_status` để ra `status` (xem dưới)
      7. Gọi benefit.estimate() → benefit_estimate
      8. Copy program.submission → result.submission (trả lời "rồi sao nữa?")

--- ⚠️ AVAILABILITY LÀ LỚP PHỦ, KHÔNG PHẢI CỬA CHẶN (sửa lỗi thiết kế) ---
Bản trước: "availability == unknown → PROGRAM_UNAVAILABLE" đặt ở bước 2, TRƯỚC khi xét rule.
Sai ở hai chỗ:
  a. Case 5 đòi vừa báo PROGRAM_UNAVAILABLE vừa "hiển thị căn cứ pháp lý" —
     không xét rule thì lấy đâu ra căn cứ để hiển thị.
  b. Nó xoá mất khác biệt giữa "đủ điều kiện nhưng chưa rõ chương trình mở"
     và "không đủ điều kiện" — đúng thứ nghiệp vụ quan trọng nhất của sản phẩm.

Nay: LUÔN xét hết rule, rồi mới phủ availability lên.

    legal_status : chỉ từ rule + hồ sơ  → "về pháp lý, DN có thuộc diện không"
    status       : legal_status + availability → cái UI hiện lên đầu

    Tra availability theo profile.province:
        province is None           → status = NEED_MORE_INFO, missing_fields += ["province"]
        by_province[province] có    → dùng
        không có                    → dùng availability.default
        status "open"               → status = legal_status        (không phủ gì)
        status "unknown" | "closed" → status = PROGRAM_UNAVAILABLE (legal_status VẪN GIỮ)

Nhờ tách hai trường này, Case 1 và Case 5 dùng CÙNG một hồ sơ mà vẫn ra kết quả khác nhau —
khác nhau ở TỈNH, không phải ở rule. Trước đây hai case mâu thuẫn nhau về mặt logic:
cùng profile + cùng program + engine tất định thì không thể vừa LIKELY_ELIGIBLE vừa
PROGRAM_UNAVAILABLE.

--- Nguyên tắc ---
  - KHÔNG dùng LLM cho quyết định đúng/sai.
  - Mỗi ConditionResult phải kèm `source` (trích dẫn) — lấy từ provenance của Condition.
  - Chỉ dùng rule có review_status trong USABLE_REVIEW_STATUSES (xem models/rule.py);
    rule "draft" bị bỏ qua + ghi log.
  - ⚠️ Bỏ rule vì `draft`/hết hiệu lực làm group MẤT điều kiện. Nếu một `all` bị lọc sạch,
    KHÔNG được trả PASS (rỗng → vacuous truth = "đủ điều kiện vì chẳng xét gì cả" — sai
    nguy hiểm nhất có thể). Trả UNKNOWN + UnknownReason.NO_EVALUABLE_RULE.
  - `evaluated_at` + `qualification.ruleset_version` phải ghi vào mọi EligibilityResult.
"""

from grantpilot import benefit as benefit_mod
from grantpilot import classifier, logic
from grantpilot.models.eligibility_result import STATUS_FROM_RULE_RESULT, EligibilityStatus
from grantpilot.models.rule import RuleResult

# Trường DẪN XUẤT: user không khai được. Khi chúng UNKNOWN, hỏi user chính nó là vô nghĩa
# ("bạn hạng siêu nhỏ hay nhỏ?" — nếu DN biết thì đã chẳng cần ta). Phải quy về đầu vào thật.
DERIVED_FIELD_INPUTS = {
    "company_age_years": ("founded_year",),
    # sme_size_category không liệt kê ở đây: classifier tự trả missing_fields chính xác hơn
    # (nó biết "doanh thu HOẶC nguồn vốn" nên không đòi cả hai khi đã có một).
}


def _dedupe(items):
    """Giữ nguyên thứ tự, bỏ trùng. Thứ tự = độ ưu tiên hỏi user."""
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _collect_missing_fields(conditions, profile, sme_trace=None):
    """Gom các trường cần hỏi user từ conditions.

    Chỉ lấy condition có `missing_field` — tức chỉ UnknownReason.MISSING_FIELD.
    THRESHOLD_UNVERIFIED / NO_EVALUABLE_RULE / TYPE_ERROR đã nằm ở warnings và
    KHÔNG được lọt vào đây: chúng là việc của đội, hỏi user chỉ làm user tưởng lỗi ở họ.
    """
    out = []
    for c in conditions:
        mf = c.get("missing_field")
        if not mf:
            continue
        if mf == "sme_size_category":
            out.extend((sme_trace or {}).get("missing_fields") or [])
        elif mf in DERIVED_FIELD_INPUTS:
            out.extend(src for src in DERIVED_FIELD_INPUTS[mf] if profile.get(src) is None)
        else:
            out.append(mf)
    return _dedupe(out)


def _count(conditions, result):
    return sum(1 for c in conditions if c.get("result") == result.value)


def check_qualification(profile, qualification, classification, ctx):
    """TẦNG 0 + TẦNG 1: DN có phải DNNVV khởi nghiệp sáng tạo không?

    Trả QualificationResult (dict), kèm key `profile` = hồ sơ ĐÃ LÀM GIÀU
    (có sme_size_category) để check_program dùng lại — tránh tra bảng 6 lần cho 6 program,
    và quan trọng hơn: đảm bảo benefit.tiers tra đúng hạng mà tầng 1 đã dùng.
    """
    # TẦNG 0 phải chạy trước: rule `is_dnnvv` của tầng 1 đọc `sme_size_category`.
    # Copy profile — engine KHÔNG được sửa dữ liệu của caller.
    enriched = dict(profile)
    sme_trace = classifier.classify_sme_size(enriched, classification, ctx)
    enriched["sme_size_category"] = sme_trace["value"]

    result, conditions = logic.evaluate_node(qualification["rules"], enriched, ctx)

    return {
        "qualification_id": qualification.get("qualification_id"),
        "status": STATUS_FROM_RULE_RESULT[result].value,
        "passed": _count(conditions, RuleResult.PASS),
        "total": len(conditions),
        "conditions": conditions,
        "sme_size_category": sme_trace,
        "missing_fields": _collect_missing_fields(conditions, enriched, sme_trace),
        "profile": enriched,
    }


def _resolve_availability(program, profile):
    """Tra availability theo tỉnh của DN. Trả (dict | None, missing_field | None).

    NĐ 80 triển khai qua UBND cấp tỉnh: chương trình, ngân sách, hạn nộp đều là chuyện
    của tỉnh. Cùng một điều khoản trung ương, startup Cần Thơ và Hà Nội ra kết quả khác nhau.
    """
    availability = program.get("availability") or {}
    province = profile.get("province")
    if province is None:
        return None, "province"
    by_province = availability.get("by_province") or {}
    return by_province.get(province) or availability.get("default") or {"status": "unknown"}, None


def check_program(profile, program, qualification_result, ctx):
    """TẦNG 2: xét một program. Trả EligibilityResult (dict).

    `profile` nên là qualification_result["profile"] (đã có sme_size_category).
    """
    program_id = program.get("program_id")
    program_name = program.get("name")
    ruleset_version = qualification_result.get("ruleset_version")

    base = {
        "program_id": program_id,
        "program_name": program_name,
        "evaluated_at": ctx.evaluated_at.isoformat(),
        "ruleset_version": ruleset_version,
        "qualification": {k: v for k, v in qualification_result.items() if k != "profile"},
        "submission": program.get("submission") or {},
    }

    # --- 1. Cổng tầng 1 ---
    # Không đạt tư cách → mọi hỗ trợ tắt. KẾ THỪA status của tầng 1 chứ không tự đặt
    # NOT_ELIGIBLE: nếu tầng 1 là NEED_MORE_INFO (thiếu doanh thu), thì lý do thật là
    # "chưa biết", không phải "không đủ điều kiện". Đặt sai ở đây là nói dối DN.
    qual_status = qualification_result.get("status")
    if qual_status != EligibilityStatus.LIKELY_ELIGIBLE.value:
        return {
            **base,
            "status": qual_status,
            "legal_status": qual_status,
            "passed": 0,
            "total": 0,
            "conditions": [],
            "missing_fields": list(qualification_result.get("missing_fields") or []),
            "missing_documents": [],
            "fixable": qual_status == EligibilityStatus.NEED_MORE_INFO.value,
            "blocking_reason": _blocking_reason(qualification_result.get("conditions") or []),
            "benefit_estimate": benefit_mod.estimate(program, profile),
            "warnings": [f"Chưa xét '{program_name}': chưa đạt tư cách DNNVV khởi nghiệp sáng tạo."],
        }

    # --- 2. Xét rule riêng của program ---
    result, conditions = logic.evaluate_node(program.get("rules") or {}, profile, ctx)
    legal_status = STATUS_FROM_RULE_RESULT[result]

    missing_fields = _collect_missing_fields(conditions, profile,
                                             qualification_result.get("sme_size_category"))
    warnings = []

    # --- 3. Hồ sơ chứng từ (Case 4) ---
    # `None` (chưa khai) và `False` (khai là chưa có) đều dẫn tới "chưa nộp được",
    # nên gộp chung vào checklist. Khác với rule: ở đó None và False khác nhau về logic,
    # còn ở đây cả hai đều ra cùng một hành động — đi lấy giấy tờ.
    missing_documents = []
    for doc in program.get("required_documents") or []:
        if not profile.get(doc.get("profile_field")):
            missing_documents.append({"doc_id": doc.get("doc_id"), "name": doc.get("name")})

    if missing_documents and legal_status is EligibilityStatus.LIKELY_ELIGIBLE:
        legal_status = EligibilityStatus.NEED_MORE_INFO

    # --- 4. benefit ---
    estimate = benefit_mod.estimate(program, profile)
    missing_fields = _dedupe(missing_fields + (estimate.get("missing_fields") or []))

    # --- 5. availability là LỚP PHỦ, không phải cửa chặn ---
    # Luôn xét hết rule rồi mới phủ, để Case 5 vừa báo PROGRAM_UNAVAILABLE vừa hiện được
    # căn cứ pháp lý. `legal_status` giữ nguyên câu trả lời "về pháp lý DN có thuộc diện không".
    status = legal_status
    availability, missing_province = _resolve_availability(program, profile)

    if missing_province:
        # Chỉ hạ xuống NEED_MORE_INFO khi mọi thứ khác đã sạch. Nếu rule đã FAIL thì
        # NOT_ELIGIBLE là câu trả lời dứt khoát hơn — hỏi thêm tỉnh cũng không cứu được.
        if status is EligibilityStatus.LIKELY_ELIGIBLE:
            status = EligibilityStatus.NEED_MORE_INFO
        missing_fields = _dedupe(missing_fields + ["province"])
        warnings.append(
            "Chưa biết tỉnh/thành của DN nên chưa tra được chương trình ở địa phương "
            "có đang mở nhận hồ sơ không."
        )
    else:
        av_status = (availability or {}).get("status")
        if av_status != "open" and status is EligibilityStatus.LIKELY_ELIGIBLE:
            status = EligibilityStatus.PROGRAM_UNAVAILABLE
        if av_status == "closed":
            warnings.append(f"Chương trình tại tỉnh {profile.get('province')!r} đã đóng/hết hạn.")
        elif av_status != "open":
            warnings.append(
                f"Chưa xác minh chương trình tại tỉnh {profile.get('province')!r} có đang mở không "
                f"— cần liên hệ cơ quan tiếp nhận."
            )
        deadline = (availability or {}).get("deadline")
        if deadline:
            # Hạn của tỉnh THẮNG hạn chung của program.
            base["submission"] = {**base["submission"], "deadline": deadline}

    fails = [c for c in conditions if c.get("result") == RuleResult.FAIL.value]

    return {
        **base,
        "status": status.value,
        "legal_status": legal_status.value,
        "passed": _count(conditions, RuleResult.PASS),
        "total": len(conditions),
        "conditions": conditions,
        "missing_fields": missing_fields,
        "missing_documents": missing_documents,
        # fixable = mọi điều kiện đang trượt đều mềm. Không có cái nào trượt → không có gì chặn.
        "fixable": all(not c.get("hard") for c in fails),
        "blocking_reason": _blocking_reason(conditions),
        "benefit_estimate": estimate,
        "warnings": warnings,
    }


def _blocking_reason(conditions):
    """Điều kiện CỨNG đầu tiên bị trượt — thứ khiến DN vô vọng với hỗ trợ này (Case 3).

    Chỉ tính FAIL + hard. Một điều kiện mềm trượt (R&D thấp) thì khắc phục được,
    không phải "rào chắn".
    """
    for c in conditions:
        if c.get("result") == RuleResult.FAIL.value and c.get("hard"):
            return f"{c.get('description')} (căn cứ: {c.get('source')})"
    return None
