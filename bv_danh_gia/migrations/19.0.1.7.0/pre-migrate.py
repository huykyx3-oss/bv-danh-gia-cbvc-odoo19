"""
19.0.1.6.0 – Thêm các cột điểm TK/TP và NV độc lập vào bảng bv_monthly_evaluation.
"""


def migrate(cr, version):
    cols = [
        ('general_score_nv', 'double precision', '0'),
        ('general_score_tp', 'double precision', '0'),
        ('task_score_nv', 'double precision', '0'),
        ('task_score_tp', 'double precision', '0'),
        ('total_score_nv', 'double precision', '0'),
        ('total_score_tp', 'double precision', '0'),
        ('classification_tp', 'varchar', None),
    ]
    for col, dtype, default in cols:
        default_clause = f'DEFAULT {default}' if default else ''
        cr.execute(f"""
            ALTER TABLE bv_monthly_evaluation
            ADD COLUMN IF NOT EXISTS {col} {dtype} {default_clause}
        """)
