from fastapi import APIRouter, HTTPException, Request
from app.models.schemas import EventResponse
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
    
    if event not in ["email_click", "landing_click", "conversion"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {event}. Must be one of: email_click, landing_click, conversion"
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
