"""Adopt Users.sql in place, or create its original four-table schema in an empty DB."""
from pathlib import Path
from alembic import op
import sqlalchemy as sa
revision='0001_legacy'
down_revision=None
branch_labels=None
depends_on=None

REQUIRED={
 'merchants':{'merchant_id','name','status','description'},
 'employees':{'employee_id','merchant_id','name','payment_details','position','login','password'},
 'payments':{'payment_id','merchant_id','employee_id','amount','tip','status','timestamp'},
 'qr_links':{'qr_id','mecrhant_id','employee_id','receipt_id','nonce','exp','signature'},
}

def upgrade():
    inspector=sa.inspect(op.get_bind());existing=set(inspector.get_table_names(schema='public'))
    present=existing & set(REQUIRED)
    if not present:
        schema=Path(__file__).resolve().parents[2]/'schema'/'legacy.sql'
        for statement in schema.read_text().split(';'):
            if statement.strip():op.execute(statement)
    else:
        if present!=set(REQUIRED):raise RuntimeError('Partial Users.sql schema found. Restore/check the full dump before migrating; no tables have been replaced.')
        for table,columns in REQUIRED.items():
            found={c['name'] for c in inspector.get_columns(table,schema='public')}
            if not columns.issubset(found):raise RuntimeError(f'Unexpected legacy columns in {table}; inspect schema before migration.')
        for table,column,enum in [('employees','position','Position_enum'),('payments','status','Payment_status')]:
            actual=next(c['type'] for c in inspector.get_columns(table) if c['name']==column)
            if getattr(actual,'name',None)!=enum:raise RuntimeError(f'Unexpected enum for {table}.{column}; migration stopped safely.')

def downgrade():
    raise RuntimeError('Destructive downgrade is disabled. Restore a verified backup into a separate database.')
