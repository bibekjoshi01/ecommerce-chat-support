from datetime import datetime

from pydantic import BaseModel


class ApiMessage(BaseModel):
    detail: str
    timestamp: datetime
