from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator, StringConstraints

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, populate_by_name=True)

class Login(Input):
    email: str = Field(min_length=1, max_length=254)
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=128)]

class Register(Input):
    role: Literal['merchant', 'employee', 'admin'] = 'merchant'
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=8, max_length=128)]
    restaurant_name: str | None = Field(default=None, alias='restaurantName', min_length=2, max_length=100)
    invite: str | None = Field(default=None, max_length=2000)

class EmployeeInput(Input):
    name: str = Field(min_length=2, max_length=80)
    role: str = Field(min_length=1, max_length=60)
    active: bool = True

class GoalInput(Input):
    title: str = Field(min_length=1, max_length=100)
    target: Decimal
    currency: str = 'RUB'

class QrInput(Input):
    label: str | None = Field(default=None, max_length=80)
    receipt_number: str | None = Field(default=None, alias='receiptNumber', min_length=1, max_length=40)
    bill_amount: Decimal | None = Field(default=None, alias='billAmount')
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expires_in_days: int | None = Field(default=None, alias='expiresInDays', ge=1, le=365)
    employee_id: int | None = Field(default=None, alias='employeeId', gt=0)

class QrUpdate(Input):
    active: bool

class PaymentInput(Input):
    employee_id: int = Field(alias='employeeId', gt=0)
    amount: Decimal | None = None
    percent: Decimal | None = Field(default=None, gt=0, le=100)
    currency: str
    scenario: Literal['success', 'declined', 'pending', 'cancelled'] = 'success'
    method: Literal['demo'] = 'demo'

    @model_validator(mode='after')
    def one_amount(self):
        if (self.amount is None) == (self.percent is None):
            raise ValueError('Specify amount OR percent')
        return self

class SettingsInput(Input):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    language: str | None = Field(default=None, pattern=r'^[a-z]{2,3}(-[A-Za-z]{2,8})?$')
    tip_percentages: list[int] | None = Field(default=None, alias='tipPercentages', min_length=1, max_length=8)
    payment_methods: list[Literal['demo']] | None = Field(default=None, alias='paymentMethods', min_length=1, max_length=1)

class WebhookInput(Input):
    event_id: str = Field(min_length=1, max_length=120)
    external_id: str = Field(min_length=1, max_length=120)
    status: Literal['success', 'failed', 'cancelled']
    amount: Decimal
    currency: str
