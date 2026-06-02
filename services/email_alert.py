import asyncio
import smtplib
from email.message import EmailMessage

from config import settings
from models.advantage_outbox import AdVantageOutbox


def send_failed_alert_sync(row: AdVantageOutbox) -> None:
    message = EmailMessage()

    message["From"] = settings.SMTP_USER
    message["To"] = settings.ALERT_EMAIL
    message["Subject"] = "AdVantage delivery failed"

    message.set_content(f"""
Событие не удалось отправить в AdVantage.

ID записи: {row.id}
CLID: {row.clid}
Payment TS: {row.payment_ts}
Click TS: {row.click_ts}
Retry count: {row.count_retry}
Status: {row.status.value}

Необходима ручная проверка
""")

    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
        smtp.send_message(message)


async def send_failed_alert(row: AdVantageOutbox) -> None:
    await asyncio.to_thread(send_failed_alert_sync, row)
