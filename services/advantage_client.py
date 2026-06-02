import httpx

from models.advantage_outbox import AdVantageOutbox
from config import settings


def build_advantage_payload(row: AdVantageOutbox) -> dict:
    return {
        "clid": row.clid,
        "payout": row.payout,
        "click_spend": row.click_spend,
        "click_ts": row.click_ts.isoformat(),
        "payment_ts": row.payment_ts.isoformat(),
        "payout_currency": row.payout_currency,
        "click_spend_currency": row.click_spend_currency,
    }


async def send_to_advantage(row: AdVantageOutbox) -> int:
    headers = {
        "Authorization": f"Bearer {settings.ADVANTAGE_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = build_advantage_payload(row)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.ADVANTAGE_URL,
            json=payload,
            headers=headers,
        )

    return response.status_code
