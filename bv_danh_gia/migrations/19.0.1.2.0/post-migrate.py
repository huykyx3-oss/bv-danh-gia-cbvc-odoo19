"""Post-migration: clean up orphan rows that block subsequent saves.

After the schema change to require `criteria_id` on
`bv.evaluation.template.criteria` and `bv.evaluation.criteria.line`, any
pre-existing rows with NULL `criteria_id` make every parent save fail.
We delete those rows here so the system is consistent.
"""

def migrate(cr, version):
    if not version:
        return

    # Template criteria orphans
    cr.execute(
        "DELETE FROM bv_evaluation_template_criteria WHERE criteria_id IS NULL"
    )
    # Evaluation criteria-line orphans
    cr.execute(
        "DELETE FROM bv_evaluation_criteria_line WHERE criteria_id IS NULL"
    )
    # Try to add the NOT NULL constraint that the previous migration could not
    try:
        cr.execute(
            "ALTER TABLE bv_evaluation_template_criteria "
            "ALTER COLUMN criteria_id SET NOT NULL"
        )
    except Exception:
        cr.execute("ROLLBACK")
