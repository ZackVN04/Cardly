from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class UserPublic(BaseModel):
    id: str
    username: str
    full_name: str
    avatar_url: str | None = None
    bio: str | None = None


UserSearchResult = UserPublic

UserSearchList = PaginatedResponse[UserPublic]
