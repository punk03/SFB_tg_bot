#!/bin/bash

# Скрипт для полной переустановки бота СФБ на Ubuntu
# Этот скрипт удаляет старые файлы, клонирует новый репозиторий и разворачивает Docker-контейнер

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Проверка, запущен ли скрипт с правами root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Этот скрипт должен быть запущен с правами root (sudo)${NC}"
  echo -e "Запустите: ${YELLOW}sudo bash $0${NC}"
  exit 1
fi

echo -e "${BOLD}${BLUE}╔═════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║   УСТАНОВКА БОТА СТРОЙ ФОРУМ БЕЛГОРОД   ║${NC}"
echo -e "${BOLD}${BLUE}╚═════════════════════════════════════════╝${NC}"
echo

# Переменные
REPO_URL="https://github.com/punk03/SFB_tg_bot.git"
INSTALL_DIR="/opt/sfb_bot"
CONTAINER_NAME="sfb_bot"
ENV_FILE="${INSTALL_DIR}/.env"

# Шаг 1: Проверка наличия Docker и Docker Compose
echo -e "${YELLOW}[1/8] Проверка наличия Docker и Docker Compose...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker не установлен!${NC}"
    echo -e "${YELLOW}Установка Docker...${NC}"
    apt-get update
    apt-get install -y docker.io
    systemctl enable docker
    systemctl start docker
else
    echo -e "${GREEN}Docker уже установлен.${NC}"
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose не установлен!${NC}"
    echo -e "${YELLOW}Установка Docker Compose...${NC}"
    apt-get update
    apt-get install -y docker-compose
else
    echo -e "${GREEN}Docker Compose уже установлен.${NC}"
fi
echo -e "${GREEN}[1/8] Проверка Docker завершена.✓${NC}"

# Шаг 2: Остановка и удаление существующего контейнера
echo -e "${YELLOW}[2/8] Поиск и удаление старых контейнеров...${NC}"
if docker ps -a --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    echo -e "${YELLOW}Найден существующий контейнер. Останавливаем и удаляем...${NC}"
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    echo -e "${GREEN}Контейнер остановлен и удален.${NC}"
else
    echo -e "${GREEN}Старые контейнеры не найдены.${NC}"
fi
echo -e "${GREEN}[2/8] Удаление старых контейнеров завершено.✓${NC}"

# Шаг 3: Удаление старого образа Docker
echo -e "${YELLOW}[3/8] Проверка и удаление старого образа Docker...${NC}"
if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${CONTAINER_NAME}:latest$"; then
    echo -e "${YELLOW}Удаляем старый образ Docker...${NC}"
    docker rmi "${CONTAINER_NAME}:latest" 2>/dev/null || true
    echo -e "${GREEN}Старый образ удален.${NC}"
else
    echo -e "${GREEN}Старые образы не найдены.${NC}"
fi
echo -e "${GREEN}[3/8] Удаление старых образов завершено.✓${NC}"

# Шаг 4: Удаление старой директории и создание новой
echo -e "${YELLOW}[4/8] Подготовка директории для установки...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Удаление старой директории бота...${NC}"
    rm -rf "$INSTALL_DIR"
fi
echo -e "${YELLOW}Создание новой директории для установки...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}[4/8] Подготовка директории завершена.✓${NC}"

# Шаг 5: Клонирование репозитория
echo -e "${YELLOW}[5/8] Клонирование репозитория из GitHub...${NC}"
git clone "$REPO_URL" "$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo -e "${RED}Ошибка при клонировании репозитория!${NC}"
    exit 1
fi
echo -e "${GREEN}[5/8] Репозиторий успешно клонирован.✓${NC}"

# Шаг 6: Создание .env файла с токенами
echo -e "${YELLOW}[6/8] Настройка переменных окружения...${NC}"
echo -e "${BLUE}Введите данные для конфигурации бота:${NC}"

# Запрос токенов и ID от пользователя
read -p "Введите TG_BOT_TOKEN(по умолчанию 7737130819:AAGTZICY6ztnYLzfceUvddCVWGORM3CFlJY): " TG_BOT_TOKEN
read -p "Введите VK_TOKEN(по умолчанию vk1.a.8kZbOfrvb6nct1zqmabnqgmSONX6-eUm_pPouRfrAd6ibjoHvC91LuERdXCB-FvNGXL_ZNJnC81czt7Hal68pLWETv2C-SmBTKWhscS09-EsisxTcg9kUa7yWLnUusmKKEiu5SzsUuBZV5FRks7bY6D42nK04Y54C_66EldapwYc_q-iubdiYzWFfJg9Jzm5cxeA26bfcfF2JGt5OfzTsw): " VK_TOKEN
read -p "Введите TG_GROUP_ID: " TG_GROUP_ID
read -p "Введите VK_GROUP_ID (по умолчанию 95855103): " VK_GROUP_ID
VK_GROUP_ID=${VK_GROUP_ID:-95855103}
read -p "Введите ADMIN_IDS (ID админов через запятую): " ADMIN_IDS

# Создание .env файла
cat > "$ENV_FILE" << EOL
# Конфигурация бота СФБ
# Создано автоматически скриптом deploy_sfb_bot.sh

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

echo -e "${GREEN}[6/8] Файл .env успешно создан.✓${NC}"

# Шаг 7: Установка прав на директорию
echo -e "${YELLOW}[7/8] Настройка прав доступа...${NC}"
chown -R $(whoami):$(whoami) "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
echo -e "${GREEN}[7/8] Права доступа настроены.✓${NC}"

# Шаг 8: Сборка и запуск Docker-контейнера
echo -e "${YELLOW}[8/8] Сборка и запуск Docker-контейнера...${NC}"
cd "$INSTALL_DIR"
docker-compose up --build -d

# Проверка успешного запуска
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    echo -e "${GREEN}[8/8] Контейнер успешно запущен.✓${NC}"
    echo
    echo -e "${BOLD}${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║  БОТ СТРОЙ ФОРУМ БЕЛГОРОД УСПЕШНО УСТАНОВЛЕН!  ║${NC}"
    echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "Директория бота: ${BLUE}$INSTALL_DIR${NC}"
    echo -e "Для просмотра логов бота: ${YELLOW}docker logs -f $CONTAINER_NAME${NC}"
    echo -e "Для остановки бота: ${YELLOW}docker stop $CONTAINER_NAME${NC}"
    echo -e "Для запуска бота: ${YELLOW}docker start $CONTAINER_NAME${NC}"
    echo
else
    echo -e "${RED}[8/8] Ошибка при запуске контейнера!${NC}"
    echo -e "${YELLOW}Проверьте журнал ошибок: ${NC}docker logs $CONTAINER_NAME"
    exit 1
fi

# Создание ярлыков команд для управления ботом
echo -e "${YELLOW}Создание ярлыков команд для удобного управления ботом...${NC}"

# Скрипт для просмотра логов
cat > /usr/local/bin/sfb-logs << EOL
#!/bin/bash
docker logs -f $CONTAINER_NAME \$@
EOL
chmod +x /usr/local/bin/sfb-logs

# Скрипт для перезапуска бота
cat > /usr/local/bin/sfb-restart << EOL
#!/bin/bash
docker restart $CONTAINER_NAME
echo "Бот СФБ перезапущен"
EOL
chmod +x /usr/local/bin/sfb-restart

# Скрипт для обновления бота
cat > /usr/local/bin/sfb-update << EOL
#!/bin/bash
cd $INSTALL_DIR
git pull
docker-compose up --build -d
echo "Бот СФБ обновлен"
EOL
chmod +x /usr/local/bin/sfb-update

echo -e "${GREEN}Ярлыки команд созданы:${NC}"
echo -e "  ${YELLOW}sfb-logs${NC} - просмотр логов бота"
echo -e "  ${YELLOW}sfb-restart${NC} - перезапуск бота"
echo -e "  ${YELLOW}sfb-update${NC} - обновление бота из репозитория"

echo -e "\n${GREEN}Установка завершена успешно!${NC}" 