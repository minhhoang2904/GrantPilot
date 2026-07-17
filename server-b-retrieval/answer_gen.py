"""
server-b-retrieval / answer_gen.py

Sinh câu trả lời cho người dùng dựa trên các policy đã tra cứu được.

Hiện tại dùng template đơn giản (không cần API key) để mọi người có thể chạy demo
end-to-end ngay. TODO: thay bằng LLM call (OpenAI/khác) khi có API key, đọc từ
biến môi trường (vd: OPENAI_API_KEY), giữ nguyên signature generate_answer().
"""

from typing import Any


def generate_answer(question: str, policies: list[dict[str, Any]]) -> str:
    if not policies:
        return (
            "Không tìm thấy chính sách phù hợp với câu hỏi của bạn. "
            "Vui lòng thử diễn đạt lại hoặc cung cấp thêm thông tin về doanh nghiệp."
        )

    lines = [f"Dựa trên câu hỏi \"{question}\", đây là các chính sách liên quan:\n"]
    for i, policy in enumerate(policies, start=1):
        lines.append(f"{i}. **{policy['title']}**")
        if policy.get("summary"):
            lines.append(f"   {policy['summary']}")
        if policy.get("source_url"):
            lines.append(f"   Nguồn: {policy['source_url']}")
        lines.append("")

    lines.append(
        "Gợi ý: cung cấp hồ sơ doanh nghiệp (ngành, số lao động, doanh thu, tỉnh/thành) "
        "để kiểm tra điều kiện hưởng cụ thể."
    )
    return "\n".join(lines)
