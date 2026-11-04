"""Add backend capabilities without replacing existing tables or deleting rows."""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from app.config import get_settings
from app.models import Base
from app.core.security import passwords
from app.core.money import CURRENCIES
revision='0002_backend'
down_revision='0001_legacy'
branch_labels=None
depends_on=None

def upgrade():
    currency=get_settings().legacy_currency
    if currency not in CURRENCIES:raise RuntimeError('LEGACY_CURRENCY is not supported.')
    def add(table,name,type_,nullable=True,default=None):op.add_column(table,sa.Column(name,type_,nullable=nullable,server_default=default))
    stamp=sa.text('CURRENT_TIMESTAMP')
    add('merchants','contact_email',sa.Text())
    add('merchants','currency',sa.String(3),False,sa.text("'"+currency+"'"))
    add('merchants','language',sa.String(16),False,sa.text("'ru'"))
    add('merchants','tip_percentages',JSONB(),False,sa.text("'[5,10,15]'::jsonb"))
    add('merchants','payment_methods',JSONB(),False,sa.text("'[\"demo\"]'::jsonb"))
    add('merchants','created_at',sa.DateTime(timezone=True),False,stamp)
    add('merchants','updated_at',sa.DateTime(timezone=True),False,stamp)
    op.alter_column('employees','merchant_id',nullable=True)
    for name,type_,nullable,default in [
      ('password_hash',sa.Text(),True,None),('auth_email',sa.Text(),True,None),
      ('platform_admin',sa.Boolean(),False,sa.false()),('active',sa.Boolean(),False,sa.true()),
      ('title',sa.String(60),False,sa.text("'Официант'")),('invite_nonce',sa.String(64),True,None),
      ('invite_expires_at',sa.DateTime(timezone=True),True,None),('invite_consumed_at',sa.DateTime(timezone=True),True,None),
      ('created_at',sa.DateTime(timezone=True),False,stamp),('updated_at',sa.DateTime(timezone=True),False,stamp),
    ]:add('employees',name,type_,nullable,default)
    bind=op.get_bind()
    rows=bind.execute(sa.text('SELECT employee_id, login, password FROM employees')).mappings().all()
    seen=set()
    for row in rows:
        login=row['login'].strip().lower() if row['login'] and row['login'].strip() else None
        if login and login in seen:raise RuntimeError('Duplicate normalized legacy logins. Resolve duplicates in the original DB before migration; the transaction will roll back.')
        if login:seen.add(login)
        password=row['password']
        if password and password.startswith(('$2a$','$2b$','$2y$','pbkdf2:','sha256:')):
            raise RuntimeError('Legacy hashed passwords require an explicit import adapter. Migration rolled back; original passwords unchanged.')
        hashed=password if password and password.startswith('$argon2') else passwords.hash(password) if password else None
        bind.execute(sa.text('UPDATE employees SET auth_email=:login, password_hash=:hashed, password=NULL WHERE employee_id=:id'),{'login':login,'hashed':hashed,'id':row['employee_id']})
    op.create_unique_constraint('uq_employees_auth_email','employees',['auth_email'])
    op.create_index('ix_employees_merchant_active','employees',['merchant_id','active'])
    op.alter_column('qr_links','employee_id',nullable=True)
    for name,type_,nullable,default in [
      ('token_version',sa.String(16),False,sa.text("'legacy'")),('expires_at',sa.DateTime(timezone=True),True,None),
      ('active',sa.Boolean(),False,sa.true()),('label',sa.String(80),False,sa.text("'QR из исходной базы'")),
      ('receipt_number',sa.String(40),True,None),('bill_amount',sa.Numeric(20,4),True,None),
      ('currency',sa.String(3),False,sa.text("'"+currency+"'")),('created_at',sa.DateTime(timezone=True),False,stamp),('updated_at',sa.DateTime(timezone=True),False,stamp),
    ]:add('qr_links',name,type_,nullable,default)
    op.create_index('ix_qr_nonce_v1','qr_links',['nonce'],unique=True,postgresql_where=sa.text("token_version='v1'"))
    # New tables reference existing primary keys; no independent merchant/employee schema.
    for table in ['tip_goals','auth_sessions','payment_webhook_events','demo_seed_records']:
        if table=='payment_webhook_events':continue
        Base.metadata.tables[table].create(bind)
    for column in ['amount','tip']:op.alter_column('payments',column,type_=sa.Numeric(20,4),existing_type=sa.Numeric(10,2))
    for name,type_,nullable,default in [
      ('currency',sa.String(3),False,sa.text("'"+currency+"'")),('qr_id',sa.Integer(),True,None),('goal_id',sa.Integer(),True,None),
      ('external_id',sa.String(120),True,None),('public_token',sa.String(100),True,None),('idempotency_key',sa.String(120),True,None),('request_fingerprint',sa.String(64),True,None),
      ('provider',sa.String(30),False,sa.text("'legacy'")),('provider_outcome',sa.String(20),True,None),('provider_due_at',sa.DateTime(timezone=True),True,None),
      ('created_at',sa.DateTime(timezone=True),True,None),('updated_at',sa.DateTime(timezone=True),False,stamp),
    ]:add('payments',name,type_,nullable,default)
    for column in ['external_id','public_token','idempotency_key']:op.create_unique_constraint('uq_payments_'+column,'payments',[column])
    op.create_foreign_key('fk_payments_qr','payments','qr_links',['qr_id'],['qr_id'])
    op.create_foreign_key('fk_payments_goal','payments','tip_goals',['goal_id'],['goal_id'])
    op.create_index('ix_payments_merchant_date','payments',['merchant_id','created_at'])
    op.create_index('ix_payments_employee_date','payments',['employee_id','created_at'])
    for row in bind.execute(sa.text('SELECT payment_id, timestamp FROM payments')).mappings().all():
        try:
            value=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
            if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
            bind.execute(sa.text('UPDATE payments SET created_at=:value WHERE payment_id=:id'),{'value':value.astimezone(timezone.utc),'id':row['payment_id']})
        except (ValueError,AttributeError):pass  # Preserve the raw timestamp; do not invent a date.
    Base.metadata.tables['payment_webhook_events'].create(bind)

def downgrade():
    raise RuntimeError('Destructive downgrade is disabled; restore a backup to a separate database.')
