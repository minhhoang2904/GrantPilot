"""
Schema `rule` — cây điều kiện, dùng chung cả 2 tầng. Xem docs/contracts.md mục B.

Một rule tree gồm 2 loại node:

  LEAF — một điều kiện cụ thể
    class Condition:
        rule_id: str              # 🔑 định danh, để trace
        field: str                # tên trường DN — phải có trong field-dictionary.md
        operator: str             # "==" "!=" "<" "<=" ">" ">=" "in" "not_in"
                                  # "contains" | "not_contains"  ⭐ mới (field là list)
        value: Any                # ngưỡng

        description: str          # diễn giải tiếng người
        hard: bool                # True = không khắc phục được (tuổi) → gap analysis
        evaluation: str           # "auto" | "human_review"

        # --- provenance: BẮT BUỘC, không có thì rule không được dùng ---
        source_document: str      # "Luật 04/2017/QH14"
        article: str              # "Điều 17, Khoản 1, Điểm a"
        source_url: str
        interpretation_note: str  # đội hiểu điều khoản này thế nào
        review_status: str        # "draft" | "manually_reviewed" | "expert_reviewed"
                                  # chỉ manually_reviewed trở lên mới bật trong demo

        # --- hiệu lực ⭐ mới ---
        effective_from: str|None  # ISO "YYYY-MM-DD"
        effective_to: str | None  # None = còn hiệu lực
        # Engine bỏ qua rule không còn hiệu lực tại result.evaluated_at,
        # GHI LOG + đẩy vào result.warnings. Không được biến mất âm thầm.
        # Vì sao: văn bản bị sửa đổi/thay thế. Không có mốc thời gian thì kết luận
        # lưu tháng trước không tái lập được.

  GROUP — gộp nhiều node (lồng nhau tùy ý)
    { "all": [node, node, ...] }   # AND
    { "any": [node, node, ...] }   # OR

Kết quả đánh giá mỗi node KHÔNG phải bool mà là 1 trong 4:
    PASS | FAIL | UNKNOWN | NEEDS_REVIEW
Xem src/eligibility/logic.py cho quy tắc gộp.

--- ĐIỀU KIỆN KHÔNG VIẾT ĐƯỢC BẰNG LEAF (xem contracts.md mục B3) ---
`value` là scalar, nên leaf KHÔNG biểu diễn được "ngưỡng phụ thuộc trường khác"
(VD: ngưỡng DNNVV phụ thuộc lĩnh vực — NĐ 80 Điều 5).
→ Đừng nhồi vào rule tree bằng any[ all[sector==X, employees<=Y] ] (nổ tổ hợp,
  provenance bị lặp và lệch). Dùng bảng tra + trường dẫn xuất: src/eligibility/classifier.py.
"""

from enum import Enum

# TODO: Pydantic — Condition, RuleGroup (all/any), union RuleNode.
# Hiện làm việc trực tiếp trên dict (đúng hình dạng JSON) để khỏi tầng chuyển đổi.


class RuleResult(str, Enum):
    """Kết quả đánh giá MỘT node. Bốn giá trị, không phải bool.

    Vì sao không bool: bool ép engine phải kết luận kể cả khi không đủ căn cứ.
    Trong domain pháp lý, "chưa biết" và "không đạt" là hai chuyện khác hẳn —
    gộp chúng lại chính là hallucination.
    """

    PASS = "PASS"                  # so sánh đúng
    FAIL = "FAIL"                  # so sánh sai
    UNKNOWN = "UNKNOWN"            # chưa đủ căn cứ để kết luận
    NEEDS_REVIEW = "NEEDS_REVIEW"  # cần người/cơ quan xác minh, máy không tự quyết


class UnknownReason(str, Enum):
    """Vì sao UNKNOWN. Quan trọng: mỗi lý do dẫn tới một HÀNH ĐỘNG khác nhau.

    Gộp chung thì gap_analysis sẽ hỏi user những thứ user không trả lời được.
    """

    MISSING_FIELD = "missing_field"                  # user chưa khai → HỎI USER được
    THRESHOLD_UNVERIFIED = "threshold_unverified"    # rule.value còn null → LỖI CỦA ĐỘI, hỏi user vô ích
    NO_EVALUABLE_RULE = "no_evaluable_rule"          # group rỗng sau khi lọc → không có căn cứ nào
    TYPE_ERROR = "type_error"                        # dữ liệu sai kiểu → lỗi data


# review_status đủ điều kiện để engine dùng. `draft` bị lọc.
USABLE_REVIEW_STATUSES = frozenset({"manually_reviewed", "expert_reviewed"})
