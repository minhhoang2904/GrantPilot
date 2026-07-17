# Đề xuất: engine eligibility 2 tầng cho server-c

> Nhánh `feat/eligibility-engine-2tang`. **Không xoá, không sửa file nào đang có.**
> Mục đích tài liệu này: để đội đọc rồi quyết, không phải để merge thẳng.

## TL;DR

Nhánh này thêm một engine eligibility thứ hai vào `server-c-eligibility/grantpilot/`,
nằm **song song** với `eligibility_engine.py` hiện tại. Cả hai cùng tồn tại, chưa cái nào bị
gọi thay cái nào — `main.py` giữ nguyên.

Hai engine dựa trên **hai giả định khác nhau về nghiệp vụ**, nên không thể merge cơ học.
Đội cần chọn một, hoặc chốt cách kết hợp.

## Cái đã thêm (toàn file mới)

```
docs/                                   ← contract & kiến trúc dùng chung
  contracts.md, field-dictionary.md, architecture.md
shared/rulebook/                        ← rulebook JSON (Thành ghi, Hoàng đọc)
  qualification.json, programs.json, sme_classification.json
server-c-eligibility/grantpilot/        ← engine mới, package riêng để KHÔNG đụng file phẳng
  operators, logic, classifier, benefit, engine, gap_analysis, ranking
  models/{rule,qualification,program,profile,eligibility_result}.py
server-c-eligibility/tests/             ← 72 test, đang xanh
benchmark/                              ← 6 test case + metric
```

Chạy test: `cd server-c-eligibility && python3 -m tests.test_eligibility` → 72/72.
Không thêm dependency nào (thuần stdlib), `requirements.txt` giữ nguyên.

## Vì sao không dùng thẳng `eligibility_engine.py` hiện tại

Engine hiện tại là scaffold **generic cho mọi loại chính sách** — hợp lý cho một khởi đầu rộng.
Nhưng scope MVP đã chốt hẹp lại: **startup phần mềm ≤5 năm, hỗ trợ DNNVV khởi nghiệp sáng tạo,
nguồn Luật 04/2017/QH14 + NĐ 80/2021**. Với scope đó, ba chỗ dưới đây trở thành lỗi nghiệp vụ
chứ không còn là đơn giản hoá.

### 1. `None` bị coi là "không đạt"

```python
# eligibility_engine.py
def _check_membership(value, allowed):
    if value is None:
        return False, "Thiếu thông tin trong hồ sơ để kiểm tra điều kiện này."
```

Hàm **biết** là thiếu thông tin, nhưng trả `False` — tức "không đủ điều kiện". Hệ quả: một DN
đủ điều kiện thật, chỉ vì chưa khai doanh thu, sẽ bị báo trượt. Sai này **im lặng** — không
crash, không cảnh báo, chỉ ra kết quả sai.

"Chưa khai" và "không đạt" là hai chuyện khác nhau và phải dẫn tới hai hành động khác nhau:
một cái hỏi lại user, một cái khuyên xem hỗ trợ khác.

### 2. Không có điều kiện nào → "đủ điều kiện"

```python
if not checks:
    return {"is_eligible": True, "score": 1.0,
            "reasons": ["Chính sách không có điều kiện ràng buộc cụ thể."]}
```

Đây là *vacuous truth*: `all([])` là `True` về mặt toán học. Nhưng ở đây nó nghĩa là
**"đủ điều kiện vì chẳng xét gì cả"**. Nếu `eligibility_criteria` rỗng hoặc chưa điền
(hiện tại phần lớn đang vậy), mọi DN đều được tuyên đủ điều kiện.

Nguyên tắc thay thế: *vắng mặt căn cứ ≠ đã kiểm và đạt*. Engine mới trả `UNKNOWN` cho
group rỗng, kèm cảnh báo.

### 3. `is_eligible: bool` không đủ để nói thật

Bool ép engine phải kết luận kể cả khi không đủ căn cứ. Thực tế có 5 tình huống khác nhau,
và gộp chúng thành 2 chính là hallucination:

| Trạng thái | Nghĩa | User làm gì |
|---|---|---|
| `LIKELY_ELIGIBLE` | có khả năng đủ | chuẩn bị hồ sơ |
| `NOT_ELIGIBLE` | có điều kiện rõ ràng trượt | xem hỗ trợ khác |
| `NEED_MORE_INFO` | thiếu dữ liệu / thiếu giấy tờ | khai thêm |
| `NEEDS_HUMAN_REVIEW` | điều kiện định tính, máy không tự quyết | liên hệ cơ quan |
| `PROGRAM_UNAVAILABLE` | đủ điều kiện nhưng chưa rõ chương trình mở ở tỉnh | xác minh |

`NEEDS_HUMAN_REVIEW` là bắt buộc: *"có tính đổi mới sáng tạo"* (Luật 04/2017) là điều kiện
định tính — ép nó thành phép so sánh là tự lừa mình.
`PROGRAM_UNAVAILABLE` cũng vậy: **đủ điều kiện pháp lý ≠ chắc chắn được cấp tiền.**

### 4. Ba thứ scope MVP cần mà criteria phẳng không diễn đạt được

- **`any` (HOẶC)**: DNNVV xét theo *doanh thu **hoặc** nguồn vốn*; tính đổi mới xét theo
  *sản phẩm phần mềm **hoặc** có bằng sáng chế*. Criteria dạng dict phẳng chỉ làm được AND.
- **Provenance**: không có `source_document`/`article` cho từng điều kiện → **không trích dẫn
  được điều/khoản**. Mà trích dẫn là giá trị cốt lõi của sản phẩm, không phải tính năng phụ.
- **Hai tầng**: cần tách *"DN có thuộc diện DNNVV KNST không"* khỏi *"DN đủ điều kiện nhận
  hỗ trợ thuê coworking không"*. Gộp một tầng thì không nói được câu quan trọng nhất:
  *"bạn thuộc diện rồi, chỉ thiếu hợp đồng thuê"*.

## Xung đột với `shared/schema.sql` — cần đội quyết

Schema hiện tại chở một mô hình dữ liệu khác:

| schema.sql | Vấn đề với scope MVP |
|---|---|
| `num_employees` | DNNVV xét theo **lao động BHXH**, không phải tổng nhân sự. Hai số này khác nhau. |
| `annual_revenue REAL` | Tiền nên là số nguyên VNĐ; `REAL` gây sai số làm tròn |
| `industry`, `business_type` | Không map thẳng sang lĩnh vực của NĐ 80 Điều 5 (cần bảng tra) |
| `eligibility_criteria TEXT` | Một cột JSON — nhét được, nhưng khi đó SQLite chỉ là chỗ chứa file JSON |
| *(thiếu)* | Không có chỗ cho: phân hạng siêu nhỏ/nhỏ/vừa, mức hỗ trợ theo hạng, availability theo tỉnh |

**Đề xuất:** giữ `profiles` trong SQLite (Huy cần lưu hồ sơ giữa các lượt chat), nhưng rulebook
để JSON ở `shared/rulebook/`. Lý do: rule tree lồng nhau + provenance từng leaf nhét vào cột SQL
thì vẫn là JSON, chỉ thêm một lớp SQLite không đem lại gì.

Nhánh này **chưa sửa `schema.sql`** — README nói mọi thay đổi schema phải qua PR review chung.

## Việc cần đội quyết

1. **Engine nào là chính?** Nếu chọn engine mới → `main.py` trỏ sang `grantpilot/`, và
   `eligibility_engine.py` nên chuyển thành baseline đối chứng trong `benchmark/`
   (nó chính là "eligibility ngây thơ" mà bảng so sánh cần).
2. **Rulebook: JSON hay SQLite?** Ảnh hưởng tới `server-a-ingestion` (Thành ingest ra cái gì).
3. **`schema.sql`**: bỏ `policies`? sửa `num_employees` → `social_insurance_employees`?

## Điều quan trọng nhất, nói thẳng

Engine mới **an toàn hơn nhưng hôm nay chưa hữu ích hơn**: mọi rule đang `review_status: "draft"`,
mọi ngưỡng còn `null`, mọi `availability` là `unknown` → nó trả `NEED_MORE_INFO` cho gần như
mọi câu hỏi. Đó là hành vi đúng theo thiết kế, không phải bug — nhưng nó có nghĩa
**demo hôm nay chưa trả lời được "tôi được bao nhiêu tiền"**.

Nút thắt nằm ở `shared/rulebook/`, không nằm ở code. Xem
`benchmark/test_questions.json` mục `_TRANG_THAI_CASE_1`: cần **1 tỉnh × 1 program × số thật ×
review chéo** là mở khoá. Đó là việc đáng làm tiếp theo, không phải viết thêm engine.
