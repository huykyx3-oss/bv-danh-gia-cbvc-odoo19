"""
19.0.1.8.0 – Thêm cột nhãn tiêu chí KQTHNV trên bảng bv_evaluation_template.
"""

DEFAULTS = {
    'label_pct_a': 'a) Tỷ lệ % số lượng kết quả thực hiện nhiệm vụ',
    'label_pct_b': 'b) Tỷ lệ % chất lượng kết quả thực hiện nhiệm vụ',
    'label_pct_c': 'c) Tỷ lệ % tiến độ kết quả thực hiện nhiệm vụ',
    'label_pct_d': 'd) Tỷ lệ % kết quả hoạt động lĩnh vực phụ trách',
    'label_pct_dd': 'đ) Tỷ lệ % khả năng tổ chức triển khai',
    'label_pct_e': 'e) Tỷ lệ % năng lực tập hợp, đoàn kết',
}


def migrate(cr, version):
    for col, default in DEFAULTS.items():
        cr.execute(f"""
            ALTER TABLE bv_evaluation_template
            ADD COLUMN IF NOT EXISTS {col} varchar DEFAULT %s
        """, (default,))
