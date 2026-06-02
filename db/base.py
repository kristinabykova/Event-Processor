from datetime import datetime
from typing import Annotated, Optional
import uuid
from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, mapped_column

pk = Annotated[
    uuid.UUID, mapped_column(primary_key=True, server_default=func.gen_random_uuid())
]
from datetime import datetime
from typing import Annotated, Optional

from sqlalchemy import DateTime, text
from sqlalchemy.orm import mapped_column

created_time = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=text("now()")),
]

updated_time = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    ),
]

optional_time = Annotated[
    Optional[datetime],
    mapped_column(DateTime(timezone=True), default=None),
]


class Base(DeclarativeBase):
    pass
