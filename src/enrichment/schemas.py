from datetime import datetime

from pydantic import BaseModel

from src.core.pagination import PaginatedResponse


class LinkedInData(BaseModel):
    connections: int | None = None
    current_role: str | None = None
    education: list[str] = []
    recent_posts: list[str] = []


class FacebookData(BaseModel):
    profile_url: str | None = None
    followers: int | None = None
    recent_posts: list[str] = []


class WebsiteData(BaseModel):
    about: str | None = None
    founded: str | None = None
    team_size: str | None = None


class EnrichmentResponse(BaseModel):
    id: str
    contact_id: str
    status: str
    brief: str | None = None
    keywords: list[str] = []
    highlights: list[str] = []
    linkedin_data: LinkedInData | None = None
    facebook_data: FacebookData | None = None
    website_data: WebsiteData | None = None
    source: str
    enriched_at: datetime | None = None


class EnrichmentUpdate(BaseModel):
    brief: str | None = None
    keywords: list[str] | None = None
    highlights: list[str] | None = None
    linkedin_data: LinkedInData | None = None
    facebook_data: FacebookData | None = None
    website_data: WebsiteData | None = None


EnrichmentList = PaginatedResponse[EnrichmentResponse]
