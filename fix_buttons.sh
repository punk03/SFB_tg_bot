#!/bin/bash

# Путь к папке проекта
PROJECT_DIR="/home/fil/SFB_tg_bot"

# Перейти в папку проекта
cd $PROJECT_DIR || { echo "Не удалось перейти в директорию проекта"; exit 1; }

echo "Поиск и модификация файлов с обработчиками кнопок..."

# Адаптируем обработчики кнопок в файле main.py
if [ -f "main.py" ]; then
    echo "Обновляем main.py..."
    
    # Создаем резервную копию
    cp main.py main.py.bak
    
    # Изменяем обработку кнопок, удаляя проверку на эмодзи
    sed -i 's/if message.text.startswith("🔄")/if message.text == "🔄 Обновить кэш" or message.text == "Обновить кэш"/g' main.py
    sed -i 's/if message.text.startswith("👨‍🔧")/if message.text == "👨‍🔧 База мастеров СФБ" or message.text == "База мастеров СФБ"/g' main.py
    sed -i 's/if message.text.startswith("🏪")/if message.text == "🏪 Магазины-партнеры СФБ" or message.text == "Магазины-партнеры СФБ"/g' main.py
    sed -i 's/if message.text.startswith("📝")/if message.text == "📝 Предложить запись" or message.text == "Предложить запись"/g' main.py
    sed -i 's/if message.text.startswith("🤝")/if message.text == "🤝 Стать партнером" or message.text == "Стать партнером"/g' main.py
    sed -i 's/if message.text.startswith("📋")/if message.text == "📋 Попасть в базу мастеров" or message.text == "Попасть в базу мастеров"/g' main.py
    sed -i 's/if message.text.startswith("ℹ️")/if message.text == "ℹ️ Информация" or message.text == "Информация"/g' main.py
    sed -i 's/if message.text.startswith("🔙")/if message.text == "🔙 Назад" or message.text == "Назад"/g' main.py
    sed -i 's/if message.text.startswith("📊")/if message.text == "📊 Статистика" or message.text == "Статистика"/g' main.py
    
    echo "Файл main.py обновлен"
fi

# Также проверяем tg_bot/buttons.py, если он существует
if [ -f "tg_bot/buttons.py" ]; then
    echo "Обновляем tg_bot/buttons.py..."
    
    # Создаем резервную копию
    cp tg_bot/buttons.py tg_bot/buttons.py.bak
    
    # Дублируем кнопки без эмодзи, если они используют только эмодзи
    sed -i 's/KeyboardButton("🔄 Обновить кэш")/KeyboardButton("🔄 Обновить кэш"), KeyboardButton("Обновить кэш")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("👨‍🔧 База мастеров СФБ")/KeyboardButton("👨‍🔧 База мастеров СФБ"), KeyboardButton("База мастеров СФБ")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("🏪 Магазины-партнеры СФБ")/KeyboardButton("🏪 Магазины-партнеры СФБ"), KeyboardButton("Магазины-партнеры СФБ")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("📝 Предложить запись")/KeyboardButton("📝 Предложить запись"), KeyboardButton("Предложить запись")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("🤝 Стать партнером")/KeyboardButton("🤝 Стать партнером"), KeyboardButton("Стать партнером")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("📋 Попасть в базу мастеров")/KeyboardButton("📋 Попасть в базу мастеров"), KeyboardButton("Попасть в базу мастеров")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("ℹ️ Информация")/KeyboardButton("ℹ️ Информация"), KeyboardButton("Информация")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("🔙 Назад")/KeyboardButton("🔙 Назад"), KeyboardButton("Назад")/g' tg_bot/buttons.py
    sed -i 's/KeyboardButton("📊 Статистика")/KeyboardButton("📊 Статистика"), KeyboardButton("Статистика")/g' tg_bot/buttons.py
    
    echo "Файл tg_bot/buttons.py обновлен"
fi

# Проверим дополнительные обработчики в других файлах
for handler_file in masters_sfb_handler_fixed.py partners_stores_handler_fixed.py back_to_master_categories_fixed.py back_to_shop_categories_fixed.py; do
    if [ -f "$handler_file" ]; then
        echo "Обновляем $handler_file..."
        
        # Создаем резервную копию
        cp "$handler_file" "${handler_file}.bak"
        
        # Аналогичные замены для обработчиков
        sed -i 's/if message.text.startswith("🔙")/if message.text == "🔙 Назад" or message.text == "Назад"/g' "$handler_file"
        sed -i 's/if message.text.startswith("👨‍🔧")/if message.text == "👨‍🔧 База мастеров СФБ" or message.text == "База мастеров СФБ"/g' "$handler_file"
        sed -i 's/if message.text.startswith("🏪")/if message.text == "🏪 Магазины-партнеры СФБ" or message.text == "Магазины-партнеры СФБ"/g' "$handler_file"
        
        echo "Файл $handler_file обновлен"
    fi
done

# Перезапускаем контейнер
echo "Перезапуск контейнера..."
docker-compose down
docker-compose up -d --build

echo "Готово. Проверьте работу кнопок."
echo "Для просмотра логов выполните:"
echo "docker-compose logs -f stroy-forum-bot" 