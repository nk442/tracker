# Click Tracker MVP

Система трекинга кликов для email-кампаний с FastAPI, PostgreSQL и HTMX.

## Требования

- Python 3.11+
- PostgreSQL 14+

## Установка

1. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте базу данных PostgreSQL:
```bash
createdb tracker_db
```

4. Инициализируйте таблицы:
```bash
psql -d tracker_db -f init.sql
```

5. Создайте файл `.env` и настройте подключение к БД:
```bash
# Создайте файл .env со следующим содержимым:
# База данных
POSTGRES_DB=tracker_db
POSTGRES_USER=tracker_user
POSTGRES_PASSWORD=your_password

# Приложение
DATABASE_URL=postgresql://tracker_user:your_password@localhost:5432/tracker_db
DEBUG=True
BASE_URL=http://localhost:8000
```

**Важно:** Замените `your_password` на пароль, который вы использовали при создании пользователя PostgreSQL.

6. Запустите сервер:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. Откройте в браузере: http://localhost:8000

## API

### Прием событий

```
GET /api/event?cid=5&event=email_click&email=john@gmail.com&domain=example1.com
```

Параметры:
- `cid` - ID кампании (обязательный)
- `event` - тип события: `email_click`, `landing_click`, `conversion` (обязательный)
- `email` - email пользователя (обязательный)
- `domain` - домен отправителя (обязательный)
- любые дополнительные параметры сохраняются в JSONB

## Структура проекта

```
tracker/
├── app/
│   ├── main.py              # FastAPI приложение
│   ├── config.py            # Конфигурация
│   ├── database.py          # Подключение к БД
│   ├── models/
│   │   └── schemas.py       # Pydantic модели
│   ├── routers/
│   │   ├── api.py           # API endpoints
│   │   └── pages.py         # HTML страницы
│   └── templates/           # Jinja2 шаблоны
├── static/                  # CSS
├── requirements.txt
├── init.sql                 # SQL схема
└── .env                     # Конфигурация (не в git)
```

## Лицензия

MIT
