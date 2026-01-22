"""
Скрипт для добавления тестовых данных в базу.
Запустите после инициализации БД для создания примеров кампаний и событий.
Включает создание офферов, кампаний, событий и данных о количестве отправленных писем.
"""

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
import random


async def add_test_data():
    """Добавляет тестовые данные в базу"""
    
    # Подключение к БД (использует DATABASE_URL из окружения или значение по умолчанию)
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/tracker_db"
    )
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Создаем тестовые офферы
        offers = [
            ("Wellgreen Dog Food", "https://wellgreen.com/dog-food-offer?aff=123"),
            ("PetCo Cat Toys", "https://petco.com/cat-toys?aff=456"),
            ("HealthPlus Fish Oil", "https://healthplus.com/fish-oil?aff=789"),
        ]
        
        offer_ids = []
        for name, url in offers:
            result = await conn.fetchrow(
                "INSERT INTO offers (name, url) VALUES ($1, $2) RETURNING id",
                name,
                url
            )
            offer_ids.append(result["id"])
            print(f"Создан оффер: {name} (ID: {result['id']})")
        
        # Создаем тестовые кампании с привязкой к офферам
        campaigns = [
            ("Dog Food US, Wellgreen", offer_ids[0]),
            ("Cat Toys EU, PetCo", offer_ids[1]),
            ("Fish Oil CA, HealthPlus", offer_ids[2]),
        ]
        
        campaign_ids = []
        for name, offer_id in campaigns:
            offer = await conn.fetchrow("SELECT url FROM offers WHERE id = $1", offer_id)
            result = await conn.fetchrow(
                "INSERT INTO campaigns (name, offer_id, offer_url) VALUES ($1, $2, $3) RETURNING id",
                name,
                offer_id,
                offer["url"]
            )
            campaign_ids.append(result["id"])
            print(f"Создана кампания: {name} (ID: {result['id']})")
        
        # Генерируем тестовые домены
        domains = ["example1.com", "example2.com", "example3.com"]
        
        # Генерируем 100 уникальных email
        emails = [f"user{i}@example.com" for i in range(1, 101)]
        
        events_count = 0
        
        # Для каждой кампании создаем данные
        for campaign_id in campaign_ids:
            print(f"\nОбработка кампании ID: {campaign_id}")
            
            # Словарь для подсчета email кликов по доменам (для расчета отправленных писем)
            domain_email_clicks = {domain: 0 for domain in domains}
            
            # Для каждой кампании создаем события от 30-50 пользователей
            selected_emails = random.sample(emails, random.randint(30, 50))
            
            for email in selected_emails:
                domain = random.choice(domains)
                base_time = datetime.now() - timedelta(days=random.randint(0, 7))
                
                # Email click (всегда есть)
                await conn.execute(
                    """
                    INSERT INTO events (campaign_id, event_type, email, domain, ip, user_agent, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    campaign_id,
                    "email_click",
                    email,
                    domain,
                    f"192.168.1.{random.randint(1, 255)}",
                    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                    base_time
                )
                events_count += 1
                domain_email_clicks[domain] += 1
                
                # Landing click (75% вероятность)
                if random.random() < 0.75:
                    await conn.execute(
                        """
                        INSERT INTO events (campaign_id, event_type, email, domain, ip, user_agent, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        campaign_id,
                        "landing_click",
                        email,
                        domain,
                        f"192.168.1.{random.randint(1, 255)}",
                        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                        base_time + timedelta(minutes=random.randint(1, 30))
                    )
                    events_count += 1
                    
                    # Conversion (25% вероятность от тех, кто кликнул на landing)
                    if random.random() < 0.25:
                        await conn.execute(
                            """
                            INSERT INTO events (campaign_id, event_type, email, domain, ip, user_agent, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            """,
                            campaign_id,
                            "conversion",
                            email,
                            domain,
                            f"192.168.1.{random.randint(1, 255)}",
                            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                            base_time + timedelta(minutes=random.randint(30, 120))
                        )
                        events_count += 1
                
                # Unsubscribe (5% вероятность)
                if random.random() < 0.05:
                    await conn.execute(
                        """
                        INSERT INTO events (campaign_id, event_type, email, domain, ip, user_agent, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        campaign_id,
                        "unsubscribe",
                        email,
                        domain,
                        f"192.168.1.{random.randint(1, 255)}",
                        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                        base_time + timedelta(hours=random.randint(1, 48))
                    )
                    events_count += 1
            
            # Создаем записи о количестве отправленных писем для каждого домена
            # Количество отправленных писем должно быть >= количества email кликов
            for domain in domains:
                email_clicks = domain_email_clicks[domain]
                # Отправленных писем больше, чем кликов (не все письма были открыты)
                emails_sent = email_clicks + random.randint(5, 30)
                
                await conn.execute(
                    """
                    INSERT INTO campaign_domain_emails (campaign_id, domain, emails_sent)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (campaign_id, domain) 
                    DO UPDATE SET emails_sent = EXCLUDED.emails_sent, updated_at = NOW()
                    """,
                    campaign_id,
                    domain,
                    emails_sent
                )
                print(f"  Домен {domain}: отправлено {emails_sent} писем, кликов {email_clicks}")
        
        print(f"\n✅ Создано {events_count} событий")
        print("✅ Тестовые данные успешно добавлены!")
        print("\nТеперь вы можете:")
        print("  1. Открыть http://localhost:8000 и увидеть данные")
        print("  2. Проверить статистику по доменам с колонкой 'Отправлено писем'")
        print("  3. Протестировать API: PUT /api/campaign/{campaign_id}/domain/{domain}/emails-sent")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(add_test_data())
