"""
operators.py — Các phép so sánh nguyên thủy. (chủ: Hoàng)

Đây là nơi DUY NHẤT trong hệ thống được phép quyết định đúng/sai.
Thuần code, không LLM: `0.005 >= 0.01` luôn False, mãi mãi, không đổi ý.

10 toán tử: ==  !=  <  <=  >  >=  in  not_in  contains  not_contains

--- `in` vs `contains` — ngược chiều nhau, đừng nhầm ---
  in       : DN có MỘT giá trị, rule cho DANH SÁCH
             product_type ("software") in ["software", "ai"]
  contains : DN có DANH SÁCH, rule cho MỘT giá trị
             received_support_program_ids (["training"]) contains "training"
"""

from grantpilot.models.rule import RuleResult, UnknownReason

# Mỗi hàm nhận (giá_trị_của_DN, ngưỡng_trong_rule) -> bool
OPERATORS = {
    "==": lambda dn, nguong: dn == nguong,
    "!=": lambda dn, nguong: dn != nguong,
    "<": lambda dn, nguong: dn < nguong,
    "<=": lambda dn, nguong: dn <= nguong,
    ">": lambda dn, nguong: dn > nguong,
    ">=": lambda dn, nguong: dn >= nguong,
    "in": lambda dn, nguong: dn in nguong,
    "not_in": lambda dn, nguong: dn not in nguong,
    "contains": lambda dn, nguong: nguong in dn,
    "not_contains": lambda dn, nguong: nguong not in dn,
}


class UnknownOperatorError(ValueError):
    """Rule dùng toán tử không tồn tại → lỗi DATA, phải nổ to chứ không nuốt.

    Nuốt lỗi này thành UNKNOWN sẽ giấu một rule hỏng: nó im lặng không bao giờ
    xét được, mà không ai biết.
    """


def apply(field_value, operator, value):
    """So một giá trị của DN với ngưỡng trong rule.

    Trả về (RuleResult, UnknownReason | None).

    Thứ tự kiểm tra có chủ đích:

    1. Toán tử lạ           → NỔ (lỗi data, không được nuốt)
    2. value is None        → UNKNOWN/THRESHOLD_UNVERIFIED
       Ngưỡng trong rule còn trống = ĐỘI chưa xác minh từ văn bản gốc.
       Kiểm TRƯỚC field_value vì đây là lỗi của đội, không phải của user:
       hỏi user thêm cũng vô ích khi chính ta chưa biết ngưỡng là bao nhiêu.
    3. field_value is None  → UNKNOWN/MISSING_FIELD
       User chưa khai → hỏi lại được. Đây là đường sống của Case 2.
       ⚠️ `None` KHÁC `False`/`0`: "chưa khai" không bao giờ được tự suy thành "không đạt".
       Nhờ dùng `is None` (không phải falsy check), `0` và `False` vẫn là giá trị THẬT.
    4. So sánh lỗi kiểu     → UNKNOWN/TYPE_ERROR (không cho crash cả engine)
    """
    if operator not in OPERATORS:
        raise UnknownOperatorError(
            f"Toán tử không hợp lệ: {operator!r}. Hợp lệ: {sorted(OPERATORS)}"
        )

    if value is None:
        return RuleResult.UNKNOWN, UnknownReason.THRESHOLD_UNVERIFIED

    if field_value is None:
        return RuleResult.UNKNOWN, UnknownReason.MISSING_FIELD

    try:
        ok = OPERATORS[operator](field_value, value)
    except TypeError:
        # VD: so chuỗi với số, hoặc `contains` trên field không phải list.
        return RuleResult.UNKNOWN, UnknownReason.TYPE_ERROR

    return (RuleResult.PASS if ok else RuleResult.FAIL), None
