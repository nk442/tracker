from fastapi import APIRouter, HTTPException, Request
from app.models.schemas import EventResponse, DomainEmailsSentUpdate
from app.database import db
import json

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/event", response_model=EventResponse)
async def track_event(
    request: Request,
    cid: int,
    event: str,
    email: str,
    domain: str
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
    campaign = await db.fetch_one(
        "SELECT id FROM campaigns WHERE id = $1",
        cid
    )
    
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
    
    # Сохраняем событие в БД
    result = await db.fetch_one(
        """
        INSERT INTO events (campaign_id, event_type, email, domain, ip, user_agent, extra_params)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        cid,
        event,
        email,
        domain,
        client_ip,
        user_agent,
        json.dumps(extra_params) if extra_params else None
    )
    
    return EventResponse(status="ok", event_id=result["id"])


@router.put("/campaign/{campaign_id}/domain/{domain}/emails-sent")
async def update_domain_emails_sent(
    campaign_id: int,
    domain: str,
    data: DomainEmailsSentUpdate
):
    """
    Обновляет количество отправленных писем для домена в кампании.
    Если записи не существует, создает новую.
    """
    
    # Проверяем существование кампании
    campaign = await db.fetch_one(
        "SELECT id FROM campaigns WHERE id = $1",
        campaign_id
    )
    
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign with id {campaign_id} not found"
        )
    
    # Проверяем, существует ли запись для этого домена и кампании
    existing = await db.fetch_one(
        """
        SELECT id FROM campaign_domain_emails 
        WHERE campaign_id = $1 AND domain = $2
        """,
        campaign_id,
        domain
    )
    
    if existing:
        # Обновляем существующую запись
        await db.execute(
            """
            UPDATE campaign_domain_emails 
            SET emails_sent = $1, updated_at = NOW()
            WHERE campaign_id = $2 AND domain = $3
            """,
            data.emails_sent,
            campaign_id,
            domain
        )
    else:
        # Создаем новую запись
        await db.execute(
            """
            INSERT INTO campaign_domain_emails (campaign_id, domain, emails_sent)
            VALUES ($1, $2, $3)
            """,
            campaign_id,
            domain,
            data.emails_sent
        )
    
    return {"status": "ok", "campaign_id": campaign_id, "domain": domain, "emails_sent": data.emails_sent}
