"""
Migration 19.0.1.6.0 — pre-migrate
Adds template KQTHNV label columns + NV-score computed-store columns.
"""


def migrate(cr, version):
    # bv.evaluation.template — 6 label Char fields
    template_cols = [
        'task_label_quantity',
        'task_label_quality',
        'task_label_progress',
        'task_label_field_result',
        'task_label_organization',
        'task_label_team_cohesion',
    ]
    for col in template_cols:
        cr.execute(
            f"""
            ALTER TABLE bv_evaluation_template
            ADD COLUMN IF NOT EXISTS {col} VARCHAR
            """
        )

    # bv.monthly.evaluation — 3 stored computed Float fields
    eval_cols = [
        'general_score_nv',
        'task_score_nv',
        'total_score_nv',
    ]
    for col in eval_cols:
        cr.execute(
            f"""
            ALTER TABLE bv_monthly_evaluation
            ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION DEFAULT 0.0
            """
        )
