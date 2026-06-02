from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from routers.v1.event_processor import router

from db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Event-Processor", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
