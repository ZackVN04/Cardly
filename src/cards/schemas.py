from pydantic import BaseModel


class CardCreate(BaseModel):
    title: str | None = None
    bio: str | None = None
    company: str | None = None
    title_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    social_links: dict | None = None
    is_public: bool = True


class CardUpdate(BaseModel):
    title: str | None = None
    bio: str | None = None
    company: str | None = None
    title_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    social_links: dict | None = None
    is_public: bool | None = None


class CardResponse(BaseModel):
    id: str
    owner_id: str
    slug: str
    title: str | None = None
    bio: str | None = None
    company: str | None = None
    title_role: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    social_links: dict | None = None
    is_public: bool
    qr_code_url: str | None = None
    view_count: int = 0
