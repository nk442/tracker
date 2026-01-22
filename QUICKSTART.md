# Быстрый старт Click Tracker

## 1. Установка зависимостей

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Настройка PostgreSQL

Создайте базу данных:

```bash
sudo -u postgres psql
CREATE DATABASE tracker_db;
CREATE USER tracker_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tracker_db TO tracker_user;
\q
```

Инициализируйте таблицы:

```bash
psql -U tracker_user -d tracker_db -f init.sql
```

## 3. Конфигурация

Создайте файл `.env` в корне проекта:

```env
DATABASE_URL=postgresql://tracker_user:your_password@localhost:5432/tracker_db
DEBUG=True
```

## 4. Добавление тестовых данных (опционально)

```bash
python add_test_data.py
```

## 5. Запуск сервера

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Откройте браузер: **http://localhost:8000**

## 6. Использование API

### Создание кампании

Через веб-интерфейс: http://localhost:8000/create

### Отправка событий

```bash
# Email click
curl "http://localhost:8000/api/event?cid=1&event=email_click&email=test@example.com&domain=example1.com"

# Landing click
curl "http://localhost:8000/api/event?cid=1&event=landing_click&email=test@example.com&domain=example1.com"

# Conversion
curl "http://localhost:8000/api/event?cid=1&event=conversion&email=test@example.com&domain=example1.com"
```

### Использование в коде

```python
import requests

# Отправка события
response = requests.get(
    "http://localhost:8000/api/event",
    params={
        "cid": 1,
        "event": "email_click",
        "email": "user@example.com",
        "domain": "example1.com",
        "utm_source": "newsletter",  # дополнительные параметры
        "utm_campaign": "summer_sale"
    }
)

print(response.json())  # {"status": "ok", "event_id": 123}
```

## 7. Интеграция на landing page

Добавьте на вашу landing page (замените параметры на реальные):

```html
<script>
// Получаем параметры из URL
const params = new URLSearchParams(window.location.search);
const cid = params.get('cid');
const email = params.get('email');
const domain = params.get('domain');

// Отправляем событие при загрузке страницы
if (cid && email && domain) {
    fetch(`https://tracker.com/api/event?cid=${cid}&event=landing_click&email=${email}&domain=${domain}`)
        .then(r => r.json())
        .then(data => console.log('Event tracked:', data));
}

// Отправляем событие при клике на кнопку CTA
document.querySelector('.cta-button').addEventListener('click', function() {
    if (cid && email && domain) {
        fetch(`https://tracker.com/api/event?cid=${cid}&event=conversion&email=${email}&domain=${domain}`)
            .then(r => r.json())
            .then(data => console.log('Conversion tracked:', data));
    }
});
</script>
```

## Возможные проблемы

### Ошибка подключения к БД

Проверьте:
- PostgreSQL запущен: `sudo systemctl status postgresql`
- Правильные данные в `.env`
- База данных создана: `psql -l`

### Ошибка импорта модулей

Убедитесь, что виртуальное окружение активировано:
```bash
source venv/bin/activate
```

### Порт уже занят

Измените порт при запуске:
```bash
uvicorn app.main:app --reload --port 8001
```
