from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentKey(BaseModel):
    clid: str
    ts: datetime


class PaymentSchema(PaymentKey):
    payout: Decimal
    payout_currency: str


class ClickSchema(BaseModel):
    clid: str
    click_spend: Decimal
    ts: datetime
    click_spend_currency: str
