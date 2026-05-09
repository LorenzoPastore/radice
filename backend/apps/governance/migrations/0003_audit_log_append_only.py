"""Install PostgreSQL trigger that makes governance_audit_log append-only.

See apps/governance/CLAUDE.md vincolo 1.
"""

from django.db import migrations


CREATE_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION reject_audit_log_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_no_update_delete ON governance_audit_log;
CREATE TRIGGER audit_log_no_update_delete
BEFORE UPDATE OR DELETE ON governance_audit_log
FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
"""

DROP_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS audit_log_no_update_delete ON governance_audit_log;
DROP FUNCTION IF EXISTS reject_audit_log_mutation();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_TRIGGER_SQL,
            reverse_sql=DROP_TRIGGER_SQL,
        ),
    ]
