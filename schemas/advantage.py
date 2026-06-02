from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PaymentKey(BaseModel):
    clid: str
    ts: datetime


class PaymentSchema(PaymentKey):
    payout: float


class ClickSchema(BaseModel):
    clid: str
    ad_id: int
    click_spend: float
    ts: datetime


class EventResponse(BaseModel):
    status: str
    msg: str
