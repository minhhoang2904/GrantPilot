# Spec cho server-a (ingestion) và server-b (retrieval + chatbot)

> Đây là **ghi chú thiết kế**, không phải code. Cố tình KHÔNG dúi file vào `server-a-ingestion/`
> hay `server-b-retrieval/` — đó là folder của Thành và Huy, các bạn tự quyết cách hiện thực.
>
> Engine ở `server-c-eligibility/grantpilot/` đã code xong theo đúng các quy ước dưới đây.
> Contract giữa 3 service: `docs/contracts.md` · Tên trường: `docs/field-dictionary.md`

---

# SERVER A — Ingestion (Thành)

## Nhiệm vụ
Văn bản chính sách thô → hai đầu ra **song song**:

```
data thô (Luật 04/2017/QH14, NĐ 80/2021)
   ├──► shared/rulebook/*.json   (để XÉT — quan trọng hơn)
   └──► vector store             (để TÌM — thứ yếu, xem ghi chú server-b)
```

## Chunk: theo CẤU TRÚC, không cắt theo độ dài

Văn bản pháp lý VN có sẵn phân cấp `Chương → Điều → Khoản → Điểm` và viết rất khuôn mẫu
(regex bắt được). Cắt cứng mỗi 500 token sẽ:
- xé đôi một điều kiện → search ra nửa vô nghĩa
- gộp 2 khoản không liên quan → nhiễu
- **phá mất cấu trúc → không trích dẫn được điều/khoản**, mà trích dẫn là giá trị cốt lõi

Quy tắc:
1. **1 Khoản = 1 chunk** (Điều ngắn thì để nguyên Điều), ~100–400 từ.
2. **Chèn tiêu đề cha vào đầu chunk trước khi embed.** Một khoản tách rời hay mất ngữ cảnh
   ("Trường hợp này được miễn thêm 2 năm" — trường hợp nào?). Thêm một dòng
   `[NĐ 80/2021 – Điều 3: Ưu đãi… – Khoản 2]` là chất lượng search tăng rõ. Mẹo rẻ nhất.
3. **Metadata đầy đủ**: `program_id`, `dieu`, `khoan`, `loai_noi_dung`, `con_hieu_luc`,
   `ngay_hieu_luc` → dùng để lọc TRƯỚC khi search và để trích dẫn.
4. **`loai_noi_dung`**: `dieu_kien` | `uu_dai` | `thu_tuc` | `khac`.
   Chunk `dieu_kien` là chỗ bóc rule; chunk `uu_dai` là chỗ trả lời "được gì".

⚠️ **Chunk KHÔNG chứa rule.** Rule nằm ở cấp *program* trong `shared/rulebook/`, chunk ở cấp
*khoản*. Chunk chỉ mang `program_id` để tra ngược. Chép rule xuống từng chunk sẽ sinh 3 bệnh:
trùng lặp, sửa một chỗ quên chỗ khác, và xét eligibility lặp cho cùng một program.

## Bóc rule: LLM gợi ý, NGƯỜI quyết

`"Doanh nghiệp thành lập dưới 5 năm"` → `{field: "company_age_years", operator: "<=", value: 5}`

- LLM **chỉ gợi ý**. Rule chỉ được engine dùng khi `review_status = "manually_reviewed"`
  (2 người đồng ý — xem quy trình review chéo ở `shared/rulebook/README.md`).
- `field` sinh ra **phải có trong `field-dictionary.md`**, nếu không engine trả `UNKNOWN`
  âm thầm — không crash, chỉ sai.
- Điều kiện định tính ("có tính đổi mới sáng tạo") → `evaluation: "human_review"`,
  **đừng ép thành phép so sánh**.
- **Không có nguồn → không có rule.** Thiếu `source_document`/`article` thì bỏ.
- Số liệu (`value`, `rate`, `cap_amount`) **tuyệt đối không đoán** — thiếu để `null`.
  Engine trả `UNKNOWN` + warning, không bao giờ tự suy thành "DN không đủ điều kiện".

> Với 15–20 gói, **bóc tay hoặc bán tự động là hợp lý hơn** viết parser hoàn hảo.
> Giám khảo chấm kết quả demo, không chấm parser.

---

# SERVER B — Retrieval + Chatbot (Huy)

## ⚠️ Retrieval là THỨ YẾU trong scope MVP

MVP chỉ có **6 program**. Với 6 cái, **cứ xét hết cả 6** — nhanh hơn và không bao giờ bỏ sót.
Đừng để retrieval vô tình loại mất một program mà DN đủ điều kiện: đó là lỗi tệ nhất có thể,
vì nó im lặng.

Vector store còn đúng hai công dụng thật:
1. Trả lời câu hỏi tự do về nội dung văn bản ("điều kiện DNNVV là gì?")
2. Lấy đoạn văn để trích dẫn

→ Đừng dồn giờ đầu vào nó. `shared/rulebook/` mới là xương sống.

## Hybrid search
Vector giỏi ngữ nghĩa nhưng yếu với mã số/tên riêng ("NĐ 80/2021") — BM25 bù chỗ đó.
Lọc metadata (`con_hieu_luc`) **trước** khi search, đừng lọc sau.

**Metric:** program đúng phải nằm trong **top 3**; citation dẫn **đúng điều/khoản**.

## profile_builder — chỗ dễ phá cả hệ thống nhất

> ### `None` ≠ `False`. Đây là quy tắc quan trọng nhất của server-b.

User không nhắc tới một trường → để **`None`**, TUYỆT ĐỐI không suy thành `0`/`false`.

*"Không nói có bằng sáng chế"* ≠ *"không có bằng sáng chế"*.

Engine phân biệt hai cái này: `None` → `UNKNOWN` → `NEED_MORE_INFO` → chatbot hỏi lại.
Nếu profile_builder điền `false` thay cho `None`, engine sẽ trả `NOT_ELIGIBLE` — một DN đủ
điều kiện thật bị báo trượt, **và không ai biết**. Toàn bộ cơ chế chống hallucination của
server-c sụp đổ ngay tại đây.

Việc khác:
- **Trường dẫn xuất**: `company_age_years = năm nay − founded_year`.
  `sme_size_category` thì **KHÔNG tự tính** — `grantpilot/classifier.py` lo, user không khai được.
- Chuẩn hoá đơn vị theo `field-dictionary.md`: tiền = số nguyên VNĐ; tỉ lệ = thập phân (1% → 0.01).
- Nhận `missing_fields` từ `eligibility_result` → hỏi lại **đúng** field đó, hỏi theo nhóm nhỏ,
  đừng bắt user khai 15 trường một lúc.
- Trường ⏳ trong `field-dictionary.md` (`has_tax_debt`…) **không đưa vào form** cho tới khi có
  rule thật dùng tới. Hỏi mà không dùng = làm phiền DN và tạo ảo giác sản phẩm chặt chẽ hơn thực tế.

## answer_generator — LLM là người phát ngôn, không phải thẩm phán

LLM **chỉ diễn giải** dữ liệu engine đã tính đúng sẵn. **Không tự tính lại logic đủ/thiếu.**

Nói theo từng status (`eligibility_result.status`):

| Status | Cách nói |
|---|---|
| `LIKELY_ELIGIBLE` | *"Bạn **có khả năng** thuộc diện…"* — không nói "chắc chắn được nhận" |
| `NOT_ELIGIBLE` | nêu `blocking_reason` + trích dẫn điều khoản |
| `NEED_MORE_INFO` | hỏi đúng `missing_fields` / liệt kê `missing_documents` thành checklist |
| `NEEDS_HUMAN_REVIEW` | *"điều kiện này cần cơ quan xác minh"* + gợi ý liên hệ (`submission.agency`) |
| `PROGRAM_UNAVAILABLE` | nêu căn cứ pháp lý (có trong `legal_status` + `conditions`) + *"chưa xác định chương trình đang mở ở tỉnh bạn"* + bước xác minh |

Bắt buộc:
1. **Mỗi khẳng định gắn nguồn** từ `conditions[].source` ("Điều 17 Khoản 1 Điểm a, Luật 04/2017/QH14").
2. `benefit_estimate.computable == false` → nói *"chưa tính được, cần xác minh"*. **Không bịa số.**
3. Không tìm thấy program phù hợp → *"chưa tìm thấy"*. Không bịa.
4. **KHÔNG hứa chắc chắn được cấp tiền.** Đủ điều kiện pháp lý ≠ được cấp tiền.
5. Gọi tổng tiền là **"giá trị hỗ trợ tiềm năng, ước tính sơ bộ"** — không gọi là ROI hay
   "tiền chắc chắn nhận".

> Dùng `legal_status` để nói phần pháp lý, `status` để nói kết luận cuối. Nhờ tách hai trường
> này, một DN ở tỉnh chưa xác minh vẫn được nghe *"về pháp lý bạn thuộc diện, đây là căn cứ —
> nhưng chương trình ở tỉnh bạn thì tôi chưa xác minh được"*, thay vì im lặng.

## conversation — nhạc trưởng một lượt hỏi

```
1. profile_builder      → profile (chưa khai = None)
2. retriever            → program liên quan (MVP: lấy hết 6)
3. gọi server-c /check  → qualification (tầng 1) + eligibility_result × N (tầng 2)
4. answer_generator     → câu trả lời + trích dẫn
5. có missing_fields    → hỏi lại đúng field (vòng lặp làm giàu profile)
6. lưu profile + lịch sử vào session (bảng `profiles` trong shared/policy.db)
```
