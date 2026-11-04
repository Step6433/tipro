"""Advance legacy identity sequences if the dump restored values behind existing IDs."""
from alembic import op
import sqlalchemy as sa
revision='0003_sequences'
down_revision='0002_backend'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    for table,column in [('merchants','merchant_id'),('employees','employee_id'),('payments','payment_id'),('qr_links','qr_id')]:
        sequence=bind.scalar(sa.text('SELECT pg_get_serial_sequence(:table,:column)'),{'table':table,'column':column})
        maximum=bind.scalar(sa.text(f'SELECT max({column}) FROM {table}'))
        if sequence and maximum is not None:
            sequence_name=sequence.rsplit('.',1)[-1].strip('"')
            current=bind.scalar(sa.text("SELECT last_value FROM pg_sequences WHERE schemaname='public' AND sequencename=:name"),{'name':sequence_name})
            if current is None or current<maximum:
                bind.execute(sa.text('SELECT setval(CAST(:sequence AS regclass), :value, true)'),{'sequence':sequence,'value':maximum})

def downgrade():
    # Sequence values must never be moved backwards over existing records.
    pass
