from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PaymentKey(BaseModel):
    clid: str
    ts: datetime


class PaymentSchema(PaymentKey):
    payout: float
    payout_currency: str


class ClickSchema(BaseModel):
    clid: str
    click_spend: float
    ts: datetime
    click_spend_currency: str


class EventResponse(BaseModel):
    status: str
    msg: str
