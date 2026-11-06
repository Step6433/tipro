"""Bind QR to receipts, introduce confirmation and persistent audit."""
from alembic import op
import sqlalchemy as sa
revision='0008_receipt_payments'
down_revision='0007_employee_qr'
branch_labels=None
depends_on=None

def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE \"Payment_status\" ADD VALUE IF NOT EXISTS 'CREATED'")
    op.execute("UPDATE qr_links SET active=false WHERE token_version='v2'")
    op.execute("CREATE SEQUENCE receipt_id_seq")
    op.execute("SELECT setval('receipt_id_seq', GREATEST(COALESCE((SELECT max(receipt_id) FROM qr_links),0)+1,1),false)")
    op.execute("UPDATE employees SET payment_details = CASE WHEN length(regexp_replace(COALESCE(payment_details,''),'[^0-9]','','g')) >= 4 THEN '****' || right(regexp_replace(payment_details,'[^0-9]','','g'),4) ELSE '' END")
    op.create_check_constraint('ck_employee_payment_mask','employees',"payment_details = '' OR payment_details ~ '^[*]{4}[0-9]{4}$'")
    op.create_index('ix_qr_nonce_v3','qr_links',['nonce'],unique=True,postgresql_where=sa.text("token_version='v3'"))
    op.create_index('uq_qr_v3_receipt','qr_links',['mecrhant_id','receipt_id'],unique=True,postgresql_where=sa.text("token_version='v3'"))
    op.create_index('uq_qr_v3_receipt_number','qr_links',['mecrhant_id','receipt_number'],unique=True,postgresql_where=sa.text("token_version='v3'"))
    op.create_check_constraint('ck_qr_v3_receipt','qr_links',"token_version != 'v3' OR (employee_id IS NOT NULL AND receipt_id > 0 AND receipt_number IS NOT NULL AND bill_amount IS NOT NULL AND bill_amount > 0 AND bill_amount <= 1000000 AND expires_at IS NOT NULL AND exp != '0' AND expires_at = created_at + INTERVAL '24 hours')")
    op.create_table('audit_events',
        sa.Column('event_id',sa.Integer(),sa.Identity(always=True),primary_key=True),
        sa.Column('payment_id',sa.Integer(),sa.ForeignKey('payments.payment_id'),nullable=True),
        sa.Column('qr_id',sa.Integer(),sa.ForeignKey('qr_links.qr_id'),nullable=True),
        sa.Column('merchant_id',sa.Integer(),sa.ForeignKey('merchants.merchant_id'),nullable=False),
        sa.Column('action',sa.String(40),nullable=False),sa.Column('from_status',sa.String(20)),
        sa.Column('to_status',sa.String(20),nullable=False),sa.Column('amount_total',sa.Numeric(20,4)),
        sa.Column('actor',sa.String(80),nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_audit_events_payment_id','audit_events',['payment_id'])
    op.create_index('ix_audit_events_merchant_id','audit_events',['merchant_id'])

def downgrade():
    raise RuntimeError('Restore a backup; payment and audit history must be preserved.')
