import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from outbox_poller import outbox_poller
from routers.v1.event_processor import router

from db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    poller_task = asyncio.create_task(outbox_poller())
    yield
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Event-Processor", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {"status": "ok"}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
