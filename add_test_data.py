"""
Скрипт для добавления тестовых данных в базу.
Запустите после инициализации БД для создания примеров кампаний и событий.
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
        # Создаем тестовые кампании
        campaigns = [
            ("Dog Food US, Wellgreen", "https://wellgreen.com/dog-food-offer?aff=123"),
            ("Cat Toys EU, PetCo", "https://petco.com/cat-toys?aff=456"),
            ("Fish Oil CA, HealthPlus", "https://healthplus.com/fish-oil?aff=789"),
        ]
        
        campaign_ids = []
        for name, offer_url in campaigns:
            result = await conn.fetchrow(
                "INSERT INTO campaigns (name, offer_url) VALUES ($1, $2) RETURNING id",
                name,
                offer_url
            )
            campaign_ids.append(result["id"])
            print(f"Создана кампания: {name} (ID: {result['id']})")
        
        # Генерируем тестовые события
        domains = ["example1.com", "example2.com", "example3.com"]
        event_types = ["email_click", "landing_click", "conversion"]
        
        # Генерируем 100 уникальных email
        emails = [f"user{i}@example.com" for i in range(1, 101)]
        
        events_count = 0
        for campaign_id in campaign_ids:
            # Для каждой кампании создаем события от 30-40 пользователей
            selected_emails = random.sample(emails, random.randint(30, 40))
            
            for email in selected_emails:
                domain = random.choice(domains)
                
                # Email click (всегда есть)
                await conn.execute(
                    """
                    INSERT INTO events (campaign_id, event_type, email, domain, ip, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    campaign_id,
                    "email_click",
                    email,
                    domain,
                    f"192.168.1.{random.randint(1, 255)}",
                    datetime.now() - timedelta(days=random.randint(0, 7))
                )
                events_count += 1
                
                # Landing click (80% вероятность)
                if random.random() < 0.8:
                    await conn.execute(
                        """
                        INSERT INTO events (campaign_id, event_type, email, domain, ip, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        campaign_id,
                        "landing_click",
                        email,
                        domain,
                        f"192.168.1.{random.randint(1, 255)}",
                        datetime.now() - timedelta(days=random.randint(0, 7))
                    )
                    events_count += 1
                    
                    # Conversion (30% вероятность от тех, кто кликнул на landing)
                    if random.random() < 0.3:
                        await conn.execute(
                            """
                            INSERT INTO events (campaign_id, event_type, email, domain, ip, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            """,
                            campaign_id,
                            "conversion",
                            email,
                            domain,
                            f"192.168.1.{random.randint(1, 255)}",
                            datetime.now() - timedelta(days=random.randint(0, 7))
                        )
                        events_count += 1
        
        print(f"\nСоздано {events_count} событий")
        print("\nТестовые данные успешно добавлены!")
        print("Теперь вы можете открыть http://localhost:8000 и увидеть данные")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(add_test_data())
