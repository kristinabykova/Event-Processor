from datetime import datetime
from typing import Annotated, Optional
import uuid
from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, mapped_column

pk = Annotated[
    uuid.UUID, mapped_column(primary_key=True, server_default=func.gen_random_uuid())
]
created_time = Annotated[
    datetime, mapped_column(server_default=text("TIMEZONE('utc', now())"))
]

optional_datetime = Annotated[
    Optional[datetime],
    mapped_column(DateTime(timezone=True), default=None),
]


class Base(DeclarativeBase):
    pass
