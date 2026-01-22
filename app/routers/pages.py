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
    return templates.TemplateResponse("create.html", {"request": request})


@router.post("/campaigns")
async def create_campaign(
    request: Request,
    name: str = Form(...),
    offer_url: str = Form(...)
):
    """Создание новой кампании"""
    
    if not name or not offer_url:
        raise HTTPException(status_code=400, detail="Name and offer_url are required")
    
    result = await db.fetch_one(
        "INSERT INTO campaigns (name, offer_url) VALUES ($1, $2) RETURNING id",
        name,
        offer_url
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
            "SELECT id, name, offer_url, created_at FROM campaigns WHERE id = $1",
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
            "created_at": campaign_row["created_at"]
        }
        
        logger.debug("Fetching overall stats")
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
            "conversions": overall_stats_row["conversions"] or 0 if overall_stats_row else 0
        }
        
        # Вычисляем conversion rate
        email_clicks = overall_stats["email_clicks"]
        conversions = overall_stats["conversions"]
        conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
        
        logger.debug("Fetching domain stats")
        # Статистика по доменам
        domain_stats_rows = await db.fetch_all("""
            SELECT 
                domain,
                COUNT(CASE WHEN event_type = 'email_click' THEN 1 END) as email_clicks,
                COUNT(CASE WHEN event_type = 'landing_click' THEN 1 END) as landing_clicks,
                COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) as conversions
            FROM events
            WHERE campaign_id = $1
            GROUP BY domain
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
                    "has_conversion": bool(journey["has_conversion"])
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
            "conversions": overall_stats_row["conversions"] or 0 if overall_stats_row else 0
        }
        
        email_clicks = overall_stats["email_clicks"]
        conversions = overall_stats["conversions"]
        conversion_rate = (conversions / email_clicks * 100) if email_clicks > 0 else 0
        
        # Статистика по доменам
        domain_stats = await db.fetch_all("""
            SELECT 
                domain,
                COUNT(CASE WHEN event_type = 'email_click' THEN 1 END) as email_clicks,
                COUNT(CASE WHEN event_type = 'landing_click' THEN 1 END) as landing_clicks,
                COUNT(CASE WHEN event_type = 'conversion' THEN 1 END) as conversions
            FROM events
            WHERE campaign_id = $1
            GROUP BY domain
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
            "has_conversion": bool(journey["has_conversion"])
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
