#!/bin/bash

# Скрипт для обновления бота через клонирование репозитория
# Вместо git pull полностью клонирует свежую версию репозитория

# Цвета для вывода
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
RESET="\033[0m"

# URL репозитория
REPO_URL="https://github.com/punk03/SFB_tg_bot.git"
# Директория для временного клонирования
TEMP_DIR="/tmp/sfb_bot_temp"
# Текущая директория бота
CURRENT_DIR=$(pwd)

echo -e "${GREEN}=== Обновление бота через клонирование репозитория ===${RESET}"

# Проверка наличия необходимых программ
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git не установлен. Установите Git для продолжения.${RESET}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose не установлен. Установите Docker Compose для продолжения.${RESET}"
    exit 1
fi

# Остановка бота
echo -e "${YELLOW}1. Останавливаем бота...${RESET}"
docker-compose down
echo -e "${GREEN}✅ Бот остановлен${RESET}"

# Сохранение файла .env
echo -e "${YELLOW}2. Сохранение конфигурации...${RESET}"
if [ -f ".env" ]; then
    cp .env .env.backup
    echo -e "${GREEN}✅ Файл .env сохранен${RESET}"
else
    echo -e "${RED}⚠️ Файл .env не найден, продолжаем без сохранения конфигурации${RESET}"
fi

# Сохранение директории logs, если она существует
if [ -d "logs" ]; then
    echo -e "${YELLOW}Сохранение логов...${RESET}"
    mkdir -p logs.backup
    cp -r logs/* logs.backup/ 2>/dev/null
    echo -e "${GREEN}✅ Логи сохранены${RESET}"
fi

# Клонирование свежей версии репозитория
echo -e "${YELLOW}3. Клонирование свежей версии репозитория...${RESET}"
rm -rf $TEMP_DIR
git clone $REPO_URL $TEMP_DIR
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка клонирования репозитория.${RESET}"
    echo -e "${BLUE}ℹ️ Восстанавливаем предыдущее состояние и запускаем бота...${RESET}"
    docker-compose up -d
    exit 1
fi
echo -e "${GREEN}✅ Репозиторий склонирован${RESET}"

# Копирование всех файлов из временной директории
echo -e "${YELLOW}4. Обновление файлов...${RESET}"

# Сначала удаляем старые файлы, кроме .env, .env.backup и директории logs
find $CURRENT_DIR -maxdepth 1 -not -path "$CURRENT_DIR" -not -path "$CURRENT_DIR/.env*" -not -path "$CURRENT_DIR/logs*" -not -path "$CURRENT_DIR/.git*" -exec rm -rf {} \;

# Копируем все файлы из временной директории
cp -r $TEMP_DIR/* $CURRENT_DIR/
echo -e "${GREEN}✅ Файлы обновлены${RESET}"

# Восстановление файла .env
if [ -f ".env.backup" ]; then
    echo -e "${YELLOW}5. Восстановление конфигурации...${RESET}"
    cp .env.backup .env
    echo -e "${GREEN}✅ Файл .env восстановлен${RESET}"
fi

# Восстановление директории logs
if [ -d "logs.backup" ]; then
    echo -e "${YELLOW}Восстановление логов...${RESET}"
    mkdir -p logs
    cp -r logs.backup/* logs/ 2>/dev/null
    rm -rf logs.backup
    echo -e "${GREEN}✅ Логи восстановлены${RESET}"
fi

# Делаем скрипты исполняемыми
echo -e "${YELLOW}6. Установка прав на исполнение скриптов...${RESET}"
chmod +x *.sh
echo -e "${GREEN}✅ Права установлены${RESET}"

# Очистка временной директории
echo -e "${YELLOW}7. Очистка временных файлов...${RESET}"
rm -rf $TEMP_DIR
if [ -f ".env.backup" ]; then
    rm .env.backup
fi
echo -e "${GREEN}✅ Временные файлы удалены${RESET}"

# Сборка и запуск обновленного бота
echo -e "${YELLOW}8. Сборка и запуск обновленного бота...${RESET}"
docker-compose build
docker-compose up -d
echo -e "${GREEN}✅ Бот собран и запущен${RESET}"

# Проверка статуса
echo -e "${YELLOW}9. Проверка статуса бота...${RESET}"
sleep 5  # Даем немного времени для запуска
if docker ps | grep -q "sfb"; then
    echo -e "${GREEN}✅ Бот успешно обновлен и запущен${RESET}"
    echo -e "${YELLOW}Последние логи бота:${RESET}"
    docker logs --tail 10 sfb
else
    echo -e "${RED}❌ Возникла проблема при запуске бота.${RESET}"
    echo -e "${YELLOW}Проверьте логи:${RESET}"
    docker-compose logs -t --tail 20
fi

echo -e "${GREEN}=== Обновление через клонирование репозитория завершено! ===${RESET}" 