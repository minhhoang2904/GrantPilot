# data/ — Dữ liệu chính sách (chủ: Thành)

> ⭐ **Đọc `_TRANG_THAI_CASE_1` trong `benchmark/test_questions.json` trước.**
> Thư mục này đang là **nút thắt của cả dự án**: engine đã xong phần lớn, nhưng mọi
> `value`/`rate`/`availability` còn trống nên sản phẩm chưa trả lời được gì.
> Đòn bẩy lớn nhất lúc này nằm ở đây, không nằm ở `src/`.

## Scope MVP
Persona: **startup phần mềm/công nghệ VN ≤ 5 năm**.
Nhóm chính sách: **hỗ trợ DNNVV khởi nghiệp sáng tạo**.
Nguồn: **Luật 04/2017/QH14** + **Nghị định 80/2021/NĐ-CP** (+ 1 văn bản triển khai nếu tìm được).

Không đưa vào MVP: ưu đãi thuế, FDI, vay vốn, đất đai, các quỹ tài trợ khác.

## Nội dung thư mục

| Đường dẫn | Là gì |
|---|---|
| `raw/` | Văn bản gốc tải về (.txt/.pdf). Đầu vào ingestion. |
| `sme_classification.json` | ⭐ **TẦNG 0** — bảng tra hạng DNNVV (Điều 5): lĩnh vực × siêu nhỏ/nhỏ/vừa. |
| `qualification.json` | **TẦNG 1** — bộ rule xác định tư cách "DNNVV khởi nghiệp sáng tạo". Chỉ 1 bộ. |
| `programs.json` | **TẦNG 2** — 6 loại hỗ trợ, mỗi cái có rule + hồ sơ + mức trần + availability theo tỉnh. |
| `vector_store/` | (sinh tự động) Chroma. Không commit. |

## ⚠️ Luật bất di bất dịch

> **Không có nguồn → không có rule.**
> Mọi condition phải có `source_document` + `article` + `source_url` thật.
> Số liệu (`value`, `rate`, `cap_amount`) **tuyệt đối không đoán** — thiếu thì để `null`.

`null` không làm hỏng gì: engine trả `UNKNOWN` + ghi warning "chưa xác minh", và **không bao
giờ** tự suy thành "DN không đủ điều kiện". Điền bừa mới làm hỏng — nó tạo ra kết luận sai
mà trông như đúng.

## Quy trình review chéo (bắt buộc, không có domain expert nên phải bù bằng quy trình)

1. **Thành** đọc văn bản gốc → bóc rule → `review_status: "draft"`
2. **Hoàng** đọc lại NGUYÊN VĂN điều khoản → kiểm logic có khớp `interpretation_note` không
3. **Huy** kiểm citation hiển thị ra UI có đúng điều/khoản không
4. Hai người đồng ý → `review_status: "manually_reviewed"` → rule mới được engine dùng
5. Điều kiện mơ hồ/định tính → `evaluation: "human_review"`, KHÔNG cố ép thành phép so sánh

❌ Không để một người vừa đọc, vừa diễn giải, vừa tự xác nhận.

> ⚠️ Hiện **100% rule đang là `draft`** → engine lọc sạch → mọi group rỗng → `UNKNOWN`.
> Đó là hành vi đúng (chưa ai review thì engine không có quyền kết luận), nhưng nó có nghĩa
> **demo hôm nay trả về rỗng**. Bước 4 là bước mở khoá, không phải thủ tục hình thức.

---

## ⭐ Nhiệm vụ Thành — theo thứ tự

### Ưu tiên 0 — MỘT LÁT CẮT DỌC, không phải phủ rộng
Đừng điền đều 6 program. Làm **đúng 1 tỉnh × 1 program** chạy thông từ đầu tới cuối:

```
sme_classification (ngưỡng Điều 5 + map lĩnh vực)
  → qualification.json (4 rule, review xong)
    → programs.json: coworking_rent_support
        → benefit.tiers[hạng].rate + cap_amount     ← số thật
        → availability.by_province[<tỉnh>] = open   ← gọi Sở KH&ĐT xác minh
        → submission.agency + where                 ← nộp ở đâu
```

Xong lát cắt này thì Case 1 PASS và `decision_yield` khác 0 — ranh giới giữa "demo kiến trúc"
và "sản phẩm". Xem `benchmark/README.md` mục "Giải pháp có hiệu quả không".

### 1. Tải văn bản
Luật 04/2017/QH14 + NĐ 80/2021/NĐ-CP vào `raw/`.

### 2. `sme_classification.json` — làm TRƯỚC qualification
Tầng 1 phụ thuộc nó (rule `is_dnnvv` đọc `sme_size_category`).
- Điền `criteria[lĩnh vực][hạng]`: ngưỡng LĐ BHXH + doanh thu + nguồn vốn.
- ⭐ Điền `sector_to_linh_vuc` — **map sai là toàn bộ tầng 1 sai, mà sai im lặng.**
  `information_technology` thuộc lĩnh vực nào của NĐ 80? **Không tự quyết** — hỏi chuyên gia.

### 3. `qualification.json` (tầng 1)
4 rule: `is_dnnvv`, `startup_age_limit`, `not_public_offering`, nhóm `any` tính đổi mới.
Điền provenance đầy đủ + `effective_from`/`effective_to`.
Ghi `interpretation_note` **trung thực** — đội hiểu sao ghi vậy, để chuyên gia soi được.

### 4. `programs.json` — coworking trước
- `benefit.tiers`: điền **đủ cả 3 hạng**. Nếu văn bản KHÔNG phân biệt hạng → vẫn điền cả 3
  giống nhau và **ghi rõ ở `note` rằng đã đọc và xác nhận** văn bản không phân biệt.
  Để trống rồi ngầm giả định là đúng thứ quy trình này sinh ra để chặn.
- `benefit.basis_field`: trỏ đúng trường chi phí trong `field-dictionary.md`.
  Thiếu nó thì **không bao giờ tính ra tiền**, dù rate/cap đã điền đủ.
- `availability.by_province`: chỉ điền tỉnh đã **thật sự xác minh**. Tỉnh khác rơi vào
  `default` → `unknown` → `PROGRAM_UNAVAILABLE`. Đó là đúng, không phải thiếu sót —
  ta thà nói "chưa xác minh ở tỉnh bạn" còn hơn suy từ tỉnh khác sang.
- `submission`: agency + where + forms. Đây là câu "rồi sao nữa?" của DN.
- ⚠️ Loại hỗ trợ nào là **hiện vật** (suất đào tạo, gian hàng) → `type: "in_kind"`,
  KHÔNG quy đổi ra tiền. Đọc văn bản rồi quyết, đừng mặc định `percentage_of_cost`.

### 5. Đất diễn cho test case
- Case 5: cần 1 tỉnh **chưa xác minh** (đã có sẵn: `can_tho` → rơi vào `default`).
- Case 6: cần 1 program `availability.by_province[<tỉnh Case 1>].status = "closed"`
  và 1 cặp `conflicts_with` nhau.

---

## ⭐ Câu hỏi mang đi hỏi chuyên gia (30–60 phút là đủ)

Xếp theo mức độ chặn tiến độ:

1. **`information_technology` thuộc lĩnh vực nào của NĐ 80 Điều 5?**
   (nông-lâm-thủy sản & công nghiệp-xây dựng | thương mại-dịch vụ)
   → Chặn cả tầng 0 và tầng 1. Hỏi câu này trước.
2. Chúng tôi hiểu điều kiện này đúng chưa? (đưa `interpretation_note` cho họ đọc)
3. Điều kiện nào **không thể** tự động kết luận?
4. Mức hỗ trợ có **khác nhau theo hạng** siêu nhỏ/nhỏ/vừa không?
5. Hồ sơ nào thường dùng để chứng minh?
6. "Đủ điều kiện" có đồng nghĩa được nhận hỗ trợ không?
7. **Cơ quan nào tiếp nhận hồ sơ, ở tỉnh thì liên hệ ai?**
   → Chặn `availability` + `submission`, tức chặn Case 1.
8. Có yêu cầu **không nợ thuế / không vi phạm** không? Có giới hạn **số lần nhận** không?
   → Đang là field ⏳ trong `field-dictionary.md`, chờ nguồn mới bật rule.
