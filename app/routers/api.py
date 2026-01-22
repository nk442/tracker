from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.schemas import EventResponse, DomainEmailsSentUpdate
from app.models.database import Campaign, Event, CampaignDomainEmails
from app.dependencies import get_db_session
import json

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/event", response_model=EventResponse)
async def track_event(
    request: Request,
    cid: int,
    event: str,
    email: str,
    domain: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Принимает события от внешних сайтов.
    Все дополнительные query параметры сохраняются в extra_params.
    """
    
    if event not in ["email_click", "landing_click", "conversion", "unsubscribe"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {event}. Must be one of: email_click, landing_click, conversion, unsubscribe"
        )
    
    # Проверяем существование кампании
    result = await session.execute(
        select(Campaign).where(Campaign.id == cid)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign with id {cid} not found"
        )
    
    # Извлекаем IP и User-Agent
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Собираем дополнительные параметры
    extra_params = {}
    query_params = dict(request.query_params)
    
    # Удаляем обязательные параметры из extra_params
    for key in ["cid", "event", "email", "domain"]:
        query_params.pop(key, None)
    
    if query_params:
        extra_params = query_params
    
    # Создаем новое событие
    new_event = Event(
        campaign_id=cid,
        event_type=event,
        email=email,
        domain=domain,
        ip=client_ip,
        user_agent=user_agent,
        extra_params=extra_params if extra_params else None
    )
    
    session.add(new_event)
    await session.flush()
    
    return EventResponse(status="ok", event_id=new_event.id)


@router.put("/campaign/{campaign_id}/domain/{domain}/emails-sent")
async def update_domain_emails_sent(
    campaign_id: int,
    domain: str,
    data: DomainEmailsSentUpdate,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Обновляет количество отправленных писем для домена в кампании.
    Если записи не существует, создает новую.
    """
    
    # Проверяем существование кампании
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign with id {campaign_id} not found"
        )
    
    # Проверяем, существует ли запись для этого домена и кампании
    result = await session.execute(
        select(CampaignDomainEmails).where(
            CampaignDomainEmails.campaign_id == campaign_id,
            CampaignDomainEmails.domain == domain
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Обновляем существующую запись
        existing.emails_sent = data.emails_sent
        session.add(existing)
    else:
        # Создаем новую запись
        new_record = CampaignDomainEmails(
            campaign_id=campaign_id,
            domain=domain,
            emails_sent=data.emails_sent
        )
        session.add(new_record)
    
    await session.flush()
    
    return {"status": "ok", "campaign_id": campaign_id, "domain": domain, "emails_sent": data.emails_sent}
