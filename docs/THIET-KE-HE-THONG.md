# Thiết kế & vận hành — Module đánh giá CB (`bv_danh_gia`)

Cập nhật: 2026-05-10.

---

## 1. Luồng trạng thái (`bv.monthly.evaluation`)

| State | Ý nghĩa |
|-------|---------|
| `draft` | NV đang nhập |
| `submitted` | Đã gửi — TK/TP chấm / duyệt |
| `dept_approved` | TK/TP đã duyệt |
| `hr_reviewed` | TCCB đã xét |
| `approved` | BGĐ phê duyệt |
| `rejected` | Trả lại |

---

## 2. Form Odoo — gắn menu / action (quan trọng)

| Action | Form list / form |
|--------|-------------------|
| `action_monthly_evaluation` (menu NV) | **Tree + `view_monthly_evaluation_form`** (form NV, `priority` 10) |
| `action_monthly_evaluation_dept` (TK/TP) | Tree + `view_monthly_evaluation_dept_form` (priority 20) |
| `action_monthly_evaluation_hr` (TCCB) | Tree + **`view_monthly_evaluation_dept_form`** (cùng layout chấm/điểm; PDF readonly khi `state != submitted`) |

**Lý do:** Nếu `action_monthly_evaluation` **không** khai báo `views`, Odoo có thể lấy form ưu tiên cao hơn (form TK) → NV thấy sai form, PDF/minh chứng lệch kỳ vọng.

---

## 3. Quyền minh chứng PDF (Tab II, `widget="bv_binary"`)

| Vai trò | Khi nào sửa / thay PDF |
|---------|-------------------------|
| **NV** | Chỉ `draft`. Sau khi gửi (`submitted` trở đi): **không** upload lại — `readonly="state != 'draft'"` trên form NV. |
| **TK/TP** | Chỉ `submitted` trên **form TK**: xem, tải, thay PDF — `readonly="state != 'submitted'"`. Sau **duyệt** (`dept_approved`…): **không** sửa file — cùng biểu thức → readonly. |
| **TCCB** | Menu HR chỉ domain `dept_approved` trở đi → luôn **không** upload (chỉ xem/tải qua link). Không cần nhóm riêng trong XML vì **state** đã khóa. |

Widget: `readonly=true` + có file → link `/web/content`; `readonly=true` + không file → "—".

---

## 4. CSS widget PDF

File `monthly_evaluation_form.css`: chỉ ẩn `label.o_form_label` của Odoo, **không** dùng `label:not(...)` rộng — tránh ẩn nhầm `<label class="bv-ev-btn">` (nút Tải lên).

---

## 5. Encoding tiếng Việt trong XML

Chuỗi trong `monthly_evaluation_views.xml` phải được lưu **UTF-8** trong repo (IDE/editor UTF-8). Kiểm tra nhanh: các label như "Gửi đánh giá", "Hướng dẫn" không được có `?` thay ký tự có dấu.

---

## 6. File tham chiếu

| File | Vai trò |
|------|---------|
| `bv_danh_gia/views/monthly_evaluation_views.xml` | View + action |
| `bv_danh_gia/static/src/js/notification_service.js` | `BvBinaryField` |
