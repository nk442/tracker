"""
Скрипт для добавления тестовых данных в базу.
Запустите после инициализации БД для создания примеров кампаний и событий.
Включает создание офферов, кампаний, событий и данных о количестве отправленных писем.
"""

import asyncio
import os
from datetime import datetime, timedelta
import random
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.database import Base, Offer, Campaign, Event, CampaignDomainEmails
from app.config import Settings


async def add_test_data():
    """Добавляет тестовые данные в базу"""
    
    # Подключение к БД (использует DATABASE_URL из окружения или значение по умолчанию)
    settings = Settings()
    database_url = settings.database_url.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    
    engine = create_async_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        try:
            # Создаем тестовые офферы
            offers = [
                ("Wellgreen Dog Food", "https://wellgreen.com/dog-food-offer?aff=123"),
                ("PetCo Cat Toys", "https://petco.com/cat-toys?aff=456"),
                ("HealthPlus Fish Oil", "https://healthplus.com/fish-oil?aff=789"),
            ]
            
            offer_ids = []
            for name, url in offers:
                new_offer = Offer(name=name, url=url)
                session.add(new_offer)
                await session.flush()
                offer_ids.append(new_offer.id)
                print(f"Создан оффер: {name} (ID: {new_offer.id})")
            
            # Создаем тестовые кампании с привязкой к офферам
            campaigns = [
                ("Dog Food US, Wellgreen", offer_ids[0]),
                ("Cat Toys EU, PetCo", offer_ids[1]),
                ("Fish Oil CA, HealthPlus", offer_ids[2]),
            ]
            
            campaign_ids = []
            for name, offer_id in campaigns:
                offer_result = await session.execute(
                    select(Offer).where(Offer.id == offer_id)
                )
                offer = offer_result.scalar_one()
                
                new_campaign = Campaign(
                    name=name,
                    offer_id=offer_id,
                    offer_url=offer.url
                )
                session.add(new_campaign)
                await session.flush()
                campaign_ids.append(new_campaign.id)
                print(f"Создана кампания: {name} (ID: {new_campaign.id})")
            
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
                    new_event = Event(
                        campaign_id=campaign_id,
                        event_type="email_click",
                        email=email,
                        domain=domain,
                        ip=f"192.168.1.{random.randint(1, 255)}",
                        user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                        created_at=base_time
                    )
                    session.add(new_event)
                    events_count += 1
                    domain_email_clicks[domain] += 1
                    
                    # Landing click (75% вероятность)
                    if random.random() < 0.75:
                        landing_event = Event(
                            campaign_id=campaign_id,
                            event_type="landing_click",
                            email=email,
                            domain=domain,
                            ip=f"192.168.1.{random.randint(1, 255)}",
                            user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                            created_at=base_time + timedelta(minutes=random.randint(1, 30))
                        )
                        session.add(landing_event)
                        events_count += 1
                        
                        # Conversion (25% вероятность от тех, кто кликнул на landing)
                        if random.random() < 0.25:
                            conversion_event = Event(
                                campaign_id=campaign_id,
                                event_type="conversion",
                                email=email,
                                domain=domain,
                                ip=f"192.168.1.{random.randint(1, 255)}",
                                user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                                created_at=base_time + timedelta(minutes=random.randint(30, 120))
                            )
                            session.add(conversion_event)
                            events_count += 1
                    
                    # Unsubscribe (5% вероятность)
                    if random.random() < 0.05:
                        unsubscribe_event = Event(
                            campaign_id=campaign_id,
                            event_type="unsubscribe",
                            email=email,
                            domain=domain,
                            ip=f"192.168.1.{random.randint(1, 255)}",
                            user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random.randint(500, 600)}.36",
                            created_at=base_time + timedelta(hours=random.randint(1, 48))
                        )
                        session.add(unsubscribe_event)
                        events_count += 1
                
                # Создаем записи о количестве отправленных писем для каждого домена
                # Количество отправленных писем должно быть >= количества email кликов
                for domain in domains:
                    email_clicks = domain_email_clicks[domain]
                    # Отправленных писем больше, чем кликов (не все письма были открыты)
                    emails_sent = email_clicks + random.randint(5, 30)
                    
                    # Проверяем, существует ли запись
                    existing_result = await session.execute(
                        select(CampaignDomainEmails).where(
                            CampaignDomainEmails.campaign_id == campaign_id,
                            CampaignDomainEmails.domain == domain
                        )
                    )
                    existing = existing_result.scalar_one_or_none()
                    
                    if existing:
                        existing.emails_sent = emails_sent
                        session.add(existing)
                    else:
                        new_domain_emails = CampaignDomainEmails(
                            campaign_id=campaign_id,
                            domain=domain,
                            emails_sent=emails_sent
                        )
                        session.add(new_domain_emails)
                    
                    print(f"  Домен {domain}: отправлено {emails_sent} писем, кликов {email_clicks}")
            
            await session.commit()
            
            print(f"\n✅ Создано {events_count} событий")
            print("✅ Тестовые данные успешно добавлены!")
            print("\nТеперь вы можете:")
            print("  1. Открыть http://localhost:8000 и увидеть данные")
            print("  2. Проверить статистику по доменам с колонкой 'Отправлено писем'")
            print("  3. Протестировать API: PUT /api/campaign/{campaign_id}/domain/{domain}/emails-sent")
            
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(add_test_data())
