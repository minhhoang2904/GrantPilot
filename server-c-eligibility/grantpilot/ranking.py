"""
ranking.py — Xếp hạng program + tổng hợp + cảnh báo. (chủ: Hoàng)

rank_and_summarize(results: list[EligibilityResult], programs) -> dict

--- 1. Xếp hạng ---
  LIKELY_ELIGIBLE                     → đầu (trong nhóm: benefit cao lên trước)
  NEED_MORE_INFO (fixable)            → giữa
  NEEDS_HUMAN_REVIEW                  → giữa
  PROGRAM_UNAVAILABLE                 → gần cuối
  NOT_ELIGIBLE                        → cuối

  ⚠️ Trong nhóm PROGRAM_UNAVAILABLE, xếp theo `legal_status`: cái có
  legal_status=LIKELY_ELIGIBLE lên trước. Lý do: "bạn thuộc diện, chỉ cần gọi Sở hỏi
  xem có đang mở không" đáng chú ý hơn nhiều so với "bạn không thuộc diện, mà chương
  trình cũng chưa rõ mở". Xếp bằng `status` trơn thì hai thứ đó lẫn vào nhau.

--- 2. Cảnh báo xung khắc (Case 6) ---
  Nếu 2 program cùng LIKELY_ELIGIBLE mà conflicts_with nhau
    → thêm warning "chỉ được chọn một"
    → ⚠️ KHÔNG cộng trùng benefit của cả hai

--- 3. Tổng hợp giá trị ---
  Chỉ cộng benefit của program:
    - status == LIKELY_ELIGIBLE   (KHÔNG phải legal_status — chương trình chưa xác minh
                                   đang mở thì không được tính vào tổng "có thể nhận")
    - benefit_estimate.computable == True
    - đã loại xung khắc (mỗi nhóm xung khắc chỉ lấy 1 — chọn cái cao nhất)
  Nếu có program computable=False → ghi rõ "chưa tính được N hỗ trợ, cần xác minh"
  → KHÔNG im lặng bỏ qua, KHÔNG bịa.

  ⚠️ Tách `uncomputable` theo lý do (từ benefit_estimate.note):
     "đội chưa xác minh mức trần" vs "DN chưa khai chi phí" — cái sau user bấm một
     nút là ra số, cái trước thì không. Gộp chung thành "chưa tính được N hỗ trợ"
     là giấu mất việc user CÓ THỂ tự làm ngay.

--- ⚠️ Về ROI ---
Không gọi đây là "ROI" hay "tiền chắc chắn nhận được".
Gọi đúng: "giá trị hỗ trợ TIỀM NĂNG, ước tính sơ bộ, chưa phải cam kết cấp phát".
Đủ điều kiện pháp lý ≠ chắc chắn được cấp tiền.

--- ⚠️ Khi tổng = 0 thì PHẢI nói tại sao ---
Hiện tại mọi program đều `availability: unknown` và mọi `tiers.*.rate` đều null,
nên total_potential = 0 với MỌI doanh nghiệp. Nếu UI chỉ hiện "0 đ" thì sản phẩm
vô dụng và còn tệ hơn im lặng.

Bắt buộc trả kèm lý do phân biệt được ba trường hợp:
   a. "DN không thuộc diện"                    → NOT_ELIGIBLE, đúng là 0
   b. "đội chưa xác minh mức hỗ trợ/chương trình" → chưa biết, KHÔNG phải 0
   c. "DN chưa khai chi phí"                    → hỏi một câu là ra
Trả về 0 trơn cho cả ba = nói dối bằng con số. Đây đúng là lỗi ta chê RAG phẳng mắc phải,
chỉ khác là ta mắc nó một cách có tổ chức hơn.
"""

# TODO: hàm rank_and_summarize(results, programs) -> {ranked, total_potential, warnings, uncomputable}
