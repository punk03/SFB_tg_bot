"""
Скрипт для исправления обработчиков кнопок в боте.
Добавляет проверку на версию текста кнопки без эмодзи.
Запустите этот скрипт после обновления основных файлов.
"""

import re
import os

def fix_main_py():
    """Исправление обработчиков кнопок в main.py"""
    filename = "main.py"
    
    if not os.path.exists(filename):
        print(f"Файл {filename} не найден!")
        return False
    
    # Прочитаем содержимое файла
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Паттерны для замены
    patterns = [
        # База мастеров СФБ
        (r'@dp\.message_handler\(lambda m: m\.text == "👷‍♂️ База мастеров СФБ"\)',
         '@dp.message_handler(lambda m: m.text == "👷‍♂️ База мастеров СФБ" or m.text == "База мастеров СФБ")'),
        
        # Магазины-партнеры СФБ
        (r'@dp\.message_handler\(lambda m: m\.text == "🏪 Магазины-партнеры СФБ"\)',
         '@dp.message_handler(lambda m: m.text == "🏪 Магазины-партнеры СФБ" or m.text == "Магазины-партнеры СФБ")'),
        
        # Предложить запись
        (r'@dp\.message_handler\(lambda m: m\.text == "📝 Предложить запись"\)',
         '@dp.message_handler(lambda m: m.text == "📝 Предложить запись" or m.text == "Предложить запись")'),
        
        # Стать магазином-партнером
        (r'@dp\.message_handler\(lambda m: m\.text == "🤝 Стать магазином-партнером"\)',
         '@dp.message_handler(lambda m: m.text == "🤝 Стать магазином-партнером" or m.text == "Стать магазином-партнером")'),
        
        # Попасть в базу мастеров
        (r'@dp\.message_handler\(lambda m: m\.text == "📋 Попасть в базу мастеров"\)',
         '@dp.message_handler(lambda m: m.text == "📋 Попасть в базу мастеров" or m.text == "Попасть в базу мастеров")'),
        
        # Стена сообщества
        (r'@dp\.message_handler\(lambda m: m\.text == "📰 Стена сообщества"\)',
         '@dp.message_handler(lambda m: m.text == "📰 Стена сообщества" or m.text == "Стена сообщества")')
    ]
    
    # Счетчик изменений
    changes_count = 0
    
    # Применяем замены
    for pattern, replacement in patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            changes_count += 1
    
    # Если были внесены изменения, сохраняем файл
    if changes_count > 0:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Внесено {changes_count} изменений в файл {filename}")
        return True
    else:
        print(f"Изменения в файл {filename} не требуются")
        return False

def fix_button_py():
    """Создает копию кнопок без эмодзи в buttons.py"""
    filename = "tg_bot/buttons.py"
    
    if not os.path.exists(filename):
        print(f"Файл {filename} не найден!")
        return False
    
    # Прочитаем содержимое файла
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Ищем определение основной клавиатуры
    main_keyboard_pattern = r'main = ReplyKeyboardMarkup\(resize_keyboard=True, row_width=2\)\s+# Добавляем основные кнопки на клавиатуру согласно новому расположению\s+main\.row\(\s+KeyboardButton\("(.+?)"\),\s+KeyboardButton\("(.+?)"\)\s+\)\s+main\.add\(KeyboardButton\("(.+?)"\)\)\s+main\.add\(KeyboardButton\("(.+?)"\)\)\s+main\.row\(\s+KeyboardButton\("(.+?)"\),\s+KeyboardButton\("(.+?)"\)\s+\)'
    
    match = re.search(main_keyboard_pattern, content)
    
    if not match:
        print("Не удалось найти определение основной клавиатуры")
        return False
    
    # Проверим, уже добавлены ли версии без эмодзи
    if "База мастеров СФБ" in content and "Магазины-партнеры СФБ" in content:
        print("Версии кнопок без эмодзи уже существуют в файле")
        return False
    
    # Модифицируем клавиатуру, добавляя версии без эмодзи
    with open(filename, 'w', encoding='utf-8') as file:
        # Заменяем эмодзи на пустую строку в названиях кнопок
        button1 = match.group(1).replace("🏪 ", "")
        button2 = match.group(2).replace("👷‍♂️ ", "")
        button3 = match.group(3).replace("📰 ", "")
        button4 = match.group(4).replace("📝 ", "")
        button5 = match.group(5).replace("🤝 ", "")
        button6 = match.group(6).replace("📋 ", "")
        
        # Создаем новое определение клавиатуры, добавляя версии без эмодзи
        new_keyboard = f"""main = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

# Добавляем основные кнопки на клавиатуру согласно новому расположению
main.row(
    KeyboardButton("{button1}"),
    KeyboardButton("{button2}")
)
main.add(KeyboardButton("{button3}"))
main.add(KeyboardButton("{button4}"))
main.row(
    KeyboardButton("{button5}"),
    KeyboardButton("{button6}")
)
"""
        
        # Заменяем оригинальное определение клавиатуры на новое
        content = re.sub(main_keyboard_pattern, new_keyboard, content)
        file.write(content)
        
        print(f"Обновлена клавиатура в файле {filename}")
        return True

if __name__ == "__main__":
    print("Начинаю исправление обработчиков кнопок...")
    main_fixed = fix_main_py()
    buttons_fixed = fix_button_py()
    
    if main_fixed or buttons_fixed:
        print("Исправления внесены успешно!")
    else:
        print("Изменения не требуются или не удалось внести изменения.") 