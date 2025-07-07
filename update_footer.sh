#!/bin/bash

# Цвета для вывода
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

echo -e "${GREEN}=== Обновление бота: добавление ссылок в футер сообщений ===${RESET}"

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен. Установите Docker для продолжения.${RESET}"
    exit 1
fi

# Остановка контейнера бота
echo -e "${YELLOW}1. Остановка контейнера бота...${RESET}"
docker-compose down
echo -e "${GREEN}✅ Контейнер остановлен${RESET}"

# Сборка образа с новыми изменениями
echo -e "${YELLOW}2. Сборка образа с новыми изменениями...${RESET}"
docker-compose build
echo -e "${GREEN}✅ Сборка завершена${RESET}"

# Запуск контейнера с новой версией
echo -e "${YELLOW}3. Запуск обновленной версии бота...${RESET}"
docker-compose up -d
echo -e "${GREEN}✅ Бот запущен${RESET}"

# Проверка состояния бота
echo -e "${YELLOW}4. Проверка состояния бота...${RESET}"
sleep 3
if docker ps | grep -q "sfb"; then
    echo -e "${GREEN}✅ Бот успешно запущен и работает${RESET}"
    echo -e "${YELLOW}Логи бота (последние 10 строк):${RESET}"
    docker logs --tail 10 sfb
else
    echo -e "${RED}❌ Бот не запустился. Проверьте логи:${RESET}"
    docker-compose logs -t --tail 20
fi

echo -e "${GREEN}=== Обновление завершено ===${RESET}"
echo -e "${YELLOW}Теперь во всех сообщениях бота будут добавлены ссылки на все ресурсы:${RESET}"
echo -e "• ВКонтакте: ${GREEN}${config.VK_GROUP_URL}${RESET}"
echo -e "• Telegram канал: ${GREEN}${config.TG_CHANNEL_URL}${RESET}"
echo -e "• Telegram бот: ${GREEN}${config.TG_BOT_URL}${RESET}" 