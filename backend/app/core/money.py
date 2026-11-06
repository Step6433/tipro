from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_DOWN
from app.core.errors import ApiError

# ISO 4217 fractional digits. IDR uses 2; VND uses 0.
CURRENCIES = {'USD': 2, 'EUR': 2, 'CNY': 2, 'RUB': 2, 'THB': 2, 'SGD': 2, 'MYR': 2, 'IDR': 2, 'PHP': 2, 'VND': 0}

def money(value, currency: str, minimum=Decimal('0.01'), maximum=Decimal('10000000')) -> Decimal:
    if currency not in CURRENCIES:
        raise ApiError('Неподдерживаемая валюта.')
    try:
        value = Decimal(str(value))
        if not value.is_finite() or value < minimum or value > maximum:
            raise ValueError
        unit = Decimal(1).scaleb(-CURRENCIES[currency])
        rounded = value.quantize(unit)
        if rounded != value:
            raise ApiError(f'Для {currency} допустимо знаков после запятой: {CURRENCIES[currency]}.')
        return rounded
    except (InvalidOperation, ValueError, TypeError):
        raise ApiError('Недопустимая денежная сумма.','AMOUNT_OUT_OF_RANGE',422)

def percent_tip(bill: Decimal, percent: Decimal, currency: str) -> Decimal:
    value = (bill * percent / Decimal(100)).quantize(Decimal(1).scaleb(-CURRENCIES[currency]), rounding=ROUND_HALF_UP)
    # Do not round an odd minor unit above the strict 50% cap.
    cap=(bill*Decimal('.5')).quantize(Decimal(1).scaleb(-CURRENCIES[currency]),rounding=ROUND_DOWN)
    return money(min(value,cap), currency, minimum=Decimal(0))
