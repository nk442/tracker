from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    offer_url: str = Field(..., min_length=1)


class Campaign(BaseModel):
    id: int
    name: str
    offer_url: str
    created_at: datetime


class CampaignStats(BaseModel):
    id: int
    name: str
    clicks: int
    conversions: int
    created_at: datetime


class EventCreate(BaseModel):
    campaign_id: int = Field(..., alias="cid")
    event_type: str = Field(..., alias="event")
    email: str
    domain: str
    ip: str | None = None
    user_agent: str | None = None
    extra_params: dict[str, Any] | None = None


class EventResponse(BaseModel):
    status: str
    event_id: int


class OverallStats(BaseModel):
    email_clicks: int
    landing_clicks: int
    conversions: int
    conversion_rate: float


class DomainStats(BaseModel):
    domain: str
    email_clicks: int
    landing_clicks: int
    conversions: int
    conversion_rate: float


class UserJourney(BaseModel):
    email: str
    domain: str
    has_email_click: bool
    has_landing_click: bool
    has_conversion: bool
