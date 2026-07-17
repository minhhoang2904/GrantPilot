# benchmark/ — Đo lường & so sánh (chủ: Hoàng) ⭐ vũ khí ăn điểm

Không đo "chatbot trả lời hay". Đo bằng **metric rõ ràng** + so với RAG phẳng.

## File

| File | Nhiệm vụ |
|---|---|
| `test_questions.json` | Persona GreenVision AI + **6 test case có chủ đích** |
| `flat_rag.py` | RAG phẳng đối chứng (chunk+embed+top-k+LLM, KHÔNG eligibility) |
| `run_benchmark.py` | Chạy 6 case qua 2 hệ → bảng so sánh + chấm metric |

## 6 test case

| Case | Chứng minh năng lực |
|---|---|
| 1 — Đủ điều kiện rõ ràng | happy path, có citation, **tính được mức hỗ trợ** |
| 2 — Thiếu thông tin | **chống hallucination**: None≠False, hỏi lại đúng field, đúng người |
| 3 — Không đạt đk cứng | logic 4 giá trị: FAIL thắng UNKNOWN; phân biệt cứng/mềm |
| 4 — Thiếu hồ sơ | mô hình 2 tầng: đủ tư cách nhưng thiếu giấy tờ → checklist |
| 5 — Chương trình chưa rõ mở | ⭐ **quan trọng nhất**: đủ điều kiện ≠ chắc chắn nhận tiền |
| 6 — Hết hạn / xung khắc | loại hết hạn, cảnh báo xung khắc, **không cộng trùng** |

> Case 1 và Case 5 dùng **cùng hồ sơ**, chỉ khác `province`. Đó là chủ đích: nó chứng minh
> khác biệt đến từ *chương trình có mở ở tỉnh bạn không*, chứ không phải từ *bạn có đủ điều
> kiện không*. Hai câu đó khác nhau — và phân biệt được chúng chính là cả sản phẩm.

---

# ⭐ "Giải pháp của chúng ta có hiệu quả không?"

Câu này có **hai tầng**, đừng trộn. Trả lời được tầng 1 mà tưởng đã xong tầng 2 là tự lừa mình.

## Tầng 1 — Engine có làm đúng thiết kế không?

Đây là cái `run_benchmark.py` đo: chạy 6 case, so kết quả với khối `ky_vong`.

⚠️ **Giới hạn phải nói thẳng khi pitch:** benchmark này **tự chấm bài của chính mình**.
Ta viết rule, ta viết luôn `ky_vong`. PASS 6/6 chỉ chứng minh *engine implement đúng thiết kế
của ta* — **không** chứng minh *thiết kế của ta đúng luật*. Nếu ta hiểu sai Điều 5,
benchmark vẫn xanh lè.

Muốn có ground truth thật thì chỉ có một đường: **đưa N hồ sơ cho chuyên gia/cơ quan chấm
độc lập rồi so**. Chưa làm được thì đừng nói "đã kiểm chứng" — nói "đã tự kiểm tính nhất quán".

## Tầng 2 — Sản phẩm có giúp DN quyết định không? ⭐ tầng đáng tiền

### Cái bẫy chết người của bộ metric hiện tại

Bộ metric bên dưới **toàn là metric an toàn**. Thử baseline này:

```python
def answer(question, profile):
    return "Chưa đủ dữ liệu để kết luận. Bạn vui lòng liên hệ cơ quan có thẩm quyền."
```

Nó đạt **100% mọi metric Safety**: không bao giờ hallucinate, không bao giờ đoán bừa, không
bao giờ hứa được cấp tiền. Nó **thắng GrantPilot** ở mọi ô trong bảng so sánh cuối trang.
Và nó **hoàn toàn vô dụng**.

Chỉ đo an toàn = đang tối ưu về phía cái baseline đó. Tệ hơn: **hôm nay GrantPilot gần như
CHÍNH LÀ nó** — mọi rule `review_status: "draft"` (bị lọc → UNKNOWN), mọi `availability:
"unknown"` (→ PROGRAM_UNAVAILABLE), mọi `rate: null` (→ computable=false). Chạy benchmark
hôm nay, GrantPilot sẽ "an toàn" tuyệt đối và không trả lời được gì.

> **An toàn KHÔNG phải giá trị. An toàn là điều kiện CẦN.**
> Giá trị = trả lời được, **và** trả lời đúng, **và** biết lúc nào nên im.

### Metric bắt buộc phải thêm: Decision Yield

Đo tỉ lệ câu trả lời **hành động được** — user đọc xong biết phải làm gì tiếp:

| Loại kết quả | Hành động được? |
|---|---|
| `LIKELY_ELIGIBLE` + `computable=true` + có `submission.agency` | ✅ biết được bao nhiêu, nộp ở đâu |
| `NOT_ELIGIBLE` + `blocking_reason` + citation | ✅ biết trượt vì gì, khỏi mất công |
| `NEED_MORE_INFO` + `missing_fields` user **tự khai được** | ✅ khai một câu là xong |
| `NEED_MORE_INFO` vì `THRESHOLD_UNVERIFIED` | ❌ **lỗi của đội**, user bó tay |
| `PROGRAM_UNAVAILABLE` vì chưa xác minh tỉnh nào | ❌ **lỗi của đội** |
| `NEEDS_HUMAN_REVIEW` cho mọi thứ | ❌ đẩy hết việc về phía user |

```
decision_yield = số case hành động được / tổng số case
```

Hôm nay `decision_yield ≈ 0`. Đó là con số thật — ghi ra, đừng giấu.

⚠️ **Yield và Safety phải đọc CÙNG NHAU:**

|  | Safety thấp | Safety cao |
|---|---|---|
| **Yield cao** | con vẹt liều lĩnh — *chính là RAG phẳng* | ✅ sản phẩm |
| **Yield thấp** | vô dụng và còn sai | con vẹt lịch sự — *chính là ta, hôm nay* |

Báo cáo một con số mà giấu con kia là gian lận.

### Vì sao `decision_yield ≈ 0` KHÔNG phải lỗi engine

Là **lỗi dữ liệu** — và đó là tin tốt: engine đã đúng, chỉ thiếu số. Mọi mảnh thiếu đều nằm
ở `data/`, không nằm ở `src/`. Xem `test_questions.json` mục `_TRANG_THAI_CASE_1`: bốn thứ
cần xác minh để mở khoá Case 1.

> **Đòn bẩy lớn nhất của dự án lúc này KHÔNG phải viết thêm code.**
> Là hoàn thành **một lát cắt dọc**: 1 tỉnh × 1 program × số thật × review chéo xong.
> Lát cắt đó đưa `decision_yield` từ 0 lên khác 0 — ranh giới giữa "demo kiến trúc đẹp"
> và "sản phẩm".

### Câu giám khảo chắc chắn hỏi — chuẩn bị sẵn

> *"Vậy rốt cuộc nó có nói được doanh nghiệp tôi nhận bao nhiêu tiền không?"*

Trả lời trung thực, đừng vòng vo:

- **Đã có lát cắt dọc:** *"Có — với hỗ trợ X ở tỉnh Y: đây là số, đây là điều khoản, đây là
  nơi nộp."* Rồi nói thêm: 5 hỗ trợ còn lại chưa xác minh, và hệ thống **nói thẳng là chưa
  biết** thay vì đoán.
- **Chưa có:** *"Chưa. Hôm nay nó nói được bạn có thuộc diện không và thiếu gì, nhưng chưa
  nói được bao nhiêu tiền — vì chúng tôi chưa xác minh xong mức trần và chương trình ở tỉnh.
  Chúng tôi chọn không đoán."*

Câu thứ hai tệ hơn hẳn câu thứ nhất, nhưng vẫn tốt hơn một con số bịa, và nó cho thấy đội
hiểu ranh giới của chính mình. Đừng che nó bằng *"kiến trúc của chúng em có 5 trạng thái và
logic 4 giá trị"* — giám khảo hỏi giá trị, không hỏi sơ đồ.

---

## Metric chấm điểm

### Retrieval
- Program đúng có nằm trong **top 3** không?
- Citation dẫn **đúng điều/khoản** không?

### Eligibility
- Số điều kiện đánh giá đúng / tổng điều kiện
- Có phát hiện đúng **field bị thiếu** không?
- Có phân biệt **hard fail** vs **missing data** không?
- ⭐ Có phân biệt `legal_status` vs `status` không? (Case 5)

### Safety ⭐ (khác biệt lớn nhất vs RAG thường — nhưng xem cái bẫy ở trên)
- Không có nguồn → có **từ chối kết luận** không?
- Thiếu dữ liệu → có **hỏi lại** không (thay vì đoán)?
- Đủ điều kiện pháp lý → có **tránh hứa chắc được cấp tiền** không?
- ⭐ Group rỗng (rule bị lọc hết) → có **KHÔNG** trả LIKELY_ELIGIBLE không? (vacuous truth)

### Decision Yield ⭐ (đọc kèm Safety, không tách rời)
- `decision_yield` = tỉ lệ case hành động được
- Trong số case **không** hành động được: bao nhiêu vì **đội chưa xác minh** vs bao nhiêu vì
  **DN chưa khai**? Cái đầu là việc của đội; cái sau user khai một câu là xong.
- Có hỏi user đúng field user **tự trả lời được** không? (không hỏi `sme_size_category`,
  không hỏi field bị `THRESHOLD_UNVERIFIED`)

### Benefit calculation
- Tính đúng phần trăm?
- Áp đúng **mức trần**?
- Đúng đơn vị **tháng/năm/hợp đồng**?
- ⭐ Tra đúng **tier theo hạng DN** không?
- Có tránh **cộng trùng** quyền lợi không?

## Bảng so sánh mục tiêu (dán slide)

| Tình huống | RAG thường | GrantPilot |
|---|---|---|
| Thiếu dữ liệu | ❌ đoán bừa | ✅ NEED_MORE_INFO, hỏi lại đúng field |
| DN quá tuổi | ❌ trả lời chung chung | ✅ NOT_ELIGIBLE + trích dẫn điều khoản |
| "Chắc chắn nhận tiền chứ?" | ❌ hứa liều | ✅ PROGRAM_UNAVAILABLE + bước xác minh |
| 2 hỗ trợ xung khắc | ❌ cộng trùng | ✅ cảnh báo, chỉ tính một |
| **"Tôi được bao nhiêu?"** | ❌ bịa số | ⚠️ **cần lát cắt dọc — chưa xong thì cũng chịu** |

> ⚠️ **Dòng cuối là dòng trung thực nhất bảng — đừng xoá cho slide đẹp.**
> Bốn dòng trên chứng minh ta *an toàn hơn*. Chỉ dòng cuối chứng minh ta *hữu ích hơn*.
> Giám khảo tinh sẽ hỏi đúng vào đó.
