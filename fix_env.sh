#!/bin/bash

# Путь к папке проекта
PROJECT_DIR="/home/fil/SFB_tg_bot"

# Перейти в папку проекта
cd $PROJECT_DIR || { echo "Не удалось перейти в директорию проекта"; exit 1; }

# Создание правильного .env файла с верной кодировкой UTF-8
echo "# Создаем новый файл .env с правильной кодировкой UTF-8"
cat > .env.new << 'EOF'
TG_BOT_TOKEN=ваш_токен_телеграм_бота
VK_TOKEN=ваш_токен_вк_апи
VK_GROUP_ID=95855103
ADMIN_IDS=ваш_id_администратора
EOF

# Заменяем старый .env новым
mv .env.new .env

echo "Файл .env пересоздан с кодировкой UTF-8"

# Перезапускаем контейнер
echo "Перезапуск контейнера..."
docker-compose down
docker-compose up -d --build

echo "Готово. Проверьте логи:"
docker-compose logs -f stroy-forum-bot 