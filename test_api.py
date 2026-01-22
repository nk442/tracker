"""
Тестовый скрипт для проверки работоспособности API трекера
"""
import requests
import sys
from urllib.parse import urlencode


TRACKER_URL = "http://localhost:8000"


def test_api_event(campaign_id: int, event_type: str, email: str, domain: str, **extra_params):
    """Тестирует отправку события в API"""
    
    params = {
        'cid': campaign_id,
        'event': event_type,
        'email': email,
        'domain': domain,
        **extra_params
    }
    
    url = f"{TRACKER_URL}/api/event?{urlencode(params)}"
    
    try:
        print(f"\n📤 Отправка события:")
        print(f"   URL: {url}")
        print(f"   Параметры: cid={campaign_id}, event={event_type}, email={email}, domain={domain}")
        if extra_params:
            print(f"   Доп. параметры: {extra_params}")
        
        response = requests.get(url, timeout=10)
        
        print(f"\n📥 Ответ сервера:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Успешно! Event ID: {data.get('event_id')}")
            return True, data
        else:
            print(f"   ❌ Ошибка: {response.text}")
            return False, None
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Ошибка подключения: не удалось подключиться к {TRACKER_URL}")
        print(f"   Убедитесь, что трекер запущен на {TRACKER_URL}")
        return False, None
    except requests.exceptions.Timeout:
        print(f"   ❌ Таймаут: сервер не ответил за 10 секунд")
        return False, None
    except Exception as e:
        print(f"   ❌ Неожиданная ошибка: {e}")
        return False, None


def test_invalid_event_type(campaign_id: int):
    """Тестирует обработку неверного типа события"""
    print(f"\n🧪 Тест: неверный тип события")
    params = {
        'cid': campaign_id,
        'event': 'invalid_event',
        'email': 'test@example.com',
        'domain': 'example.com'
    }
    url = f"{TRACKER_URL}/api/event?{urlencode(params)}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 400:
            print(f"   ✅ Корректно обработана ошибка: {response.json()}")
            return True
        else:
            print(f"   ❌ Ожидался статус 400, получен {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def test_nonexistent_campaign():
    """Тестирует обработку несуществующей кампании"""
    print(f"\n🧪 Тест: несуществующая кампания")
    params = {
        'cid': 99999,
        'event': 'email_click',
        'email': 'test@example.com',
        'domain': 'example.com'
    }
    url = f"{TRACKER_URL}/api/event?{urlencode(params)}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            print(f"   ✅ Корректно обработана ошибка: {response.json()}")
            return True
        else:
            print(f"   ❌ Ожидался статус 404, получен {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def get_first_campaign_id():
    """Получает ID первой доступной кампании"""
    try:
        response = requests.get(f"{TRACKER_URL}/", timeout=10)
        if response.status_code == 200:
            # Пытаемся найти campaign_id из HTML или просто возвращаем 1
            # Для простоты используем 1, но можно парсить HTML
            return 1
    except:
        pass
    return 1


def main():
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ API ТРЕКЕРА")
    print("=" * 60)
    
    # Проверяем доступность сервера
    print(f"\n1️⃣ Проверка доступности сервера {TRACKER_URL}...")
    try:
        response = requests.get(TRACKER_URL, timeout=5)
        if response.status_code == 200:
            print("   ✅ Сервер доступен")
        else:
            print(f"   ⚠️ Сервер ответил со статусом {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Сервер недоступен!")
        print(f"   Убедитесь, что трекер запущен на {TRACKER_URL}")
        sys.exit(1)
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        sys.exit(1)
    
    # Получаем ID кампании для тестов
    campaign_id = get_first_campaign_id()
    print(f"\n📋 Используем campaign_id={campaign_id} для тестов")
    print(f"   (если кампании нет, создайте её через веб-интерфейс)")
    
    # Тест 1: Валидное событие email_click
    print(f"\n" + "=" * 60)
    print("ТЕСТ 1: Отправка события email_click")
    print("=" * 60)
    success1, _ = test_api_event(
        campaign_id=campaign_id,
        event_type="email_click",
        email="test1@example.com",
        domain="example1.com",
        source="newsletter",
        utm_campaign="test_campaign"
    )
    
    # Тест 2: Валидное событие landing_click
    print(f"\n" + "=" * 60)
    print("ТЕСТ 2: Отправка события landing_click")
    print("=" * 60)
    success2, _ = test_api_event(
        campaign_id=campaign_id,
        event_type="landing_click",
        email="test1@example.com",
        domain="example1.com",
        button="cta_primary"
    )
    
    # Тест 3: Валидное событие conversion
    print(f"\n" + "=" * 60)
    print("ТЕСТ 3: Отправка события conversion")
    print("=" * 60)
    success3, _ = test_api_event(
        campaign_id=campaign_id,
        event_type="conversion",
        email="test1@example.com",
        domain="example1.com",
        order_id="12345",
        amount="99.99"
    )
    
    # Тест 4: Неверный тип события
    print(f"\n" + "=" * 60)
    print("ТЕСТ 4: Обработка неверного типа события")
    print("=" * 60)
    success4 = test_invalid_event_type(campaign_id)
    
    # Тест 5: Несуществующая кампания
    print(f"\n" + "=" * 60)
    print("ТЕСТ 5: Обработка несуществующей кампании")
    print("=" * 60)
    success5 = test_nonexistent_campaign()
    
    # Итоги
    print(f"\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    tests = [
        ("Email click", success1),
        ("Landing click", success2),
        ("Conversion", success3),
        ("Неверный тип события", success4),
        ("Несуществующая кампания", success5),
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    for name, success in tests:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} - {name}")
    
    print(f"\n   Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n   🎉 Все тесты пройдены успешно!")
        sys.exit(0)
    else:
        print(f"\n   ⚠️ {total - passed} тест(ов) не пройдено")
        sys.exit(1)


if __name__ == "__main__":
    main()
