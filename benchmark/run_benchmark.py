"""
run_benchmark.py — Chạy 6 test case qua 2 hệ + chấm metric. (chủ: Hoàng)

Chạy: python -m benchmark.run_benchmark

Trình tự:
  1. Đọc benchmark/test_questions.json (persona + 6 case)
  2. Với mỗi case: lấy persona_mac_dinh, áp profile_override → profile
  3. Chạy qua GrantPilot (conversation.handle_message) và flat_rag.answer()
  4. So kết quả GrantPilot với khối `ky_vong` → PASS/FAIL từng case
  5. In bảng so sánh cạnh nhau + tổng hợp metric

Metric xuất ra (xem README):
  - Retrieval : program đúng trong top 3? citation đúng điều/khoản?
  - Eligibility: điều kiện đánh giá đúng / tổng; phát hiện đúng missing field?
                 phân biệt hard fail vs missing data? phân biệt legal_status vs status?
  - Safety    : từ chối kết luận khi thiếu nguồn? hỏi lại khi thiếu data?
                tránh hứa chắc được cấp tiền? group rỗng KHÔNG ra LIKELY_ELIGIBLE?
  - Yield ⭐  : decision_yield — xem bên dưới
  - Benefit   : đúng %? đúng mức trần? đúng chu kỳ? đúng tier theo hạng? không cộng trùng?

--- ⭐ BẮT BUỘC IN decision_yield CẠNH safety ---
Chỉ in metric Safety là tự lừa mình: một hàm trả "chưa đủ dữ liệu để kết luận" cho MỌI câu hỏi
sẽ đạt 100% Safety và thắng GrantPilot ở mọi ô — trong khi hoàn toàn vô dụng.
Xem README mục "Cái bẫy chết người của bộ metric hiện tại".

    decision_yield = số case HÀNH ĐỘNG ĐƯỢC / tổng số case

Hành động được =
    - LIKELY_ELIGIBLE + benefit.computable + có submission.agency, HOẶC
    - NOT_ELIGIBLE + blocking_reason + citation, HOẶC
    - NEED_MORE_INFO mà MỌI missing_field đều là thứ USER TỰ KHAI ĐƯỢC

KHÔNG tính là hành động được (đều là việc của ĐỘI, user bó tay):
    - UNKNOWN vì THRESHOLD_UNVERIFIED / NO_EVALUABLE_RULE
    - PROGRAM_UNAVAILABLE vì chưa xác minh tỉnh nào
    - benefit computable=false vì rate/cap còn null

--- ⭐ TÁCH LÝ DO KHI KHÔNG ĐẠT YIELD ---
Với mỗi case fail yield, phân loại vào ĐÚNG MỘT nhóm và in ra:
    "doi_chua_xac_minh"  → data/ còn null: đội phải đi đọc văn bản / gọi Sở
    "dn_chua_khai"       → user khai thêm là xong
    "dn_khong_thuoc_dien"→ kết luận thật, không phải thiếu sót

Gộp cả ba thành "chưa tính được N hỗ trợ" là giấu mất phần việc user CÓ THỂ tự làm ngay,
và giấu luôn phần việc của đội. Bảng này chính là to-do list của dự án.

--- ⚠️ KỲ VỌNG HÔM NAY: gần như mọi case FAIL ---
Mọi rule đang review_status="draft" → bị lọc → group rỗng → UNKNOWN.
Mọi availability="unknown" → PROGRAM_UNAVAILABLE. Mọi tiers.*.rate=null → computable=false.
→ decision_yield ≈ 0, và Case 1 chắc chắn FAIL.

ĐÂY LÀ HÀNH VI ĐÚNG, KHÔNG PHẢI BUG. Đừng "sửa" bằng cách hạ require_reviewed=False rồi
điền bừa số cho benchmark xanh — làm vậy là biến benchmark thành đồ trang trí và phá luôn
nguyên tắc "không có nguồn → không có rule".

Cách mở khoá: hoàn thành 1 lát cắt dọc thật (1 tỉnh × 1 program × số thật × review chéo).
Xem test_questions.json mục _TRANG_THAI_CASE_1.

--- ⚠️ Benchmark này TỰ CHẤM BÀI CỦA CHÍNH MÌNH ---
Ta viết rule, ta viết luôn `ky_vong`. PASS 6/6 chỉ chứng minh engine implement đúng THIẾT KẾ
của ta — không chứng minh thiết kế đúng LUẬT. In kèm dòng cảnh báo này ở cuối báo cáo để
không ai (kể cả ta) đọc nhầm con số.
"""

# TODO: vòng lặp 6 case + chấm metric + decision_yield + in bảng
