from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic_core import core_schema


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(cls._validate)

    @classmethod
    def _validate(cls, v: Any) -> "PyObjectId":
        if isinstance(v, ObjectId):
            return cls(str(v))
        if isinstance(v, str) and ObjectId.is_valid(v):
            return cls(v)
        raise ValueError(f"Invalid ObjectId: {v!r}")

    def __repr__(self) -> str:
        return f"PyObjectId({super().__repr__()})"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseDocument(BaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
