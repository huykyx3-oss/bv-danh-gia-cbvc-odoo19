# Hệ thống Đánh giá Xếp loại Cán bộ, Viên chức (Odoo 19)

**Module Odoo 19** dành cho bệnh viện, xây dựng hệ thống tự đánh giá, xếp loại chất lượng cán bộ, công chức, viên chức theo **Quyết định số 06/2026/QĐ-UBND tỉnh Quảng Ninh**.

---

## Tổng quan

Module `bv_danh_gia` cung cấp đầy đủ quy trình đánh giá nhân sự bệnh viện:

- **Tự đánh giá hằng tháng** (Mẫu số 01) với hệ thống chấm điểm 100 điểm
- **Tổng hợp đánh giá theo quý** tự động từ các phiếu tháng
- **Xếp loại chất lượng năm** (Mẫu số 02) tổng hợp cả năm
- **Quy trình phê duyệt nhiều cấp**: Nhân viên → Trưởng khoa → TCCB → Ban Giám đốc
- **Dashboard phân quyền** cho từng vai trò
- **Giao diện đánh giá hiện đại** theo thiết kế custom (OWL component)

---

## Cấu trúc Module

```
bv_danh_gia/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── dashboard.py              # API dashboard data (JSON RPC)
│   └── export_docx.py            # Export phiếu đánh giá ra Word (DOCX)
├── data/
│   ├── criteria_data.xml          # Dữ liệu tiêu chí đánh giá mặc định
│   └── cron_data.xml              # Cron job nhắc nhở, kiểm tra tỷ lệ
├── models/
│   ├── __init__.py
│   ├── evaluation_config.py       # Cấu hình hệ thống (tỷ lệ, auto-approve, deadline)
│   ├── evaluation_criteria.py     # Master data tiêu chí đánh giá
│   ├── evaluation_criteria_line.py # Dòng chấm điểm từng tiêu chí
│   ├── evaluation_task_line.py    # Theo dõi nhiệm vụ được giao
│   ├── evaluation_template.py     # Biểu mẫu đánh giá (TCCB tạo/quản lý)
│   ├── monthly_evaluation.py      # Phiếu đánh giá hằng tháng (core model)
│   ├── quarterly_summary.py       # Tổng hợp quý
│   └── yearly_classification.py   # Xếp loại năm
├── reports/
│   ├── report_department_summary.xml  # Báo cáo tổng hợp theo khoa/phòng (PDF)
│   ├── report_mau_01.xml             # In phiếu Mẫu 01 (PDF)
│   └── report_mau_02.xml             # In phiếu Mẫu 02 (PDF)
├── security/
│   ├── evaluation_security.xml    # Nhóm quyền & record rules
│   └── ir.model.access.csv        # Quyền truy cập model
├── static/
│   ├── description/
│   │   └── icon.png               # Icon module
│   └── src/
│       ├── css/
│       │   └── evaluation_form.css  # CSS giao diện navy/gold theme
│       ├── js/
│       │   ├── dashboard.js         # OWL component - Dashboard
│       │   ├── evaluation_form_view.js  # OWL component - Form đánh giá custom
│       │   └── notification_service.js  # Service thông báo realtime (bus)
│       └── xml/
│           ├── dashboard_templates.xml         # QWeb template Dashboard
│           ├── evaluation_form_templates.xml   # QWeb template Form đánh giá
│           └── notification_templates.xml      # Template thông báo
├── views/
│   ├── dashboard_views.xml            # Client action Dashboard & Form custom
│   ├── evaluation_config_views.xml    # View cấu hình hệ thống
│   ├── evaluation_criteria_views.xml  # View quản lý tiêu chí
│   ├── evaluation_template_views.xml  # View quản lý biểu mẫu
│   ├── menu.xml                       # Menu module
│   ├── monthly_evaluation_views.xml   # View phiếu đánh giá tháng
│   ├── quarterly_summary_views.xml    # View tổng hợp quý
│   └── yearly_classification_views.xml # View xếp loại năm
└── wizards/
    ├── __init__.py
    ├── quarterly_aggregate_wizard.py       # Wizard tổng hợp quý
    ├── quarterly_aggregate_wizard_views.xml
    ├── ratio_check_wizard.py               # Wizard kiểm tra tỷ lệ xuất sắc
    ├── ratio_check_wizard_views.xml
    ├── yearly_aggregate_wizard.py          # Wizard tổng hợp năm
    └── yearly_aggregate_wizard_views.xml
```

---

## Chức năng chi tiết

### 1. Hệ thống chấm điểm 100 điểm

| Phần | Nội dung | Điểm tối đa |
|------|----------|:------------:|
| **Phần I** | Tiêu chí chung | **30 điểm** |
| Nhóm I | Phẩm chất chính trị, đạo đức, văn hóa, ý thức kỷ luật | 10 |
| Nhóm II | Năng lực chuyên môn, tinh thần trách nhiệm, thái độ | 10 |
| Nhóm III | Năng lực đổi mới, sáng tạo, dám nghĩ dám làm | 10 |
| **Phần II** | Kết quả thực hiện nhiệm vụ | **70 điểm** |
| a | Số lượng thực hiện chỉ tiêu, nhiệm vụ chuyên môn | 15 |
| b | Chất lượng kết quả thực hiện nhiệm vụ | 15 |
| c | Tiến độ thực hiện | 10 |
| d | Kết quả hoạt động lĩnh vực phụ trách *(chỉ quản lý)* | 10 |
| đ | Khả năng tổ chức triển khai *(chỉ quản lý)* | 10 |
| e | Năng lực tập hợp đoàn kết *(chỉ quản lý)* | 10 |

### Thang xếp loại

| Mức | Điều kiện |
|-----|-----------|
| Hoàn thành xuất sắc nhiệm vụ | ≥ 90 điểm |
| Hoàn thành tốt nhiệm vụ | 75 – 89 điểm |
| Hoàn thành nhiệm vụ | 50 – 74 điểm |
| Không hoàn thành nhiệm vụ | < 50 điểm |

### 2. Quy trình phê duyệt (Workflow)

```
Nháp → Đã gửi → Trưởng khoa duyệt → TCCB xét duyệt → BGĐ phê duyệt
                                                         ↓
                                                    Trả lại (ở bất kỳ bước nào)
```

- Hỗ trợ **auto-approve** cho từng cấp (cấu hình bởi TCCB)
- Tự động gửi **thông báo realtime** qua Odoo Bus khi:
  - Nhân viên gửi phiếu → thông báo Trưởng khoa
  - Trưởng khoa duyệt → thông báo TCCB
  - Phê duyệt hoàn tất → thông báo nhân viên
  - Tỷ lệ "Xuất sắc" vượt giới hạn → cảnh báo TCCB

### 3. Giao diện đánh giá Custom (Design mới)

Giao diện được thiết kế dạng **modern card-based UI** với color scheme navy/gold:

- **Layout 2 cột**: Form đánh giá (trái) + Bảng điểm realtime (phải, sticky)
- **Radio card** cho từng tiêu chí - click chọn mức điểm trực quan
- **Donut chart** hiển thị tổng điểm realtime
- **Progress bar** tiến độ hoàn thành biểu mẫu
- **Responsive** trên mobile
- Truy cập: Mở phiếu → nút **"Giao diện đánh giá mới"**

### 4. Dashboard phân quyền

| Vai trò | Nội dung hiển thị |
|---------|-------------------|
| **Nhân viên** | Thống kê cá nhân, điểm TB, bảng phiếu gần đây |
| **Trưởng khoa/phòng** | Thống kê khoa/phòng, số phiếu chờ duyệt |
| **TCCB** | Thống kê toàn viện, bảng theo khoa/phòng, cảnh báo tỷ lệ, phiếu chờ xử lý ở mỗi cấp |
| **Ban Giám đốc** | Như TCCB - tổng quan toàn viện |

### 5. Quản lý biểu mẫu (TCCB)

- Tạo, sửa, xóa, nhân bản biểu mẫu đánh giá
- Định nghĩa tiêu chí riêng cho từng biểu mẫu
- Phân loại đối tượng: tất cả / quản lý / nhân viên
- Thiết lập thời hạn áp dụng

### 6. Cấu hình hệ thống

- **Tỷ lệ xếp loại**: Giới hạn % "Xuất sắc" (mặc định 20%)
- **Auto-approve**: Bật/tắt tự động duyệt cho từng cấp
- **Deadline**: Hạn nộp phiếu tháng, hạn tổng hợp quý
- **Thông báo**: Bật/tắt thông báo khi gửi phiếu
- **Cảnh báo tỷ lệ**: Tự động cảnh báo khi vượt tỷ lệ

### 7. Báo cáo & Xuất file

- **PDF**: In phiếu Mẫu 01, Mẫu 02, Báo cáo tổng hợp khoa/phòng (QWeb)
- **DOCX**: Xuất phiếu Mẫu 01, Mẫu 02 ra file Word (python-docx)

### 8. Tự động hóa (Cron Jobs)

- Nhắc nhở nộp phiếu đánh giá tháng
- Nhắc nhở deadline tổng hợp quý
- Kiểm tra tỷ lệ "Xuất sắc" định kỳ

---

## Cài đặt

### Yêu cầu

- **Odoo 19** (version 19.0-20260118 trở lên)
- Python packages: `python-docx`
- Odoo modules: `base`, `hr`, `mail`, `bus`

### Các bước

1. Copy thư mục `bv_danh_gia` vào thư mục addons của Odoo
2. Cài đặt dependency Python:
   ```bash
   pip install python-docx
   ```
3. Khởi động lại Odoo server
4. Vào **Apps** → Tìm "Đánh giá xếp loại" → **Install**

### Phân quyền sau cài đặt

Vào **Settings → Users** để gán nhóm quyền cho từng user:

| Nhóm | Mô tả |
|------|--------|
| Đánh giá CBVC / Nhân viên | Tạo, sửa phiếu của mình |
| Đánh giá CBVC / Trưởng khoa | Duyệt phiếu trong khoa/phòng |
| Đánh giá CBVC / TCCB | Xét duyệt toàn viện, quản lý biểu mẫu, cấu hình |
| Đánh giá CBVC / Ban Giám đốc | Phê duyệt cuối cùng, xem báo cáo toàn viện |

---

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Backend | Python 3, Odoo 19 ORM |
| Frontend | OWL 3.0 (Odoo Web Library), QWeb Templates |
| Realtime | Odoo Bus Service |
| Reports | QWeb (PDF), python-docx (DOCX) |
| Styling | Custom CSS (Navy/Gold theme) |

---

## Căn cứ pháp lý

- Quyết định số 06/2026/QĐ-UBND tỉnh Quảng Ninh
- Phụ lục II: Mẫu số 01 (Phiếu theo dõi, đánh giá hằng tháng), Mẫu số 02 (Xếp loại năm)

---

## License

LGPL-3

## Author

Hospital IT Department
