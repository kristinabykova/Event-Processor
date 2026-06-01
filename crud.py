from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.advantage_outbox import AdVantageOutbox, Status
from schemas.advantage import (
    ClickSchema,
    PaymentKey,
    PaymentSchema,
)


# получение строки с покупкой по заданным clid и ts
async def get_payment(
    data: PaymentKey,
    session: AsyncSession,
) -> AdVantageOutbox | None:
    query = select(AdVantageOutbox).where(
        and_(
            AdVantageOutbox.clid == data.clid,
            AdVantageOutbox.payment_ts == data.payment_ts,
        )
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


# ищем, существует ли определенный клик
async def get_click_source_row(
    clid: str,
    session: AsyncSession,
) -> AdVantageOutbox | None:
    query = (
        select(AdVantageOutbox)
        .where(
            and_(
                AdVantageOutbox.clid == clid,
                AdVantageOutbox.click_spend.is_not(None),
                AdVantageOutbox.click_ts.is_not(None),
            )
        )
        .limit(1)
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


# ищем покупки без клика
async def get_waiting_click_rows(
    clid: str,
    session: AsyncSession,
):
    query = select(AdVantageOutbox).where(
        and_(
            AdVantageOutbox.clid == clid,
            AdVantageOutbox.status == Status.WAITING_CLICK,
        )
    )
    res = await session.execute(query)
    return res.scalars().all()


# создаем строку покупки
async def create_payment_row(
    data: PaymentSchema,
    session: AsyncSession,
) -> AdVantageOutbox:
    row = AdVantageOutbox(
        clid=data.clid,
        payout=data.payout,
        payment_ts=data.ts,
        payout_currency=data.payout_currency,
        status=Status.WAITING_CLICK,
    )
    session.add(row)
    return row


# создаем строку клика
async def create_click_row(
    data: ClickSchema,
    session: AsyncSession,
) -> AdVantageOutbox:
    row = AdVantageOutbox(
        clid=data.clid,
        click_spend=data.click_spend,
        click_ts=data.ts,
        click_spend_currency=data.click_spend_currency,
        status=Status.WAITING_PAYMENT,
    )
    session.add(row)
    return row


# в строку, где есть клик, добавляем данные по покупке и готовим к отправке
async def fill_payment_data(
    row: AdVantageOutbox,
    data: PaymentSchema,
) -> AdVantageOutbox:
    row.payout = data.payout
    row.payment_ts = data.ts
    row.payout_currency = data.payout_currency
    row.status = Status.READY_TO_SEND
    row.updated_at = datetime.now(timezone.utc)
    return row


# в строку, где есть данные о покупке, добавляем данные по клику и готовим к отправке
async def fill_click_data(
    row: AdVantageOutbox,
    data: ClickSchema,
) -> AdVantageOutbox:
    row.click_spend = data.click_spend
    row.click_ts = data.ts
    row.click_spend_currency = data.click_spend_currency
    row.status = Status.READY_TO_SEND
    row.updated_at = datetime.now(timezone.utc)
    return row


# по данных о клике и покупке создаем новую запись в таблице
async def create_ready_payment_row(
    data: PaymentSchema,
    click_row: AdVantageOutbox,
    session: AsyncSession,
) -> AdVantageOutbox:
    row = AdVantageOutbox(
        clid=data.clid,
        payout=data.payout,
        payment_ts=data.ts,
        payout_currency=data.payout_currency,
        click_spend=click_row.click_spend,
        click_ts=click_row.click_ts,
        click_spend_currency=click_row.click_spend_currency,
        status=Status.READY_TO_SEND,
    )
    session.add(row)
    return row


async def process_payment(
    data: PaymentSchema,
    session: AsyncSession,
) -> AdVantageOutbox | None:

    # проверяем, есть ли уже такая покупка
    # если есть, то возвращаем ее же и ничего нового не создаем

    existing_payment = await get_payment(data.clid, data.payment_ts, session)

    if existing_payment is not None:
        return existing_payment

    # проверяем наличие клика с таким clid
    click_source_row = await get_click_source_row(data.clid, session)

    # если клика для покупки нет, то создаем строку, состоящую только из данных покупки
    if click_source_row is None:
        return await create_payment_row(data, session)

    # если есть пустой клик для покупки есть, то в эту строчку дописываем данные о покупке
    if click_source_row.payment_ts is None:
        return await fill_payment_data(click_source_row, data)

    # если клик не пустой, то есть пришла повторная покупка по clid,
    # то мы берем данные о клике и покупке и создаем новую строчку
    return await create_ready_payment_row(data, click_source_row, session)


async def process_click(
    data: ClickSchema,
    session: AsyncSession,
) -> list[AdVantageOutbox] | None:

    # проверяем, есть ли уже такой клик
    # если есть, то ничего не создаем и ничего не возвращаем
    click_source_row = await get_click_source_row(data.clid, session)

    if click_source_row is not None:
        return None

    # ищем все покупки, которые ожидают кликов
    waiting_click_rows = await get_waiting_click_rows(data.clid, session)

    # для каждой найденной покупки дописываем информацию о клике
    if waiting_click_rows:
        updated_rows = []

        for row in waiting_click_rows:
            updated_row = await fill_click_data(row, data)
            updated_rows.append(updated_row)

        return updated_rows

    # если не было покупок с таким clid, то создаем новую запись для клика
    click_row = await create_click_row(data, session)
    return [click_row]


async def get_ready_to_send(
    session: AsyncSession,
    limit: int = 100,
) -> Sequence[AdVantageOutbox]:
    query = (
        select(AdVantageOutbox)
        .where(AdVantageOutbox.status.in_([Status.READY_TO_SEND, Status.FAILED]))
        .order_by(AdVantageOutbox.created_at)
        .limit(limit)
    )
    res = await session.execute(query)
    return res.scalars().all()


async def mark_as_sent(
    row: AdVantageOutbox,
) -> AdVantageOutbox:
    row.status = Status.SENT
    row.updated_at = datetime.now(timezone.utc)
    return row


async def mark_as_failed(
    row: AdVantageOutbox,
) -> AdVantageOutbox:
    row.status = Status.FAILED
    row.count_retry += 1
    row.updated_at = datetime.now(timezone.utc)
    return row
