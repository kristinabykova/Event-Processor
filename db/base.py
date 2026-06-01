from datetime import datetime
from typing import Annotated
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, mapped_column

created_time = Annotated[
    datetime, mapped_column(server_default=text("TIMEZONE('utc', now())"))
]


class Base(DeclarativeBase):
    pass
