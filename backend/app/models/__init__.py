from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Integer, Text, String, Boolean, DateTime, Numeric, ForeignKey, Identity, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

POSITION = ENUM('visitor', 'worker', 'manager', name='Position_enum', create_type=False)
PAYMENT_STATUS = ENUM('SUCCESS', 'DECLINED', 'PENDING', 'CANCELED', name='Payment_status', create_type=False)

def utcnow():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Merchant(Base):
    __tablename__ = 'merchants'
    merchant_id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default='ACTIVE')
    description: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('employees.employee_id'))
    currency: Mapped[str] = mapped_column(String(3), default='RUB')
    language: Mapped[str] = mapped_column(String(16), default='ru')
    tip_percentages: Mapped[list] = mapped_column(JSONB, default=lambda: [5, 10, 15])
    payment_methods: Mapped[list] = mapped_column(JSONB, default=lambda: ['demo'])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Employee(Base):
    __tablename__ = 'employees'
    employee_id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey('merchants.merchant_id'))
    name: Mapped[str] = mapped_column(Text)
    payment_details: Mapped[str] = mapped_column(Text, default='')
    position: Mapped[str | None] = mapped_column(POSITION)
    login: Mapped[str | None] = mapped_column(Text)
    password: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    auth_email: Mapped[str | None] = mapped_column(Text, unique=True)
    platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    title: Mapped[str] = mapped_column(String(60), default='Официант')
    invite_nonce: Mapped[str | None] = mapped_column(String(64))
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invite_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (Index('ix_employees_merchant_active', 'merchant_id', 'active'),)

class Goal(Base):
    __tablename__ = 'tip_goals'
    goal_id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.employee_id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    target: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    raised: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal(0))
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        Index('uq_goal_active_employee', 'employee_id', unique=True, postgresql_where=active.is_(True)),
        CheckConstraint('target > 0 AND raised >= 0', name='ck_goal_amounts'),
    )

class QrLink(Base):
    __tablename__ = 'qr_links'
    qr_id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    # Preserve the spelling in Users.sql; expose a correct Python attribute.
    merchant_id: Mapped[int] = mapped_column('mecrhant_id', ForeignKey('merchants.merchant_id'))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey('employees.employee_id'))
    receipt_id: Mapped[int] = mapped_column(Integer, default=0)
    nonce: Mapped[str] = mapped_column(Text)
    exp: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(Text)
    token_version: Mapped[str] = mapped_column(String(16), default='v2')
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    label: Mapped[str] = mapped_column(String(80), default='QR сотрудника')
    receipt_number: Mapped[str | None] = mapped_column(String(40))
    bill_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (
        Index('ix_qr_nonce_v1', 'nonce', unique=True, postgresql_where=token_version == 'v1'),
        Index('ix_qr_nonce_v2', 'nonce', unique=True, postgresql_where=token_version == 'v2'),
        CheckConstraint("token_version != 'v2' OR (employee_id IS NOT NULL AND expires_at IS NOT NULL AND exp != '0' AND expires_at = created_at + INTERVAL '24 hours')", name='ck_qr_v2_employee_deadline'),
    )

class Payment(Base):
    __tablename__ = 'payments'
    payment_id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.merchant_id'))
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.employee_id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4))  # Original: bill amount.
    tip: Mapped[Decimal] = mapped_column(Numeric(20, 4))     # Original: tip amount.
    status: Mapped[str] = mapped_column(PAYMENT_STATUS, default='PENDING')
    timestamp: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3))
    qr_id: Mapped[int | None] = mapped_column(ForeignKey('qr_links.qr_id'))
    qr_nonce: Mapped[str | None] = mapped_column(Text)  # Nonce at the start of this payment session.
    qr_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(30))
    goal_id: Mapped[int | None] = mapped_column(ForeignKey('tip_goals.goal_id'))
    external_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    public_token: Mapped[str | None] = mapped_column(String(100), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(30), default='demo')
    provider_outcome: Mapped[str | None] = mapped_column(String(20))
    provider_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (
        Index('ix_payments_merchant_date', 'merchant_id', 'created_at'),
        Index('ix_payments_employee_date', 'employee_id', 'created_at'),
    )

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.employee_id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WebhookEvent(Base):
    __tablename__ = 'payment_webhook_events'
    event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    payment_id: Mapped[int] = mapped_column(ForeignKey('payments.payment_id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class SeedRecord(Base):
    __tablename__ = 'demo_seed_records'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)
