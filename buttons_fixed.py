"""
Исправленная версия клавиатуры без эмодзи
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Создание основной клавиатуры (ReplyKeyboardMarkup) без эмодзи
main_fixed = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

# Добавляем основные кнопки на клавиатуру согласно новому расположению
main_fixed.row(
    KeyboardButton("Магазины-партнеры СФБ"),
    KeyboardButton("База мастеров СФБ")
)
main_fixed.add(KeyboardButton("Стена сообщества"))
main_fixed.add(KeyboardButton("Предложить запись"))
main_fixed.row(
    KeyboardButton("Стать магазином-партнером"),
    KeyboardButton("Попасть в базу мастеров")
)

# Функция для замены клавиатуры в main.py
def replace_keyboard():
    """
    Заменяет клавиатуру с эмодзи на клавиатуру без эмодзи в main.py
    """
    try:
        import main
        # Заменяем клавиатуру на новую версию без эмодзи
        from buttons import main as orig_keyboard
        orig_keyboard = main_fixed
        print("Клавиатура успешно заменена на версию без эмодзи")
        return True
    except Exception as e:
        print(f"Ошибка при замене клавиатуры: {e}")
        return False

if __name__ == "__main__":
    replace_keyboard() 