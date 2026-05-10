"""
Migration 19.0.1.4.0 — pre-migrate
Thêm các cột dept_pct_* và evidence_*_name vào bảng bv_monthly_evaluation.
Các cột Binary(attachment=True) không cần ALTER TABLE (Odoo quản lý qua ir.attachment).
"""


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'bv_monthly_evaluation'
        """
    )
    if not cr.fetchone():
        return

    float_cols = [
        'dept_pct_quantity', 'dept_pct_quality', 'dept_pct_progress',
        'dept_pct_field_result', 'dept_pct_organization', 'dept_pct_team_cohesion',
    ]
    char_cols = [
        'evidence_quantity_name', 'evidence_quality_name', 'evidence_progress_name',
        'evidence_field_result_name', 'evidence_organization_name',
        'evidence_team_cohesion_name',
    ]

    for col in float_cols:
        cr.execute("""
            ALTER TABLE bv_monthly_evaluation
            ADD COLUMN IF NOT EXISTS %s double precision DEFAULT 0
        """ % col)

    for col in char_cols:
        cr.execute("""
            ALTER TABLE bv_monthly_evaluation
            ADD COLUMN IF NOT EXISTS %s varchar
        """ % col)
