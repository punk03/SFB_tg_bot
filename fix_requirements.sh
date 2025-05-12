#!/bin/bash

# Путь к папке проекта
PROJECT_DIR="/home/fil/SFB_tg_bot"

# Перейти в папку проекта
cd $PROJECT_DIR || { echo "Не удалось перейти в директорию проекта"; exit 1; }

# Проверяем наличие psutil в requirements.txt и добавляем при необходимости
if ! grep -q "psutil" requirements.txt; then
    echo "Добавляем psutil в requirements.txt"
    echo "psutil==5.9.5" >> requirements.txt
    echo "psutil успешно добавлен в requirements.txt"
else
    echo "psutil уже присутствует в requirements.txt"
fi

# Перезапускаем контейнер
echo "Перезапуск контейнера..."
docker-compose down
docker-compose up -d --build

echo "Готово. Проверьте логи:"
docker-compose logs -f stroy-forum-bot 