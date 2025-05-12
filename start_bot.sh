#!/bin/bash

# Проверка наличия файла .env
if [ ! -f .env ]; then
    echo "Файл .env не найден. Создаю из шаблона..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Файл .env создан. Пожалуйста, отредактируйте его, указав правильные токены и ID."
        echo "После редактирования запустите скрипт снова."
        exit 1
    else
        echo "Ошибка: Файл .env.example не найден!"
        exit 1
    fi
fi

# Создание директории для логов
mkdir -p logs
echo "Директория для логов создана."

# Запуск бота через docker-compose
if command -v docker-compose &> /dev/null; then
    echo "Запуск бота через docker-compose..."
    docker-compose up -d
    
    # Проверка статуса запуска
    if [ $? -eq 0 ]; then
        echo "Бот успешно запущен!"
        echo "Для просмотра логов введите: docker-compose logs -f"
    else
        echo "Ошибка при запуске бота. Проверьте логи: docker-compose logs"
    fi
else
    echo "Docker Compose не установлен. Попытка запуска через Docker..."
    
    # Проверка наличия Docker
    if command -v docker &> /dev/null; then
        # Сборка образа
        echo "Сборка Docker образа..."
        docker build -t stroy-forum-bot .
        
        # Запуск контейнера
        echo "Запуск контейнера..."
        docker run -d --name stroy-forum-bot \
            -v "$(pwd)"/logs:/app/logs \
            -v "$(pwd)"/.env:/app/.env \
            --restart always \
            stroy-forum-bot
            
        # Проверка статуса запуска
        if [ $? -eq 0 ]; then
            echo "Бот успешно запущен!"
            echo "Для просмотра логов введите: docker logs -f stroy-forum-bot"
        else
            echo "Ошибка при запуске бота. Проверьте логи: docker logs stroy-forum-bot"
        fi
    else
        echo "Docker не установлен. Пожалуйста, установите Docker и попробуйте снова."
        exit 1
    fi
fi 