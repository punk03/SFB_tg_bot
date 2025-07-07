#!/bin/bash

# Скрипт автоматического развертывания Telegram бота "Строй Форум Белгород" на сервере
# Используется Docker и docker-compose

# Цвета для вывода
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

echo -e "${GREEN}=== Автоматическое развертывание Telegram бота ===${RESET}"

# Проверка наличия необходимых программ
check_dependencies() {
    echo -e "${YELLOW}Проверка необходимых зависимостей...${RESET}"
    
    if ! command -v git &> /dev/null; then
        echo -e "${RED}Git не установлен. Устанавливаем...${RESET}"
        apt-get update && apt-get install -y git
    else
        echo -e "${GREEN}✅ Git установлен${RESET}"
    fi
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker не установлен. Устанавливаем...${RESET}"
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        systemctl enable docker
        systemctl start docker
    else
        echo -e "${GREEN}✅ Docker установлен${RESET}"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}Docker-compose не установлен. Устанавливаем...${RESET}"
        apt-get update && apt-get install -y docker-compose
    else
        echo -e "${GREEN}✅ Docker-compose установлен${RESET}"
    fi
}

# Создание файла конфигурации .env, если его нет
create_env_file() {
    echo -e "${YELLOW}Настройка конфигурационного файла .env...${RESET}"
    
    if [ -f ".env" ]; then
        echo -e "${GREEN}✅ Файл .env уже существует${RESET}"
    else
        echo -e "${YELLOW}Создание файла .env...${RESET}"
        cat > .env << EOL
# Токен Telegram бота (получить у @BotFather)
TG_BOT_TOKEN=

# Токен VK API
VK_TOKEN=

# ID группы VK (число)
VK_GROUP_ID=

# ID администраторов (через запятую)
ADMIN_IDS=

# Дополнительные настройки
DEBUG=False
EOL
        echo -e "${GREEN}✅ Файл .env создан. Пожалуйста, заполните его необходимыми данными${RESET}"
        echo -e "${YELLOW}Для продолжения необходимо заполнить файл .env.${RESET}"
        echo -e "${YELLOW}Откройте файл командой: nano .env${RESET}"
        read -p "Нажмите Enter после заполнения .env для продолжения..."
    fi
}

# Основная функция развертывания
deploy_bot() {
    echo -e "${YELLOW}Начинаем развертывание бота...${RESET}"
    
    # Создаем директорию для логов, если ее нет
    mkdir -p logs
    echo -e "${GREEN}✅ Директория для логов создана${RESET}"
    
    # Создаем скрипт для запуска бота
    cat > start_bot.sh << EOL
#!/bin/bash
echo "Запуск бота..."
docker-compose up -d
echo "Бот запущен в фоновом режиме!"
EOL
    chmod +x start_bot.sh
    echo -e "${GREEN}✅ Скрипт запуска создан${RESET}"
    
    # Создаем скрипт для остановки бота
    cat > stop_bot.sh << EOL
#!/bin/bash
echo "Остановка бота..."
docker-compose down
echo "Бот остановлен!"
EOL
    chmod +x stop_bot.sh
    echo -e "${GREEN}✅ Скрипт остановки создан${RESET}"
    
    # Создаем скрипты для обновления бота
    cat > update_bot.sh << EOL
#!/bin/bash
echo "Обновление бота через git pull..."
git pull
docker-compose build
docker-compose up -d
echo "Бот обновлен и перезапущен!"
EOL
    chmod +x update_bot.sh
    
    # Создаем скрипт для обновления через клонирование репозитория
    cat > update_bot_clone.sh << EOL
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
CURRENT_DIR=\$(pwd)

echo -e "\${GREEN}=== Обновление бота через клонирование репозитория ===\${RESET}"

# Проверка наличия необходимых программ
if ! command -v git &> /dev/null; then
    echo -e "\${RED}❌ Git не установлен. Установите Git для продолжения.\${RESET}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "\${RED}❌ Docker Compose не установлен. Установите Docker Compose для продолжения.\${RESET}"
    exit 1
fi

# Остановка бота
echo -e "\${YELLOW}1. Останавливаем бота...\${RESET}"
docker-compose down
echo -e "\${GREEN}✅ Бот остановлен\${RESET}"

# Сохранение файла .env
echo -e "\${YELLOW}2. Сохранение конфигурации...\${RESET}"
if [ -f ".env" ]; then
    cp .env .env.backup
    echo -e "\${GREEN}✅ Файл .env сохранен\${RESET}"
else
    echo -e "\${RED}⚠️ Файл .env не найден, продолжаем без сохранения конфигурации\${RESET}"
fi

# Сохранение директории logs, если она существует
if [ -d "logs" ]; then
    echo -e "\${YELLOW}Сохранение логов...\${RESET}"
    mkdir -p logs.backup
    cp -r logs/* logs.backup/ 2>/dev/null
    echo -e "\${GREEN}✅ Логи сохранены\${RESET}"
fi

# Клонирование свежей версии репозитория
echo -e "\${YELLOW}3. Клонирование свежей версии репозитория...\${RESET}"
rm -rf \$TEMP_DIR
git clone \$REPO_URL \$TEMP_DIR
if [ \$? -ne 0 ]; then
    echo -e "\${RED}❌ Ошибка клонирования репозитория.\${RESET}"
    echo -e "\${BLUE}ℹ️ Восстанавливаем предыдущее состояние и запускаем бота...\${RESET}"
    docker-compose up -d
    exit 1
fi
echo -e "\${GREEN}✅ Репозиторий склонирован\${RESET}"

# Копирование всех файлов из временной директории
echo -e "\${YELLOW}4. Обновление файлов...\${RESET}"

# Сначала удаляем старые файлы, кроме .env, .env.backup и директории logs
find \$CURRENT_DIR -maxdepth 1 -not -path "\$CURRENT_DIR" -not -path "\$CURRENT_DIR/.env*" -not -path "\$CURRENT_DIR/logs*" -not -path "\$CURRENT_DIR/.git*" -exec rm -rf {} \;

# Копируем все файлы из временной директории
cp -r \$TEMP_DIR/* \$CURRENT_DIR/
echo -e "\${GREEN}✅ Файлы обновлены\${RESET}"

# Восстановление файла .env
if [ -f ".env.backup" ]; then
    echo -e "\${YELLOW}5. Восстановление конфигурации...\${RESET}"
    cp .env.backup .env
    echo -e "\${GREEN}✅ Файл .env восстановлен\${RESET}"
fi

# Восстановление директории logs
if [ -d "logs.backup" ]; then
    echo -e "\${YELLOW}Восстановление логов...\${RESET}"
    mkdir -p logs
    cp -r logs.backup/* logs/ 2>/dev/null
    rm -rf logs.backup
    echo -e "\${GREEN}✅ Логи восстановлены\${RESET}"
fi

# Делаем скрипты исполняемыми
echo -e "\${YELLOW}6. Установка прав на исполнение скриптов...\${RESET}"
chmod +x *.sh
echo -e "\${GREEN}✅ Права установлены\${RESET}"

# Очистка временной директории
echo -e "\${YELLOW}7. Очистка временных файлов...\${RESET}"
rm -rf \$TEMP_DIR
if [ -f ".env.backup" ]; then
    rm .env.backup
fi
echo -e "\${GREEN}✅ Временные файлы удалены\${RESET}"

# Сборка и запуск обновленного бота
echo -e "\${YELLOW}8. Сборка и запуск обновленного бота...\${RESET}"
docker-compose build
docker-compose up -d
echo -e "\${GREEN}✅ Бот собран и запущен\${RESET}"

# Проверка статуса
echo -e "\${YELLOW}9. Проверка статуса бота...\${RESET}"
sleep 5  # Даем немного времени для запуска
if docker ps | grep -q "sfb"; then
    echo -e "\${GREEN}✅ Бот успешно обновлен и запущен\${RESET}"
    echo -e "\${YELLOW}Последние логи бота:\${RESET}"
    docker logs --tail 10 sfb
else
    echo -e "\${RED}❌ Возникла проблема при запуске бота.\${RESET}"
    echo -e "\${YELLOW}Проверьте логи:\${RESET}"
    docker-compose logs -t --tail 20
fi

echo -e "\${GREEN}=== Обновление через клонирование репозитория завершено! ===\${RESET}"
EOL
    chmod +x update_bot_clone.sh
    
    echo -e "${GREEN}✅ Скрипты обновления созданы${RESET}"
    
    # Создаем скрипт для просмотра логов
    cat > logs.sh << EOL
#!/bin/bash
echo "Вывод логов бота (Ctrl+C для выхода)..."
docker-compose logs -f
EOL
    chmod +x logs.sh
    echo -e "${GREEN}✅ Скрипт для просмотра логов создан${RESET}"
    
    # Запускаем бота
    echo -e "${YELLOW}Сборка и запуск Docker-контейнера...${RESET}"
    docker-compose build
    docker-compose up -d
    echo -e "${GREEN}✅ Бот успешно запущен!${RESET}"
}

# Проверка работоспособности
check_bot_status() {
    echo -e "${YELLOW}Проверка статуса бота...${RESET}"
    
    if docker ps | grep -q "sfb"; then
        echo -e "${GREEN}✅ Контейнер запущен${RESET}"
        echo -e "${YELLOW}Логи бота (последние 10 строк):${RESET}"
        docker logs --tail 10 sfb
    else
        echo -e "${RED}❌ Контейнер не запущен. Проверьте логи: ./logs.sh${RESET}"
        docker-compose logs -t --tail 20
    fi
}

# Настройка автозапуска
setup_autostart() {
    echo -e "${YELLOW}Настройка автозапуска бота при перезагрузке сервера...${RESET}"
    
    # Создаем сервис systemd
    cat > /etc/systemd/system/sfb-bot.service << EOL
[Unit]
Description=SFB Telegram Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/start_bot.sh
ExecStop=$(pwd)/stop_bot.sh

[Install]
WantedBy=multi-user.target
EOL

    # Активируем сервис
    systemctl daemon-reload
    systemctl enable sfb-bot.service
    echo -e "${GREEN}✅ Автозапуск настроен${RESET}"
}

# Основной скрипт
main() {
    check_dependencies
    create_env_file
    deploy_bot
    check_bot_status
    
    echo -e "${YELLOW}Настроить автозапуск бота при перезагрузке сервера? (y/n)${RESET}"
    read choice
    if [[ "$choice" == "y" || "$choice" == "Y" ]]; then
        setup_autostart
    fi
    
    echo -e "${GREEN}=== Развертывание завершено! ===${RESET}"
    echo -e "${YELLOW}Доступные команды:${RESET}"
    echo -e "  ${GREEN}./start_bot.sh${RESET}        - Запуск бота"
    echo -e "  ${GREEN}./stop_bot.sh${RESET}         - Остановка бота"
    echo -e "  ${GREEN}./update_bot.sh${RESET}       - Обновление бота через git pull"
    echo -e "  ${GREEN}./update_bot_clone.sh${RESET} - Полное обновление через клонирование репозитория"
    echo -e "  ${GREEN}./check_bot.sh${RESET}        - Проверка состояния бота"
    echo -e "  ${GREEN}./logs.sh${RESET}             - Просмотр логов бота"
}

# Запускаем основной скрипт
main 