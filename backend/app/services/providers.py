"""Provider boundary. A real adapter must implement these operations and verify its webhook."""
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from app.config import get_settings
from app.core.errors import ApiError
from app.models import utcnow

@dataclass
class CheckoutRequest:
    amount: Decimal
    currency: str
    idempotency_key: str
    scenario: str

@dataclass
class ProviderIntent:
    external_id: str
    outcome: str
    due_at: datetime | None

class PaymentProvider(Protocol):
    async def create(self, request: CheckoutRequest) -> ProviderIntent: ...
    async def status(self, external_id: str, outcome: str, due_at: datetime | None) -> str: ...

class DemoProvider:
    async def create(self, request: CheckoutRequest) -> ProviderIntent:
        scenario=request.scenario
        if scenario != 'success' and not get_settings().allow_demo_controls:
            raise ApiError('Управление демосценариями выключено.')
        due = None if scenario == 'pending' else utcnow() + timedelta(seconds=get_settings().demo_delay_seconds)
        return ProviderIntent('demo_' + secrets.token_urlsafe(24), scenario, due)

    async def status(self, external_id: str, outcome: str, due_at: datetime | None) -> str:
        if due_at is None or due_at > utcnow(): return 'PENDING'
        return {'success':'SUCCESS','declined':'DECLINED','cancelled':'CANCELED'}.get(outcome,'PENDING')

PROVIDERS: dict[str, PaymentProvider] = {'demo': DemoProvider()}
