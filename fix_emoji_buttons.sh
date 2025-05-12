#!/bin/bash

# Скрипт для исправления проблемы с кнопками после удаления эмодзи
echo "Начинаю исправление проблем с кнопками..."

# Применяем фиксы из updated_handlers.py если файл существует
if [ -f "updated_handlers.py" ]; then
  echo "Применяю фиксы из updated_handlers.py..."
  python fix_buttons.py
  echo "Исправления для обработчиков кнопок применены."
else
  echo "Файл updated_handlers.py не найден. Пропускаю этот шаг."
fi

# Проверяем, есть ли уже кнопки без эмодзи в main.py
if grep -q 'lambda m: m.text == "База мастеров СФБ"' main.py; then
  echo "Кнопки без эмодзи уже обрабатываются в main.py"
else
  echo "Добавляю обработку кнопок без эмодзи в main.py..."
  python fix_buttons.py
fi

# Проверяем, есть ли кнопки без эмодзи в buttons.py
if grep -q 'KeyboardButton("База мастеров СФБ")' "tg_bot/buttons.py"; then
  echo "Кнопки без эмодзи уже добавлены в buttons.py"
else
  echo "Добавляю кнопки без эмодзи в buttons.py..."
  python buttons_fixed.py
fi

echo "Исправления завершены!"
echo "Теперь бот должен корректно реагировать на кнопки и с эмодзи, и без них."
echo "Перезапустите бота для применения изменений." 