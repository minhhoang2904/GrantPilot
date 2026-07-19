"""User-facing, deterministic presentation of Server C decisions."""

from __future__ import annotations

from typing import Any

from policy_discovery import DiscoveryResult


_FIELD_LABELS = {
    "is_sme": "quy mô doanh nghiệp nhỏ và vừa",
    "primary_business_activity_group": "nhóm hoạt động kinh doanh chính",
    "sector": "lĩnh vực hoạt động",
    "social_insurance_employees": "số lao động tham gia BHXH",
    "annual_revenue_vnd": "doanh thu năm",
    "total_capital_vnd": "tổng nguồn vốn",
    "legal_form": "loại hình pháp lý",
    "first_business_registration_date": "ngày đăng ký kinh doanh lần đầu",
    "has_public_offering": "tình trạng chào bán chứng khoán ra công chúng",
}


def friendly_field(field: str) -> str:
    return _FIELD_LABELS.get(field, field.replace("_", " "))


def not_covered_answer(scope: DiscoveryResult) -> str:
    topics = ", ".join(scope.unsupported_topics) or "nội dung này"
    return (
        f"Hiện GrantPilot chưa thể đánh giá {topics} vì phạm vi tư vấn hiện tại chưa có "
        "chính sách tương ứng đã được chuẩn hóa và phê duyệt để đối chiếu theo hồ sơ.\n\n"
        "Điều này không có nghĩa là doanh nghiệp của bạn không đủ điều kiện; hệ thống "
        "chỉ chưa có đủ phạm vi dữ liệu để đưa ra kết luận đáng tin cậy.\n\n"
        "Hiện tôi có thể tư vấn theo hồ sơ về: hỗ trợ thông tin cho DNNVV, đào tạo "
        "khởi sự/quản trị doanh nghiệp, và hỗ trợ thuê hoặc mua giải pháp chuyển đổi số."
    )


def build_advisory_answer(
    scope: DiscoveryResult,
    results: list[dict[str, Any]],
) -> str:
    if scope.coverage_status == "not_covered":
        return not_covered_answer(scope)

    eligible = [result for result in results if result.get("status") == "eligible"]
    not_eligible = [result for result in results if result.get("status") == "not_eligible"]
    incomplete = [
        result for result in results if result.get("status") == "needs_more_information"
    ]
    manual = [result for result in results if result.get("status") == "manual_review"]

    lines = [f"Tôi đã đối chiếu hồ sơ của bạn với {len(results)} chính sách phù hợp với câu hỏi."]

    if eligible:
        lines.append("\nHồ sơ hiện tại đáp ứng các điều kiện đã được chuẩn hóa của:")
        lines.extend(f"- {result.get('policy_name') or result.get('policy_id')}" for result in eligible)

        lines.append("\nGợi ý ưu tiên:")
        for index, result in enumerate(eligible, start=1):
            title = result.get("policy_name") or result.get("policy_id")
            benefit = result.get("benefit_calculator") or {}
            benefit_text = benefit.get("note") or benefit.get("type")
            if benefit_text:
                lines.append(f"{index}. {title}: {benefit_text}")
            else:
                lines.append(f"{index}. {title}: nên xem trước vì hồ sơ hiện phù hợp.")

    if not_eligible:
        lines.append("\nChưa nên ưu tiên:")
        for result in not_eligible:
            title = result.get("policy_name") or result.get("policy_id")
            reasons = " ".join(str(reason) for reason in (result.get("reasons") or []))
            if "primary_business_activity_group" in reasons:
                reason = "hoạt động chính không thuộc nhóm sản xuất hoặc chế biến."
            elif "is_sme" in reasons:
                reason = "hồ sơ hiện không được xác định thuộc nhóm DNNVV."
            else:
                reason = "hồ sơ chưa phù hợp với một hoặc nhiều điều kiện của chính sách."
            lines.append(f"- {title}: {reason}")

    if incomplete:
        lines.append("\nCần bổ sung thông tin trước khi có thể kết luận:")
        for result in incomplete:
            title = result.get("policy_name") or result.get("policy_id")
            fields = ", ".join(
                friendly_field(field) for field in (result.get("missing_fields") or [])
            ) or "thông tin hồ sơ liên quan"
            lines.append(f"- {title}: {fields}.")

    if manual:
        lines.append("\nCần chuyên viên kiểm tra thêm:")
        lines.extend(f"- {result.get('policy_name') or result.get('policy_id')}" for result in manual)

    requirements = list(dict.fromkeys(
        requirement
        for result in eligible
        for requirement in (result.get("application_requirements") or [])
        if requirement
    ))
    if requirements:
        lines.append("\nViệc nên làm tiếp:")
        lines.extend(f"- {requirement}" for requirement in requirements)
        lines.append("- Mở căn cứ của từng chính sách bên dưới để kiểm tra thông tin trước khi chuẩn bị hồ sơ.")

    if scope.unsupported_topics:
        topics = ", ".join(scope.unsupported_topics)
        lines.append(
            f"\nPhần chưa thể đánh giá: {topics}. Phạm vi tư vấn hiện tại chưa có chính sách đã chuẩn hóa "
            "cho phần này; đây không phải kết luận doanh nghiệp không đủ điều kiện."
        )

    lines.append(
        "\nKết quả dựa trên hồ sơ hiện có và các chính sách đã được kiểm duyệt trong phạm vi hiện tại. "
        "Bạn có thể xem từng dòng bên dưới để kiểm tra căn cứ và yêu cầu cụ thể."
    )
    return "\n".join(lines)
