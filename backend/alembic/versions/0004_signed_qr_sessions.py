"""Sign nonce + exp and bind payment sessions to their original QR generation."""
from alembic import op
import sqlalchemy as sa
from app.core.security import sign_qr

revision = '0004_qr_sessions'
down_revision = '0003_sequences'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('payments', sa.Column('qr_nonce', sa.Text(), nullable=True))
    op.add_column('payments', sa.Column('qr_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payments', sa.Column('failure_reason', sa.String(30), nullable=True))
    bind = op.get_bind()
    # Preserve QR rows/nonces and their original deadlines. Legacy dump signatures stay untouched.
    rows = bind.execute(sa.text("SELECT qr_id, nonce, expires_at FROM qr_links WHERE token_version='v1' AND expires_at IS NOT NULL")).mappings().all()
    for row in rows:
        exp = str(int(row['expires_at'].timestamp()))
        bind.execute(sa.text('UPDATE qr_links SET exp=:exp, signature=:signature WHERE qr_id=:id'),
                     {'exp': exp, 'signature': sign_qr(row['nonce'], exp), 'id': row['qr_id']})
    bind.execute(sa.text("""
        UPDATE payments p SET qr_nonce=q.nonce,
            qr_expires_at=to_timestamp(q.exp::double precision)
        FROM qr_links q WHERE p.qr_id=q.qr_id AND p.status='PENDING'
            AND q.token_version='v1' AND q.expires_at IS NOT NULL
    """))

def downgrade():
    raise RuntimeError('Restore a backup in a separate database; QR session protection cannot be removed safely.')
