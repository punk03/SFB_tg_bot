#!/bin/bash

# Скрипт для переустановки Docker-контейнера с последними обновлениями из GitHub
# и правильной конфигурацией файла .env

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Запуск скрипта обновления бота СФБ в Docker...${NC}"

# Переменные
REPO_URL="https://github.com/punk03/SFB_tg_bot.git"
PROJECT_DIR="/opt/sfb_bot"
CONTAINER_NAME="sfb_bot"
ENV_FILE="${PROJECT_DIR}/.env"
ADMIN_IDS="771824107"

# Функция для создания файла .env с правильными кодировками
create_env_file() {
    echo -e "${YELLOW}Создание файла .env...${NC}"
    
    # Проверяем, существует ли уже файл .env для сохранения токенов
    if [ -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}Обнаружен существующий файл .env. Сохраняем токены...${NC}"
        # Извлекаем токены из существующего файла
        TG_BOT_TOKEN=$(grep "TG_BOT_TOKEN" "$ENV_FILE" | cut -d "=" -f2)
        VK_TOKEN=$(grep "VK_TOKEN" "$ENV_FILE" | cut -d "=" -f2)
        TG_GROUP_ID=$(grep "TG_GROUP_ID" "$ENV_FILE" | cut -d "=" -f2)
        VK_GROUP_ID=$(grep "VK_GROUP_ID" "$ENV_FILE" | cut -d "=" -f2)
    else
        echo -e "${YELLOW}Файл .env не найден. Пожалуйста, введите токены:${NC}"
        read -p "Введите TG_BOT_TOKEN: " TG_BOT_TOKEN
        read -p "Введите VK_TOKEN: " VK_TOKEN
        read -p "Введите TG_GROUP_ID: " TG_GROUP_ID
        read -p "Введите VK_GROUP_ID: " VK_GROUP_ID
    fi
    
    # Создаем новый файл .env с UTF-8 кодировкой
    cat > "$ENV_FILE" << EOL
# Конфигурация для бота СФБ
# Файл создан автоматически скриптом update_docker.sh

# Токены и ID
TG_BOT_TOKEN=$TG_BOT_TOKEN
VK_TOKEN=$VK_TOKEN
TG_GROUP_ID=$TG_GROUP_ID
VK_GROUP_ID=$VK_GROUP_ID

# Администраторы
ADMIN_IDS=$ADMIN_IDS

# Настройки бота
CACHE_TIME=3600
PHOTO_DELAY=0.5
DEBUG=False
EOL
    
    echo -e "${GREEN}Файл .env успешно создан с правильной кодировкой!${NC}"
}

# Шаг 1: Убедиться, что Docker установлен
echo -e "${YELLOW}Проверка наличия установленного Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker не установлен! Пожалуйста, установите Docker и запустите скрипт снова.${NC}"
    exit 1
else
    echo -e "${GREEN}Docker установлен!${NC}"
fi

# Шаг 2: Создать директорию проекта, если она не существует
echo -e "${YELLOW}Проверка директории проекта...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Директория проекта не существует. Создаём...${NC}"
    mkdir -p "$PROJECT_DIR"
    echo -e "${GREEN}Директория создана: $PROJECT_DIR${NC}"
else
    echo -e "${GREEN}Директория проекта уже существует: $PROJECT_DIR${NC}"
fi

# Шаг 3: Перейти в директорию проекта
cd "$PROJECT_DIR"
echo -e "${GREEN}Текущая директория: $(pwd)${NC}"

# Шаг 4: Клонировать или обновить репозиторий
if [ -d ".git" ]; then
    echo -e "${YELLOW}Обновляем репозиторий...${NC}"
    git reset --hard
    git pull
    echo -e "${GREEN}Репозиторий обновлен!${NC}"
else
    echo -e "${YELLOW}Клонируем репозиторий...${NC}"
    # Если директория не пуста, удалить все файлы (кроме .env, если он существует)
    if [ "$(ls -A | grep -v '.env')" ]; then
        find . -not -name '.env' -not -path './.git*' -delete
    fi
    git clone "$REPO_URL" .
    echo -e "${GREEN}Репозиторий успешно клонирован!${NC}"
fi

# Шаг 5: Создать файл .env с правильными кодировками
create_env_file

# Шаг 6: Остановить и удалить существующий контейнер, если он есть
echo -e "${YELLOW}Проверяем, запущен ли контейнер...${NC}"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}Останавливаем и удаляем существующий контейнер...${NC}"
    docker stop "$CONTAINER_NAME"
    docker rm "$CONTAINER_NAME"
    echo -e "${GREEN}Существующий контейнер удален!${NC}"
else
    echo -e "${GREEN}Контейнер не найден. Продолжаем установку...${NC}"
fi

# Шаг 7: Удаление старого образа (опционально)
echo -e "${YELLOW}Удаляем старый образ, если он существует...${NC}"
if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${CONTAINER_NAME}:latest$"; then
    docker rmi "${CONTAINER_NAME}:latest"
    echo -e "${GREEN}Старый образ удален!${NC}"
else
    echo -e "${GREEN}Старый образ не найден. Продолжаем...${NC}"
fi

# Шаг 8: Сборка и запуск Docker-контейнера
echo -e "${YELLOW}Собираем и запускаем новый Docker-контейнер...${NC}"
docker-compose up --build -d

# Шаг 9: Проверка, что контейнер запущен
echo -e "${YELLOW}Проверяем, запущен ли новый контейнер...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${GREEN}Контейнер успешно запущен!${NC}"
    echo -e "${GREEN}Бот СФБ успешно обновлен и запущен в Docker!${NC}"
else
    echo -e "${RED}Ошибка! Контейнер не запущен. Проверьте журналы Docker:${NC}"
    echo -e "${YELLOW}docker logs ${CONTAINER_NAME}${NC}"
    exit 1
fi

# Шаг 10: Вывод журналов контейнера (опционально)
echo -e "${YELLOW}Хотите посмотреть логи бота? (y/n)${NC}"
read -r show_logs
if [ "$show_logs" = "y" ] || [ "$show_logs" = "Y" ]; then
    docker logs -f "$CONTAINER_NAME"
fi

echo -e "${GREEN}Скрипт завершен успешно!${NC}" 