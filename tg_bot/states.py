from aiogram.dispatcher.filters.state import StatesGroup, State


class User(StatesGroup):
    """Состояния для пользователей бота"""
    # Основные состояния
    get_master = State()  # Состояние просмотра мастеров
    get_shop = State()  # Состояние просмотра магазинов
    get_shop_info = State()  # Состояние просмотра информации о магазине
    get_shop_category = State()  # Состояние выбора категории магазинов
    view_masters_carousel = State()  # Состояние просмотра карусели мастеров
    view_master_works = State()  # Состояние просмотра работ мастера
    
    # Новые состояния для работы с мастерами
    select_master_category = State()  # Состояние выбора категории мастеров
    select_master = State()  # Состояние выбора мастера из категории
    view_master = State()  # Состояние просмотра информации о мастере
    
    # Расширенные состояния
    send_post = State()  # Состояние создания поста
    view_post = State()  # Состояние просмотра постов
    search_query = State()  # Состояние поиска
    
    # Состояния для обратной связи
    feedback = State()  # Состояние обратной связи
    contact_admin = State()  # Состояние связи с администратором

