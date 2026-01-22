# Развертывание трекера на production сервере

## Быстрый старт

### 1. Подготовка сервера

Установите Docker и Docker Compose на сервер:

```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER

# Установите Docker Compose
sudo apt install docker-compose-plugin -y
```

### 2. Загрузите проект на сервер

```bash
# Через git
git clone ваш_репозиторий
cd tracker

# Или загрузите архив и распакуйте
```

### 3. Настройте переменные окружения

**Все настройки теперь в одном файле `.env`!**

Создайте файл `.env` и настройте значения для production:

```bash
# База данных
POSTGRES_DB=tracker_db
POSTGRES_USER=tracker_user
POSTGRES_PASSWORD=ВАШИ_СЛОЖНЫЙ_ПАРОЛЬ_ЗДЕСЬ  # ОБЯЗАТЕЛЬНО измените!

# Приложение
DATABASE_URL=postgresql://tracker_user:ВАШИ_СЛОЖНЫЙ_ПАРОЛЬ_ЗДЕСЬ@db:5432/tracker_db
DEBUG=False  # ВАЖНО: отключите debug в production!
BASE_URL=http://ваш_ip:8000  # или домен
```

**Примеры BASE_URL:**
- По IP: `http://123.45.67.89:8000`
- По домену: `http://tracker.yourdomain.com`
- С HTTPS (если настроили SSL): `https://tracker.yourdomain.com`

**Важно:** Все значения в `.env` автоматически подхватываются и `docker-compose.yml`, и приложением. Не нужно менять `docker-compose.yml` вручную!

### 5. Запустите проект

```bash
# Соберите и запустите контейнеры
docker compose up -d --build

# Проверьте логи
docker compose logs -f app

# Проверьте статус
docker compose ps
```

### 6. Проверьте доступность

Откройте в браузере:
- `http://ваш_ip:8000` - главная страница
- `http://ваш_ip:8000/api/event?cid=1&event=email_click&email=test@test.com&domain=test.com` - тестовый API

## Настройка firewall

Откройте порт 8000:

```bash
# Для UFW (Ubuntu)
sudo ufw allow 8000/tcp
sudo ufw enable

# Для firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## Настройка домена (опционально)

### Вариант 1: Простой проброс через Nginx

Установите Nginx на хост-машине:

```bash
sudo apt install nginx -y
```

Создайте конфиг `/etc/nginx/sites-available/tracker`:

```nginx
server {
    listen 80;
    server_name tracker.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активируйте конфиг:

```bash
sudo ln -s /etc/nginx/sites-available/tracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Обновите `BASE_URL` в `.env` файле:

```bash
BASE_URL=http://tracker.yourdomain.com
```

### Вариант 2: SSL/HTTPS через Let's Encrypt

```bash
# Установите certbot
sudo apt install certbot python3-certbot-nginx -y

# Получите сертификат
sudo certbot --nginx -d tracker.yourdomain.com

# Certbot автоматически настроит SSL
```

Обновите `BASE_URL` в `.env` файле:

```bash
BASE_URL=https://tracker.yourdomain.com
```

## Обслуживание

### Просмотр логов

```bash
# Все логи
docker compose logs -f

# Только app
docker compose logs -f app

# Только БД
docker compose logs -f db
```

### Перезапуск

```bash
# Перезапустить все сервисы
docker compose restart

# Перезапустить только app
docker compose restart app
```

### Обновление кода

```bash
# Получите новый код
git pull

# Пересоберите и перезапустите
docker compose up -d --build

# Или без даунтайма:
docker compose build app
docker compose up -d app
```

### Бэкап базы данных

```bash
# Создать бэкап
docker compose exec db pg_dump -U tracker_user tracker_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из бэкапа
docker compose exec -T db psql -U tracker_user tracker_db < backup_20260122_123000.sql
```

### Остановка

```bash
# Остановить (сохраняет данные)
docker compose down

# Остановить и удалить данные БД
docker compose down -v
```

## Мониторинг

### Проверка здоровья контейнеров

```bash
docker compose ps
docker stats
```

### Автоматический рестарт

Контейнер app уже настроен с `restart: unless-stopped`, что означает автоматический перезапуск при сбое или перезагрузке сервера.

## Безопасность

### Чеклист для production:

- ✅ Измените пароли БД в `docker-compose.yml`
- ✅ Установите `DEBUG: "False"`
- ✅ Настройте firewall
- ✅ Используйте HTTPS (через Nginx + Let's Encrypt)
- ✅ Регулярно делайте бэкапы БД
- ✅ Обновляйте Docker образы: `docker compose pull && docker compose up -d`
- ✅ Ограничьте доступ к порту PostgreSQL (5432) - он не должен быть открыт извне

### Закрыть порт PostgreSQL

Если вы открывали порт 5432, закройте его:

```bash
# В docker-compose.yml удалите или закомментируйте:
# ports:
#   - "5432:5432"

# Перезапустите
docker compose up -d
```

## Проблемы и решения

### Проблема: контейнер app не запускается

```bash
# Проверьте логи
docker compose logs app

# Проверьте подключение к БД
docker compose exec app ping db
```

### Проблема: не могу подключиться извне

```bash
# Проверьте firewall
sudo ufw status

# Проверьте, слушает ли порт
sudo netstat -tulpn | grep 8000

# Проверьте доступ к серверу
curl http://localhost:8000
```

### Проблема: ссылки трекинга показывают localhost

Проверьте `BASE_URL` в `.env` файле и перезапустите:

```bash
# Убедитесь что BASE_URL правильный в .env
cat .env | grep BASE_URL

# Перезапустите приложение
docker compose up -d --force-recreate app
```

## Полезные команды

```bash
# Войти в контейнер app
docker compose exec app bash

# Войти в БД
docker compose exec db psql -U tracker_user tracker_db

# Просмотреть переменные окружения
docker compose exec app env

# Очистить старые образы
docker system prune -a
```
