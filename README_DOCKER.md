# Запуск бота "Строй Форум Белгород" в Docker

## Подготовка к запуску

### 1. Создайте файл с переменными окружения

Скопируйте файл `.env.example` в `.env` и заполните его необходимыми данными:

```bash
cp .env.example .env
```

Отредактируйте файл `.env`, указав ваши токены и идентификаторы:

```
TG_BOT_TOKEN=ваш_токен_телеграм_бота
VK_TOKEN=ваш_токен_вк_апи
VK_GROUP_ID=95855103
ADMIN_IDS=ваш_id_администратора
```

### 2. Создайте директорию для логов

```bash
mkdir -p logs
```

## Запуск бота

### Вариант 1: С использованием docker-compose (рекомендуется)

```bash
docker-compose up -d
```

Для просмотра логов:

```bash
docker-compose logs -f
```

Для остановки:

```bash
docker-compose down
```

### Вариант 2: Запуск с использованием Docker

Сборка образа:

```bash
docker build -t stroy-forum-bot .
```

Запуск контейнера:

```bash
docker run -d --name stroy-forum-bot \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env \
  --restart always \
  stroy-forum-bot
```

## Обновление бота

Для обновления бота до последней версии:

```bash
# Остановите текущий контейнер
docker-compose down

# Соберите новый образ и запустите его
docker-compose up -d --build
```

## Проверка статуса

Чтобы проверить, что бот запущен и работает:

```bash
docker ps | grep stroy-forum-bot
```

## Устранение неполадок

Если возникли проблемы с запуском, проверьте логи:

```bash
docker-compose logs
```

или

```bash
docker logs stroy-forum-bot
``` 