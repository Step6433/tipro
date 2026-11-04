"""Make current restaurant QR codes permanent without removing history."""
from alembic import op
import sqlalchemy as sa
from app.core.security import sign_qr

revision = '0005_permanent_qr'
down_revision = '0004_qr_sessions'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT qr_id, nonce FROM qr_links WHERE token_version='v1'")).mappings().all()
    for row in rows:
        bind.execute(sa.text("UPDATE qr_links SET exp='0', expires_at=NULL, signature=:sign WHERE qr_id=:id"),
                     {'sign': sign_qr(row['nonce'], '0'), 'id': row['qr_id']})
    # Original receipt metadata and payments are retained for historical compatibility.

def downgrade():
    raise RuntimeError('Restoring deadlines would invalidate printed QR codes; restore a separate backup instead.')
