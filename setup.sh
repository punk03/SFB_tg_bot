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