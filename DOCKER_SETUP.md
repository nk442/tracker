# Запуск Click Tracker через Docker

## Требования

- Docker (версия 20.10+)
- Docker Compose (версия 1.29+)

Проверьте установку:
```bash
docker --version
docker-compose --version
```

## Быстрый запуск

### 1. Перейдите в директорию проекта
```bash
cd /home/nk4/Desktop/cursor/tracker
```

### 2. Запустите контейнеры
```bash
docker-compose up -d
```

Эта команда:
- Скачает образы PostgreSQL и Python
- Соберет образ приложения
- Создаст и запустит контейнеры
- Автоматически инициализирует базу данных

### 3. Проверьте статус
```bash
docker-compose ps
```

Должны быть запущены два сервиса:
- `tracker-db-1` (PostgreSQL)
- `tracker-app-1` (FastAPI приложение)

### 4. Откройте в браузере
**http://localhost:8000**

## Полезные команды

### Просмотр логов
```bash
# Все логи
docker-compose logs

# Логи приложения
docker-compose logs app

# Логи базы данных
docker-compose logs db

# Логи в реальном времени
docker-compose logs -f app
```

### Остановка контейнеров
```bash
docker-compose stop
```

### Запуск после остановки
```bash
docker-compose start
```

### Полная остановка и удаление
```bash
docker-compose down
```

### Удаление с данными БД
```bash
docker-compose down -v
```
⚠️ **Внимание:** Это удалит все данные из базы!

### Пересборка образов
```bash
# Если изменили код или зависимости
docker-compose up -d --build
```

## Добавление тестовых данных

### Вариант 1: Через Python скрипт (внутри контейнера)
```bash
# Запустите команду внутри контейнера приложения
docker-compose exec app python add_test_data.py
```

Но сначала нужно скопировать `add_test_data.py` в контейнер или изменить Dockerfile.

### Вариант 2: Через API (рекомендуется)
```bash
# Создайте кампанию через веб-интерфейс
# Или отправьте события через API:

curl "http://localhost:8000/api/event?cid=1&event=email_click&email=test@example.com&domain=example1.com"
```

## Подключение к базе данных

### Через psql внутри контейнера
```bash
docker-compose exec db psql -U tracker_user -d tracker_db
```

### Через внешний клиент
- **Host:** localhost
- **Port:** 5432
- **Database:** tracker_db
- **User:** tracker_user
- **Password:** tracker_password

## Отладка

### Войти в контейнер приложения
```bash
docker-compose exec app bash
```

### Проверить переменные окружения
```bash
docker-compose exec app env | grep DATABASE
```

### Перезапустить только приложение
```bash
docker-compose restart app
```

## Структура портов

- **8000** - FastAPI приложение (http://localhost:8000)
- **5432** - PostgreSQL (localhost:5432)

Если порты заняты, измените их в `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Внешний:Внутренний
```

## Решение проблем

### Порт 8000 уже занят
```bash
# Найдите процесс
sudo lsof -i :8000
# Или измените порт в docker-compose.yml
```

### Порт 5432 уже занят
```bash
# Если у вас уже запущен PostgreSQL локально
# Измените порт в docker-compose.yml:
ports:
  - "5433:5432"  # Используйте 5433 вместо 5432
```

### Ошибка при сборке
```bash
# Очистите кэш и пересоберите
docker-compose build --no-cache
docker-compose up -d
```

### База данных не инициализировалась
```bash
# Проверьте логи
docker-compose logs db

# Пересоздайте контейнеры
docker-compose down -v
docker-compose up -d
```

## Остановка и очистка

```bash
# Остановить контейнеры
docker-compose stop

# Удалить контейнеры
docker-compose down

# Удалить контейнеры + volumes (удалит данные БД)
docker-compose down -v

# Удалить контейнеры + volumes + образы
docker-compose down -v --rmi all
```
