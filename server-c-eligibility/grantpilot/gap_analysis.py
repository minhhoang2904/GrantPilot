"""
gap_analysis.py — Phân tích khoảng cách. (chủ: Hoàng) ⭐ ăn điểm

Biến "chưa đủ điều kiện" thành lời khuyên hành động được.

analyze(result: EligibilityResult) -> EligibilityResult (đã bổ sung)

Nhiệm vụ theo từng loại ConditionResult:

  FAIL + hard=True   → không khắc phục được (VD 7 tuổi > 5 năm)
                       → fixable=False, blocking_reason="<điều kiện>" (Case 3)
                       → kèm trích dẫn điều khoản

  FAIL + hard=False  → sinh gợi ý cải thiện cụ thể
                       → "hiện tại X, cần Y"

  UNKNOWN            → PHẢI rẽ theo `unknown_reason` (xem models/rule.py) ⚠️
                       → TUYỆT ĐỐI không đoán, không kết luận bừa

  NEEDS_REVIEW       → ghi rõ "điều kiện này cần cơ quan/chuyên gia xác minh"
                       → gợi ý bước: liên hệ ai (lấy từ result.submission.agency), nộp gì

  Thiếu hồ sơ        → missing_documents → checklist bổ sung (Case 4)

--- ⚠️ UNKNOWN KHÔNG PHẢI MỘT LOẠI — RẼ THEO unknown_reason ---
Đây là chỗ dễ sai nhất file này. Bốn lý do → bốn hành động khác hẳn nhau:

  MISSING_FIELD        → missing_fields += [field] → chatbot hỏi user (Case 2)
                         USER làm được. Đây là đường sống của Case 2.
  THRESHOLD_UNVERIFIED → KHÔNG đưa vào missing_fields.
                         Ngưỡng còn trống là lỗi của ĐỘI — hỏi user vô ích và làm user
                         tưởng lỗi ở họ. Đưa vào warnings: "điều kiện này chưa xác minh
                         được ngưỡng từ văn bản gốc".
  NO_EVALUABLE_RULE    → KHÔNG hỏi user gì cả. Nói thật: "chưa đủ căn cứ đã được review
                         để kết luận về hỗ trợ này".
  TYPE_ERROR           → lỗi data → warnings, không làm phiền user.

Trộn cả bốn vào missing_fields = chatbot sẽ hỏi user những câu user không thể trả lời,
và giấu đi phần việc của đội. Đó là cách nhanh nhất biến một engine trung thực thành
một con vẹt lịch sự.

--- province ---
Thiếu `province` → missing_fields += ["province"], hỏi user như MISSING_FIELD thường.
Nhưng thông điệp phải nói RÕ vì sao cần: "để biết chương trình ở tỉnh bạn có đang mở
nhận hồ sơ không", chứ không phải hỏi khơi khơi.

fixable = True khi MỌI điều kiện FAIL đều có hard=False.

Thông điệp mẫu:
  "Bạn thuộc diện DNNVV KNST (4/4, hạng: nhỏ). Với hỗ trợ thuê coworking: đạt 2/3,
   còn thiếu hợp đồng thuê mặt bằng. Bổ sung giấy tờ này là có thể nộp hồ sơ."
"""

# TODO: hàm analyze(result) -> EligibilityResult
