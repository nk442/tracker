import logging
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import db
from app.models.schemas import CampaignCreate
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница со списком всех кампаний"""
    
    campaigns = await db.fetch_all("""
        SELECT 
            c.id,
            c.name,
            c.created_at,
            COUNT(CASE WHEN e.event_type IN ('email_click', 'landing_click') THEN 1 END) as clicks,
            COUNT(CASE WHEN e.event_type = 'conversion' THEN 1 END) as conversions
        FROM campaigns c
        LEFT JOIN events e ON c.id = e.campaign_id
        GROUP BY c.id, c.name, c.created_at
        ORDER BY c.created_at DESC
    """)
    
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "campaigns": campaigns, "base_url": settings.base_url}
    )


@router.get("/campaigns-table", response_class=HTMLResponse)
async def campaigns_table(request: Request):
    """HTMX endpoint для обновления таблицы кампаний"""
    
    campaigns = await db.fetch_all("""
        SELECT 
            c.id,
            c.name,
            c.created_at,
            COUNT(CASE WHEN e.event_type IN ('email_click', 'landing_click') THEN 1 END) as clicks,
            COUNT(CASE WHEN e.event_type = 'conversion' THEN 1 END) as conversions
        FROM campaigns c
        LEFT JOIN events e ON c.id = e.campaign_id
        GROUP BY c.id, c.name, c.created_at
        ORDER BY c.created_at DESC
    """)
    
    return templates.TemplateResponse(
        "partials/campaigns_table.html",
        {"request": request, "campaigns": campaigns, "base_url": settings.base_url}
    )


@router.get("/create", response_class=HTMLResponse)
async def create_campaign_page(request: Request):
    """Страница создания новой кампании"""
    offers = await db.fetch_all("SELECT id, name, url FROM offers ORDER BY name")
    return templates.TemplateResponse("create.html", {"request": request, "offers": offers})


@router.post("/campaigns")
async def create_campaign(
    request: Request,
    name: str = Form(...),
    offer_id: int = Form(None)
):
    """Создание новой кампании"""
    
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    
    if not offer_id:
        raise HTTPException(status_code=400, detail="Offer is required")
    
    # Получаем URL оффера
    offer = await db.fetch_one("SELECT url FROM offers WHERE id = $1", offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    result = await db.fetch_one(
        "INSERT INTO campaigns (name, offer_id, offer_url) VALUES ($1, $2, $3) RETURNING id",
        name,
        offer_id,
        offer["url"]
    )
    
    # Для HTMX возвращаем редирект
    if request.headers.get("hx-request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/campaign/{result['id']}"}
        )
    
    return RedirectResponse(url=f"/campaign/{result['id']}", status_code=303)


@router.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int):
    """Детальная страница кампании с полной статистикой"""
    
    try:
        logger.info(f"Loading campaign detail for campaign_id={campaign_id}")
        
        # Получаем информацию о кампании
        campaign_row = await db.fetch_one(
            """
            SELECT 
                c.id, 
                c.name, 
                c.offer_url, 
                c.offer_id,
                c.created_at,
                o.name as offer_name
            FROM campaigns c
            LEFT JOIN offers o ON c.offer_id = o.id
            WHERE c.id = $1
            """,
            campaign_id
        )
        
        if not campaign_row:
            logger.warning(f"Campaign {campaign_id} not found")
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        logger.debug(f"Campaign row: {dict(campaign_row)}")
        
        # Преобразуем Record в словарь
        campaign = {
            "id": campaign_row["id"],
            "name": campaign_row["name"],
            "offer_url": campaign_row["offer_url"],
            "offer_id": campaign_row["offer_id"],
            "offer_name": campaign_row["offer_name"],
            "created_at": campaign_row["created_at"]
        }
        
        # Получаем список всех офферов для выбора
        all_offers = await db.fetch_all("SELECT id, name FROM offers ORDER BY name")
        
        logger.debug("Fetching overall stats")
        # Общая статистика
        overall_stats_row = await db.fetch_one("""
            SELECT 
                COUNT(CASE WHEN event_type = 'email_click' THEN 1 END) as email_clicks,
                COUNT(CASE WHEN event_type = 'landing_click' THEN 1 END) as landing_clicks,
                COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) as conversions,
                COUNT(CASE WHEN event_type = 'unsubscribe' THEN 1 END) as unsubscribes
            FROM events
            WHERE campaign_id = $1
        """, campaign_id)
        
        logger.debug(f"Overall stats row: {dict(overall_stats_row) if overall_stats_row else None}")
        
        # Преобразуем Record в словарь и обрабатываем None значения
        overall_stats = {
            "email_clicks": overall_stats_row["email_clicks"] or 0 if overall_stats_row else 0,
            "landing_clicks": overall_stats_row["landing_clicks"] or 0 if overall_stats_row else 0,
            "conversions": overall_stats_row["conversions"] or 0 if overall_stats_row else 0,
            "unsubscribes": overall_stats_row["unsubscribes"] or 0 if overall_stats_row else 0
        }
        
        # Вычисляем conversion rate
        email_clicks = overall_stats["email_clicks"]
        conversions = overall_stats["conversions"]
        conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
        
        logger.debug("Fetching domain stats")
        # Статистика по доменам - объединяем данные из events и campaign_domain_emails
        domain_stats_rows = await db.fetch_all("""
            SELECT 
                all_domains.domain,
                COUNT(CASE WHEN e.event_type = 'email_click' THEN 1 END) as email_clicks,
                COUNT(CASE WHEN e.event_type = 'landing_click' THEN 1 END) as landing_clicks,
                COUNT(CASE WHEN e.event_type = 'conversion' THEN 1 END) as conversions,
                COUNT(CASE WHEN e.event_type = 'unsubscribe' THEN 1 END) as unsubscribes,
                COALESCE(MAX(cde.emails_sent), 0) as emails_sent
            FROM (
                SELECT DISTINCT domain FROM events WHERE campaign_id = $1
                UNION
                SELECT DISTINCT domain FROM campaign_domain_emails WHERE campaign_id = $1
            ) all_domains
            LEFT JOIN events e ON all_domains.domain = e.domain AND e.campaign_id = $1
            LEFT JOIN campaign_domain_emails cde ON all_domains.domain = cde.domain AND cde.campaign_id = $1
            GROUP BY all_domains.domain
            ORDER BY email_clicks DESC
        """, campaign_id)
        
        logger.debug(f"Domain stats rows count: {len(domain_stats_rows)}")
        
        # Преобразуем Record объекты в словари и добавляем conversion rate
        domain_stats = []
        for stat in domain_stats_rows:
            try:
                e_clicks = stat["email_clicks"] or 0
                convs = stat["conversions"] or 0
                domain_stats.append({
                    "domain": stat["domain"],
                    "email_clicks": e_clicks,
                    "landing_clicks": stat["landing_clicks"] or 0,
                    "conversions": convs,
                    "unsubscribes": stat["unsubscribes"] or 0,
                    "emails_sent": stat["emails_sent"] or 0,
                    "conversion_rate": (convs / e_clicks * 100) if e_clicks > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error processing domain stat: {e}, stat={dict(stat)}", exc_info=True)
                raise
        
        logger.debug("Fetching user journeys")
        # Получаем уникальных пользователей с их путешествием
        user_journeys_rows = await db.fetch_all("""
            SELECT DISTINCT
                email,
                domain,
                BOOL_OR(event_type = 'email_click') as has_email_click,
                BOOL_OR(event_type = 'landing_click') as has_landing_click,
                BOOL_OR(event_type = 'conversion') as has_conversion,
                BOOL_OR(event_type = 'unsubscribe') as has_unsubscribe,
                MIN(created_at) as first_event
            FROM events
            WHERE campaign_id = $1
            GROUP BY email, domain
            ORDER BY first_event DESC
            LIMIT 50
        """, campaign_id)
        
        logger.debug(f"User journeys rows count: {len(user_journeys_rows)}")
        
        # Преобразуем Record объекты в словари
        user_journeys = []
        for journey in user_journeys_rows:
            try:
                user_journeys.append({
                    "email": journey["email"],
                    "domain": journey["domain"],
                    "has_email_click": bool(journey["has_email_click"]),
                    "has_landing_click": bool(journey["has_landing_click"]),
                    "has_conversion": bool(journey["has_conversion"]),
                    "has_unsubscribe": bool(journey["has_unsubscribe"])
                })
            except Exception as e:
                logger.error(f"Error processing user journey: {e}, journey={dict(journey)}", exc_info=True)
                raise
        
        logger.debug("Fetching total users")
        # Получаем общее количество уникальных пользователей
        total_users_row = await db.fetch_one("""
            SELECT COUNT(DISTINCT email) as total
            FROM events
            WHERE campaign_id = $1
        """, campaign_id)
        
        total_users = total_users_row["total"] or 0 if total_users_row else 0
        
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
async def campaign_stats(request: Request, campaign_id: int):
    """HTMX endpoint для обновления статистики"""
    
    try:
        logger.debug(f"Loading stats for campaign_id={campaign_id}")
        
        # Общая статистика
        overall_stats_row = await db.fetch_one("""
            SELECT 
                COUNT(CASE WHEN event_type = 'email_click' THEN 1 END) as email_clicks,
                COUNT(CASE WHEN event_type = 'landing_click' THEN 1 END) as landing_clicks,
                COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) as conversions
            FROM events
            WHERE campaign_id = $1
        """, campaign_id)
        
        logger.debug(f"Overall stats row: {dict(overall_stats_row) if overall_stats_row else None}")
        
        # Преобразуем Record в словарь и обрабатываем None значения
        overall_stats = {
            "email_clicks": overall_stats_row["email_clicks"] or 0 if overall_stats_row else 0,
            "landing_clicks": overall_stats_row["landing_clicks"] or 0 if overall_stats_row else 0,
            "conversions": overall_stats_row["conversions"] or 0 if overall_stats_row else 0,
            "unsubscribes": overall_stats_row["unsubscribes"] or 0 if overall_stats_row else 0
        }
        
        email_clicks = overall_stats["email_clicks"]
        conversions = overall_stats["conversions"]
        conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
        
        # Статистика по доменам - объединяем данные из events и campaign_domain_emails
        domain_stats = await db.fetch_all("""
            SELECT 
                all_domains.domain,
                COUNT(CASE WHEN e.event_type = 'email_click' THEN 1 END) as email_clicks,
                COUNT(CASE WHEN e.event_type = 'landing_click' THEN 1 END) as landing_clicks,
                COUNT(CASE WHEN e.event_type = 'conversion' THEN 1 END) as conversions,
                COUNT(CASE WHEN e.event_type = 'unsubscribe' THEN 1 END) as unsubscribes,
                COALESCE(MAX(cde.emails_sent), 0) as emails_sent
            FROM (
                SELECT DISTINCT domain FROM events WHERE campaign_id = $1
                UNION
                SELECT DISTINCT domain FROM campaign_domain_emails WHERE campaign_id = $1
            ) all_domains
            LEFT JOIN events e ON all_domains.domain = e.domain AND e.campaign_id = $1
            LEFT JOIN campaign_domain_emails cde ON all_domains.domain = cde.domain AND cde.campaign_id = $1
            GROUP BY all_domains.domain
            ORDER BY email_clicks DESC
        """, campaign_id)
        
        logger.debug(f"Domain stats rows count: {len(domain_stats)}")
        
        # Преобразуем Record объекты в словари
        domain_stats_list = []
        for stat in domain_stats:
            try:
                e_clicks = stat["email_clicks"] or 0
                convs = stat["conversions"] or 0
                domain_stats_list.append({
                    "domain": stat["domain"],
                    "email_clicks": e_clicks,
                    "landing_clicks": stat["landing_clicks"] or 0,
                    "conversions": convs,
                    "unsubscribes": stat["unsubscribes"] or 0,
                    "emails_sent": stat["emails_sent"] or 0,
                    "conversion_rate": (convs / e_clicks * 100) if e_clicks > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error processing domain stat: {e}, stat={dict(stat)}", exc_info=True)
                raise
        
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
    offset: int = 0
):
    """HTMX endpoint для фильтрации и пагинации пользователей"""
    
    query = """
        SELECT DISTINCT
            email,
            domain,
            BOOL_OR(event_type = 'email_click') as has_email_click,
            BOOL_OR(event_type = 'landing_click') as has_landing_click,
            BOOL_OR(event_type = 'conversion') as has_conversion,
            BOOL_OR(event_type = 'unsubscribe') as has_unsubscribe,
            MIN(created_at) as first_event
        FROM events
        WHERE campaign_id = $1
    """
    
    params = [campaign_id]
    param_idx = 2
    
    if domain:
        query += f" AND domain = ${param_idx}"
        params.append(domain)
        param_idx += 1
    
    if email_search:
        query += f" AND email ILIKE ${param_idx}"
        params.append(f"%{email_search}%")
        param_idx += 1
    
    query += f"""
        GROUP BY email, domain
        ORDER BY first_event DESC
        LIMIT 50 OFFSET ${param_idx}
    """
    params.append(offset)
    
    user_journeys_rows = await db.fetch_all(query, *params)
    
    # Преобразуем Record объекты в словари
    user_journeys = []
    for journey in user_journeys_rows:
        user_journeys.append({
            "email": journey["email"],
            "domain": journey["domain"],
            "has_email_click": bool(journey["has_email_click"]),
            "has_landing_click": bool(journey["has_landing_click"]),
            "has_conversion": bool(journey["has_conversion"]),
            "has_unsubscribe": bool(journey["has_unsubscribe"])
        })
    
    # Получаем общее количество для текущего фильтра
    count_query = """
        SELECT COUNT(DISTINCT email) as total
        FROM events
        WHERE campaign_id = $1
    """
    count_params = [campaign_id]
    
    if domain:
        count_query += " AND domain = $2"
        count_params.append(domain)
    
    if email_search:
        count_query += f" AND email ILIKE ${len(count_params) + 1}"
        count_params.append(f"%{email_search}%")
    
    total_result = await db.fetch_one(count_query, *count_params)
    total_users = total_result["total"] or 0 if total_result else 0
    
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
async def offers_list(request: Request):
    """Страница со списком всех офферов"""
    offers = await db.fetch_all("""
        SELECT 
            o.id,
            o.name,
            o.url,
            o.created_at,
            COUNT(DISTINCT c.id) as campaigns_count,
            COUNT(e.id) as total_events
        FROM offers o
        LEFT JOIN campaigns c ON o.id = c.offer_id
        LEFT JOIN events e ON c.id = e.campaign_id
        GROUP BY o.id, o.name, o.url, o.created_at
        ORDER BY o.created_at DESC
    """)
    
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
    url: str = Form(...)
):
    """Создание нового оффера"""
    
    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and URL are required")
    
    result = await db.fetch_one(
        "INSERT INTO offers (name, url) VALUES ($1, $2) RETURNING id",
        name,
        url
    )
    
    if request.headers.get("hx-request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/offer/{result['id']}"}
        )
    
    return RedirectResponse(url=f"/offer/{result['id']}", status_code=303)


@router.get("/offer/{offer_id}", response_class=HTMLResponse)
async def offer_detail(request: Request, offer_id: int):
    """Детальная страница оффера со статистикой"""
    
    offer = await db.fetch_one(
        "SELECT id, name, url, created_at FROM offers WHERE id = $1",
        offer_id
    )
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Общая статистика по офферу (через все кампании)
    overall_stats = await db.fetch_one("""
        SELECT 
            COUNT(DISTINCT c.id) as campaigns_count,
            COUNT(CASE WHEN e.event_type = 'email_click' THEN 1 END) as email_clicks,
            COUNT(CASE WHEN e.event_type = 'landing_click' THEN 1 END) as landing_clicks,
            COUNT(CASE WHEN e.event_type = 'conversion' THEN 1 END) as conversions,
            COUNT(CASE WHEN e.event_type = 'unsubscribe' THEN 1 END) as unsubscribes
        FROM offers o
        LEFT JOIN campaigns c ON o.id = c.offer_id
        LEFT JOIN events e ON c.id = e.campaign_id
        WHERE o.id = $1
    """, offer_id)
    
    # Статистика по кампаниям этого оффера
    campaigns_stats = await db.fetch_all("""
        SELECT 
            c.id,
            c.name,
            COUNT(CASE WHEN e.event_type = 'email_click' THEN 1 END) as email_clicks,
            COUNT(CASE WHEN e.event_type = 'landing_click' THEN 1 END) as landing_clicks,
            COUNT(CASE WHEN e.event_type = 'conversion' THEN 1 END) as conversions,
            COUNT(CASE WHEN e.event_type = 'unsubscribe' THEN 1 END) as unsubscribes
        FROM campaigns c
        LEFT JOIN events e ON c.id = e.campaign_id
        WHERE c.offer_id = $1
        GROUP BY c.id, c.name
        ORDER BY email_clicks DESC
    """, offer_id)
    
    # Вычисляем conversion rate
    email_clicks = overall_stats["email_clicks"] or 0
    conversions = overall_stats["conversions"] or 0
    conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
    
    return templates.TemplateResponse(
        "offer_detail.html",
        {
            "request": request,
            "offer": offer,
            "overall_stats": {
                "campaigns_count": overall_stats["campaigns_count"] or 0,
                "email_clicks": overall_stats["email_clicks"] or 0,
                "landing_clicks": overall_stats["landing_clicks"] or 0,
                "conversions": overall_stats["conversions"] or 0,
                "unsubscribes": overall_stats["unsubscribes"] or 0,
                "conversion_rate": conversion_rate
            },
            "campaigns_stats": campaigns_stats
        }
    )


@router.get("/offer/{offer_id}/edit", response_class=HTMLResponse)
async def edit_offer_page(request: Request, offer_id: int):
    """Страница редактирования оффера"""
    offer = await db.fetch_one(
        "SELECT id, name, url FROM offers WHERE id = $1",
        offer_id
    )
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    return templates.TemplateResponse(
        "edit_offer.html",
        {"request": request, "offer": offer}
    )


@router.post("/offer/{offer_id}/update")
async def update_offer(
    request: Request,
    offer_id: int,
    name: str = Form(...),
    url: str = Form(...)
):
    """Обновление оффера"""
    
    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and URL are required")
    
    # Проверяем существование оффера
    offer = await db.fetch_one("SELECT id FROM offers WHERE id = $1", offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Обновляем оффер
    await db.execute(
        "UPDATE offers SET name = $1, url = $2 WHERE id = $3",
        name,
        url,
        offer_id
    )
    
    # Обновляем offer_url во всех кампаниях с этим оффером
    await db.execute(
        "UPDATE campaigns SET offer_url = $1 WHERE offer_id = $2",
        url,
        offer_id
    )
    
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
    offer_id: int = Form(...)
):
    """Обновление оффера в кампании"""
    
    # Проверяем существование кампании
    campaign = await db.fetch_one("SELECT id FROM campaigns WHERE id = $1", campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Проверяем существование оффера
    offer = await db.fetch_one("SELECT id, url FROM offers WHERE id = $1", offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Обновляем оффер в кампании
    await db.execute(
        "UPDATE campaigns SET offer_id = $1, offer_url = $2 WHERE id = $3",
        offer_id,
        offer["url"],
        campaign_id
    )
    
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
