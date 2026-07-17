"""
Schema `eligibility_result` — kết quả xét cho MỘT program. Xem docs/contracts.md mục G.

Chủ: Hoàng tạo → Huy (LLM diễn giải) + UI hiển thị.

--- 5 TRẠNG THÁI (không phải bool đủ/không) ---
  LIKELY_ELIGIBLE      : có khả năng đủ điều kiện          → chuẩn bị hồ sơ
  NOT_ELIGIBLE         : có điều kiện rõ ràng không đạt     → xem hỗ trợ khác
  NEED_MORE_INFO       : thiếu dữ liệu HOẶC thiếu hồ sơ     → khai thêm / bổ sung giấy tờ
  NEEDS_HUMAN_REVIEW   : cần chuyên gia/cơ quan xác minh    → liên hệ cơ quan
  PROGRAM_UNAVAILABLE  : có căn cứ nhưng chưa rõ đang mở TẠI TỈNH → xác minh với cơ quan

Ghi chú: KHÔNG tách NEEDS_DOCUMENTS riêng — thiếu hồ sơ nằm trong NEED_MORE_INFO,
nhưng liệt kê ở `missing_documents` để UI hiện checklist.

  class ConditionResult:
      rule_id: str
      description: str
      result: str            # PASS | FAIL | UNKNOWN | NEEDS_REVIEW
      current_value: Any     # giá trị hiện tại của DN
      hard: bool
      missing_field: str|None # nếu UNKNOWN → trường nào thiếu
      source: str            # ⭐ trích dẫn "Điều 17 Khoản 1 Điểm a, Luật 04/2017/QH14"

  class SizeCategoryTrace:          # ⭐ mới — vì sao DN bị xếp hạng này
      value: str | None      # sieu_nho | nho | vua | khong_thuoc_dnnvv | None
      result: str            # PASS | UNKNOWN  (xem classifier.py)
      trace: str             # "LĐ BHXH 18 ≤ <ngưỡng>; doanh thu 6.000.000.000 ≤ <ngưỡng>"
      source: str            # "Điều 5, Nghị định 80/2021/NĐ-CP"
      missing_fields: list[str]  # đầu vào phép tra còn thiếu (sector, LĐ BHXH, doanh thu/vốn)
                                 # ⚠️ hỏi user MẤY TRƯỜNG NÀY, không phải "sme_size_category"
                                 #    — user không khai được trường dẫn xuất
      # Bảng tra KHÔNG được là hộp đen. Nếu giấu logic khỏi user thì ta đang làm
      # đúng thứ ta chê RAG phẳng.

  class QualificationResult:
      qualification_id: str
      status: str            # 5 trạng thái
      passed: int
      total: int
      sme_size_category: SizeCategoryTrace   # ⭐ mới

  class BenefitEstimate:
      computable: bool       # False khi chưa rõ rate/cap/chi phí → KHÔNG bịa số
      amount_vnd: int | None
      tier_used: str | None  # ⭐ hạng đã tra: sieu_nho | nho | vua
      note: str              # lý do CỤ THỂ khi computable=False
                             # ("chưa xác minh mức trần" vs "DN chưa khai chi phí thuê"
                             #  là hai việc khác nhau — một cái đội phải làm, một cái user phải làm)
      missing_fields: list[str]  # trường chi phí user cần khai để tính được tiền
                                 # → engine gộp lên EligibilityResult.missing_fields

  class EligibilityResult:
      program_id: str
      program_name: str
      status: str                          # ⭐ 1 trong 5 — legal_status ĐÃ PHỦ availability
      legal_status: str                    # ⭐ 1 trong 4 (không bao giờ PROGRAM_UNAVAILABLE)
                                           #    chỉ từ rule + hồ sơ: "về pháp lý DN có thuộc diện không"

      evaluated_at: str                    # ⭐ ISO 8601 — thời điểm xét, dùng lọc rule theo hiệu lực
      ruleset_version: str                 # ⭐ phiên bản bộ rule đã dùng

      qualification: QualificationResult   # kết quả tầng 1 (giải thích vì sao tắt)
      passed: int
      total: int
      conditions: list[ConditionResult]
      missing_fields: list[str]            # → chatbot hỏi lại đúng field (Case 2)
      missing_documents: list[dict]        # → checklist hồ sơ (Case 4)
      fixable: bool                        # mọi điều kiện trượt đều hard=False?
      blocking_reason: str | None          # nếu NOT_ELIGIBLE: điều kiện cứng nào chặn (Case 3)
      benefit_estimate: BenefitEstimate
      submission: dict                     # ⭐ copy từ program → UI hiện "bước tiếp theo"
                                           #    ngay cạnh kết quả (agency/where/deadline/...)
      warnings: list[str]                  # xung khắc / hết hiệu lực / rule bị bỏ (Case 6)

--- VÌ SAO TÁCH `status` VÀ `legal_status` ---
`availability` là LỚP PHỦ, không phải cửa chặn (xem engine.py):

    legal_status = LIKELY_ELIGIBLE  +  availability "open"     → status = LIKELY_ELIGIBLE
    legal_status = LIKELY_ELIGIBLE  +  availability "unknown"  → status = PROGRAM_UNAVAILABLE
    legal_status = NOT_ELIGIBLE     +  availability "unknown"  → status = PROGRAM_UNAVAILABLE

Hai dòng đầu là cả nghiệp vụ của sản phẩm: "ĐỦ điều kiện pháp lý ≠ CHẮC CHẮN được cấp tiền".
Gộp vào một trường `status` thì mất luôn vế đầu — UI không nói được
"bạn thuộc diện ✅, nhưng chương trình ở tỉnh bạn chưa xác minh đang mở".

⚠️ Dòng thứ ba: khi legal_status = NOT_ELIGIBLE, UI nên hiện lý do TRƯỢT trước,
không phải "chưa rõ chương trình mở" — DN trượt điều kiện cứng thì availability vô nghĩa.
Đây là quyết định trình bày của UI, nhưng dữ liệu phải mang đủ cả hai để UI chọn được.

--- VÌ SAO evaluated_at + ruleset_version ---
Hai trường này biến kết quả từ "một câu trả lời" thành "một kết luận TÁI LẬP ĐƯỢC".
DN in ra mang đi họp, 3 tháng sau bị hỏi "căn cứ đâu, lúc đó luật thế nào" —
không có chúng thì không ai trả lời được, kể cả chính đội.
Cũng là điều kiện cần để sau này audit engine.
"""

from enum import Enum

from grantpilot.models.rule import RuleResult

# TODO: Pydantic BaseModel. Hiện dùng dict thuần (đúng hình dạng JSON).


class EligibilityStatus(str, Enum):
    """5 trạng thái. Xem bảng ở docstring trên."""

    LIKELY_ELIGIBLE = "LIKELY_ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    NEED_MORE_INFO = "NEED_MORE_INFO"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    PROGRAM_UNAVAILABLE = "PROGRAM_UNAVAILABLE"


# Ánh xạ kết quả cây rule → trạng thái sản phẩm.
# PROGRAM_UNAVAILABLE KHÔNG có ở đây: nó đến từ program.availability (chuyện của chương trình),
# không đến từ rule (chuyện của doanh nghiệp).
STATUS_FROM_RULE_RESULT = {
    RuleResult.PASS: EligibilityStatus.LIKELY_ELIGIBLE,
    RuleResult.FAIL: EligibilityStatus.NOT_ELIGIBLE,
    RuleResult.UNKNOWN: EligibilityStatus.NEED_MORE_INFO,
    RuleResult.NEEDS_REVIEW: EligibilityStatus.NEEDS_HUMAN_REVIEW,
}
