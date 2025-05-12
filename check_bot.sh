#!/bin/bash

# Скрипт для проверки работоспособности бота
echo "Проверка работоспособности бота 'Строй Форум Белгород'..."

# Проверяем, работает ли Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен или не доступен"
    exit 1
fi

# Проверяем, запущен ли контейнер с ботом
if docker ps | grep -q "stroy-forum-bot"; then
    echo "✅ Контейнер stroy-forum-bot запущен"
    
    # Проверяем статус контейнера
    status=$(docker inspect -f '{{.State.Status}}' stroy-forum-bot)
    if [ "$status" == "running" ]; then
        echo "✅ Статус контейнера: $status"
    else
        echo "❌ Статус контейнера: $status"
    fi
    
    # Проверяем количество перезапусков
    restarts=$(docker inspect -f '{{.RestartCount}}' stroy-forum-bot)
    echo "ℹ️ Количество перезапусков: $restarts"
    
    # Проверяем последние логи
    echo "ℹ️ Последние 10 строк логов контейнера:"
    docker logs --tail 10 stroy-forum-bot
else
    echo "❌ Контейнер stroy-forum-bot не запущен"
fi

# Проверяем содержимое файла .env (без показа реальных токенов)
echo -e "\nℹ️ Проверка конфигурации .env:"
if [ -f ~/.env ]; then
    echo "✅ Файл .env существует"
    
    # Проверяем наличие необходимых переменных без показа их значений
    if grep -q "TG_BOT_TOKEN" ~/.env; then
        echo "✅ TG_BOT_TOKEN настроен"
    else
        echo "❌ TG_BOT_TOKEN не настроен"
    fi
    
    if grep -q "VK_TOKEN" ~/.env; then
        echo "✅ VK_TOKEN настроен"
    else
        echo "❌ VK_TOKEN не настроен"
    fi
    
    if grep -q "VK_GROUP_ID" ~/.env; then
        echo "✅ VK_GROUP_ID настроен"
    else
        echo "❌ VK_GROUP_ID не настроен"
    fi
    
    if grep -q "ADMIN_IDS" ~/.env; then
        echo "✅ ADMIN_IDS настроен"
    else
        echo "❌ ADMIN_IDS не настроен"
    fi
else
    echo "❌ Файл .env не существует"
fi

echo -e "\nДля полноценной работы бота требуются реальные токены Telegram и VK API."
echo "Если статус контейнера 'restarting', это может означать, что токены недействительны."
echo "Отредактируйте файл .env с правильными токенами и перезапустите бота с помощью ./start_bot.sh" 