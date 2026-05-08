from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int


def paginate_query(page: int, limit: int) -> tuple[int, int]:
    skip = (page - 1) * limit
    return skip, limit
