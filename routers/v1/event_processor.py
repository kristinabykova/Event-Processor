from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crud import process_click, process_payment
from db.dependencies import get_session
from schemas.advantage import ClickSchema, PaymentSchema, EventResponse

logger = getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("/click", response_model=EventResponse)
async def receive_click(
    data: ClickSchema,
    session: AsyncSession = Depends(get_session),
) -> EventResponse:
    try:

        result = await process_click(data, session)
        await session.commit()

        if result is None:
            return EventResponse(
                status="ignored",
                msg="Repeated click ignored",
            )

        return EventResponse(
            status="ok",
            msg="Click processed",
        )

    except Exception as e:
        await session.rollback()

        logger.exception(
            "Failed to save click event to advantage_outbox: clid=%s, ts=%s",
            data.clid,
            data.ts,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process click: {e}",
        )


@router.post("/payment", response_model=EventResponse)
async def receive_payment(
    data: PaymentSchema,
    session: AsyncSession = Depends(get_session),
) -> EventResponse:
    try:
        result = await process_payment(data, session)
        await session.commit()

        if result is None:
            return EventResponse(
                status="ignored",
                msg="Repeated payment ignored",
            )

        return EventResponse(
            status="ok",
            msg="Payment processed",
        )

    except IntegrityError:
        await session.rollback()
        return EventResponse(
            status="ignored",
            msg="Repeated payment ignored",
        )

    except Exception as e:
        await session.rollback()

        logger.info(
            "Repeated payment ignored by unique constraint: clid=%s, ts=%s",
            data.clid,
            data.ts,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process payment: {e}",
        )
