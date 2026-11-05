"""Record who approved a restaurant. Existing restaurant statuses are retained."""
from alembic import op
import sqlalchemy as sa
revision = '0006_approval'
down_revision = '0005_permanent_qr'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('merchants', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('merchants', sa.Column('approved_by', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_merchants_approved_by', 'merchants', 'employees', ['approved_by'], ['employee_id'])

def downgrade():
    op.drop_constraint('fk_merchants_approved_by', 'merchants', type_='foreignkey')
    op.drop_column('merchants', 'approved_by')
    op.drop_column('merchants', 'approved_at')
