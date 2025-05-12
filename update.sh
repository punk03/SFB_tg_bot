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