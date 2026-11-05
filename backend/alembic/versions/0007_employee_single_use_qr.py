"""Issue employee-bound single-use QR with a fixed 24-hour deadline."""
from alembic import op
import sqlalchemy as sa
revision='0007_employee_qr'
down_revision='0006_approval'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('qr_links',sa.Column('used_at',sa.DateTime(timezone=True),nullable=True))
    # Existing shared/permanent links cannot meet this contract: retain their rows as history.
    op.execute("UPDATE qr_links SET active=false, token_version='legacy' WHERE token_version='v1'")
    op.create_index('ix_qr_nonce_v2','qr_links',['nonce'],unique=True,postgresql_where=sa.text("token_version='v2'"))
    op.create_check_constraint('ck_qr_v2_employee_deadline','qr_links',"token_version != 'v2' OR (employee_id IS NOT NULL AND expires_at IS NOT NULL AND exp != '0' AND expires_at = created_at + INTERVAL '24 hours')")

def downgrade():
    raise RuntimeError('Re-enabling old shared QR codes is unsafe; restore a separate backup instead.')
