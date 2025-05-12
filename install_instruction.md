# Пошаговая инструкция по установке бота СФБ на сервере

## Шаг 1: Подключение к серверу

```bash
ssh fil@172.22.224.43
```

Когда будет запрошен пароль, введите: `3325`

## Шаг 2: Создание временной директории и скачивание файлов

```bash
mkdir -p ~/temp
cd ~/temp
```

## Шаг 3: Создание всех необходимых файлов

### 3.1. Создание скрипта setup.sh
```bash
cat > setup.sh << 'EOF'
#!/bin/bash

# Путь к папке проекта
PROJECT_DIR="/home/fil/SFB_tg_bot"

# Создаем директорию проекта, если она не существует
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR || { echo "Не удалось перейти в директорию проекта"; exit 1; }

# Клонируем репозиторий, если директория пуста
if [ -z "$(ls -A $PROJECT_DIR)" ]; then
    echo "Клонирование репозитория..."
    git clone https://github.com/punk03/SFB_tg_bot.git .
    if [ $? -ne 0 ]; then
        echo "Ошибка при клонировании репозитория."
        exit 1
    fi
    echo "Репозиторий успешно клонирован."
else
    echo "Директория не пуста. Пропускаем клонирование."
fi

# Создаем директорию для логов
mkdir -p logs

# Проверяем наличие файла .env
if [ ! -f ".env" ]; then
    echo "Файл .env не найден. Создаем из шаблона..."
    # Если есть файл-шаблон .env.example, копируем его
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Файл .env создан из шаблона. Пожалуйста, отредактируйте его и впишите ваши токены."
    else
        # Если шаблона нет, создаем пустой файл .env
        touch .env
        echo "TG_BOT_TOKEN=" >> .env
        echo "VK_TOKEN=" >> .env
        echo "VK_GROUP_ID=95855103" >> .env
        echo "ADMIN_IDS=" >> .env
        echo "Создан пустой файл .env. Пожалуйста, впишите ваши токены."
    fi
fi

# Создаем файл docker-compose.yml
cat > docker-compose.yml << 'EOFDC'
version: '3'

services:
  stroy-forum-bot:
    build: .
    container_name: stroy-forum-bot
    restart: always
    volumes:
      - ./logs:/app/logs
      - ./.env:/app/.env
    environment:
      - TZ=Europe/Moscow
    networks:
      - bot-network
      
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: always
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 300 stroy-forum-bot --cleanup
    environment:
      - TZ=Europe/Moscow
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge
EOFDC

# Создаем файл Dockerfile
cat > Dockerfile << 'EOFD'
FROM python:3.9-slim

WORKDIR /app

# Установка Git для webhook
RUN apt-get update && apt-get install -y git && apt-get clean

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Создаём каталог для логов
RUN mkdir -p logs

# Права на выполнение скриптов
RUN chmod +x *.sh

# Запускаем бота
CMD ["python", "main.py"]
EOFD

# Создаем скрипт обновления
cat > update.sh << 'EOFU'
#!/bin/bash

# Путь к папке проекта
PROJECT_DIR="/home/fil/SFB_tg_bot"

# Перейти в папку проекта
cd $PROJECT_DIR || { echo "Не удалось перейти в директорию проекта"; exit 1; }

# Сохраняем текущую дату и время
DATE=$(date '+%Y-%m-%d_%H-%M-%S')

# Создаем лог-файл
LOG_FILE="$PROJECT_DIR/logs/update_$DATE.log"
touch $LOG_FILE

# Функция для логирования
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

log "Начало обновления бота SFB Telegram"

# Проверяем, существует ли файл .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
  log "Файл .env не найден. Создайте его перед обновлением."
  exit 1
fi

# Получаем обновления из репозитория
log "Получение обновлений из GitHub..."
git fetch origin main >> $LOG_FILE 2>&1
git reset --hard origin/main >> $LOG_FILE 2>&1

if [ $? -ne 0 ]; then
  log "Ошибка при получении обновлений из GitHub."
  exit 1
fi

log "Обновления из GitHub успешно получены."

# Пересобираем и перезапускаем Docker-контейнер
log "Перезапуск Docker-контейнера..."
docker-compose down >> $LOG_FILE 2>&1
docker-compose up -d --build >> $LOG_FILE 2>&1

if [ $? -ne 0 ]; then
  log "Ошибка при перезапуске Docker-контейнера."
  exit 1
fi

log "Docker-контейнер успешно перезапущен."
log "Обновление завершено."

# Выводим статус контейнера
log "Статус контейнера:"
docker ps | grep stroy-forum-bot | tee -a $LOG_FILE

exit 0
EOFU

# Создаем обработчик вебхуков
cat > webhook-handler.sh << 'EOFWH'
#!/bin/bash

# Путь к скрипту обновления
UPDATE_SCRIPT="/home/fil/SFB_tg_bot/update.sh"
LOG_FILE="/home/fil/SFB_tg_bot/logs/webhook-$(date '+%Y-%m-%d').log"

# Функция для логирования
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Запись начала работы скрипта
log "Получен webhook от GitHub"

# Проверка существования файла обновления
if [ ! -f "$UPDATE_SCRIPT" ]; then
  log "Ошибка: скрипт обновления не найден по пути $UPDATE_SCRIPT"
  exit 1
fi

# Проверка, не запущен ли уже скрипт обновления
if pgrep -f "$UPDATE_SCRIPT" > /dev/null; then
  log "Обновление уже запущено, пропускаем"
  exit 0
fi

# Запуск скрипта обновления
log "Запуск скрипта обновления..."
bash "$UPDATE_SCRIPT" >> "$LOG_FILE" 2>&1 &

log "Скрипт обновления запущен в фоновом режиме"
exit 0
EOFWH

# Устанавливаем права на выполнение скриптов
chmod +x *.sh

# Настройки CRON для автоматического обновления (каждые 30 минут)
if ! crontab -l | grep -q "SFB_tg_bot/update.sh"; then
    echo "Добавление задачи в CRON для автоматического обновления..."
    (crontab -l 2>/dev/null; echo "*/30 * * * * $PROJECT_DIR/update.sh") | crontab -
    echo "Задача CRON успешно добавлена."
fi

# Запуск в Docker
echo "Запуск в Docker..."
docker-compose up -d --build

if [ $? -ne 0 ]; then
    echo "Ошибка при запуске Docker-контейнера."
    exit 1
fi

echo "SFB Telegram бот успешно установлен и запущен."
echo "Статус контейнера:"
docker ps | grep stroy-forum-bot

exit 0
EOF

### 3.2. Установите права на выполнение скрипта
```bash
chmod +x setup.sh
```

## Шаг 4: Выполнение установки

```bash
./setup.sh
```

## Шаг 5: Настройка токенов

После завершения установки отредактируйте файл .env с токенами:

```bash
cd /home/fil/SFB_tg_bot
nano .env
```

Впишите необходимые токены:
```
TG_BOT_TOKEN=ваш_токен_телеграм_бота
VK_TOKEN=ваш_токен_вк_апи
VK_GROUP_ID=95855103
ADMIN_IDS=ваш_id_администратора
```

Для сохранения и выхода из редактора нажмите: Ctrl+O, затем Enter, затем Ctrl+X

## Шаг 6: Перезапуск бота

```bash
docker-compose down
docker-compose up -d --build
```

## Шаг 7: Проверка статуса

```bash
docker ps | grep stroy-forum-bot
```

Если вы видите запущенный контейнер stroy-forum-bot, значит установка прошла успешно.

## Дополнительные команды

### Просмотр логов бота
```bash
docker-compose logs -f stroy-forum-bot
```

### Ручное обновление бота
```bash
./update.sh
```

### Проверка заданий CRON
```bash
crontab -l
``` 