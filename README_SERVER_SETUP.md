# Инструкция по установке бота СФБ на сервере

## Требования

- SSH-доступ к серверу
- Docker и Docker Compose
- Git
- Права на создание cron задач

## Начальная установка

1. **Подключение к серверу:**

```bash
ssh fil@172.22.224.43
```

2. **Скачивание скриптов установки:**

```bash
mkdir -p ~/temp
cd ~/temp
curl -O https://raw.githubusercontent.com/punk03/SFB_tg_bot/main/setup.sh
chmod +x setup.sh
```

3. **Запуск установки:**

```bash
./setup.sh
```

Скрипт выполнит следующие действия:
- Создаст директорию `/home/fil/SFB_tg_bot`
- Клонирует репозиторий GitHub
- Создаст файл `.env` из шаблона
- Настроит CRON для автоматических обновлений
- Запустит бота в Docker-контейнере

4. **Настройка переменных окружения:**

После установки отредактируйте файл `.env`:

```bash
nano /home/fil/SFB_tg_bot/.env
```

Укажите необходимые токены:
```
TG_BOT_TOKEN=ваш_токен_телеграм_бота
VK_TOKEN=ваш_токен_вк_апи
VK_GROUP_ID=95855103
ADMIN_IDS=ваш_id_администратора
```

5. **Перезапуск бота:**

```bash
cd /home/fil/SFB_tg_bot
docker-compose down
docker-compose up -d --build
```

## Автоматическое обновление

Бот настроен на автоматическое обновление из репозитория GitHub двумя способами:

### 1. Регулярные проверки через CRON

Скрипт установки добавил задачу в CRON, которая каждые 30 минут проверяет наличие обновлений в репозитории и обновляет бота при необходимости.

Для просмотра текущих CRON-задач:
```bash
crontab -l
```

### 2. Обновление через Watchtower

В docker-compose.yml добавлен сервис Watchtower, который каждые 5 минут проверяет обновления образа контейнера.

### 3. Ручное обновление

Если вам нужно обновить бота вручную:

```bash
cd /home/fil/SFB_tg_bot
./update.sh
```

## Мониторинг и управление

### Проверка статуса

```bash
docker ps | grep stroy-forum-bot
```

### Просмотр логов

```bash
# Логи бота
docker-compose logs -f stroy-forum-bot

# Логи обновлений
ls -la /home/fil/SFB_tg_bot/logs/update_*.log
```

### Остановка бота

```bash
cd /home/fil/SFB_tg_bot
docker-compose down
```

### Перезапуск бота

```bash
cd /home/fil/SFB_tg_bot
docker-compose up -d
```

## Устранение неполадок

### Если бот не запускается

1. Проверьте логи:
```bash
docker-compose logs stroy-forum-bot
```

2. Убедитесь, что файл `.env` содержит корректные данные

3. Проверьте доступность внешних API (Telegram, ВКонтакте)

### Если не происходит обновление

1. Проверьте логи обновлений:
```bash
ls -la /home/fil/SFB_tg_bot/logs/
cat /home/fil/SFB_tg_bot/logs/update_*.log
```

2. Убедитесь, что скрипт имеет права на выполнение:
```bash
chmod +x /home/fil/SFB_tg_bot/update.sh
```

3. Проверьте, запущен ли Watchtower:
```bash
docker ps | grep watchtower
``` 