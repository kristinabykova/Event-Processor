from .session import engine
from .base import Base
from models.advantage_outbox import AdVantageOutbox


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
