# from typing import Generic, TypeVar

# from pydantic import BaseModel

# T = TypeVar("T")


# class PaginatedResponse(BaseModel, Generic[T]):
#     items: list[T]
#     total: int
#     page: int
#     limit: int
#     pages: int


# def paginate_query(page: int, limit: int) -> tuple[int, int]:
#     skip = (page - 1) * limit
#     return skip, limit


"""
src/core/pagination.py
----------------------
Generic pagination wrapper dùng chung cho toàn bộ project.

Dùng skip/limit thay vì page/pages vì:
- Tất cả service (tags, events, activity) đều nhận skip + limit
- skip/limit linh hoạt hơn cho cursor-based pagination sau này
- page/pages chỉ là alias tính toán thêm để client tiện dùng
"""

import math
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]       # danh sách items trong trang hiện tại
    total: int           # tổng số documents khớp query (không phải chỉ trang này)
    skip: int            # số documents bỏ qua — dùng để tính page hiện tại
    limit: int           # số items tối đa mỗi trang
    pages: int           # tổng số trang — tính từ total / limit, tiện cho frontend

    @classmethod
    def build(cls, items: list[T], total: int, skip: int, limit: int) -> "PaginatedResponse[T]":
        """
        Factory method để tạo response — tự tính pages thay vì bắt caller tính.
        pages = ceil(total / limit), tối thiểu là 1 dù total = 0.
        """
        pages = math.ceil(total / limit) if limit > 0 else 1
        return cls(items=items, total=total, skip=skip, limit=limit, pages=pages)


def paginate_query(page: int, limit: int) -> tuple[int, int]:
    """
    Convert page-based sang skip/limit.
    Giữ lại để tương thích nếu có chỗ nào dùng page-based pagination.
    page bắt đầu từ 1 — page=1 → skip=0.
    """
    skip = (page - 1) * limit
    return skip, limit