"""
logic.py — Logic BỐN GIÁ TRỊ + duyệt cây rule. (chủ: Hoàng) ⭐ trái tim engine

Xem docs/contracts.md mục C.

Module này KHÔNG biết gì về DNNVV, về chính sách, về hỗ trợ. Nó chỉ biết:
  - đi đệ quy trên một cây `all`/`any`
  - ở mỗi lá, nhờ operators.py so sánh
  - gộp kết quả con lên cha theo thứ tự ưu tiên
Toàn bộ tri thức pháp lý nằm ở DATA (qualification.json / programs.json), không ở đây.
"""

from dataclasses import dataclass, field
from datetime import date

from grantpilot import operators
from grantpilot.models.rule import USABLE_REVIEW_STATUSES, RuleResult, UnknownReason

# --- Thứ tự ưu tiên khi gộp con lên cha. Cái đứng trước thắng. ---
#
# all (AND): FAIL > UNKNOWN > NEEDS_REVIEW > PASS
#   FAIL thắng tất cả — một điều kiện đã trượt rõ ràng thì thiếu dữ liệu ở chỗ khác
#   cũng vô nghĩa. Đây chính là Case 3: DN 7 tuổi → NOT_ELIGIBLE ngay, không lằng nhằng
#   hỏi doanh thu. Nếu đảo lại (UNKNOWN thắng FAIL), sản phẩm sẽ tra tấn user bằng một
#   loạt câu hỏi rồi cuối cùng vẫn báo trượt vì cái tuổi biết ngay từ đầu.
#
#   UNKNOWN trên NEEDS_REVIEW — hỏi user là bước RẺ NHẤT (một câu chat).
#   Chỉ đẩy lên "cần cơ quan xác minh" khi user đã khai hết những gì khai được.
#
# any (OR): PASS > UNKNOWN > NEEDS_REVIEW > FAIL
#   Một nhánh đạt là đủ, khỏi xét nhánh còn lại. Đây là lý do startup phần mềm qua được
#   nhánh `product_type in [software...]` mà không cần chạm tới nhánh `is_innovative`
#   (vốn là human_review).
_ALL_PRIORITY = (RuleResult.FAIL, RuleResult.UNKNOWN, RuleResult.NEEDS_REVIEW, RuleResult.PASS)
_ANY_PRIORITY = (RuleResult.PASS, RuleResult.UNKNOWN, RuleResult.NEEDS_REVIEW, RuleResult.FAIL)


@dataclass
class EvalContext:
    """Bối cảnh một lần xét. Gom vào đây để hàm khỏi mang 5 tham số.

    evaluated_at     : xét tại thời điểm nào → lọc rule theo hiệu lực.
                       Cho phép truyền vào (không dùng date.today() cứng) để test tái lập được
                       và để sau này trả lời "hồi tháng 3 luật thế nào".
    require_reviewed : True = chỉ dùng rule đã review chéo. MẶC ĐỊNH TRUE, và đây là
                       mặc định AN TOÀN — xem ghi chú "cổng review" bên dưới.
    warnings         : nơi gom mọi thứ bị bỏ qua. Không có cái gì được biến mất âm thầm.
    """

    evaluated_at: date
    require_reviewed: bool = True
    warnings: list = field(default_factory=list)


def combine(results, mode):
    """Gộp kết quả các node con lên node cha.

    Thuật toán: duyệt bảng ưu tiên, gặp cái nào có mặt trong `results` thì trả cái đó.

    --- GROUP RỖNG → UNKNOWN (không phải PASS) ⚠️ quan trọng nhất file này ---
    Toán học thuần túy thì `all([])` là True (vacuous truth). Ở đây làm vậy là THẢM HỌA:
    nếu mọi rule của một group đều bị lọc (chưa review xong / hết hiệu lực), group thành rỗng
    → PASS → LIKELY_ELIGIBLE → sản phẩm tuyên "bạn đủ điều kiện!" trong khi nó
    KHÔNG KIỂM TRA GÌ CẢ.

    "Không có điều kiện nào để kiểm" ≠ "đã kiểm và đạt".
    Vắng mặt căn cứ phải nghiêng về phía thận trọng, luôn luôn.
    """
    if not results:
        return RuleResult.UNKNOWN

    priority = _ALL_PRIORITY if mode == "all" else _ANY_PRIORITY
    for r in priority:
        if r in results:
            return r
    return RuleResult.UNKNOWN


def is_group(node):
    return isinstance(node, dict) and ("all" in node or "any" in node)


def _parse_date(value):
    """ISO date → date, hoặc None nếu không parse được.

    Data đang đầy "<TODO>" nên hàm này phải chịu được rác mà không nổ.
    """
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None  # "<TODO>", "" ... → coi như chưa xác minh


def _skip_reason(leaf, ctx):
    """Rule này có bị loại khỏi lần xét không? Trả lý do (str) hoặc None.

    HAI CỔNG LỌC, phục vụ hai mục đích khác nhau:

    1. Cổng review — chống "rule chưa ai kiểm mà đã đem đi kết luận".
       Data hiện tại review_status="draft" hết → cổng này lọc sạch → mọi group rỗng
       → UNKNOWN → NEED_MORE_INFO. Nghe như hỏng, nhưng đó chính là hành vi ĐÚNG:
       chưa ai review rule thì engine không có quyền tuyên bố gì. Bật
       require_reviewed=False chỉ khi test.

    2. Cổng hiệu lực — chống dùng điều khoản đã hết hiệu lực.
       Ngày không parse được ("<TODO>") thì KHÔNG loại rule, chỉ cảnh báo. Lý do:
       effective_from trống là chuyện data chưa hoàn thiện, mà cổng review đã bắt
       trường hợp đó rồi. Hai cổng cùng chặn một thứ thì thừa, và sẽ làm rule biến mất
       vì lý do sai.
    """
    rule_id = leaf.get("rule_id", "<không có rule_id>")

    if ctx.require_reviewed and leaf.get("review_status") not in USABLE_REVIEW_STATUSES:
        return (
            f"Rule '{rule_id}' bị bỏ qua: review_status="
            f"{leaf.get('review_status')!r}, chưa qua review chéo."
        )

    ef = _parse_date(leaf.get("effective_from"))
    et = _parse_date(leaf.get("effective_to"))

    if ef and ctx.evaluated_at < ef:
        return f"Rule '{rule_id}' bị bỏ qua: chưa có hiệu lực (từ {ef})."
    if et and ctx.evaluated_at > et:
        return f"Rule '{rule_id}' bị bỏ qua: đã hết hiệu lực ({et})."

    if leaf.get("effective_from") and ef is None:
        ctx.warnings.append(
            f"Rule '{rule_id}': effective_from={leaf.get('effective_from')!r} "
            f"không phải ngày hợp lệ — chưa xác minh được hiệu lực."
        )
    return None


def _source_of(leaf):
    """Ghép trích dẫn. Mọi kết luận phải trỏ về được điều/khoản gốc."""
    article = leaf.get("article") or "<chưa có điều khoản>"
    doc = leaf.get("source_document") or "<chưa có văn bản>"
    return f"{article}, {doc}"


def _evaluate_leaf(node, profile, ctx):
    """Xét một điều kiện. Trả (RuleResult | None, list[ConditionResult]).

    None = rule bị loại (đã ghi warning) → node cha không tính nó vào.
    """
    skip = _skip_reason(node, ctx)
    if skip:
        ctx.warnings.append(skip)
        return None, []

    field_name = node.get("field")
    current_value = profile.get(field_name)

    condition = {
        "rule_id": node.get("rule_id"),
        "description": node.get("description"),
        "current_value": current_value,
        "hard": bool(node.get("hard", False)),
        "missing_field": None,
        "unknown_reason": None,
        "source": _source_of(node),
    }

    # Điều kiện định tính ("có tính đổi mới sáng tạo") — máy KHÔNG được tự quyết.
    # Kiểm TRƯỚC khi so sánh: dù profile có sẵn giá trị, ta vẫn không nhận thẩm quyền
    # kết luận thay cơ quan. Ép thứ này thành phép so sánh là tự lừa mình.
    if node.get("evaluation") == "human_review":
        condition["result"] = RuleResult.NEEDS_REVIEW.value
        return RuleResult.NEEDS_REVIEW, [condition]

    result, reason = operators.apply(current_value, node.get("operator"), node.get("value"))
    condition["result"] = result.value

    if reason is not None:
        condition["unknown_reason"] = reason.value
        # Chỉ coi là "user thiếu khai" khi đúng là user thiếu khai.
        # THRESHOLD_UNVERIFIED là lỗi của ĐỘI (ngưỡng còn null) — đẩy vào missing_field
        # sẽ khiến chatbot đi hỏi user một câu mà user không thể trả lời.
        if reason is UnknownReason.MISSING_FIELD:
            condition["missing_field"] = field_name
        elif reason is UnknownReason.THRESHOLD_UNVERIFIED:
            ctx.warnings.append(
                f"Rule '{node.get('rule_id')}': ngưỡng (value) còn trống — chưa xác minh từ văn bản gốc."
            )
        elif reason is UnknownReason.TYPE_ERROR:
            ctx.warnings.append(
                f"Rule '{node.get('rule_id')}': lỗi kiểu dữ liệu khi so "
                f"{current_value!r} {node.get('operator')} {node.get('value')!r}."
            )

    return result, [condition]


def evaluate_node(node, profile, ctx):
    """Duyệt đệ quy một node bất kỳ. Trả (RuleResult | None, list[ConditionResult]).

    Đây là toàn bộ "trí tuệ" của engine: đi xuống lá, so sánh, gộp ngược lên.
    """
    if not is_group(node):
        return _evaluate_leaf(node, profile, ctx)

    mode = "all" if "all" in node else "any"
    children = node[mode] or []

    child_results = []
    conditions = []
    for child in children:
        result, child_conditions = evaluate_node(child, profile, ctx)
        conditions.extend(child_conditions)
        if result is not None:  # None = bị loại, không tính vào phép gộp
            child_results.append(result)

    if not child_results:
        # Mọi con đều bị loại (hoặc group vốn rỗng) → không có căn cứ nào để kết luận.
        ctx.warnings.append(
            f"Nhóm '{mode}' không còn điều kiện nào xét được "
            f"(bị lọc hết hoặc rỗng) → UNKNOWN."
        )
        return RuleResult.UNKNOWN, conditions

    return combine(child_results, mode), conditions
