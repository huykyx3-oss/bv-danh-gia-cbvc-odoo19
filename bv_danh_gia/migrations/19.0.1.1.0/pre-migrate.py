"""Pre-migration: clean up old template criteria rows.

The schema for `bv.evaluation.template.criteria` has changed: each row now
references the master catalog through `criteria_id` (required), instead of
storing `name`/`code`/`parent_line_id` locally. Existing rows from the old
schema would fail the new NOT NULL/required constraints, so we drop them.

In production this would attempt to remap by name/code first; for the current
development environment we simply truncate.
"""

def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'bv_evaluation_template_criteria'"
    )
    if not cr.fetchone():
        return

    # Best-effort remap: link rows where the (name, parent name) matches a
    # master criterion. Anything that can't be remapped is deleted.
    cr.execute("""
        ALTER TABLE bv_evaluation_template_criteria
        ADD COLUMN IF NOT EXISTS criteria_id INTEGER
    """)
    cr.execute("""
        UPDATE bv_evaluation_template_criteria tc
        SET criteria_id = c.id
        FROM bv_evaluation_criteria c
        WHERE tc.criteria_id IS NULL
          AND tc.name = c.name
          AND COALESCE(tc.code, '') = COALESCE(c.code, '')
    """)
    cr.execute("""
        DELETE FROM bv_evaluation_template_criteria
        WHERE criteria_id IS NULL
    """)
