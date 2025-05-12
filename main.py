import logging
import aiogram
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from tg_bot.states import User
from tg_bot import buttons
import vk
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import asyncio
import config
import time
from datetime import datetime
from aiogram.utils import exceptions
import os
import sys
import socket
import tempfile
import psutil

# Настройка логирования
if config.LOG_TO_FILE:
    # Настройка для логирования в файл с ротацией
    from logging.handlers import RotatingFileHandler
    
    # Создаем директорию для логов, если ее не существует
    log_dir = os.path.dirname(config.LOG_FILENAME)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем обработчик файла с ротацией
    file_handler = RotatingFileHandler(
        config.LOG_FILENAME,
        maxBytes=config.LOG_FILE_MAX_SIZE,
        backupCount=config.LOG_FILE_BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter(config.LOG_FORMAT, config.LOG_DATE_FORMAT))
    
    # Настраиваем консольный вывод
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(config.LOG_FORMAT, config.LOG_DATE_FORMAT))
    
    # Настраиваем корневой логгер
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        handlers=[file_handler, console_handler],
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT
    )
else:
    # Только консольное логирование
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT
    )

logger = logging.getLogger(__name__)

# Механизм блокировки для предотвращения запуска нескольких экземпляров
LOCK_SOCKET = None
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'sfb_bot.lock')

def is_bot_already_running():
    """Проверяет, запущен ли уже экземпляр бота"""
    global LOCK_SOCKET
    
    try:
        # Создаем файл блокировки
        if os.path.exists(LOCK_FILE):
            # Проверяем, существует ли еще процесс
            with open(LOCK_FILE, 'r') as f:
                pid = f.read().strip()
                
            try:
                # Проверяем, существует ли процесс с таким PID
                pid = int(pid)
                os.kill(pid, 0)  # Не убивает процесс, а только проверяет его существование
                logger.warning(f"Бот уже запущен (PID: {pid})!")
                return True
            except (ValueError, ProcessLookupError, OSError):
                # Процесс не существует, файл блокировки устарел
                logger.info("Найден устаревший файл блокировки, перезаписываем")
        
        # Создаем новый файл блокировки
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        # В качестве дополнительной защиты используем сокет
        LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        LOCK_SOCKET.bind(('localhost', 47200))  # Используем уникальный порт для бота
        logger.info(f"Блокировка создана (PID: {os.getpid()})")
        return False
    except Exception as e:
        logger.error(f"Ошибка при создании блокировки: {e}")
        # В случае ошибки позволяем боту запуститься
        return False

def release_lock():
    """Освобождает блокировку при остановке бота"""
    global LOCK_SOCKET
    
    try:
        # Закрываем сокет, если он был создан
        if LOCK_SOCKET is not None:
            LOCK_SOCKET.close()
        
        # Удаляем файл блокировки
        if os.path.exists(LOCK_FILE):
            # Проверяем, что файл принадлежит текущему процессу
            with open(LOCK_FILE, 'r') as f:
                pid = f.read().strip()
                
            if pid == str(os.getpid()):
                os.remove(LOCK_FILE)
                logger.info("Блокировка освобождена")
    except Exception as e:
        logger.error(f"Ошибка при освобождении блокировки: {e}")

# Инициализация бота и диспетчера
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Кэш для хранения данных
cache = {}

# Добавляем кэш для непустых категорий мастеров
non_empty_masters_cache = {}
non_empty_masters_cache_time = 0

# Добавляем кэш для магазинов
shops_categories_cache = {}
shops_categories_cache_time = 0

# Добавляем лимитер запросов к ВК API
vk_api_semaphore = asyncio.Semaphore(config.API_RATE_LIMIT)  # Используем лимит из конфига
vk_api_last_request_time = {}  # Словарь для отслеживания времени последнего запроса для каждого метода

async def vk_api_rate_limit():
    """Функция для ограничения частоты запросов к API ВКонтакте"""
    async with vk_api_semaphore:
        # Гарантируем, что между запросами к ВК API будет минимальная пауза
        current_time = datetime.now()
        method_key = "global"  # Используем глобальный ключ для всех запросов
        
        if method_key in vk_api_last_request_time:
            time_since_last_request = (current_time - vk_api_last_request_time[method_key]).total_seconds()
            if time_since_last_request < config.API_RATE_LIMIT_INTERVAL:  # Используем интервал из конфига
                await asyncio.sleep(config.API_RATE_LIMIT_INTERVAL - time_since_last_request)
        
        # Обновляем время последнего запроса
        vk_api_last_request_time[method_key] = datetime.now()

# Добавляем дополнительные оптимизации для кэша
def clear_old_cache_entries():
    """Очищает устаревшие записи в кэше для освобождения памяти"""
    current_time = time.time()
    keys_to_remove = []
    
    for key, cache_entry in cache.items():
        if current_time - cache_entry["time"] > config.CACHE_TIME * 2:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del cache[key]
    
    if keys_to_remove:
        logger.info(f"Очищено {len(keys_to_remove)} устаревших записей из кэша")

# Периодическая очистка кэша каждые 30 минут
async def periodic_cache_cleanup():
    """Периодически очищает устаревшие записи в кэше"""
    while True:
        await asyncio.sleep(1800)  # 30 минут
        clear_old_cache_entries()
        
        # Логирование использования памяти
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # В МБ
        logger.info(f"Текущее использование памяти: {memory_usage:.2f} МБ")

# Функция для оптимизированной загрузки данных
async def preload_critical_data():
    """Предварительно загружает критически важные данные в кэш"""
    try:
        # Загружаем только основные данные, которые нужны для быстрого старта
        logger.info("Предварительная загрузка критических данных...")
        
        # Загрузка описания группы (легкий запрос)
        await vk_api_rate_limit()
        await get_group_description_async(config.VK_TOKEN, config.VK_GROUP_ID)
        
        # Запускаем асинхронную задачу для загрузки остальных данных
        asyncio.create_task(preload_remaining_data())
        
    except Exception as e:
        logger.error(f"Ошибка при предварительной загрузке критических данных: {e}")

async def preload_remaining_data():
    """Асинхронно загружает остальные данные после запуска бота"""
    try:
        # Даем боту время на инициализацию и обработку первых запросов
        await asyncio.sleep(5)
        
        logger.info("Начинаю фоновую загрузку дополнительных данных...")
        
        # Загружаем категории магазинов (ресурсоемкий запрос)
        await vk_api_rate_limit()
        global shops_categories_cache, shops_categories_cache_time
        shops = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID)
        shops_categories_cache = shops
        shops_categories_cache_time = time.time()
        logger.info("✅ Категории магазинов загружены в фоновом режиме")
        
        # Загружаем альбомы мастеров
        await vk_api_rate_limit()
        albums = await get_album_names_async(config.VK_TOKEN, config.VK_GROUP_ID)
        logger.info("✅ Альбомы мастеров загружены в фоновом режиме")
        
        # Загружаем категории маркета
        await vk_api_rate_limit()
        await get_market_categories_async(config.VK_TOKEN, config.VK_GROUP_ID)
        logger.info("✅ Категории маркета загружены в фоновом режиме")
        
        logger.info("✅ Фоновая загрузка дополнительных данных завершена")
        
    except Exception as e:
        logger.error(f"Ошибка при фоновой загрузке дополнительных данных: {e}")

# Функция для кэширования результатов
def cached(func):
    async def wrapper(*args, force_update=False, **kwargs):
        key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
        current_time = time.time()
        
        # Проверяем, есть ли данные в кэше и не устарели ли они
        if (key in cache and not force_update and 
            current_time - cache[key]['time'] < config.CACHE_TIME):
            logger.info(f"Данные получены из кэша: {func.__name__}")
            return cache[key]['data']
        
        # Применяем ограничение частоты запросов
        await vk_api_rate_limit()
        
        # Если данных нет в кэше или нужно обновить их, вызываем функцию
        start_time = time.time()
        result = await func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Логируем время выполнения для тяжелых запросов
        if execution_time > 1.0:
            logger.info(f"Тяжелый запрос {func.__name__} выполнен за {execution_time:.2f} сек")
        
        cache[key] = {'data': result, 'time': current_time}
        logger.info(f"Данные обновлены в кэше: {func.__name__}")
        return result
    return wrapper

@cached
async def get_group_description_async(token, group_id, force_update=False):
    """Асинхронная обертка для получения описания группы"""
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_group_description, token, group_id)

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    user_name = message.from_user.first_name
    
    # Получаем описание группы из ВКонтакте или из кэша
    welcome_message = await get_group_description_async(config.VK_TOKEN, config.VK_GROUP_ID)
    
    # Если не удалось получить описание, используем сообщение из конфига
    if not welcome_message:
        welcome_message = config.WELCOME_MESSAGE
    
    await message.answer(
        f"👋 Здравствуйте, {user_name}!\n\n{welcome_message}", 
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.main
    )
    
@dp.message_handler(lambda m: m.text == '◀️ Назад' or m.text == 'Назад' or m.text == '◀️ Назад в главное меню', state='*')
async def back_to_main(message: types.Message, state: FSMContext):
    user_name = message.from_user.first_name
    
    # Получаем описание группы из ВКонтакте или из кэша
    welcome_message = await get_group_description_async(config.VK_TOKEN, config.VK_GROUP_ID)
    
    # Если не удалось получить описание, используем сообщение из конфига
    if not welcome_message:
        welcome_message = config.WELCOME_MESSAGE
    
    await message.answer(
        f"👋 Здравствуйте, {user_name}!\n\n{welcome_message}", 
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.main
    )
    await state.finish()
    
@cached
async def get_album_photos_async(token, owner_id, album_id, force_update=False):
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_album_photos, token, owner_id, album_id)
    
@cached
async def get_photo_comments_async(token, owner_id, photo_id, force_update=False):
    """Асинхронная обертка для получения комментариев к фотографии"""
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_photo_comments, token, owner_id, photo_id)
    
@dp.message_handler(state=User.get_master)
async def show_master(message: types.Message, state: FSMContext):
    # Проверяем, не является ли сообщение командой возврата
    if message.text == "◀️ НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ ◀️" or message.text == "◀️ Вернуться к категориям мастеров":
        logger.info(f"Перехвачена кнопка возврата к категориям: '{message.text}'")
        await back_to_master_categories(message, state)
        return
    
    data = await state.get_data()
    
    # Убираем эмодзи и счетчик количества из текста сообщения
    original_text = message.text
    category = message.text
    # Список эмодзи, которые могут быть в начале текста
    emoji_list = ["📋", "📂", "🔧", "🏢", "📝", "🛒", "🔨", "🏪", "🏗", "🚿", "🔌", "🏡", "🧱", "🚜", "🪑", "🌱"]
    
    # Убираем все эмодзи из начала текста
    for emoji in emoji_list:
        if category.startswith(emoji + " "):
            category = category[len(emoji) + 1:]
            break
    
    # Убираем счетчик количества в формате [N]
    if ' [' in category and category.endswith(']'):
        category = category.split(' [')[0]
    
    logger.info(f"Запрос категории: '{original_text}', обработанное название: '{category}'")
    logger.info(f"Доступные категории: {list(data.keys())}")
    
    # Ищем категорию в данных различными способами
    found_category = None
    
    # 1. Прямое совпадение
    if category in data:
        found_category = category
    else:
        # 2. Поиск без учета регистра
        for key in data.keys():
            clean_key = key
            # Удаляем эмодзи из ключа для сравнения
            for emoji in emoji_list:
                if clean_key.startswith(emoji + " "):
                    clean_key = clean_key[len(emoji) + 1:]
                    break
                    
            logger.info(f"Сравниваем: '{category.lower()}' с '{clean_key.lower()}'")
            
            # Проверяем совпадение с очищенными от эмодзи ключами
            if clean_key.lower() == category.lower():
                found_category = key
                logger.info(f"Найдено совпадение: '{key}'")
                break
            
            # Проверяем, если категория в сообщении содержит эмодзи, а ключ - нет
            for emoji in emoji_list:
                if original_text.startswith(emoji + " "):
                    original_without_emoji = original_text[len(emoji) + 1:]
                    if key.lower() == original_without_emoji.lower():
                        found_category = key
                        logger.info(f"Найдено совпадение с оригинальным текстом без эмодзи: '{key}'")
                        break
    
    # Если категория не найдена
    if not found_category:
        logger.warning(f"Категория не найдена: '{category}'. Доступные категории: {list(data.keys())}")
        
        # Используем данные из кэша для отображения доступных категорий
        global non_empty_masters_cache
        if non_empty_masters_cache and "buttons" in non_empty_masters_cache:
            category_buttons = non_empty_masters_cache["buttons"]
        else:
            # Если кэша нет, формируем список категорий (редкий случай)
            category_buttons = []
            for cat, album_id in data.items():
                await vk_api_rate_limit()  # Применяем ограничение API
                photos = await get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id)
                category_buttons.append((cat, len(photos)))
        
        await message.answer("⚠️ Извините, такой категории не найдено. Выберите категорию из списка ниже.", 
                            reply_markup=buttons.generator(category_buttons))
        return
    
    # Показываем сообщение о загрузке
    loading_message = await message.answer(f"🔍 <b>Загружаю информацию о мастерах категории:</b> {found_category}...", 
                        parse_mode=ParseMode.HTML)
                          
    current = data.get(found_category)
    logger.info(f"Загружаем альбом ID: {current} для категории '{found_category}'")
    await vk_api_rate_limit()  # Применяем ограничение API
    photos = await get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, current)
    
    # Удаляем сообщение о загрузке после получения данных
    await loading_message.delete()
    
    # Сохраняем выбранную категорию и фотографии в состоянии для карусели
    await state.update_data(
        current_master_category=found_category,
        master_photos=photos,
        current_photo_index=0
    )
    
    if not photos or len(photos) == 0:
        await message.answer(f"📂 <b>Категория {found_category}</b>\n\n⚠️ В данной категории пока нет мастеров. Вы можете стать первым, нажав кнопку 'Попасть в базу мастеров'.", 
                            parse_mode=ParseMode.HTML,
                            reply_markup=buttons.navigation_keyboard(include_masters_categories=True))
        return
    
    # Отправляем первую фотографию с кнопками навигации
    await send_master_photo(message.chat.id, state)
    
    # Переходим в состояние просмотра карусели мастеров
    await User.view_masters_carousel.set()

# Функция для отправки фотографии мастера с кнопками навигации
async def send_master_photo(chat_id, state):
    # Получаем данные из состояния
    data = await state.get_data()
    photos = data.get('master_photos', [])
    current_index = data.get('current_photo_index', 0)
    category = data.get('current_master_category', 'Мастера')
    
    if not photos or len(photos) == 0:
        await bot.send_message(
            chat_id,
            "⚠️ Фотографии не найдены.",
            reply_markup=buttons.navigation_keyboard(include_masters_categories=True)
        )
        return
    
    # Получаем текущую фотографию
    photo = photos[current_index]
    
    # Формируем подпись
    caption = photo.get('description', '') if photo.get('description') else f"Фото {current_index+1} из {len(photos)}"
    full_caption = f"<b>📸 {category}</b>\n\n{caption}"
    
    # Добавляем ссылку на основной паблик ВКонтакте
    full_caption += f"\n\n🌐 <a href='{config.VK_GROUP_URL}'>Перейти в основной паблик СФБ ВКонтакте</a>"
    
    # Создаем клавиатуру с кнопками навигации
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопку "Назад", если не первая фотография
    if current_index > 0:
        kb.insert(InlineKeyboardButton("◀️ Назад", callback_data="master_prev"))
    
    # Добавляем кнопку "Далее", если не последняя фотография
    if current_index < len(photos) - 1:
        kb.insert(InlineKeyboardButton("Далее ▶️", callback_data="master_next"))
    
    # Добавляем счетчик
    kb.add(InlineKeyboardButton(f"{current_index+1}/{len(photos)}", callback_data="master_count"))
    
    # Добавляем кнопку для просмотра работ мастера
    # Сначала проверяем, есть ли у фотографии ID для получения комментариев
    photo_id = photo.get('id')
    if photo_id:
        # Проверяем, есть ли у этого мастера работы
        work_photos = await get_photo_comments_async(config.VK_TOKEN, config.VK_GROUP_ID, photo_id)
        works_count = len(work_photos) if work_photos else 0
        
        # Добавляем кнопку "Работы мастера" с количеством работ
        if works_count > 0:
            kb.add(InlineKeyboardButton(f"📸 Посмотреть работы мастера [{works_count}]", callback_data=f"master_works_{photo_id}"))
    
    # Добавляем кнопку возврата к категориям мастеров
    kb.add(InlineKeyboardButton("◀️ Вернуться к категориям", callback_data="master_back_to_categories"))
    
    # Используем новую клавиатуру только с кнопкой возврата к категориям мастеров
    reply_markup = buttons.masters_carousel_keyboard()
    
    try:
        # Проверяем длину подписи
        if len(full_caption) <= 1024:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo['url'],
                caption=full_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        else:
            # Если подпись слишком длинная, отправляем фото и текст отдельно
            logger.info(f"Слишком длинная подпись для фото мастера: {len(full_caption)} символов. Отправляем фото и текст отдельно.")
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo['url'],
                reply_markup=kb
            )
            await bot.send_message(
                chat_id=chat_id,
                text=full_caption,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке фото мастера: {error_msg}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Не удалось загрузить фото мастера.\n\n{full_caption}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

# Функция для отправки фотографии работ мастера с кнопками навигации
async def send_master_work_photo(chat_id, state):
    # Получаем данные из состояния
    data = await state.get_data()
    photos = data.get('master_work_photos', [])
    current_index = data.get('current_work_index', 0)
    category = data.get('current_master_category', 'Мастера')
    
    if not photos or len(photos) == 0:
        await bot.send_message(
            chat_id,
            "⚠️ Фотографии работ не найдены.",
            reply_markup=buttons.navigation_keyboard(include_masters_categories=True)
        )
        return
    
    # Получаем текущую фотографию
    photo = photos[current_index]
    
    # Формируем подпись
    caption = photo.get('description', '') if photo.get('description') else f"Работа {current_index+1} из {len(photos)}"
    full_caption = f"<b>🛠️ Работы мастера ({category})</b>\n\n{caption}"
    
    # Добавляем ссылку на основной паблик ВКонтакте
    full_caption += f"\n\n🌐 <a href='{config.VK_GROUP_URL}'>Перейти в основной паблик СФБ ВКонтакте</a>"
    
    # Создаем inline-клавиатуру только с кнопками пролистывания фото
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопку "Назад", если не первая фотография
    if current_index > 0:
        kb.insert(InlineKeyboardButton("◀️ Назад", callback_data="work_prev"))
    
    # Добавляем кнопку "Далее", если не последняя фотография
    if current_index < len(photos) - 1:
        kb.insert(InlineKeyboardButton("Далее ▶️", callback_data="work_next"))
    
    # Добавляем счетчик
    kb.add(InlineKeyboardButton(f"{current_index+1}/{len(photos)}", callback_data="work_count"))
    
    # Получаем клавиатуру с кнопками навигации
    reply_markup = buttons.master_works_keyboard()
    
    try:
        # Проверяем длину подписи
        if len(full_caption) <= 1024:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo['url'],
                caption=full_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        else:
            # Если подпись слишком длинная, отправляем фото и текст отдельно
            logger.info(f"Слишком длинная подпись для фото работы мастера: {len(full_caption)} символов. Отправляем фото и текст отдельно.")
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo['url'],
                reply_markup=kb
            )
            await bot.send_message(
                chat_id=chat_id,
                text=full_caption,
                parse_mode=ParseMode.HTML
            )
            
        # Устанавливаем клавиатуру с кнопками навигации
        await bot.send_message(
            chat_id=chat_id,
            text="\u200B", # Невидимый символ
            reply_markup=reply_markup
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке фото работы мастера: {error_msg}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Не удалось загрузить фото работы мастера.\n\n{full_caption}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

# Обработчик нажатия кнопки "Посмотреть работы мастера"
@dp.callback_query_handler(lambda c: c.data.startswith("master_works_"), state=User.view_masters_carousel)
async def master_works_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID фотографии из callback_data
    photo_id = callback_query.data.replace("master_works_", "")
    
    # Показываем сообщение о загрузке
    await callback_query.answer("Загружаем работы мастера...")
    loading_message = await callback_query.message.answer("🔄 <b>Загружаем работы мастера...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    # Получаем данные из состояния
    data = await state.get_data()
    category = data.get('current_master_category', 'Мастера')
    
    try:
        # Получаем комментарии к фотографии (работы мастера)
        logger.info(f"Получаем работы мастера для фото ID: {photo_id}")
        work_photos = await get_photo_comments_async(config.VK_TOKEN, config.VK_GROUP_ID, photo_id)
        
        # Удаляем сообщение о загрузке
        await loading_message.delete()
        
        # Проверяем, есть ли фотографии работ
        if not work_photos or len(work_photos) == 0:
            await callback_query.message.answer(
                "⚠️ У этого мастера пока нет фотографий работ.",
                reply_markup=buttons.masters_carousel_keyboard()
            )
            return
        
        # Логируем количество найденных работ
        logger.info(f"Найдено {len(work_photos)} работ мастера для фото ID: {photo_id}")
        
        # Сохраняем фотографии работ и индекс текущей фотографии в состоянии
        await state.update_data(
            master_work_photos=work_photos,
            current_work_index=0
        )
        
        # Удаляем предыдущее сообщение с фото мастера
        await callback_query.message.delete()
        
        # Переходим в состояние просмотра работ мастера
        await User.view_master_works.set()
        
        # Отправляем первую фотографию работы
        await send_master_work_photo(callback_query.message.chat.id, state)
    except Exception as e:
        logger.error(f"Ошибка при получении работ мастера: {e}")
        await loading_message.delete()
        await callback_query.message.answer(
            f"⚠️ Произошла ошибка при загрузке работ мастера: {str(e)}",
            reply_markup=buttons.masters_carousel_keyboard()
        )

# Обработчик нажатия кнопки "Далее" в карусели работ мастера
@dp.callback_query_handler(lambda c: c.data == "work_next", state=User.view_master_works)
async def work_next_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    current_index = data.get('current_work_index', 0)
    photos = data.get('master_work_photos', [])
    
    # Увеличиваем индекс, если не последняя фотография
    if current_index < len(photos) - 1:
        current_index += 1
        await state.update_data(current_work_index=current_index)
    
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Отправляем новую фотографию
    await send_master_work_photo(callback_query.message.chat.id, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик нажатия кнопки "Назад" в карусели работ мастера
@dp.callback_query_handler(lambda c: c.data == "work_prev", state=User.view_master_works)
async def work_prev_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    current_index = data.get('current_work_index', 0)
    
    # Уменьшаем индекс, если не первая фотография
    if current_index > 0:
        current_index -= 1
        await state.update_data(current_work_index=current_index)
    
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Отправляем новую фотографию
    await send_master_work_photo(callback_query.message.chat.id, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик нажатия на счетчик работ (ничего не делает)
@dp.callback_query_handler(lambda c: c.data == "work_count", state=User.view_master_works)
async def work_count_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Текущая позиция в галерее работ")

# Обработчик нажатия кнопки "Вернуться к анкете мастера" в карусели работ
@dp.callback_query_handler(lambda c: c.data == "back_to_master", state=User.view_master_works)
async def back_to_master_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Переходим обратно в состояние просмотра карусели мастеров
    await User.view_masters_carousel.set()
    
    # Отправляем фото мастера
    await send_master_photo(callback_query.message.chat.id, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

@cached
async def get_market_items_async(token, owner_id, album_id, force_update=False):
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_market_item_info, token, owner_id, album_id)

@dp.message_handler(state=User.get_shop)
async def show_shop(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text not in data and message.text.replace('🛒 ', '') not in data:
        await message.answer("⚠️ Извините, такой категории не найдено. Выберите категорию из списка ниже.", 
                             reply_markup=buttons.generator(data.keys()))
        return
        
    # Удаляем эмодзи из текста сообщения, если они есть
    category = message.text
    for prefix in ['🛒 ', '🧱 ', '🔨 ', '🪑 ', '🌱 ']:
        if prefix in category:
            category = category.replace(prefix, '')
            break
        
    current = data.get(category, data.get(message.text))
    await message.answer(f"🔍 <b>Загружаю информацию о товарах категории:</b> {category}...", 
                          parse_mode=ParseMode.HTML)
                          
    items = await get_market_items_async(config.VK_TOKEN, config.VK_GROUP_ID, current)
    
    if not items:
        await message.answer("⚠️ К сожалению, товары не найдены", 
                            reply_markup=buttons.go_back())
        return
        
    for i, item in enumerate(items):
        try:
            # Добавляем ссылку на товар в текст
            item_url = item.get('url', '')
            price_text = f"\n💰 {item.get('price')}" if item.get('price') else ""
            
            caption = f"<b>🛒 {item['title']}</b>{price_text}\n\n{item['description']}"
            if item_url:
                caption += f"\n\n<a href='{item_url}'>Посмотреть в магазине ВКонтакте</a>"
            
            # Добавляем ссылку на основной паблик ВКонтакте
            caption += f"\n\n🌐 <a href='{config.VK_GROUP_URL}'>Перейти в основной паблик СФБ ВКонтакте</a>"
            
            # Проверяем длину подписи    
            if len(caption) <= 1024:  # Telegram ограничивает длину подписи к фото
                await message.answer_photo(photo=item['photo'], caption=caption, parse_mode=ParseMode.HTML)
            else:
                # Если подпись слишком длинная, отправляем фото и текст отдельно
                logger.info(f"Слишком длинная подпись для товара '{item['title']}': {len(caption)} символов. Отправляем фото и текст отдельно.")
                await message.answer_photo(photo=item['photo'])
                await message.answer(caption, parse_mode=ParseMode.HTML)
            
            # Небольшая задержка между сообщениями
            await asyncio.sleep(0.3)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка при отправке информации о товаре '{item.get('title')}': {error_msg}")
            
            # Обработка ошибок, связанных с фото
            if "Bad Request" in error_msg and ("Wrong file identifier" in error_msg or "PHOTO_INVALID_DIMENSIONS" in error_msg):
                logger.warning(f"Проблема с фото товара '{item.get('title')}': {error_msg}")
                await message.answer(
                    f"<b>🛒 {item['title']}</b>{price_text}\n\n{item['description']}"
                    f"\n\n⚠️ Не удалось загрузить изображение товара.", 
                    parse_mode=ParseMode.HTML
                )
            elif "Message caption is too long" in error_msg:
                # Обработка ошибки с длинной подписью, если проверка выше не сработала
                logger.warning(f"Слишком длинная подпись для товара '{item.get('title')}'")
                try:
                    await message.answer_photo(photo=item['photo'])
                    await message.answer(caption, parse_mode=ParseMode.HTML)
                except Exception as inner_e:
                    logger.error(f"Повторная ошибка при отправке информации о товаре: {inner_e}")
                    await message.answer(f"<b>🛒 {item['title']}</b>\n\n{item['description']}", 
                                     parse_mode=ParseMode.HTML)
            else:
                # Общая обработка ошибок
                try:
                    await message.answer_photo(photo=item['photo'])
                    await message.answer(f"<b>🛒 {item['title']}</b>\n\n{item['description']}", 
                                        parse_mode=ParseMode.HTML)
                except:
                    await message.answer(f"⚠️ Не удалось загрузить информацию о товаре: {item['title']}")

    # После отправки всех товаров показываем кнопку "Назад"
    await message.answer("🔍 <b>Просмотр завершен.</b> Вы можете вернуться в главное меню или выбрать другую категорию.", 
                         parse_mode=ParseMode.HTML,
                         reply_markup=buttons.navigation_keyboard(include_shop_categories=True))

@cached
async def get_album_names_async(token, group_id, force_update=False):
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_album_names, token, group_id)

# Обработчик для кнопки "База мастеров СФБ"
@dp.message_handler(lambda m: m.text == "👷‍♂️ База мастеров СФБ" or m.text == "База мастеров СФБ")
async def masters_sfb_message(message: types.Message, state: FSMContext):
    await masters_sfb_button_handler(message)

# Отдельная функция для обработки нажатия кнопки "База мастеров СФБ"
# Эта функция будет использоваться как при первом нажатии, так и при возврате к категориям
async def masters_sfb_button_handler(message: types.Message):
    # Создаем новое состояние
    state = dp.current_state(user=message.from_user.id)
    # Сбрасываем текущее состояние для начала нового сценария
    await state.finish()
    # Вызываем обработчик для отображения категорий мастеров
    await masters_sfb_handler(message, state)

# Общая функция для обработки запроса к базе мастеров
async def masters_sfb_handler(message, state: FSMContext):
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю категории мастеров...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    global non_empty_masters_cache, non_empty_masters_cache_time
    current_time = time.time()
    
    # Проверяем, есть ли актуальный кэш непустых категорий
    if non_empty_masters_cache and current_time - non_empty_masters_cache_time < config.CACHE_TIME:
        logger.info("Используем кэш категорий мастеров")
        category_buttons = non_empty_masters_cache.get("buttons", [])
        all_categories = non_empty_masters_cache.get("all_categories", {})
    else:
        # Получаем данные о категориях только если кэш устарел
        try:
            data = await get_album_names_async(config.VK_TOKEN, config.VK_GROUP_ID)
            
            if not data:
                await loading_message.delete()
                await message.answer("⚠️ К сожалению, категории мастеров не найдены",
                                    reply_markup=buttons.go_back())
                return
                
            logger.info("Обновляем кэш категорий мастеров")
            # Создаем задачи для параллельной загрузки фотографий
            tasks = []
            for cat, album_id in data.items():
                # Применяем ограничение частоты запросов перед каждым запросом
                await vk_api_rate_limit()
                tasks.append((cat, album_id, get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id)))
            
            # Последовательно обрабатываем результаты с паузами между запросами
            category_buttons = []
            all_categories = {}
            
            # Сохраняем все категории и их ID
            for cat, album_id in data.items():
                all_categories[cat] = album_id
            
            # Получаем информацию о количестве фото в каждой категории
            for cat, album_id, task in tasks:
                photos = await task
                count = len(photos) if photos else 0
                category_buttons.append((cat, count))
            
            # Сохраняем результаты в кэш
            non_empty_masters_cache = {
                "buttons": category_buttons,
                "all_categories": all_categories
            }
            non_empty_masters_cache_time = current_time
            
            # Логируем ключи для отладки
            logger.info(f"Все категории мастеров в кэше: {list(all_categories.keys())}")
        except Exception as e:
            logger.error(f"Ошибка при получении категорий мастеров: {e}")
            await loading_message.delete()
            await message.answer(
                "⚠️ Произошла ошибка при загрузке категорий мастеров. Пожалуйста, попробуйте позже.",
                reply_markup=buttons.go_back()
            )
            return
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    if not category_buttons:
        await message.answer("⚠️ Нет ни одной категории мастеров.", reply_markup=buttons.go_back())
        return
    
    # Логируем для отладки
    logger.info(f"Категории кнопок: {[cat for cat, _ in category_buttons]}")
    logger.info(f"Категории данных: {list(all_categories.keys())}")
        
    kb = buttons.generator(category_buttons)
    await message.answer('👷‍♂️ <b>Открытая база мастеров и спецтехники</b>\n\nВыберите категорию из списка:', 
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb)
    await User.get_master.set()
    await state.set_data(all_categories)

@cached
async def get_market_categories_async(token, group_id, force_update=False):
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_market_items, token, group_id)

@cached
async def get_shop_list_async(token, group_id, force_update=False):
    """Асинхронная обертка для получения списка магазинов"""
    # Применяем ограничение частоты запросов
    await vk_api_rate_limit()
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vk.get_shop_list, token, group_id)

# Обработчик для кнопки "Магазины-партнеры СФБ"
@dp.message_handler(lambda m: m.text == "🏪 Магазины-партнеры СФБ" or m.text == "Магазины-партнеры СФБ")
async def partners_stores_message(message: types.Message, state: FSMContext):
    await partners_stores_handler(message, state)

# Общая функция для обработки запроса к магазинам-партнерам
async def partners_stores_handler(message, state: FSMContext):
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю категории магазинов...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    global shops_categories_cache, shops_categories_cache_time
    current_time = time.time()
    
    # Проверяем, есть ли актуальный кэш категорий магазинов
    if shops_categories_cache and current_time - shops_categories_cache_time < config.CACHE_TIME:
        logger.info("Используем кэш категорий магазинов")
        shop_categories = shops_categories_cache
    else:
        # Если кэш устарел, обновляем данные
        logger.info("Обновляем кэш категорий магазинов")
        shop_categories = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID)
        
        # Сохраняем результаты в кэш
        shops_categories_cache = shop_categories
        shops_categories_cache_time = current_time
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    # Получаем только категории (исключаем all_shops)
    categories = {k: v for k, v in shop_categories.items() if k != "all_shops"}
    
    # Проверяем, есть ли доступные категории
    if not categories:
        await message.answer(
            "⚠️ К сожалению, не удалось получить информацию о магазинах-партнерах из ВКонтакте.\n\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору группы.",
            reply_markup=buttons.go_back()
        )
        return
    
    # Проверяем, есть ли магазины в категориях
    has_shops = False
    for category, shops in categories.items():
        if shops and len(shops) > 0:
            has_shops = True
            break
    
    if not has_shops:
        await message.answer(
            "⚠️ В настоящее время список магазинов-партнеров пуст.\n\n"
            "Вы можете стать первым партнером, нажав на кнопку 'Стать магазином-партнером'.",
            reply_markup=buttons.go_back()
        )
        return
    
    # Логируем доступные категории для отладки
    logger.info(f"Доступные категории магазинов: {list(categories.keys())}")
    
    # Сортируем категории по алфавиту (без учета эмодзи)
    sorted_categories = buttons.sort_buttons(categories.keys())
    
    # Создаем клавиатуру для категорий магазинов (без количества)
    kb = buttons.generator(sorted_categories, row_width=1, force_single_column=True, preserve_emoji=True)
    await message.answer('🏪 <b>Наши магазины-партнёры</b>\n\nВыберите категорию магазинов:', 
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb)
    await User.get_shop_category.set()
    await state.set_data(shop_categories)

# Обработчик для выбора категории магазинов
@dp.message_handler(state=User.get_shop_category)
async def show_shops_by_category(message: types.Message, state: FSMContext):
    shop_categories = await state.get_data()
    
    # Выводим для отладки
    logger.info(f"Полученный текст категории: {message.text}")
    logger.info(f"Доступные категории: {[k for k in shop_categories.keys() if k != 'all_shops']}")
    
    # Находим выбранную категорию - убираем эмодзи и счетчик [N]
    category_name = message.text
    
    # Убираем счетчик количества в формате [N]
    if ' [' in category_name and category_name.endswith(']'):
        category_name = category_name.split(' [')[0]
    
    # Убираем эмодзи, если есть
    if '📋 ' in category_name:
        category_name = category_name.replace('📋 ', '')
    
    # Ищем категорию с учетом эмодзи и без
    found_category = None
    for cat in shop_categories.keys():
        if cat == category_name or cat == category_name.strip():
            found_category = cat
            break
        # Убираем эмодзи из названия категории для сравнения
        no_emoji_cat = cat
        for emoji in ["🏪", "🧱", "🔨", "🪑", "🌱", "🚿", "🔌", "🏡"]:
            if cat.startswith(emoji + " "):
                no_emoji_cat = cat[len(emoji) + 1:]
                break
        if no_emoji_cat == category_name or no_emoji_cat.strip() == category_name.strip():
            found_category = cat
            break
    
    # Если категория не найдена
    if not found_category:
        categories = {k: v for k, v in shop_categories.items() if k != "all_shops"}
        # Сортируем категории по алфавиту (без учета эмодзи)
        sorted_categories = buttons.sort_buttons(categories.keys())
        await message.answer(
            f"⚠️ Категория '{message.text}' не найдена. Пожалуйста, выберите категорию из списка ниже.", 
            reply_markup=buttons.generator(sorted_categories, row_width=1, force_single_column=True, preserve_emoji=True)
        )
        return
    
    # Получаем магазины этой категории
    shops = shop_categories[found_category]
    
    # Если нет магазинов в этой категории
    if not shops:
        await message.answer(
            f"⚠️ В категории '{found_category}' пока нет магазинов.\n\n"
            "Вы можете стать первым партнером в этой категории, нажав на кнопку 'Стать магазином-партнером' в главном меню.", 
            reply_markup=buttons.go_back()
        )
        return
    
    # Создаем клавиатуру с кнопками магазинов и кнопкой возврата к категориям
    kb = buttons.generator_with_categories_button(shops.keys(), row_width=1, force_single_column=True, preserve_emoji=True)
    await message.answer(
        f"🏪 <b>Магазины категории:</b> {found_category}\n\nВыберите магазин из списка:", 
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    
    # Сохраняем информацию о выбранной категории и магазинах
    await state.update_data(current_category=found_category)
    await User.get_shop_info.set()

# Обработчик для возврата к списку магазинов
@dp.message_handler(lambda m: m.text == "◀️ Вернуться к списку магазинов", state=User.get_shop_info)
async def back_to_shops_list(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_category = data.get('current_category')
    
    # Если категории нет, возвращаемся в главное меню
    if not current_category:
        await message.answer("⚠️ Произошла ошибка. Возвращаемся в главное меню.",
                          reply_markup=buttons.main)
        await state.finish()
        return
    
    # Получаем магазины текущей категории
    shops = data[current_category]
    
    # Если список магазинов пуст, возвращаемся к категориям
    if not shops:
        await message.answer(
            f"⚠️ В категории '{current_category}' нет магазинов. Возвращаемся к категориям.", 
            reply_markup=buttons.go_back()
        )
        await back_to_shop_categories(message, state)
        return
    
    # Создаем клавиатуру с кнопками магазинов и кнопкой возврата к категориям
    kb = buttons.generator_with_categories_button(shops.keys(), row_width=1, force_single_column=True, preserve_emoji=True)
    await message.answer(
        f"🏪 <b>Магазины категории:</b> {current_category}\n\nВыберите магазин из списка:", 
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    
    # Оставляем то же состояние User.get_shop_info
    # Данные состояния не меняются, так как мы остаемся в той же категории

# Обработчик для возврата к категориям магазинов
@dp.message_handler(lambda m: m.text == "◀️ Вернуться к категориям магазинов", state=User.get_shop_info)
async def back_to_shop_categories(message: types.Message, state: FSMContext):
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю категории магазинов...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    global shops_categories_cache, shops_categories_cache_time
    current_time = time.time()
    
    # Проверяем, есть ли актуальный кэш категорий магазинов
    if shops_categories_cache and current_time - shops_categories_cache_time < config.CACHE_TIME:
        logger.info("Используем кэш категорий магазинов при возврате")
        shop_categories = shops_categories_cache
    else:
        # Если кэш устарел, обновляем данные
        logger.info("Обновляем кэш категорий магазинов при возврате")
        shop_categories = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID)
        
        # Сохраняем результаты в кэш
        shops_categories_cache = shop_categories
        shops_categories_cache_time = current_time
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    # Получаем только категории (исключаем all_shops)
    categories = {k: v for k, v in shop_categories.items() if k != "all_shops"}
    
    # Проверяем, есть ли доступные категории
    if not categories:
        await message.answer(
            "⚠️ К сожалению, не удалось получить информацию о магазинах-партнерах из ВКонтакте.\n\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору группы.",
            reply_markup=buttons.go_back()
        )
        return
    
    # Проверяем, есть ли магазины в категориях
    has_shops = False
    for category, shops in categories.items():
        if shops and len(shops) > 0:
            has_shops = True
            break
    
    if not has_shops:
        await message.answer(
            "⚠️ В настоящее время список магазинов-партнеров пуст.\n\n"
            "Вы можете стать первым партнером, нажав на кнопку 'Стать магазином-партнером'.",
            reply_markup=buttons.go_back()
        )
        await state.finish()
        return
    
    # Логируем доступные категории для отладки
    logger.info(f"Доступные категории магазинов при возврате: {list(categories.keys())}")
    
    # Сортируем категории по алфавиту (без учета эмодзи)
    sorted_categories = buttons.sort_buttons(categories.keys())
    
    # Создаем клавиатуру для категорий магазинов (без количества)
    kb = buttons.generator(sorted_categories, row_width=1, force_single_column=True, preserve_emoji=True)
    await message.answer('🏪 <b>Наши магазины-партнёры</b>\n\nВыберите категорию магазинов:', 
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb)
    
    # Сохраняем новые данные в состояние
    await state.set_data(shop_categories)
    await User.get_shop_category.set()

# Обработчик для выбора конкретного магазина из списка
@dp.message_handler(state=User.get_shop_info)
async def show_shop_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_category = data.get('current_category')
    
    # Если нет текущей категории, возвращаемся к выбору категорий
    if not current_category:
        await message.answer("⚠️ Произошла ошибка. Выберите категорию магазинов заново.", 
                          reply_markup=buttons.go_back())
        await back_to_shop_categories(message, state)
        return
    
    # Получаем список магазинов для текущей категории
    shops = data.get(current_category, {})
    
    # Если список магазинов пуст, возвращаемся к выбору категорий
    if not shops:
        await message.answer(
            f"⚠️ В категории '{current_category}' нет магазинов. Возвращаемся к категориям.", 
            reply_markup=buttons.go_back()
        )
        await back_to_shop_categories(message, state)
        return
    
    # Находим выбранный магазин - убираем эмодзи
    shop_name = message.text
    if shop_name.startswith('📋 '):
        shop_name = shop_name.replace('📋 ', '')
    if shop_name.startswith('🏪 '):
        shop_name = shop_name.replace('🏪 ', '')
    
    # Ищем магазин с учетом эмодзи и без
    found_shop = None
    for shop_key in shops.keys():
        # Прямое сравнение
        if shop_key == shop_name:
            found_shop = shop_key
            break
        # Сравнение без эмодзи
        if shop_key.startswith('🏪 ') and shop_key[2:] == shop_name:
            found_shop = shop_key
            break
        if shop_key.startswith('📋 ') and shop_key[2:] == shop_name:
            found_shop = shop_key
            break
        # Сравнение названий без учета пробелов и регистра
        if shop_key.lower().strip() == shop_name.lower().strip():
            found_shop = shop_key
            break
        # Сравнение без эмодзи, пробелов и регистра
        if shop_key.startswith('🏪 ') and shop_key[2:].lower().strip() == shop_name.lower().strip():
            found_shop = shop_key
            break
        if shop_key.startswith('📋 ') and shop_key[2:].lower().strip() == shop_name.lower().strip():
            found_shop = shop_key
            break
    
    # Если магазин не найден
    if not found_shop:
        logger.warning(f"Магазин не найден: '{shop_name}'. Доступные магазины: {list(shops.keys())}")
        kb = buttons.generator_with_categories_button(shops.keys(), row_width=1, force_single_column=True, preserve_emoji=True)
        await message.answer(
            f"⚠️ Магазин '{shop_name}' не найден. Пожалуйста, выберите магазин из списка ниже.", 
            reply_markup=kb
        )
        return
    
    # Показываем сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю информацию о магазине...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    # Получаем информацию о выбранном магазине
    shop = shops[found_shop]
    
    # Создаем клавиатуру с кнопками навигации
    kb = buttons.navigation_keyboard(include_shop_list=True, include_shop_categories=True)
    
    # Форматируем основную информацию о магазине
    shop_info = f"<b>🏪 {shop['title']}</b>\n\n"
    
    # Добавляем описание, если оно есть
    if shop.get('description'):
        shop_info += f"{shop['description']}\n\n"
    
    # Добавляем адрес, если он есть
    if shop.get('address'):
        shop_info += f"📍 <b>Адрес:</b> {shop['address']}\n"
    
    # Добавляем телефон, если он есть
    if shop.get('phone'):
        shop_info += f"📞 <b>Телефон:</b> {shop['phone']}\n"
    
    # Добавляем время работы, если оно есть
    if shop.get('work_hours'):
        shop_info += f"🕒 <b>Время работы:</b> {shop['work_hours']}\n"
    
    # Добавляем сайт, если он есть
    if shop.get('website'):
        # Проверяем, есть ли протокол в URL
        website = shop['website']
        if website and not (website.startswith('http://') or website.startswith('https://')):
            website = f"https://{website}"
        shop_info += f"🌐 <b>Сайт:</b> <a href='{website}'>{shop['website']}</a>\n"
    
    # Добавляем ссылку на ВКонтакте, если она есть
    if shop.get('vk_url'):
        shop_info += f"\n🔗 <a href='{shop['vk_url']}'>Смотреть в магазине ВКонтакте</a>\n"
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    # Получаем URL изображения
    photo_url = shop.get('photo')
    
    # Если нет URL фото, отправляем только текст
    if not photo_url:
        logger.warning(f"Отсутствует URL фото для магазина: {shop['title']}")
        await message.answer(
            shop_info,
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return
    
    # Проверяем длину подписи к фото
    if len(shop_info) > 1024:
        logger.info(f"Слишком длинная подпись для магазина '{shop['title']}': {len(shop_info)} символов. Отправляем фото и текст отдельно.")
        
        try:
            # Отправляем фото без подписи
            await message.answer_photo(
                photo=photo_url,
                parse_mode=ParseMode.HTML
            )
            
            # Отправляем информацию отдельным сообщением
            await message.answer(
                shop_info,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
            logger.info(f"Успешно отправлено фото магазина '{shop['title']}' и отдельное текстовое описание")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка при отправке фото и информации магазина '{shop['title']}': {error_msg}")
            
            # Отправляем только информацию без фото при ошибке
            await message.answer(
                f"⚠️ Не удалось загрузить фото магазина.\n\n{shop_info}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        
        return
    
    # Если подпись не слишком длинная, отправляем фото с подписью
    try:
        await message.answer_photo(
            photo=photo_url,
            caption=shop_info,
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        logger.info(f"Успешно отправлено фото магазина: {shop['title']}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке фото магазина '{shop['title']}': {error_msg}")
        
        # Проверяем тип ошибки и предоставляем соответствующее сообщение
        if "Bad Request" in error_msg and "Wrong file identifier" in error_msg:
            logger.warning(f"Ошибка с URL изображения: {photo_url}")
            await message.answer(
                f"⚠️ Не удалось загрузить логотип магазина.\n\n{shop_info}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        elif "Bad Request" in error_msg and "PHOTO_INVALID_DIMENSIONS" in error_msg:
            logger.warning(f"Изображение имеет недопустимые размеры: {photo_url}")
            await message.answer(
                f"⚠️ Логотип магазина имеет недопустимый формат.\n\n{shop_info}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
        elif "Message caption is too long" in error_msg:
            # Дополнительная проверка на случай, если предыдущая проверка длины не сработала
            logger.warning(f"Слишком длинная подпись для фото (обработка исключения): {len(shop_info)}")
            try:
                await message.answer_photo(photo=photo_url)
                await message.answer(shop_info, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception as inner_e:
                logger.error(f"Повторная ошибка при отправке фото и текста магазина: {inner_e}")
                await message.answer(shop_info, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            # Общая обработка ошибок - отправляем только информацию
            await message.answer(
                f"⚠️ Произошла ошибка при загрузке фото магазина.\n\n{shop_info}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )

# Обработчик для кнопки "Предложить запись"
@dp.message_handler(lambda m: m.text == "📝 Предложить запись" or m.text == "Предложить запись")
async def offer_post_message(message: types.Message):
    await message.answer(
        "📝 <b>Предложить запись в сообществе</b>\n\n"
        "Эта функция находится в разработке и будет доступна в ближайшее время. "
        "Пока вы можете предложить запись напрямую в сообществе ВКонтакте.",
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.go_back()
    )

# Обработчик для кнопки "Стать магазином-партнером"
@dp.message_handler(lambda m: m.text == "🤝 Стать магазином-партнером" or m.text == "Стать магазином-партнером")
async def vk_partner_handler(message: types.Message):
    await message.answer(
        "🤝 <b>Стать магазином-партнером</b>\n\n"
        "Чтобы стать магазином-партнером, перейдите по ссылке ниже и оставьте заявку:\n"
        f"<a href='{config.VK_PARTNER_TOPIC_URL}'>Оставить заявку в ВКонтакте</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.go_back()
    )

# Обработчик для кнопки "Попасть в базу мастеров"
@dp.message_handler(lambda m: m.text == "📋 Попасть в базу мастеров" or m.text == "Попасть в базу мастеров")
async def vk_master_handler(message: types.Message):
    # Проверяем есть ли кэш категорий для информационного сообщения
    global non_empty_masters_cache
    
    # Формируем сообщение о категориях
    category_info = ""
    if non_empty_masters_cache and "all_categories" in non_empty_masters_cache:
        categories = list(non_empty_masters_cache["all_categories"].keys())
        if categories:
            category_info = "\n\n<b>Доступные категории мастеров:</b>\n"
            for cat in sorted(categories):
                # Убираем эмодзи из названия категории для вывода
                cleaned_cat = cat
                for emoji in ["🔨", "🚜", "🏗", "🔧", "📁"]:
                    if cleaned_cat.startswith(emoji + " "):
                        cleaned_cat = cleaned_cat[len(emoji) + 1:]
                        break
                category_info += f"• {cleaned_cat}\n"
    
    await message.answer(
        "📋 <b>Хочу в базу мастеров и спецтехники</b>\n\n"
        "Чтобы попасть в базу мастеров:\n\n"
        "1️⃣ Подготовьте фотографию с информацией о ваших услугах\n"
        "2️⃣ Укажите категорию из списка ниже\n"
        "3️⃣ Оставьте заявку по ссылке:" 
        f"{category_info}\n\n"
        f"<a href='{config.VK_MASTER_TOPIC_URL}'>Оставить заявку в ВКонтакте</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.go_back()
    )

# Обработчик для кнопки "Стена сообщества"
@dp.message_handler(lambda m: m.text == "📰 Стена сообщества" or m.text == "Стена сообщества")
async def community_wall_handler(message: types.Message):
    await message.answer(
        "📰 <b>Стена сообщества</b>\n\n"
        "Посетите нашу стену сообщества, чтобы быть в курсе всех новостей:\n"
        f"<a href='{config.TG_CHANNEL_URL}'>Стена сообщества в Telegram</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.go_back()
    )

@dp.message_handler(commands=['cache_status'])
async def cache_status_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    if str(message.from_user.id) not in config.ADMIN_IDS.split(','):
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
        return
    
    current_time = time.time()
    cache_info = []
    
    # Собираем информацию о кэше из декорированных функций
    for func_name, cache_entry in cache.items():
        entry_time = cache_entry["time"]
        age = current_time - entry_time
        age_hours = age // 3600
        age_minutes = (age % 3600) // 60
        age_seconds = age % 60
        expires_in = max(0, config.CACHE_TIME - age)
        expires_hours = expires_in // 3600
        expires_minutes = (expires_in % 3600) // 60
        expires_seconds = expires_in % 60
        
        cache_info.append({
            'key': func_name,
            'age': f"{int(age_hours)}ч {int(age_minutes)}м {int(age_seconds)}с",
            'expires': f"{int(expires_hours)}ч {int(expires_minutes)}м {int(expires_seconds)}с",
            'expired': age > config.CACHE_TIME
        })
    
    # Добавляем информацию о кэше категорий мастеров
    if non_empty_masters_cache:
        age = current_time - non_empty_masters_cache_time
        age_hours = age // 3600
        age_minutes = (age % 3600) // 60
        age_seconds = age % 60
        expires_in = max(0, config.CACHE_TIME - age)
        expires_hours = expires_in // 3600
        expires_minutes = (expires_in % 3600) // 60
        expires_seconds = expires_in % 60
        
        # Подсчитываем количество категорий с мастерами (непустых)
        non_empty_count = 0
        if "buttons" in non_empty_masters_cache:
            non_empty_count = len([cat for cat, count in non_empty_masters_cache["buttons"] if count > 0])
        
        cache_info.append({
            'key': 'masters_categories_cache',
            'age': f"{int(age_hours)}ч {int(age_minutes)}м {int(age_seconds)}с",
            'expires': f"{int(expires_hours)}ч {int(expires_minutes)}м {int(expires_seconds)}с",
            'expired': age > config.CACHE_TIME,
            'all_categories': len(non_empty_masters_cache.get('all_categories', {})),
            'non_empty_categories': non_empty_count,
            'buttons': len(non_empty_masters_cache.get('buttons', []))
        })
    
    # Добавляем информацию о кэше магазинов
    if shops_categories_cache:
        age = current_time - shops_categories_cache_time
        age_hours = age // 3600
        age_minutes = (age % 3600) // 60
        age_seconds = age % 60
        expires_in = max(0, config.CACHE_TIME - age)
        expires_hours = expires_in // 3600
        expires_minutes = (expires_in % 3600) // 60
        expires_seconds = expires_in % 60
        
        # Подсчитываем общее количество магазинов
        total_shops = len(shops_categories_cache.get("all_shops", {}))
        
        # Подсчитываем количество категорий (исключая all_shops)
        categories_count = len([k for k in shops_categories_cache.keys() if k != "all_shops"])
        
        cache_info.append({
            'key': 'shops_categories_cache',
            'age': f"{int(age_hours)}ч {int(age_minutes)}м {int(age_seconds)}с",
            'expires': f"{int(expires_hours)}ч {int(expires_minutes)}м {int(expires_seconds)}с",
            'expired': age > config.CACHE_TIME,
            'categories': categories_count,
            'shops': total_shops
        })
    
    if not cache_info:
        await message.answer("❌ Кэш пуст. Запустите /update_cache для заполнения кэша.")
        return
    
    # Формируем сообщение о состоянии кэша
    cache_status = "📊 <b>Состояние кэша:</b>\n\n"
    for item in cache_info:
        status = "🔴 истек" if item['expired'] else "🟢 активен"
        cache_status += f"<b>{item['key']}</b> - {status}\n"
        cache_status += f"⏱ Возраст: {item['age']}\n"
        if not item['expired']:
            cache_status += f"⏳ Истекает через: {item['expires']}\n"
        
        # Добавляем информацию о категориях мастеров
        if item['key'] == 'masters_categories_cache':
            cache_status += f"📁 Всего категорий мастеров: {item['all_categories']}\n"
            cache_status += f"📊 Категорий с мастерами: {item['non_empty_categories']}\n"
            cache_status += f"🔢 Кнопок: {item['buttons']}\n"
        
        # Добавляем информацию о магазинах
        if item['key'] == 'shops_categories_cache':
            cache_status += f"📁 Категорий магазинов: {item['categories']}\n"
            cache_status += f"🏪 Всего магазинов: {item['shops']}\n"
        
        cache_status += "\n"
    
    cache_status += f"\n📁 Всего записей в кэше: {len(cache_info)}\n"
    cache_status += f"⏰ Время жизни кэша: {config.CACHE_TIME // 3600} часов\n\n"
    cache_status += "Используйте /update_cache для принудительного обновления кэша."
    
    await message.answer(cache_status, parse_mode=ParseMode.HTML)

@dp.message_handler(commands=['update_cache'])
async def update_cache_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    if str(message.from_user.id) not in config.ADMIN_IDS.split(','):
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")
        return
        
    await message.answer("🔄 Начинаю обновление кэша...")
    
    try:
        # Обновляем данные о магазинах
        global shops_categories_cache, shops_categories_cache_time
        await vk_api_rate_limit()  # Ограничение API
        shops = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID, force_update=True)
        shops_categories_cache = shops
        shops_categories_cache_time = time.time()
        
        # Подсчитываем общее количество магазинов
        total_shops = len(shops.get("all_shops", {}))
        
        # Подсчитываем количество магазинов в каждой категории
        category_counts = {}
        for category, shops_in_category in shops.items():
            if category != "all_shops":
                category_counts[category] = len(shops_in_category)
        
        # Формируем подробный отчет
        shops_report = f"✅ Данные о магазинах обновлены.\n"
        shops_report += f"📊 Всего магазинов: {total_shops}\n"
        shops_report += f"📂 Категорий: {len(shops)-1}\n\n"
        
        # Добавляем информацию о категориях
        if category_counts:
            shops_report += "📋 Магазины по категориям:\n"
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                shops_report += f"- {category}: {count} магазинов\n"
        
        await message.answer(shops_report)
        
        # Обновляем данные об альбомах
        await vk_api_rate_limit()  # Ограничение API
        albums = await get_album_names_async(config.VK_TOKEN, config.VK_GROUP_ID, force_update=True)
        await message.answer(f"✅ Данные об альбомах обновлены. Альбомов: {len(albums)}")
        
        # Обновляем кэш категорий мастеров
        global non_empty_masters_cache, non_empty_masters_cache_time
        
        # Показываем сообщение о начале обновления кэша мастеров
        updating_masters_message = await message.answer("🔄 Обновляю кэш категорий мастеров...")
        
        # Создаем задачи для параллельной загрузки фотографий
        tasks = []
        for cat, album_id in albums.items():
            # Применяем ограничение частоты запросов перед каждым запросом
            await vk_api_rate_limit()
            tasks.append((cat, album_id, get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id, force_update=True)))
        
        # Обрабатываем результаты
        category_buttons = []
        all_categories = {}
        
        # Сохраняем все категории и их ID
        for cat, album_id in albums.items():
            all_categories[cat] = album_id
            
        # Получаем информацию о количестве фото в каждой категории
        for cat, album_id, task in tasks:
            photos = await task
            count = len(photos) if photos else 0
            category_buttons.append((cat, count))
        
        # Сохраняем результаты в кэш
        non_empty_masters_cache = {
            "buttons": category_buttons,
            "all_categories": all_categories
        }
        non_empty_masters_cache_time = time.time()
        
        # Удаляем сообщение о загрузке и показываем результат
        await updating_masters_message.delete()
        
        # Подсчитываем количество категорий с контентом
        non_empty_count = len([cat for cat, count in category_buttons if count > 0])
        
        await message.answer(f"✅ Кэш категорий мастеров обновлен.\n📊 Всего категорий: {len(all_categories)}\n📈 Категорий с мастерами: {non_empty_count}")
        
        # Обновляем данные о категориях маркета
        await vk_api_rate_limit()  # Ограничение API
        market_categories = await get_market_categories_async(config.VK_TOKEN, config.VK_GROUP_ID, force_update=True)
        await message.answer(f"✅ Данные о категориях маркета обновлены. Категорий: {len(market_categories)}")
        
        # Очищаем кэш старых записей
        clear_old_cache_entries()
        
        await message.answer("✅ Обновление кэша завершено!")
    except Exception as e:
        logger.error(f"Ошибка при обновлении кэша: {e}")
        await message.answer(f"⚠️ Произошла ошибка при обновлении кэша: {str(e)}")
        return

async def on_startup(dp):
    logger.info('🚀 Бот запущен')
    
    # Сначала очищаем все обновления, которые могли накопиться
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем таймер очистки кэша
    asyncio.create_task(periodic_cache_cleanup())
    
    # Предварительная загрузка критически важных данных
    await preload_critical_data()
    
    logger.info('✅ Бот готов к работе')

async def on_shutdown(dp):
    logger.info('👋 Бот остановлен')
    # Закрываем сессии бота
    session = await bot.get_session()
    if session and not session.closed:
        await session.close()
    # Освобождаем блокировку
    release_lock()

# Обработчик для возврата к категориям мастеров (с новым именем кнопки)
@dp.message_handler(lambda m: m.text == "◀️ НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ ◀️", state="*")
async def back_to_master_categories(message: types.Message, state: FSMContext):
    # Пишем в лог для отладки
    logger.info(f"Обработка возврата к категориям мастеров с новой кнопкой: '{message.text}'")
    
    try:
        # Полностью очищаем текущее состояние
        await state.finish()
        
        # Показываем пользователю сообщение о загрузке
        loading_message = await message.answer("🔄 <b>Загружаю категории мастеров...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
        
        global non_empty_masters_cache, non_empty_masters_cache_time
        current_time = time.time()
        
        # Проверяем, есть ли актуальный кэш непустых категорий
        if non_empty_masters_cache and current_time - non_empty_masters_cache_time < config.CACHE_TIME:
            logger.info("Используем кэш категорий мастеров при возврате")
            category_buttons = non_empty_masters_cache.get("buttons", [])
            all_categories = non_empty_masters_cache.get("all_categories", {})
        else:
            # Получаем данные о категориях только если кэш устарел
            logger.info("Обновляем кэш категорий мастеров при возврате")
            data = await get_album_names_async(config.VK_TOKEN, config.VK_GROUP_ID)
            
            if not data:
                await loading_message.delete()
                await message.answer("⚠️ К сожалению, категории мастеров не найдены",
                                    reply_markup=buttons.go_back())
                return
                
            # Создаем задачи для параллельной загрузки фотографий
            tasks = []
            for cat, album_id in data.items():
                # Применяем ограничение частоты запросов перед каждым запросом
                await vk_api_rate_limit()
                tasks.append((cat, album_id, get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id)))
            
            # Последовательно обрабатываем результаты с паузами между запросами
            category_buttons = []
            all_categories = {}
            
            # Сохраняем все категории и их ID
            for cat, album_id in data.items():
                all_categories[cat] = album_id
            
            # Получаем информацию о количестве фото в каждой категории
            for cat, album_id, task in tasks:
                photos = await task
                count = len(photos) if photos else 0
                category_buttons.append((cat, count))
            
            # Сохраняем результаты в кэш
            non_empty_masters_cache = {
                "buttons": category_buttons,
                "all_categories": all_categories
            }
            non_empty_masters_cache_time = current_time
            
            logger.info(f"Все категории мастеров при возврате: {list(all_categories.keys())}")
        
        # Удаляем сообщение о загрузке
        await loading_message.delete()
        
        if not category_buttons:
            await message.answer("⚠️ Нет ни одной категории мастеров.", reply_markup=buttons.go_back())
            return
        
        # Создаем клавиатуру заново
        kb = buttons.generator(category_buttons)
        await message.answer('👷‍♂️ <b>Открытая база мастеров и спецтехники</b>\n\nВыберите категорию из списка:', 
                            parse_mode=ParseMode.HTML,
                            reply_markup=kb)
        
        # Устанавливаем состояние и сохраняем данные
        await User.get_master.set()
        await state.set_data(all_categories)
        
        logger.info("Успешно выполнен возврат к категориям мастеров")
    
    except Exception as e:
        logger.error(f"Ошибка при возврате к категориям мастеров: {e}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз или вернитесь в главное меню.",
                          reply_markup=buttons.main)
        await state.finish()

# Обработчик нажатия кнопки "Далее" в карусели мастеров
@dp.callback_query_handler(lambda c: c.data == "master_next", state=User.view_masters_carousel)
async def master_next_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    current_index = data.get('current_photo_index', 0)
    photos = data.get('master_photos', [])
    
    # Увеличиваем индекс, если не последняя фотография
    if current_index < len(photos) - 1:
        current_index += 1
        await state.update_data(current_photo_index=current_index)
    
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Отправляем новую фотографию
    await send_master_photo(callback_query.message.chat.id, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик нажатия кнопки "Назад" в карусели мастеров
@dp.callback_query_handler(lambda c: c.data == "master_prev", state=User.view_masters_carousel)
async def master_prev_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    current_index = data.get('current_photo_index', 0)
    
    # Уменьшаем индекс, если не первая фотография
    if current_index > 0:
        current_index -= 1
        await state.update_data(current_photo_index=current_index)
    
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Отправляем новую фотографию
    await send_master_photo(callback_query.message.chat.id, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик нажатия на счетчик (ничего не делает)
@dp.callback_query_handler(lambda c: c.data == "master_count", state=User.view_masters_carousel)
async def master_count_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Текущая позиция в галерее")

# Обработчик нажатия кнопки "Вернуться к категориям" в карусели мастеров
@dp.callback_query_handler(lambda c: c.data == "master_back_to_categories", state=User.view_masters_carousel)
async def master_back_to_categories_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Вызываем функцию возврата к категориям мастеров
    await back_to_master_categories(callback_query.message, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик для кнопки "Вернуться к анкете мастера" в клавиатуре
@dp.message_handler(lambda m: m.text == "◀️ Вернуться к анкете мастера", state=User.view_master_works)
async def keyboard_back_to_master(message: types.Message, state: FSMContext):
    # Переходим обратно в состояние просмотра карусели мастеров
    await User.view_masters_carousel.set()
    
    # Отправляем фото мастера
    await send_master_photo(message.chat.id, state)

# Обработчик для кнопки "НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ" в клавиатуре при просмотре работ
@dp.message_handler(lambda m: m.text == "◀️ НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ ◀️", state=User.view_master_works)
async def keyboard_back_to_categories_from_works(message: types.Message, state: FSMContext):
    # Вызываем функцию возврата к категориям мастеров
    await back_to_master_categories(message, state)

if __name__ == '__main__':
    try:
        # Проверяем, не запущен ли уже бот
        if is_bot_already_running():
            logger.error('Бот уже запущен! Завершение работы.')
            sys.exit(1)
            
        # Запускаем бота с пропуском накопившихся обновлений
        logger.info('Запуск бота...')
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
    except aiogram.utils.exceptions.TerminatedByOtherGetUpdates:
        logger.error('Бот уже запущен! Завершение работы текущего экземпляра.')
    except (KeyboardInterrupt, SystemExit):
        logger.info('Бот остановлен пользователем!')
    except Exception as e:
        logger.error(f'Необработанная ошибка: {e}')
    finally:
        # Всегда пытаемся закрыть соединения и сессии
        logger.info('Закрытие соединений...')
        # Освобождаем блокировку при любом сценарии завершения
        release_lock()
        # Дополнительная очистка, если необходимо
        try:
            asyncio.get_event_loop().run_until_complete(on_shutdown(dp))
        except Exception as e:
            logger.error(f'Ошибка при закрытии соединений: {e}')
