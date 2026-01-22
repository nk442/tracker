import logging
from fastapi import APIRouter, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, or_, and_, distinct
from sqlalchemy.orm import selectinload
from app.dependencies import get_db_session
from app.models.database import Campaign, Event, Offer, CampaignDomainEmails
from app.models.schemas import CampaignCreate
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """Главная страница со списком всех кампаний"""
    
    stmt = (
        select(
            Campaign.id,
            Campaign.name,
            Campaign.created_at,
            func.count(
                case(
                    (Event.event_type.in_(["email_click", "landing_click"]), 1)
                )
            ).label("clicks"),
            func.count(
                case((Event.event_type == "conversion", 1))
            ).label("conversions")
        )
        .outerjoin(Event, Campaign.id == Event.campaign_id)
        .group_by(Campaign.id, Campaign.name, Campaign.created_at)
        .order_by(Campaign.created_at.desc())
    )
    
    result = await session.execute(stmt)
    campaigns = [
        {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "clicks": row.clicks or 0,
            "conversions": row.conversions or 0
        }
        for row in result.all()
    ]
    
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "campaigns": campaigns, "base_url": settings.base_url}
    )


@router.get("/campaigns-table", response_class=HTMLResponse)
async def campaigns_table(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """HTMX endpoint для обновления таблицы кампаний"""
    
    stmt = (
        select(
            Campaign.id,
            Campaign.name,
            Campaign.created_at,
            func.count(
                case(
                    (Event.event_type.in_(["email_click", "landing_click"]), 1)
                )
            ).label("clicks"),
            func.count(
                case((Event.event_type == "conversion", 1))
            ).label("conversions")
        )
        .outerjoin(Event, Campaign.id == Event.campaign_id)
        .group_by(Campaign.id, Campaign.name, Campaign.created_at)
        .order_by(Campaign.created_at.desc())
    )
    
    result = await session.execute(stmt)
    campaigns = [
        {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "clicks": row.clicks or 0,
            "conversions": row.conversions or 0
        }
        for row in result.all()
    ]
    
    return templates.TemplateResponse(
        "partials/campaigns_table.html",
        {"request": request, "campaigns": campaigns, "base_url": settings.base_url}
    )


@router.get("/create", response_class=HTMLResponse)
async def create_campaign_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """Страница создания новой кампании"""
    stmt = select(Offer.id, Offer.name, Offer.url).order_by(Offer.name)
    result = await session.execute(stmt)
    offers = [
        {"id": row.id, "name": row.name, "url": row.url}
        for row in result.all()
    ]
    return templates.TemplateResponse("create.html", {"request": request, "offers": offers})


@router.post("/campaigns")
async def create_campaign(
    request: Request,
    name: str = Form(...),
    offer_id: int = Form(None),
    session: AsyncSession = Depends(get_db_session)
):
    """Создание новой кампании"""
    
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    
    if not offer_id:
        raise HTTPException(status_code=400, detail="Offer is required")
    
    # Получаем оффер
    result = await session.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Создаем новую кампанию
    new_campaign = Campaign(
        name=name,
        offer_id=offer_id,
        offer_url=offer.url
    )
    session.add(new_campaign)
    await session.flush()
    
    campaign_id = new_campaign.id
    
    # Для HTMX возвращаем редирект
    if request.headers.get("hx-request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/campaign/{campaign_id}"}
        )
    
    return RedirectResponse(url=f"/campaign/{campaign_id}", status_code=303)


@router.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(
    request: Request,
    campaign_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Детальная страница кампании с полной статистикой"""
    
    try:
        logger.info(f"Loading campaign detail for campaign_id={campaign_id}")
        
        # Получаем информацию о кампании
        stmt = (
            select(Campaign, Offer.name.label("offer_name"))
            .outerjoin(Offer, Campaign.offer_id == Offer.id)
            .where(Campaign.id == campaign_id)
        )
        result = await session.execute(stmt)
        row = result.first()
        
        if not row:
            logger.warning(f"Campaign {campaign_id} not found")
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        campaign_obj = row[0]
        campaign = {
            "id": campaign_obj.id,
            "name": campaign_obj.name,
            "offer_url": campaign_obj.offer_url,
            "offer_id": campaign_obj.offer_id,
            "offer_name": row.offer_name,
            "created_at": campaign_obj.created_at
        }
        
        # Получаем список всех офферов для выбора
        offers_stmt = select(Offer.id, Offer.name).order_by(Offer.name)
        offers_result = await session.execute(offers_stmt)
        all_offers = [
            {"id": row.id, "name": row.name}
            for row in offers_result.all()
        ]
        
        logger.debug("Fetching overall stats")
        # Общая статистика
        stats_stmt = (
            select(
                func.count(case((Event.event_type == "email_click", 1))).label("email_clicks"),
                func.count(case((Event.event_type == "landing_click", 1))).label("landing_clicks"),
                func.count(case((Event.event_type == "conversion", 1))).label("conversions"),
                func.count(case((Event.event_type == "unsubscribe", 1))).label("unsubscribes")
            )
            .where(Event.campaign_id == campaign_id)
        )
        stats_result = await session.execute(stats_stmt)
        stats_row = stats_result.first()
        
        overall_stats = {
            "email_clicks": stats_row.email_clicks or 0 if stats_row else 0,
            "landing_clicks": stats_row.landing_clicks or 0 if stats_row else 0,
            "conversions": stats_row.conversions or 0 if stats_row else 0,
            "unsubscribes": stats_row.unsubscribes or 0 if stats_row else 0
        }
        
        email_clicks = overall_stats["email_clicks"]
        conversions = overall_stats["conversions"]
        conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
        
        logger.debug("Fetching domain stats")
        # Получаем уникальные домены из events и campaign_domain_emails
        events_domains_stmt = (
            select(distinct(Event.domain))
            .where(Event.campaign_id == campaign_id)
        )
        emails_domains_stmt = (
            select(distinct(CampaignDomainEmails.domain))
            .where(CampaignDomainEmails.campaign_id == campaign_id)
        )
        
        events_domains_result = await session.execute(events_domains_stmt)
        emails_domains_result = await session.execute(emails_domains_stmt)
        
        all_domains = set()
        for row in events_domains_result.all():
            all_domains.add(row[0])
        for row in emails_domains_result.all():
            all_domains.add(row[0])
        
        # Для каждого домена получаем статистику
        domain_stats = []
        for domain in all_domains:
            # Статистика из events
            domain_events_stmt = (
                select(
                    func.count(case((Event.event_type == "email_click", 1))).label("email_clicks"),
                    func.count(case((Event.event_type == "landing_click", 1))).label("landing_clicks"),
                    func.count(case((Event.event_type == "conversion", 1))).label("conversions"),
                    func.count(case((Event.event_type == "unsubscribe", 1))).label("unsubscribes")
                )
                .where(and_(Event.campaign_id == campaign_id, Event.domain == domain))
            )
            domain_events_result = await session.execute(domain_events_stmt)
            domain_events_row = domain_events_result.first()
            
            # Количество отправленных писем
            emails_stmt = (
                select(CampaignDomainEmails.emails_sent)
                .where(
                    and_(
                        CampaignDomainEmails.campaign_id == campaign_id,
                        CampaignDomainEmails.domain == domain
                    )
                )
            )
            emails_result = await session.execute(emails_stmt)
            emails_row = emails_result.first()
            emails_sent = emails_row[0] if emails_row else 0
            
            e_clicks = domain_events_row.email_clicks or 0 if domain_events_row else 0
            convs = domain_events_row.conversions or 0 if domain_events_row else 0
            
            domain_stats.append({
                "domain": domain,
                "email_clicks": e_clicks,
                "landing_clicks": domain_events_row.landing_clicks or 0 if domain_events_row else 0,
                "conversions": convs,
                "unsubscribes": domain_events_row.unsubscribes or 0 if domain_events_row else 0,
                "emails_sent": emails_sent,
                "conversion_rate": (convs / e_clicks * 100) if e_clicks > 0 else 0
            })
        
        domain_stats.sort(key=lambda x: x["email_clicks"], reverse=True)
        
        logger.debug("Fetching user journeys")
        # Получаем уникальных пользователей с их путешествием
        user_journeys_stmt = (
            select(
                Event.email,
                Event.domain,
                func.bool_or(Event.event_type == "email_click").label("has_email_click"),
                func.bool_or(Event.event_type == "landing_click").label("has_landing_click"),
                func.bool_or(Event.event_type == "conversion").label("has_conversion"),
                func.bool_or(Event.event_type == "unsubscribe").label("has_unsubscribe"),
                func.min(Event.created_at).label("first_event")
            )
            .where(Event.campaign_id == campaign_id)
            .group_by(Event.email, Event.domain)
            .order_by(func.min(Event.created_at).desc())
            .limit(50)
        )
        user_journeys_result = await session.execute(user_journeys_stmt)
        
        user_journeys = []
        for row in user_journeys_result.all():
            user_journeys.append({
                "email": row.email,
                "domain": row.domain,
                "has_email_click": bool(row.has_email_click),
                "has_landing_click": bool(row.has_landing_click),
                "has_conversion": bool(row.has_conversion),
                "has_unsubscribe": bool(row.has_unsubscribe)
            })
        
        logger.debug("Fetching total users")
        # Получаем общее количество уникальных пользователей
        total_users_stmt = (
            select(func.count(distinct(Event.email)).label("total"))
            .where(Event.campaign_id == campaign_id)
        )
        total_users_result = await session.execute(total_users_stmt)
        total_users_row = total_users_result.first()
        total_users = total_users_row.total or 0 if total_users_row else 0
        
        logger.debug("Rendering template")
        return templates.TemplateResponse(
            "campaign_detail.html",
            {
                "request": request,
                "campaign": campaign,
                "all_offers": all_offers,
                "overall_stats": {
                    **overall_stats,
                    "conversion_rate": conversion_rate
                },
                "domain_stats": domain_stats,
                "user_journeys": user_journeys,
                "total_users": total_users,
                "offset": 0,
                "campaign_id": campaign_id,
                "domain": None,
                "email_search": None
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in campaign_detail for campaign_id={campaign_id}",
            exc_info=True,
            extra={"campaign_id": campaign_id}
        )
        raise


@router.get("/campaign/{campaign_id}/stats", response_class=HTMLResponse)
async def campaign_stats(
    request: Request,
    campaign_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """HTMX endpoint для обновления статистики"""
    
    try:
        logger.debug(f"Loading stats for campaign_id={campaign_id}")
        
        # Общая статистика
        stats_stmt = (
            select(
                func.count(case((Event.event_type == "email_click", 1))).label("email_clicks"),
                func.count(case((Event.event_type == "landing_click", 1))).label("landing_clicks"),
                func.count(case((Event.event_type == "conversion", 1))).label("conversions"),
                func.count(case((Event.event_type == "unsubscribe", 1))).label("unsubscribes")
            )
            .where(Event.campaign_id == campaign_id)
        )
        stats_result = await session.execute(stats_stmt)
        stats_row = stats_result.first()
        
        overall_stats = {
            "email_clicks": stats_row.email_clicks or 0 if stats_row else 0,
            "landing_clicks": stats_row.landing_clicks or 0 if stats_row else 0,
            "conversions": stats_row.conversions or 0 if stats_row else 0,
            "unsubscribes": stats_row.unsubscribes or 0 if stats_row else 0
        }
        
        email_clicks = overall_stats["email_clicks"]
        conversions = overall_stats["conversions"]
        conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
        
        # Получаем уникальные домены
        events_domains_stmt = (
            select(distinct(Event.domain))
            .where(Event.campaign_id == campaign_id)
        )
        emails_domains_stmt = (
            select(distinct(CampaignDomainEmails.domain))
            .where(CampaignDomainEmails.campaign_id == campaign_id)
        )
        
        events_domains_result = await session.execute(events_domains_stmt)
        emails_domains_result = await session.execute(emails_domains_stmt)
        
        all_domains = set()
        for row in events_domains_result.all():
            all_domains.add(row[0])
        for row in emails_domains_result.all():
            all_domains.add(row[0])
        
        # Для каждого домена получаем статистику
        domain_stats_list = []
        for domain in all_domains:
            domain_events_stmt = (
                select(
                    func.count(case((Event.event_type == "email_click", 1))).label("email_clicks"),
                    func.count(case((Event.event_type == "landing_click", 1))).label("landing_clicks"),
                    func.count(case((Event.event_type == "conversion", 1))).label("conversions"),
                    func.count(case((Event.event_type == "unsubscribe", 1))).label("unsubscribes")
                )
                .where(and_(Event.campaign_id == campaign_id, Event.domain == domain))
            )
            domain_events_result = await session.execute(domain_events_stmt)
            domain_events_row = domain_events_result.first()
            
            emails_stmt = (
                select(CampaignDomainEmails.emails_sent)
                .where(
                    and_(
                        CampaignDomainEmails.campaign_id == campaign_id,
                        CampaignDomainEmails.domain == domain
                    )
                )
            )
            emails_result = await session.execute(emails_stmt)
            emails_row = emails_result.first()
            emails_sent = emails_row[0] if emails_row else 0
            
            e_clicks = domain_events_row.email_clicks or 0 if domain_events_row else 0
            convs = domain_events_row.conversions or 0 if domain_events_row else 0
            
            domain_stats_list.append({
                "domain": domain,
                "email_clicks": e_clicks,
                "landing_clicks": domain_events_row.landing_clicks or 0 if domain_events_row else 0,
                "conversions": convs,
                "unsubscribes": domain_events_row.unsubscribes or 0 if domain_events_row else 0,
                "emails_sent": emails_sent,
                "conversion_rate": (convs / e_clicks * 100) if e_clicks > 0 else 0
            })
        
        domain_stats_list.sort(key=lambda x: x["email_clicks"], reverse=True)
        
        return templates.TemplateResponse(
            "partials/campaign_stats.html",
            {
                "request": request,
                "overall_stats": {
                    **overall_stats,
                    "conversion_rate": conversion_rate
                },
                "domain_stats": domain_stats_list
            }
        )
    except Exception as e:
        logger.error(
            f"Error in campaign_stats for campaign_id={campaign_id}",
            exc_info=True,
            extra={"campaign_id": campaign_id}
        )
        raise


@router.get("/campaign/{campaign_id}/users", response_class=HTMLResponse)
async def campaign_users(
    request: Request,
    campaign_id: int,
    domain: str | None = None,
    email_search: str | None = None,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """HTMX endpoint для фильтрации и пагинации пользователей"""
    
    # Строим запрос с фильтрами
    conditions = [Event.campaign_id == campaign_id]
    
    if domain:
        conditions.append(Event.domain == domain)
    
    if email_search:
        conditions.append(Event.email.ilike(f"%{email_search}%"))
    
    stmt = (
        select(
            Event.email,
            Event.domain,
            func.bool_or(Event.event_type == "email_click").label("has_email_click"),
            func.bool_or(Event.event_type == "landing_click").label("has_landing_click"),
            func.bool_or(Event.event_type == "conversion").label("has_conversion"),
            func.bool_or(Event.event_type == "unsubscribe").label("has_unsubscribe"),
            func.min(Event.created_at).label("first_event")
        )
        .where(and_(*conditions))
        .group_by(Event.email, Event.domain)
        .order_by(func.min(Event.created_at).desc())
        .limit(50)
        .offset(offset)
    )
    
    result = await session.execute(stmt)
    user_journeys = []
    for row in result.all():
        user_journeys.append({
            "email": row.email,
            "domain": row.domain,
            "has_email_click": bool(row.has_email_click),
            "has_landing_click": bool(row.has_landing_click),
            "has_conversion": bool(row.has_conversion),
            "has_unsubscribe": bool(row.has_unsubscribe)
        })
    
    # Получаем общее количество для текущего фильтра
    count_stmt = (
        select(func.count(distinct(Event.email)).label("total"))
        .where(and_(*conditions))
    )
    count_result = await session.execute(count_stmt)
    count_row = count_result.first()
    total_users = count_row.total or 0 if count_row else 0
    
    return templates.TemplateResponse(
        "partials/user_journeys.html",
        {
            "request": request,
            "user_journeys": user_journeys,
            "total_users": total_users,
            "offset": offset,
            "campaign_id": campaign_id,
            "domain": domain,
            "email_search": email_search
        }
    )


# ==================== ОФФЕРЫ ====================

@router.get("/offers", response_class=HTMLResponse)
async def offers_list(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """Страница со списком всех офферов"""
    stmt = (
        select(
            Offer.id,
            Offer.name,
            Offer.url,
            Offer.created_at,
            func.count(distinct(Campaign.id)).label("campaigns_count"),
            func.count(Event.id).label("total_events")
        )
        .outerjoin(Campaign, Offer.id == Campaign.offer_id)
        .outerjoin(Event, Campaign.id == Event.campaign_id)
        .group_by(Offer.id, Offer.name, Offer.url, Offer.created_at)
        .order_by(Offer.created_at.desc())
    )
    
    result = await session.execute(stmt)
    offers = [
        {
            "id": row.id,
            "name": row.name,
            "url": row.url,
            "created_at": row.created_at,
            "campaigns_count": row.campaigns_count or 0,
            "total_events": row.total_events or 0
        }
        for row in result.all()
    ]
    
    return templates.TemplateResponse(
        "offers.html",
        {"request": request, "offers": offers, "base_url": settings.base_url}
    )


@router.get("/offer/create", response_class=HTMLResponse)
async def create_offer_page(request: Request):
    """Страница создания нового оффера"""
    return templates.TemplateResponse("create_offer.html", {"request": request})


@router.post("/offers")
async def create_offer(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    session: AsyncSession = Depends(get_db_session)
):
    """Создание нового оффера"""
    
    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and URL are required")
    
    new_offer = Offer(name=name, url=url)
    session.add(new_offer)
    await session.flush()
    
    offer_id = new_offer.id
    
    if request.headers.get("hx-request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/offer/{offer_id}"}
        )
    
    return RedirectResponse(url=f"/offer/{offer_id}", status_code=303)


@router.get("/offer/{offer_id}", response_class=HTMLResponse)
async def offer_detail(
    request: Request,
    offer_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Детальная страница оффера со статистикой"""
    
    result = await session.execute(select(Offer).where(Offer.id == offer_id))
    offer_obj = result.scalar_one_or_none()
    
    if not offer_obj:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    offer = {
        "id": offer_obj.id,
        "name": offer_obj.name,
        "url": offer_obj.url,
        "created_at": offer_obj.created_at
    }
    
    # Общая статистика по офферу (через все кампании)
    overall_stats_stmt = (
        select(
            func.count(distinct(Campaign.id)).label("campaigns_count"),
            func.count(case((Event.event_type == "email_click", 1))).label("email_clicks"),
            func.count(case((Event.event_type == "landing_click", 1))).label("landing_clicks"),
            func.count(case((Event.event_type == "conversion", 1))).label("conversions"),
            func.count(case((Event.event_type == "unsubscribe", 1))).label("unsubscribes")
        )
        .select_from(Offer)
        .outerjoin(Campaign, Offer.id == Campaign.offer_id)
        .outerjoin(Event, Campaign.id == Event.campaign_id)
        .where(Offer.id == offer_id)
    )
    overall_stats_result = await session.execute(overall_stats_stmt)
    overall_stats_row = overall_stats_result.first()
    
    overall_stats = {
        "campaigns_count": overall_stats_row.campaigns_count or 0 if overall_stats_row else 0,
        "email_clicks": overall_stats_row.email_clicks or 0 if overall_stats_row else 0,
        "landing_clicks": overall_stats_row.landing_clicks or 0 if overall_stats_row else 0,
        "conversions": overall_stats_row.conversions or 0 if overall_stats_row else 0,
        "unsubscribes": overall_stats_row.unsubscribes or 0 if overall_stats_row else 0
    }
    
    # Статистика по кампаниям этого оффера
    campaigns_stats_stmt = (
        select(
            Campaign.id,
            Campaign.name,
            func.count(case((Event.event_type == "email_click", 1))).label("email_clicks"),
            func.count(case((Event.event_type == "landing_click", 1))).label("landing_clicks"),
            func.count(case((Event.event_type == "conversion", 1))).label("conversions"),
            func.count(case((Event.event_type == "unsubscribe", 1))).label("unsubscribes")
        )
        .outerjoin(Event, Campaign.id == Event.campaign_id)
        .where(Campaign.offer_id == offer_id)
        .group_by(Campaign.id, Campaign.name)
        .order_by(func.count(case((Event.event_type == "email_click", 1))).desc())
    )
    campaigns_stats_result = await session.execute(campaigns_stats_stmt)
    campaigns_stats = [
        {
            "id": row.id,
            "name": row.name,
            "email_clicks": row.email_clicks or 0,
            "landing_clicks": row.landing_clicks or 0,
            "conversions": row.conversions or 0,
            "unsubscribes": row.unsubscribes or 0
        }
        for row in campaigns_stats_result.all()
    ]
    
    # Вычисляем conversion rate
    email_clicks = overall_stats["email_clicks"]
    conversions = overall_stats["conversions"]
    conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
    
    return templates.TemplateResponse(
        "offer_detail.html",
        {
            "request": request,
            "offer": offer,
            "overall_stats": {
                **overall_stats,
                "conversion_rate": conversion_rate
            },
            "campaigns_stats": campaigns_stats
        }
    )


@router.get("/offer/{offer_id}/edit", response_class=HTMLResponse)
async def edit_offer_page(
    request: Request,
    offer_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Страница редактирования оффера"""
    result = await session.execute(select(Offer).where(Offer.id == offer_id))
    offer_obj = result.scalar_one_or_none()
    
    if not offer_obj:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    offer = {
        "id": offer_obj.id,
        "name": offer_obj.name,
        "url": offer_obj.url
    }
    
    return templates.TemplateResponse(
        "edit_offer.html",
        {"request": request, "offer": offer}
    )


@router.post("/offer/{offer_id}/update")
async def update_offer(
    request: Request,
    offer_id: int,
    name: str = Form(...),
    url: str = Form(...),
    session: AsyncSession = Depends(get_db_session)
):
    """Обновление оффера"""
    
    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and URL are required")
    
    # Проверяем существование оффера
    result = await session.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Обновляем оффер
    offer.name = name
    offer.url = url
    session.add(offer)
    
    # Обновляем offer_url во всех кампаниях с этим оффером
    campaigns_result = await session.execute(
        select(Campaign).where(Campaign.offer_id == offer_id)
    )
    campaigns = campaigns_result.scalars().all()
    for campaign in campaigns:
        campaign.offer_url = url
        session.add(campaign)
    
    await session.flush()
    
    if request.headers.get("hx-request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/offer/{offer_id}"}
        )
    
    return RedirectResponse(url=f"/offer/{offer_id}", status_code=303)


@router.post("/campaign/{campaign_id}/update-offer")
async def update_campaign_offer(
    request: Request,
    campaign_id: int,
    offer_id: int = Form(...),
    session: AsyncSession = Depends(get_db_session)
):
    """Обновление оффера в кампании"""
    
    # Проверяем существование кампании
    campaign_result = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Проверяем существование оффера
    offer_result = await session.execute(select(Offer).where(Offer.id == offer_id))
    offer = offer_result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Обновляем оффер в кампании
    campaign.offer_id = offer_id
    campaign.offer_url = offer.url
    session.add(campaign)
    await session.flush()
    
    if request.headers.get("hx-request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/campaign/{campaign_id}"}
        )
    
    return RedirectResponse(url=f"/campaign/{campaign_id}", status_code=303)


# ==================== API ДОКУМЕНТАЦИЯ ====================

@router.get("/api-docs", response_class=HTMLResponse)
async def api_docs(request: Request):
    """Страница с полной документацией API"""
    return templates.TemplateResponse(
        "api_docs.html",
        {
            "request": request,
            "base_url": settings.base_url
        }
    )
