"""
Пример скрипта для отправки событий в трекер.
Используйте этот скрипт на ваших landing pages для отправки событий.
"""

import requests
from urllib.parse import urlencode


def send_event(
    tracker_url: str,
    campaign_id: int,
    event_type: str,
    email: str,
    domain: str,
    **extra_params
):
    """
    Отправляет событие в трекер
    
    Args:
        tracker_url: URL трекера (например, http://tracker.com)
        campaign_id: ID кампании
        event_type: Тип события (email_click, landing_click, conversion)
        email: Email пользователя
        domain: Домен отправителя
        **extra_params: Дополнительные параметры (будут сохранены в JSONB)
    """
    
    params = {
        'cid': campaign_id,
        'event': event_type,
        'email': email,
        'domain': domain,
        **extra_params
    }
    
    url = f"{tracker_url}/api/event?{urlencode(params)}"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка отправки события: {e}")
        return None


if __name__ == "__main__":
    # Пример использования
    tracker_url = "http://localhost:8000"
    
    # Email click
    result = send_event(
        tracker_url=tracker_url,
        campaign_id=1,
        event_type="email_click",
        email="john@example.com",
        domain="example1.com",
        source="newsletter",
        utm_campaign="winter_sale"
    )
    print("Email click:", result)
    
    # Landing click
    result = send_event(
        tracker_url=tracker_url,
        campaign_id=1,
        event_type="landing_click",
        email="john@example.com",
        domain="example1.com",
        button="cta_primary"
    )
    print("Landing click:", result)
    
    # Conversion
    result = send_event(
        tracker_url=tracker_url,
        campaign_id=1,
        event_type="conversion",
        email="john@example.com",
        domain="example1.com",
        order_id="12345",
        amount="99.99"
    )
    print("Conversion:", result)
