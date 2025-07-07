from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


# Цвета для кнопок (эмодзи как визуальные индикаторы)
class ButtonColors:
    PRIMARY = "🔵"
    SUCCESS = "🟢" 
    INFO = "🔷"
    WARNING = "🟠"
    DANGER = "🔴"
    NEUTRAL = "⚪"


# Кнопка назад для inline клавиатуры
back_button = InlineKeyboardButton("◀️ Назад в главное меню", callback_data="back_to_main")

# Создание стилизованной главной inline-клавиатуры (для справки)
inline_main = InlineKeyboardMarkup(row_width=1)

# Главные кнопки с эмодзи для лучшей визуальной навигации
masters_sfb = InlineKeyboardButton(
    "👷‍♂️ База мастеров и спецтехники", callback_data="masters_sfb"
)
partners_stores = InlineKeyboardButton(
    "🏪 Магазины-партнеры", callback_data="partners_stores"
)
vk_partner = InlineKeyboardButton(
    "🤝 Стать магазином-партнером", url="https://vk.com/topic-95855103_49010445"
)
vk_master = InlineKeyboardButton(
    "📋 Хочу в базу мастеров и спецтехники", url="https://vk.com/topic-95855103_49010449"
)
vk_post = InlineKeyboardButton(
    "📝 Предложить запись", callback_data="offer_post"
)
all_posts = InlineKeyboardButton(
    "📰 Стена сообщества", url="https://t.me/sfb_31"
)

# Добавляем кнопки с группировкой для красивого отображения
inline_main.add(masters_sfb)
inline_main.add(partners_stores)
inline_main.row(vk_partner, vk_master)
inline_main.add(vk_post)
inline_main.add(all_posts)

# Создание основной клавиатуры (ReplyKeyboardMarkup)
main = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

# Добавляем основные кнопки на клавиатуру согласно новому расположению
main.row(
    KeyboardButton("Магазины-партнеры СФБ"),
    KeyboardButton("База мастеров СФБ")
)
main.add(KeyboardButton("Стена сообщества"))
main.add(KeyboardButton("Предложить запись"))
main.row(
    KeyboardButton("Стать магазином-партнером"),
    KeyboardButton("Попасть в базу мастеров")
)


# Генератор обычной клавиатуры с кнопками
def sort_buttons(buttons_list):
    """
    Сортирует список кнопок по алфавиту, игнорируя эмодзи в начале
    :param buttons_list: список названий кнопок
    :return: отсортированный список кнопок
    """
    # Эмодзи, которые могут быть в начале кнопок
    emoji_list = ["📋", "📂", "🔧", "🏢", "📝", "🛒", "🔨", "🏪", "🏗", "🚿", "🔌", "🏡", "🧱", "🚜", "🪑", "🌱", "👷‍♂️"]
    
    def get_sort_key(button):
        # Если это кортеж (название, количество), берем только название
        if isinstance(button, tuple):
            button = button[0]
            
        # Удаляем эмодзи в начале для сортировки
        button_text = button
        for emoji in emoji_list:
            if button.startswith(emoji):
                button_text = button.replace(emoji, "", 1).strip()
                break
                
        # Удаляем счетчик [N] в конце, если он есть
        if ' [' in button_text and button_text.endswith(']'):
            button_text = button_text.split(' [')[0]
            
        return button_text.lower()
    
    # Возвращаем отсортированный список
    return sorted(buttons_list, key=get_sort_key)

def generator(buttons_list, row_width=2, force_single_column=False, preserve_emoji=False, sort_alphabetically=True, hide_counts=False):
    """
    Создает красивую клавиатуру с кнопками и кнопкой "Назад" вверху и внизу
    :param buttons_list: список названий кнопок или кортежей (название, количество)
    :param row_width: количество кнопок в ряду (по умолчанию 2)
    :param force_single_column: принудительно размещать кнопки в одну колонку
    :param preserve_emoji: не добавлять эмодзи к кнопкам, если они уже есть в названии
    :param sort_alphabetically: сортировать ли кнопки по алфавиту
    :param hide_counts: скрывать ли счетчики количества мастеров [N]
    :return: ReplyKeyboardMarkup
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=row_width)
    kb.row(KeyboardButton('◀️ Назад в главное меню'))
    
    # Определяем, нужно ли отображать магазины в одну колонку
    is_shops_list = False
    # Проверяем тип элементов: если кортежи, значит это могут быть категории магазинов или мастеров
    if buttons_list and isinstance(buttons_list[0], tuple):
        is_shops_list = any('🏪' in button[0] for button in buttons_list) or force_single_column
    else:
        is_shops_list = any('🏪' in button for button in buttons_list) or force_single_column
    
    # Определяем, является ли список категорий мастеров
    is_masters_list = False
    if buttons_list and isinstance(buttons_list[0], tuple):
        is_masters_list = any('👷‍♂️' in button[0] or '🔨' in button[0] or '🚜' in button[0] or '🏗' in button[0] or '🔧' in button[0] for button in buttons_list)
    else:
        is_masters_list = any('👷‍♂️' in button or '🔨' in button or '🚜' in button or '🏗' in button or '🔧' in button for button in buttons_list)
    
    # Сортировка по алфавиту (по названию категории)
    if sort_alphabetically:
        if buttons_list and isinstance(buttons_list[0], tuple):
            buttons_list = sorted(buttons_list, key=lambda x: x[0].lower())
        else:
            buttons_list = sort_buttons(buttons_list)
    
    emoji_list = ["📋", "📂", "🔧", "🏢", "📝", "🛒", "🔨", "🏪", "🏗", "🚿", "🔌", "🏡", "🧱", "🚜", "🪑", "🌱"]
    
    if buttons_list and isinstance(buttons_list[0], tuple):
        # Для списка категорий с количеством
        for button, count in buttons_list:
            # Удаляем эмодзи из названия категории
            button_name = button
            for emoji in emoji_list:
                if button_name.startswith(emoji):
                    button_name = button_name.replace(emoji, "", 1).strip()
            
            # Для мастеров добавляем счетчик, для магазинов - нет
            if (is_masters_list or not is_shops_list) and not hide_counts:
                button_text = f"{button_name} [{count}]"
            else:
                # Для магазинов или если скрыты счетчики не добавляем счетчик
                button_text = f"{button_name}"
                
            kb.add(KeyboardButton(button_text))
    elif is_shops_list:
        # Для обычного списка магазинов (без количества)
        for button in buttons_list:
            # Удаляем эмодзи из названия категории
            button_name = button
            for emoji in emoji_list:
                if button_name.startswith(emoji):
                    button_name = button_name.replace(emoji, "", 1).strip()
            
            kb.add(KeyboardButton(button_name))
    else:
        # Для остальных списков - по row_width кнопок в ряд
        buttons = []
        for button in buttons_list:
            # Удаляем эмодзи из названия категории
            button_name = button
            for emoji in emoji_list:
                if button_name.startswith(emoji):
                    button_name = button_name.replace(emoji, "", 1).strip()
            
            buttons.append(KeyboardButton(button_name))
        rows = [buttons[i:i+row_width] for i in range(0, len(buttons), row_width)]
        for row in rows:
            kb.row(*row)
    kb.row(KeyboardButton('◀️ Назад в главное меню'))
    return kb


# Генератор клавиатуры с кнопкой "Вернуться к категориям магазинов" сверху и снизу
def generator_with_categories_button(buttons_list, row_width=1, force_single_column=True, preserve_emoji=True, sort_alphabetically=True):
    """
    Создает клавиатуру с кнопками магазинов и кнопкой "Вернуться к категориям магазинов" вверху и внизу
    :param buttons_list: список названий кнопок
    :param row_width: количество кнопок в ряду (по умолчанию 1)
    :param force_single_column: принудительно размещать кнопки в одну колонку (по умолчанию True)
    :param preserve_emoji: не добавлять эмодзи к кнопкам, если они уже есть в названии (по умолчанию True)
    :param sort_alphabetically: сортировать ли кнопки по алфавиту
    :return: ReplyKeyboardMarkup
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=row_width)
    
    # Кнопка "Вернуться к категориям магазинов" вверху
    kb.row(KeyboardButton('◀️ Вернуться к категориям магазинов'))
    
    # Кнопка "Назад в главное меню" вверху
    kb.row(KeyboardButton('◀️ Назад в главное меню'))
    
    # Всегда сортируем кнопки по алфавиту
    buttons_list = sort_buttons(buttons_list)
    
    # Список эмодзи, которые могут быть уже в кнопках
    emoji_list = ["📋", "📂", "🔧", "🏢", "📝", "🛒", "🔨", "🏪", "🏗", "🚿", "🔌", "🏡", "🧱", "🚜", "🪑", "🌱"]
    
    # Для списка магазинов - по одной кнопке в ряд
    for button in buttons_list:
        # Удаляем эмодзи из названия категории
        button_name = button
        for emoji in emoji_list:
            if button_name.startswith(emoji):
                button_name = button_name.replace(emoji, "", 1).strip()
        
        kb.add(KeyboardButton(button_name))
    
    # Кнопка "Вернуться к категориям магазинов" внизу
    kb.row(KeyboardButton('◀️ Вернуться к категориям магазинов'))
    
    # Кнопка "Назад в главное меню" внизу
    kb.row(KeyboardButton('◀️ Назад в главное меню'))
        
    return kb


# Генератор inline-клавиатуры с кнопкой "Назад"
def inline_generator(buttons_list, row_width=1, with_back_button=True):
    """
    Создает inline-клавиатуру с кнопками и, опционально, кнопкой "Назад" внизу
    :param buttons_list: список кнопок (объекты InlineKeyboardButton)
    :param row_width: количество кнопок в ряду
    :param with_back_button: добавлять ли кнопку "Назад"
    :return: InlineKeyboardMarkup
    """
    kb = InlineKeyboardMarkup(row_width=row_width)
    
    # Добавляем кнопки
    for button in buttons_list:
        kb.add(button)
    
    # Добавляем кнопку "Назад", если нужно
    if with_back_button:
        kb.add(back_button)
    
    return kb


# Создание клавиатуры с одной кнопкой для перехода в главное меню
def go_back():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton('◀️ Назад в главное меню'))
    return kb

# Создание клавиатуры с кнопками навигации
def navigation_keyboard(include_shop_categories=False, include_masters_categories=False, include_shop_list=False):
    """
    Создает клавиатуру с кнопками навигации для разных ситуаций
    :param include_shop_categories: добавлять ли кнопку возврата к категориям магазинов
    :param include_masters_categories: добавлять ли кнопку возврата к категориям мастеров
    :param include_shop_list: добавлять ли кнопку возврата к списку магазинов
    :return: ReplyKeyboardMarkup
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    # Добавляем кнопки в определенном порядке навигации - от ближайшего возврата к дальнему
    if include_shop_list:
        kb.add(KeyboardButton('◀️ Вернуться к списку магазинов'))
    
    if include_shop_categories:
        kb.add(KeyboardButton('◀️ Вернуться к категориям магазинов'))
    
    if include_masters_categories:
        # Используем особый текст для кнопки, чтобы точно идентифицировать ее
        kb.add(KeyboardButton('◀️ НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ ◀️'))
    
    # Кнопка возврата в главное меню всегда присутствует
    kb.add(KeyboardButton('◀️ Назад в главное меню'))
    
    return kb

"""from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Keyboard
from loader import topics



def main():
    kb = InlineKeyboardMarkup(resize_keyboard=True)
    buttons = [
        InlineKeyboardButton('Главное меню', callback_data='None'),
        InlineKeyboardButton('Предложить пост', callback_data='None'),
        InlineKeyboardButton('Посмотреть темы', callback_data='None'),
        InlineKeyboardButton('Ссылка на группу', callback_data='None'),
    ]
    kb.add(*buttons)
    return kb

#Клавиатура с меню топиков
def topics_menu():
    kb = InlineKeyboardMarkup()

    for key, value in topics.items():
        kb.add(InlineKeyboardButton(text=key, callback_data=value))
    
    return kb

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton



def navigation(post_id, topic_length):
    kb = InlineKeyboardMarkup()

    if post_id > 1:
        kb.add(InlineKeyboardButton(text="Назад", callback_data=f"post_id_{post_id-1}"))

    if post_id < topic_length:
        kb.add(InlineKeyboardButton(text="Вперёд", callback_data=f"post_id_{post_id+1}"))
    kb.add(InlineKeyboardButton(text="Назад в меню", callback_data=f"'start'"))

    return kb

"""