import enum
from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, created_time, pk, optional_time, updated_time


class Status(str, enum.Enum):
    WAITING_CLICK = "waiting_click"
    WAITING_PAYMENT = "waiting_payment"
    READY_TO_SEND = "ready_to_send"
    FAILED = "failed"
    SENT = "sent"


class AdVantageOutbox(Base):
    __tablename__ = "advantage_outbox"

    id: Mapped[pk]
    clid: Mapped[str]

    click_spend: Mapped[Optional[float]] = mapped_column(default=None)
    click_ts: Mapped[optional_time]
    click_spend_currency: Mapped[Optional[str]] = mapped_column(default=None)

    payout: Mapped[Optional[float]] = mapped_column(default=None)
    payment_ts: Mapped[optional_time]
    payout_currency: Mapped[Optional[str]] = mapped_column(default=None)

    status: Mapped[Status]

    created_at: Mapped[created_time]
    updated_at: Mapped[updated_time]

    count_retry: Mapped[int] = mapped_column(default=0)

    next_retry_at: Mapped[optional_time]

    __table_args__ = (
        UniqueConstraint("clid", "payment_ts", name="uq_advantage_payment"),
        Index("ix_advantage_outbox_clid", "clid"),
    )
