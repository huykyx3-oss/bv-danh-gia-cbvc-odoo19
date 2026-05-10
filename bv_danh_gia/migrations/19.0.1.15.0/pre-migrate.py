"""19.0.1.15.0 — no-op pre-migrate.

Trước đây script cố UPDATE subject_type nhưng cột không tồn tại trước bước load model → registry fail.
Chuẩn hóa dữ liệu (nếu cần) xử lý ở post-migrate hoặc sau khi field có trong DB.
"""


def migrate(cr, version):
    return
