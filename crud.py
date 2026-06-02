from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.advantage_outbox import AdVantageOutbox, Status
from schemas.advantage import (
    ClickSchema,
    PaymentKey,
    PaymentSchema,
)

from config import settings

# периодичность повторных отправок в сек
RETRY_DELAYS = [1, 1, 1, 10, 100, 1000]


# получение строки с покупкой по заданным clid и ts
async def get_payment(
    data: PaymentKey,
    session: AsyncSession,
) -> AdVantageOutbox | None:
    query = select(AdVantageOutbox).where(
        and_(
            AdVantageOutbox.clid == data.clid,
            AdVantageOutbox.payment_ts == data.ts,
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
        payout_currency=settings.PAYOUT_CURRENCY,
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
        click_spend_currency=settings.CLICK_SPEND_CURRENCY,
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
    row.payout_currency = settings.PAYOUT_CURRENCY
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
    row.click_spend_currency = settings.CLICK_SPEND_CURRENCY
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
        payout_currency=settings.PAYOUT_CURRENCY,
        click_spend=click_row.click_spend,
        click_ts=click_row.click_ts,
        click_spend_currency=settings.CLICK_SPEND_CURRENCY,
        status=Status.READY_TO_SEND,
    )
    session.add(row)
    return row


async def process_payment(
    data: PaymentSchema,
    session: AsyncSession,
) -> AdVantageOutbox | None:

    # проверяем, есть ли уже такая покупка
    # если есть, то ничего не создаем и ничего не возвращаем

    existing_payment = await get_payment(data, session)

    if existing_payment is not None:
        return None

    # проверяем наличие клика с таким clid
    click_source_row = await get_click_source_row(data.clid, session)

    # если клика для покупки нет, то создаем строку, состоящую только из данных покупки
    if click_source_row is None:
        return await create_payment_row(data, session)

    # если есть пустой клик для покупки есть, то в эту строчку дописываем данные о покупке
    if click_source_row.payment_ts is None:
        return await fill_payment_data(click_source_row, data)

    # если click данные уже есть в другой строке, создаём новую готовую запись для новой покупки
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


# ищем записи, которые готовы к отправке и у которых еще не было ретраев либо
# для которых уже наступило время следующей попытки отправки
async def get_ready_to_send(
    session: AsyncSession,
    limit: int = 100,
) -> Sequence[AdVantageOutbox]:
    now = datetime.now(timezone.utc)

    query = (
        select(AdVantageOutbox)
        .where(
            and_(
                AdVantageOutbox.status == Status.READY_TO_SEND,
                or_(
                    AdVantageOutbox.next_retry_at.is_(None),
                    AdVantageOutbox.next_retry_at <= now,
                ),
            )
        )
        .order_by(AdVantageOutbox.updated_at)
        .limit(limit)
    )

    res = await session.execute(query)
    return res.scalars().all()


# обновляет запись после неудачной отправки, увеличивает счётчик попыток и либо
# назначает время следующего ретрая, либо переводит событие в статус FAILED
async def mark_for_retry(
    row: AdVantageOutbox,
) -> AdVantageOutbox:
    now = datetime.now(timezone.utc)

    row.updated_at = now

    if row.count_retry >= len(RETRY_DELAYS):
        row.status = Status.FAILED
        row.next_retry_at = None
        return row

    row.count_retry += 1

    delay = RETRY_DELAYS[row.count_retry - 1]
    row.status = Status.READY_TO_SEND
    row.next_retry_at = now + timedelta(seconds=delay)

    return row


# помечает событие как отправленное
async def mark_as_sent(
    row: AdVantageOutbox,
) -> AdVantageOutbox:
    row.status = Status.SENT
    row.next_retry_at = None
    row.updated_at = datetime.now(timezone.utc)
    return row


async def delete_sent_older_than_24h(
    session: AsyncSession,
) -> int:
    border_time = datetime.now(timezone.utc) - timedelta(hours=24)

    query = delete(AdVantageOutbox).where(
        and_(
            AdVantageOutbox.status == Status.SENT,
            AdVantageOutbox.updated_at < border_time,
        )
    )

    res = await session.execute(query)
    return res.rowcount
