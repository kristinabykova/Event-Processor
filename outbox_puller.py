import asyncio
from datetime import datetime, timezone

from crud import (
    delete_sent_older_than_24h,
    get_ready_to_send,
    mark_as_sent,
    mark_for_retry,
)
from db.session import async_session_maker
from models.advantage_outbox import Status
from services.advantage_client import send_to_advantage
from services.email_alert import send_failed_alert

CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
POLL_INTERVAL_SECONDS = 1


# берется 100 записей, готовых к отправке, алгоритм пробует их отправить,
# и если получает 200 код, то маркирует запись SENT, если получает что-то кроме 200,
# то статус не меняет и записывает через сколько секунд нужно сделать повторную отправку
async def process_ready_events() -> None:
    async with async_session_maker() as session:

        rows = await get_ready_to_send(session, limit=100)

        for row in rows:
            try:
                status_code = await send_to_advantage(row)

                if status_code == 200:
                    await mark_as_sent(row)
                else:
                    await mark_for_retry(row)

            except Exception:
                await mark_for_retry(row)

            if row.status == Status.FAILED:
                await send_failed_alert(row)

        await session.commit()
        return len(rows)


async def cleanup_sent_events() -> None:
    async with async_session_maker() as session:
        await delete_sent_older_than_24h(session)
        await session.commit()


async def outbox_poller() -> None:
    last_cleanup_at = datetime.now(timezone.utc)

    while True:
        processed_count = await process_ready_events()

        now = datetime.now(timezone.utc)

        if (now - last_cleanup_at).total_seconds() >= CLEANUP_INTERVAL_SECONDS:
            await cleanup_sent_events()
            last_cleanup_at = now

        if processed_count == 0:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
