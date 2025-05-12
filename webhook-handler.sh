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