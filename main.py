import logging
import aiogram
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from tg_bot.states import User
from tg_bot import buttons
import vk
from vk import get_topic_info_async, get_topic_comments_async
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
import re
import json
import pytz
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_polling
from message_utils import add_links_footer, send_message_with_links, edit_message_with_links, send_photo_with_links

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

# Добавляем кэш для хранения данных
cache = {}

# Добавляем кэш для непустых категорий мастеров
non_empty_masters_cache = {}
non_empty_masters_cache_time = 0

# Добавляем кэш для магазинов
shops_categories_cache = {}
shops_categories_cache_time = 0

# Интервал обновления кэша в секундах (2 часа)
CACHE_UPDATE_INTERVAL = 7200

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

# Периодическое обновление кэша каждые 2 часа
async def periodic_cache_update():
    """Периодически обновляет кэш магазинов и мастеров"""
    while True:
        try:
            logger.info("Запуск планового обновления кэша (каждые 2 часа)")
            
            # Обновляем данные о мастерах
            await preload_masters_data()
            logger.info("✅ Кэш мастеров успешно обновлен")
            
            # Обновляем данные о магазинах
            shops = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID, force_update=True)
            global shops_categories_cache, shops_categories_cache_time
            shops_categories_cache = shops
            shops_categories_cache_time = time.time()
            logger.info("✅ Кэш магазинов успешно обновлен")
            
            # Ждем следующего обновления
            await asyncio.sleep(CACHE_UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"Ошибка при плановом обновлении кэша: {e}")
            # В случае ошибки пробуем снова через 10 минут
            await asyncio.sleep(600)

# Функция для оптимизированной загрузки данных
async def preload_critical_data():
    """Предварительно загружает критически важные данные в кэш"""
    try:
        # Загружаем только основные данные, которые нужны для быстрого старта
        logger.info("Предварительная загрузка критических данных...")
        
        # Загрузка описания группы (легкий запрос)
        await vk_api_rate_limit()
        await get_group_description_async(config.VK_TOKEN, config.VK_GROUP_ID)
        
        # Предварительно загружаем всю базу мастеров синхронно, чтобы обеспечить мгновенный отклик
        await preload_masters_data()
        
        # Запускаем асинхронную задачу для загрузки остальных данных (магазины, маркет)
        asyncio.create_task(preload_remaining_data())
        
    except Exception as e:
        logger.error(f"Ошибка при предварительной загрузке критических данных: {e}")

# Функция для полной загрузки базы мастеров
async def preload_masters_data():
    """Предварительно загружает все данные о мастерах, включая категории, фотографии и работы"""
    global non_empty_masters_cache, non_empty_masters_cache_time
    try:
        logger.info("Начинаю загрузку полной базы мастеров...")
        start_time = time.time()
        
        # Загружаем альбомы мастеров
        await vk_api_rate_limit()
        albums = await get_album_names_async(config.VK_TOKEN, config.VK_GROUP_ID)
        logger.info(f"✅ Альбомы мастеров загружены: найдено {len(albums)} категорий")
        
        if not albums:
            logger.warning("⚠️ Не найдено категорий мастеров")
            return
        
        # Создаем задачи для параллельной загрузки фотографий мастеров
        tasks = []
        for cat, album_id in albums.items():
            await vk_api_rate_limit()
            tasks.append((cat, album_id, get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id)))
        
        # Обрабатываем результаты загрузки фотографий мастеров
        category_buttons = []
        all_categories = {}
        all_master_photos = {}
        master_works = {}
        
        # Сохраняем все категории и их ID
        for cat, album_id in albums.items():
            all_categories[cat] = album_id
        
        # Получаем информацию о количестве фото в каждой категории
        for cat, album_id, task in tasks:
            photos = await task
            count = len(photos) if photos else 0
            category_buttons.append((cat, count))
            
            # Сохраняем фотографии мастеров категории
            all_master_photos[cat] = photos
            
            # Для каждого мастера также загружаем его работы
            cat_work_tasks = []
            if photos:
                for photo in photos:
                    photo_id = photo.get('id')
                    if photo_id:
                        await vk_api_rate_limit()
                        cat_work_tasks.append((photo_id, get_photo_comments_async(config.VK_TOKEN, config.VK_GROUP_ID, photo_id)))
            
            # Получаем работы для мастеров категории
            cat_works = {}
            for photo_id, work_task in cat_work_tasks:
                works = await work_task
                if works and len(works) > 0:
                    cat_works[photo_id] = works
            
            # Сохраняем работы мастеров категории
            if cat_works:
                master_works[cat] = cat_works
                logger.info(f"✅ Категория '{cat}': загружено {len(photos)} мастеров и {len(cat_works)} мастеров с работами")
            else:
                logger.info(f"✅ Категория '{cat}': загружено {len(photos)} мастеров (без работ)")
        
        # Сохраняем результаты в кэш
        non_empty_masters_cache = {
            "buttons": category_buttons,
            "all_categories": all_categories,
            "master_photos": all_master_photos,
            "master_works": master_works
        }
        non_empty_masters_cache_time = time.time()
        
        execution_time = time.time() - start_time
        logger.info(f"✅ Предзагрузка базы мастеров завершена за {execution_time:.2f} сек")
        logger.info(f"✅ Всего загружено {len(all_categories)} категорий, {sum(len(photos) for photos in all_master_photos.values())} мастеров и {sum(len(cat_works) for cat, cat_works in master_works.items())} мастеров с работами")
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке базы мастеров: {e}")

async def preload_remaining_data():
    """Асинхронно загружает остальные данные после запуска бота (магазины, маркет)"""
    try:
        # Даем боту время на инициализацию и обработку первых запросов
        await asyncio.sleep(5)
        
        logger.info("Начинаю фоновую загрузку данных магазинов и маркета...")
        
        # Загружаем категории магазинов (ресурсоемкий запрос)
        await vk_api_rate_limit()
        global shops_categories_cache, shops_categories_cache_time
        shops = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID)
        shops_categories_cache = shops
        shops_categories_cache_time = time.time()
        logger.info("✅ Категории магазинов загружены в фоновом режиме")
        
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
    
    await send_message_with_links(
        message,
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
    
    await send_message_with_links(
        message,
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
                        
            # Если до сих пор не нашли совпадение, проверяем, не осталось ли в категории другого текста-суффикса
            if not found_category:
                # Дополнительная проверка для различных вариантов суффиксов
                for suffix in [" мастера", " и спецтехника", " услуги"]:
                    test_category = category
                    if test_category.endswith(suffix):
                        test_category = test_category[:-len(suffix)]
                    
                    if clean_key.lower() == test_category.lower():
                        found_category = key
                        logger.info(f"Найдено совпадение после удаления суффикса: '{key}'")
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
    
    # Пытаемся получить фотографии мастеров из кэша
    photos = []
    if non_empty_masters_cache and "master_photos" in non_empty_masters_cache and found_category in non_empty_masters_cache["master_photos"]:
        photos = non_empty_masters_cache["master_photos"][found_category]
        logger.info(f"Использую кэшированные фотографии мастеров для категории '{found_category}'")
    else:
        # Если в кэше нет, загружаем фотографии
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
async def send_master_photo(chat_id, state, edit_message_id=None):
    # Получаем данные из состояния
    data = await state.get_data()
    photos = data.get('master_photos', [])
    current_index = data.get('current_photo_index', 0)
    category = data.get('current_master_category', 'Мастера')
    
    if not photos or len(photos) == 0:
        text_no_photos = "⚠️ Фотографии не найдены."
        # Добавляем футер с ссылками
        text_no_photos_with_links = add_links_footer(text_no_photos)
        
        if edit_message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=edit_message_id,
                text=text_no_photos_with_links,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.navigation_keyboard(include_masters_categories=True)
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text_no_photos_with_links,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.navigation_keyboard(include_masters_categories=True)
            )
        return
    
    # Получаем текущую фотографию
    photo = photos[current_index]
    
    # Сохраняем информацию о текущем мастере в состоянии
    await state.update_data(master_info=photo)
    
    # Формируем подпись
    master_name = photo.get('text', '').strip()
    master_fio = master_name.split('\n')[0] if master_name and '\n' in master_name else master_name
    
    caption = photo.get('description', '') if photo.get('description') else f"Фото {current_index+1} из {len(photos)}"
    full_caption = f"<b>📸 {category} - {master_fio}</b>\n\n{caption}"
    
    # Добавляем ссылки с помощью нашей функции
    full_caption = add_links_footer(full_caption)
    
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
    
    # Добавляем кнопку возврата в главное меню
    kb.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    try:
        # Если нам передали ID сообщения для редактирования
        if edit_message_id:
            if len(full_caption) <= 1024:
                # Редактируем существующее сообщение
                await bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    media=types.InputMediaPhoto(
                        media=photo['url'],
                        caption=full_caption,
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=kb
                )
            else:
                # Если подпись слишком длинная, редактируем без подписи
                logger.info(f"Слишком длинная подпись для фото мастера: {len(full_caption)} символов. Отправляем только фото.")
                await bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    media=types.InputMediaPhoto(
                        media=photo['url']
                    ),
                    reply_markup=kb
                )
                # И отправляем текстовое сообщение отдельно
                await bot.send_message(
                    chat_id=chat_id,
                    text=full_caption,
                    parse_mode=ParseMode.HTML
                )
        else:
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
        logger.error(f"Ошибка при отправке/редактировании фото мастера: {error_msg}")
        if edit_message_id:
            # Пробуем отредактировать текст в случае ошибки
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    text=f"⚠️ Не удалось загрузить фото мастера.\n\n{full_caption}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
                )
            except Exception as inner_e:
                logger.error(f"Ошибка при отправке текста ошибки: {inner_e}")
                # Если не удалось отредактировать, отправляем новое сообщение
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Не удалось загрузить фото мастера.\n\n{full_caption}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Не удалось загрузить фото мастера.\n\n{full_caption}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )

# Функция для отправки фотографии работ мастера с кнопками навигации
async def send_master_work_photo(chat_id, state, edit_message_id=None):
    # Получаем данные из состояния
    data = await state.get_data()
    photos = data.get('master_work_photos', [])
    current_index = data.get('current_work_index', 0)
    category = data.get('current_master_category', 'Мастера')
    
    if not photos or len(photos) == 0:
        # Используем только InlineKeyboardMarkup вместо navigation_keyboard с категориями
        inline_kb = InlineKeyboardMarkup(row_width=1)
        inline_kb.add(InlineKeyboardButton("◀️ Вернуться к анкете мастера", callback_data="back_to_master"))
        
        text_no_photos = "⚠️ Фотографии работ не найдены."
        # Добавляем футер с ссылками
        text_no_photos_with_links = add_links_footer(text_no_photos)
        
        if edit_message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=edit_message_id,
                text=text_no_photos_with_links,
                parse_mode=ParseMode.HTML,
                reply_markup=inline_kb
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text_no_photos_with_links,
                parse_mode=ParseMode.HTML,
                reply_markup=inline_kb
            )
        return
    
    # Получаем текущую фотографию
    photo = photos[current_index]
    
    # Получаем информацию о мастере
    master_info = data.get('master_info', {})
    master_name = master_info.get('text', '').strip() if master_info else ''
    
    # Логируем информацию о мастере для отладки
    logger.info(f"Информация о мастере в send_master_work_photo: {master_name}")
    
    # Получаем первую строку из описания мастера (ФИО)
    master_fio = master_name.split('\n')[0] if master_name and '\n' in master_name else master_name
    
    # Если ФИО пустое, используем значение по умолчанию
    if not master_fio:
        master_fio = "Неизвестный мастер"
        logger.warning("ФИО мастера не найдено, используем значение по умолчанию")
    
    # Формируем подпись
    caption = photo.get('description', '') if photo.get('description') else f"Работа {current_index+1} из {len(photos)}"
    full_caption = f"<b>🛠️ Работы мастера {master_fio} ({category})</b>\n\n{caption}"
    
    # Добавляем ссылки с помощью нашей функции
    full_caption = add_links_footer(full_caption)
    
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
    
    # Добавляем только кнопку для возврата к анкете мастера
    kb.add(InlineKeyboardButton("◀️ Вернуться к анкете мастера", callback_data="back_to_master"))
    
    try:
        # Если нам передали ID сообщения для редактирования
        if edit_message_id:
            if len(full_caption) <= 1024:
                # Редактируем существующее сообщение
                await bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    media=types.InputMediaPhoto(
                        media=photo['url'],
                        caption=full_caption,
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=kb
                )
            else:
                # Если подпись слишком длинная, редактируем без подписи
                logger.info(f"Слишком длинная подпись для фото работы мастера: {len(full_caption)} символов. Отправляем только фото.")
                await bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    media=types.InputMediaPhoto(
                        media=photo['url']
                    ),
                    reply_markup=kb
                )
                # И отправляем текстовое сообщение отдельно
                # Примечание: текстовое сообщение будет дублироваться при каждом пролистывании,
                # но это неизбежно при редактировании медиа с длинным текстом
                await bot.send_message(
                    chat_id=chat_id,
                    text=full_caption,
                    parse_mode=ParseMode.HTML
                )
        else:
            # Отправляем фото с подписью и с кнопками
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
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при отправке/редактировании фото работы мастера: {error_msg}")
        if edit_message_id:
            # Пробуем отредактировать текст в случае ошибки
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    text=f"⚠️ Не удалось загрузить фото работы мастера.\n\n{full_caption}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
                )
            except Exception as inner_e:
                logger.error(f"Ошибка при отправке текста ошибки: {inner_e}")
                # Если не удалось отредактировать, отправляем новое сообщение
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Не удалось загрузить фото работы мастера.\n\n{full_caption}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
            )
        else:
            # Отправляем новое сообщение с текстом ошибки
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Не удалось загрузить фото работы мастера.\n\n{full_caption}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
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
        # Обновляем только индекс текущей работы, не трогая остальные данные
        await state.update_data(current_work_index=current_index)
    
    # Вместо удаления и отправки нового сообщения, редактируем текущее
    await send_master_work_photo(
        chat_id=callback_query.message.chat.id, 
        state=state, 
        edit_message_id=callback_query.message.message_id
    )
    
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
        # Обновляем только индекс текущей работы, не трогая остальные данные
        await state.update_data(current_work_index=current_index)
    
    # Вместо удаления и отправки нового сообщения, редактируем текущее
    await send_master_work_photo(
        chat_id=callback_query.message.chat.id, 
        state=state, 
        edit_message_id=callback_query.message.message_id
    )
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик нажатия на счетчик работ (ничего не делает)
@dp.callback_query_handler(lambda c: c.data == "work_count", state=User.view_master_works)
async def work_count_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Текущая позиция в галерее работ")

# Обработчик нажатия кнопки "Вернуться к анкете мастера" в карусели работ
@dp.callback_query_handler(lambda c: c.data == "back_to_master", state=User.view_master_works)
async def back_to_master_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем необходимые данные из текущего состояния
    data = await state.get_data()
    category = data.get('current_master_category', 'Мастера')
    master_info = data.get('master_info', {})
    
    # Удаляем предыдущее сообщение
    await callback_query.message.delete()
    
    # Получаем фотографии мастера по категории
    album_id = None
    master_photos = []
    
    # Сначала проверяем, есть ли фотографии в кэше
    global non_empty_masters_cache
    if non_empty_masters_cache and "master_photos" in non_empty_masters_cache and category in non_empty_masters_cache["master_photos"]:
        master_photos = non_empty_masters_cache["master_photos"][category]
        logger.info(f"Использую кэшированные фотографии мастеров для категории '{category}'")
    else:
        # Если нет, пробуем получить альбом через кэш категорий
        if non_empty_masters_cache and "all_categories" in non_empty_masters_cache:
            album_id = non_empty_masters_cache["all_categories"].get(category)
        
        if not album_id:
            # Если не получилось, просто возвращаемся к категориям
            await back_to_master_categories(callback_query.message, state)
            await callback_query.answer()
            return
        
        # Получаем фото мастера
        await vk_api_rate_limit()
        master_photos = await get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id)
        
        # Сохраняем в кэш
        if master_photos and len(master_photos) > 0:
            if not non_empty_masters_cache:
                non_empty_masters_cache = {}
            if "master_photos" not in non_empty_masters_cache:
                non_empty_masters_cache["master_photos"] = {}
            non_empty_masters_cache["master_photos"][category] = master_photos
            logger.info(f"Сохранил {len(master_photos)} фотографий мастеров в кэш для категории '{category}'")
    
    # Очищаем все данные состояния
    await state.finish()
    
    # Переходим обратно в состояние просмотра карусели мастеров
    await User.view_masters_carousel.set()
    
    # Находим индекс мастера по его информации
    current_photo_index = 0
    if master_info and master_photos:
        master_text = master_info.get('text', '')
        for i, photo in enumerate(master_photos):
            if photo.get('text') == master_text:
                current_photo_index = i
                break
    
    # Логируем информацию о мастере для отладки
    logger.info(f"Информация о мастере при возврате: {master_info.get('text', 'Нет информации')}")
    
    # Сохраняем данные для просмотра анкеты мастера, включая информацию о мастере
    await state.update_data(
        current_master_category=category,
        master_photos=master_photos,
        current_photo_index=current_photo_index,
        master_info=master_info
    )
    
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
            
            # Добавляем ссылки на все ресурсы
            caption = add_links_footer(caption)
            
            # Используем нашу функцию для отправки фото с ссылками
            await send_photo_with_links(message, photo=item['photo'], caption=caption, parse_mode=ParseMode.HTML)
            
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

    # После отправки всех товаров показываем сообщение о завершении просмотра
    await message.answer(
        f"🔍 <b>Просмотр товаров завершен.</b>\n\nВы можете выбрать другой магазин из списка или вернуться к категориям.", 
        parse_mode=ParseMode.HTML
    )

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
        # Если кэш отсутствует или устарел, запускаем полную предзагрузку
        logger.info("Кэш отсутствует или устарел, запускаем предзагрузку")
        await preload_masters_data()
        
        # Повторно проверяем наличие данных после загрузки
        if non_empty_masters_cache:
            category_buttons = non_empty_masters_cache.get("buttons", [])
            all_categories = non_empty_masters_cache.get("all_categories", {})
        else:
            await loading_message.delete()
            await message.answer("⚠️ Не удалось загрузить категории мастеров. Пожалуйста, попробуйте позже.",
                             reply_markup=buttons.go_back())
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
    
    # Проверяем, есть ли данные в кэше
    if not shops_categories_cache:
        # Если кэша нет, запускаем загрузку
        logger.info("Кэш магазинов пуст, загружаем данные")
        shop_categories = await get_shop_list_async(config.VK_TOKEN, config.VK_GROUP_ID)
        
        # Сохраняем результаты в кэш
        shops_categories_cache = shop_categories
        shops_categories_cache_time = time.time()
    else:
        logger.info("Используем существующий кэш категорий магазинов")
        shop_categories = shops_categories_cache
    
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
        # Отправляем сообщение с тем же списком магазинов
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
    
    # Используем клавиатуру с кнопками магазинов и кнопкой возврата к категориям
    kb = buttons.generator_with_categories_button(shops.keys(), row_width=1, force_single_column=True, preserve_emoji=True)
    
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
        
        # Добавляем ссылки на ресурсы
        shop_info = add_links_footer(shop_info)
        
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
            
            # Отправляем информацию отдельным сообщением с добавлением ссылок
            shop_info = add_links_footer(shop_info)
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
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю информацию из ВКонтакте...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    # Извлекаем topic_id из URL
    topic_url = config.VK_PARTNER_TOPIC_URL
    topic_id = None
    
    try:
        # URL имеет формат https://vk.com/topic-GROUP_ID_TOPIC_ID
        parts = topic_url.split("topic-")
        if len(parts) > 1:
            parts = parts[1].split("_")
            if len(parts) > 1:
                topic_id = parts[1]
    except Exception as e:
        logger.error(f"Ошибка при извлечении ID темы из URL {topic_url}: {e}")
    
    # Если не удалось извлечь topic_id, используем значение по умолчанию
    if not topic_id:
        # ID темы задан в URL после topic-GROUP_ID_TOPIC_ID
        # Например, из https://vk.com/topic-95855103_49010445 извлекаем 49010445
        topic_id = "49010445"  # Значение по умолчанию
    
    # Извлекаем group_id из конфигурации
    group_id = str(config.VK_GROUP_ID).replace("-", "")
    
    # Получаем информацию о теме
    topic_info = None
    
    try:
        topic_info = await get_topic_info_async(config.VK_TOKEN, group_id, topic_id)
    except Exception as e:
        logger.error(f"Ошибка при получении данных из темы VK: {e}")
    
    # Формируем текст сообщения
    text_message = "🤝 <b>Стать магазином-партнером</b>\n\n"
    
    # Добавляем информацию из темы, если она доступна
    if topic_info:
        # Используем заголовок темы, если он есть
        if topic_info["title"] and topic_info["title"] != "Без названия":
            text_message = f"🤝 <b>{topic_info['title']}</b>\n\n"
        
        # Если есть текст первого сообщения, добавляем его полностью
        if topic_info["text"]:
            topic_text = topic_info["text"]
            text_message += f"{topic_text}\n\n"
    else:
        text_message += "Чтобы стать магазином-партнером, перейдите по ссылке ниже и оставьте заявку:\n"
    
    # Добавляем ссылку на тему
    text_message += f"<a href='{config.VK_PARTNER_TOPIC_URL}'>Оставить заявку в ВКонтакте</a>"
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    # Отправляем сообщение с добавлением ссылок на ресурсы
    await send_message_with_links(
        message,
        text_message,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.go_back()
    )

# Обработчик для кнопки "Попасть в базу мастеров"
@dp.message_handler(lambda m: m.text == "📋 Попасть в базу мастеров" or m.text == "Попасть в базу мастеров")
async def vk_master_handler(message: types.Message):
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю информацию из ВКонтакте...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    # Проверяем есть ли кэш категорий для информационного сообщения
    global non_empty_masters_cache
    
    # Убираем вывод списка категорий, чтобы уместилась информация из ВК
    category_info = ""
    
    # Извлекаем topic_id из URL
    topic_url = config.VK_MASTER_TOPIC_URL
    topic_id = None
    
    try:
        # URL имеет формат https://vk.com/topic-GROUP_ID_TOPIC_ID
        parts = topic_url.split("topic-")
        if len(parts) > 1:
            parts = parts[1].split("_")
            if len(parts) > 1:
                topic_id = parts[1]
    except Exception as e:
        logger.error(f"Ошибка при извлечении ID темы из URL {topic_url}: {e}")
    
    # Если не удалось извлечь topic_id, используем значение из конфигурации
    if not topic_id:
        # ID темы задан в URL после topic-GROUP_ID_TOPIC_ID
        # Например, из https://vk.com/topic-95855103_49010449 извлекаем 49010449
        topic_id = "49010449"  # Значение по умолчанию
    
    # Извлекаем group_id из конфигурации
    group_id = str(config.VK_GROUP_ID).replace("-", "")
    
    # Получаем информацию о теме
    topic_info = None
    
    try:
        topic_info = await get_topic_info_async(config.VK_TOKEN, group_id, topic_id)
    except Exception as e:
        logger.error(f"Ошибка при получении данных из темы VK: {e}")
    
    # Формируем основной текст сообщения
    text_message = "📋 <b>Хочу в базу мастеров и спецтехники</b>\n\n"
    
    # Добавляем информацию из темы, если она доступна
    if topic_info:
        # Используем заголовок темы, если он есть
        if topic_info["title"] and topic_info["title"] != "Без названия":
            text_message = f"📋 <b>{topic_info['title']}</b>\n\n"
    
    text_message += (
        "Чтобы попасть в базу мастеров:\n\n"
        "1️⃣ Подготовьте фотографию с информацией о ваших услугах\n"
        "2️⃣ Укажите категорию услуг\n"
        "3️⃣ Оставьте заявку по ссылке"
    )
    
    # Добавляем категории, если они есть
    if category_info:
        text_message += category_info
    
    # Добавляем ссылку на тему
    text_message += f"\n\n<a href='{config.VK_MASTER_TOPIC_URL}'>Оставить заявку в ВКонтакте</a>"
    
    # Используем полное первое сообщение из темы, если оно доступно
    if topic_info and topic_info.get("text"):
        # Форматируем и добавляем полный текст первого сообщения темы
        topic_text = topic_info.get("text", "")
        
        # Добавляем текст с правильным форматированием для Telegram
        text_message += f"\n\n{topic_text}"
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    # Отправляем сообщение с добавлением ссылок на ресурсы
    await send_message_with_links(
        message,
        text_message,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.go_back()
    )

# Обработчик для кнопки "Стена сообщества"
@dp.message_handler(lambda m: m.text == "📰 Стена сообщества" or m.text == "Стена сообщества")
async def community_wall_handler(message: types.Message):
    text_message = (
        "📰 <b>Стена сообщества</b>\n\n"
        "Посетите нашу стену сообщества, чтобы быть в курсе всех новостей:\n"
        f"<a href='{config.TG_CHANNEL_URL}'>Стена сообщества в Telegram</a>"
    )
    
    await send_message_with_links(
        message,
        text_message,
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
    
    # Запускаем таймер периодического обновления кэша
    asyncio.create_task(periodic_cache_update())
    
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

# Обработчик для возврата к категориям мастеров (обработчик callback_query)
@dp.callback_query_handler(lambda c: c.data == "back_to_master_categories", state=[User.select_master, User.view_master])
async def back_to_master_categories_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Отвечаем на callback
    await bot.answer_callback_query(callback_query.id, "Возвращаемся к категориям мастеров...")
    
    global non_empty_masters_cache
    
    # Создаем клавиатуру с категориями
    kb = InlineKeyboardMarkup()
    
    # Добавляем категории мастеров в клавиатуру
    if non_empty_masters_cache and "buttons" in non_empty_masters_cache:
        for cat_name, count in non_empty_masters_cache["buttons"]:
            # Если в категории есть мастера, добавляем кнопку
            if count > 0:
                button_text = f"{cat_name} ({count})"
                kb.add(InlineKeyboardButton(button_text, callback_data=f"master_cat:{cat_name}"))
    
    # Добавляем кнопку для возврата в главное меню
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    # Отображаем категории
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text='👨‍🔧 <b>Наши мастера</b>\n\nВыберите категорию мастеров:',
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    
    await User.select_master_category.set()

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
    
    # Вместо удаления и отправки нового сообщения, редактируем текущее
    await send_master_photo(
        chat_id=callback_query.message.chat.id, 
        state=state, 
        edit_message_id=callback_query.message.message_id
    )
    
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
    
    # Вместо удаления и отправки нового сообщения, редактируем текущее
    await send_master_photo(
        chat_id=callback_query.message.chat.id, 
        state=state, 
        edit_message_id=callback_query.message.message_id
    )
    
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
    # Используем обработчик сообщений вместо callback
    await back_to_master_categories_handler(callback_query.message, state)
    
    # Отвечаем на callback, чтобы убрать часики на кнопке
    await callback_query.answer()

# Обработчик для кнопки "Вернуться к анкете мастера" в клавиатуре
@dp.message_handler(lambda m: m.text == "◀️ Вернуться к анкете мастера", state=User.view_master_works)
async def keyboard_back_to_master(message: types.Message, state: FSMContext):
    # Получаем необходимые данные из текущего состояния
    data = await state.get_data()
    category = data.get('current_master_category', 'Мастера')
    master_info = data.get('master_info', {})
    
    # Логируем информацию о мастере для отладки
    logger.info(f"Информация о мастере при возврате через клавиатуру: {master_info.get('text', 'Нет информации')}")
    
    # Получаем фотографии мастера по категории
    album_id = None
    master_photos = []
    
    # Сначала проверяем, есть ли фотографии в кэше
    global non_empty_masters_cache
    if non_empty_masters_cache and "master_photos" in non_empty_masters_cache and category in non_empty_masters_cache["master_photos"]:
        master_photos = non_empty_masters_cache["master_photos"][category]
        logger.info(f"Использую кэшированные фотографии мастеров для категории '{category}'")
    else:
        # Если нет, пробуем получить альбом через кэш категорий
        if non_empty_masters_cache and "all_categories" in non_empty_masters_cache:
            album_id = non_empty_masters_cache["all_categories"].get(category)
        
        if not album_id:
            # Если не получилось, просто возвращаемся к категориям
            await back_to_master_categories_handler(message, state)
            return
        
        # Получаем фото мастера
        await vk_api_rate_limit()
        master_photos = await get_album_photos_async(config.VK_TOKEN, config.VK_GROUP_ID, album_id)
        
        # Сохраняем в кэш
        if master_photos and len(master_photos) > 0:
            if not non_empty_masters_cache:
                non_empty_masters_cache = {}
            if "master_photos" not in non_empty_masters_cache:
                non_empty_masters_cache["master_photos"] = {}
            non_empty_masters_cache["master_photos"][category] = master_photos
            logger.info(f"Сохранил {len(master_photos)} фотографий мастеров в кэш для категории '{category}'")
    
    # Очищаем все данные состояния
    await state.finish()
    
    # Переходим обратно в состояние просмотра карусели мастеров
    await User.view_masters_carousel.set()
    
    # Находим индекс мастера по его информации
    current_photo_index = 0
    if master_info and master_photos:
        master_text = master_info.get('text', '')
        for i, photo in enumerate(master_photos):
            if photo.get('text') == master_text:
                current_photo_index = i
                logger.info(f"Найден индекс мастера: {i}")
                break
    
    # Сохраняем данные для просмотра анкеты мастера, включая информацию о мастере
    await state.update_data(
        current_master_category=category,
        master_photos=master_photos,
        current_photo_index=current_photo_index,
        master_info=master_info
    )
    
    # Отправляем фото мастера
    await send_master_photo(message.chat.id, state)

# Обработчик для кнопки "НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ" в клавиатуре при просмотре работ
@dp.message_handler(lambda m: m.text == "◀️ НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ ◀️", state=User.view_master_works)
async def keyboard_back_to_categories_from_works(message: types.Message, state: FSMContext):
    # Вызываем функцию возврата к категориям мастеров
    await back_to_master_categories_handler(message, state)

# Обработчик для просмотра списка мастеров
@dp.message_handler(lambda m: m.text == "👨‍🔧 Каталог мастеров")
async def masters_handler(message: types.Message, state: FSMContext):
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю категории мастеров...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    global non_empty_masters_cache, non_empty_masters_cache_time
    
    # Проверяем, есть ли данные в кэше
    if not non_empty_masters_cache or not non_empty_masters_cache.get("buttons"):
        # Если кэша нет, запускаем загрузку
        logger.info("Кэш мастеров пуст, загружаем данные")
        await preload_masters_data()
    else:
        logger.info("Используем существующий кэш мастеров")
    
    # Удаляем сообщение о загрузке
    await loading_message.delete()
    
    # Создаем клавиатуру с категориями
    kb = InlineKeyboardMarkup()
    
    # Добавляем категории мастеров в клавиатуру
    if non_empty_masters_cache and "buttons" in non_empty_masters_cache:
        for cat_name, count in non_empty_masters_cache["buttons"]:
            # Если в категории есть мастера, добавляем кнопку
            if count > 0:
                button_text = f"{cat_name} ({count})"
                kb.add(InlineKeyboardButton(button_text, callback_data=f"master_cat:{cat_name}"))
    
    # Добавляем кнопку для возврата в главное меню
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    await message.answer('👨‍🔧 <b>Наши мастера</b>\n\nВыберите категорию мастеров:', 
                       parse_mode=ParseMode.HTML,
                       reply_markup=kb)
    
    # Сохраняем категории мастеров в состоянии пользователя
    if non_empty_masters_cache and "all_categories" in non_empty_masters_cache:
        await state.update_data(master_categories=non_empty_masters_cache["all_categories"])
    
    await User.select_master_category.set()

# Обработчик для просмотра мастеров по категории
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('master_cat:'), state=User.select_master_category)
async def process_master_category(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем название выбранной категории
    category_name = callback_query.data.split(':')[1]
    
    # Показываем статус загрузки
    await bot.answer_callback_query(callback_query.id, "Загружаю мастеров...")
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id, 
        message_id=callback_query.message.message_id,
        text=f"🔄 <b>Загружаю мастеров категории:</b> {category_name}...\n\nПожалуйста, подождите.",
        parse_mode=ParseMode.HTML
    )
    
    global non_empty_masters_cache
    
    # Получаем информацию о мастерах из кэша
    master_photos = non_empty_masters_cache.get("master_photos", {}).get(category_name, [])
    
    if not master_photos:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id, 
            message_id=callback_query.message.message_id,
            text=f"❌ <b>Мастера не найдены в категории:</b> {category_name}\n\nПожалуйста, выберите другую категорию или вернитесь в главное меню.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_masters_keyboard()
        )
        return
    
    # Сохраняем выбранную категорию и мастеров в состоянии
    await state.update_data(current_category=category_name, masters=master_photos)
    
    # Создаем клавиатуру с мастерами
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем мастеров
    for i, photo in enumerate(master_photos):
        master_name = photo.get('text', f'Мастер #{i+1}')
        # Ограничиваем имя мастера 30 символами
        if len(master_name) > 30:
            master_name = master_name[:27] + "..."
        kb.add(InlineKeyboardButton(master_name, callback_data=f"master:{i}"))
    
    # Добавляем кнопку назад
    kb.add(InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_master_categories"))
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    # Отображаем список мастеров
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id, 
        message_id=callback_query.message.message_id,
        text=f"👨‍🔧 <b>Мастера категории:</b> {category_name}\n\nВыберите мастера для просмотра информации:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    
    await User.select_master.set()

# Обработчик для просмотра информации о мастере
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('master:'), state=User.select_master)
async def process_master_selection(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем индекс выбранного мастера
    master_index = int(callback_query.data.split(':')[1])
    
    # Показываем статус загрузки
    await bot.answer_callback_query(callback_query.id, "Загружаю информацию о мастере...")
    
    # Получаем данные из состояния
    data = await state.get_data()
    category_name = data.get('current_category')
    masters = data.get('masters', [])
    
    if not masters or master_index >= len(masters):
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ <b>Информация о мастере не найдена</b>\n\nПожалуйста, вернитесь к списку мастеров.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_masters_keyboard()
        )
        return
    
    # Получаем информацию о выбранном мастере
    master = masters[master_index]
    master_name = master.get('text', f'Мастер #{master_index+1}')
    master_photo_url = master.get('url')
    master_id = master.get('id')
    
    # Получаем работы мастера из кэша
    global non_empty_masters_cache
    master_works = []
    if "master_works" in non_empty_masters_cache and category_name in non_empty_masters_cache["master_works"]:
        category_works = non_empty_masters_cache["master_works"][category_name]
        if master_id in category_works:
            master_works = category_works[master_id]
    
    # Сохраняем информацию о мастере и его работах в состоянии
    await state.update_data(master_info=master, master_works=master_works)
    
    # Формируем текст сообщения
    message_text = f"👨‍🔧 <b>{master_name}</b>\n\n"
    
    # Добавляем информацию о работах мастера
    if master_works:
        message_text += "<b>Работы мастера:</b>\n"
        for i, work in enumerate(master_works[:5]):  # Показываем до 5 работ
            work_text = work.get('text', '').strip()
            if work_text:
                message_text += f"\n{i+1}. {work_text}"
        
        # Если работ больше 5, добавляем сообщение
        if len(master_works) > 5:
            message_text += f"\n\n<i>И ещё {len(master_works) - 5} работ</i>"
    else:
        message_text += "<i>У этого мастера пока нет добавленных работ в нашей базе.</i>"
    
    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup()
    
    # Добавляем кнопку для просмотра всех работ, если они есть
    if master_works:
        kb.add(InlineKeyboardButton("📷 Просмотреть все работы мастера", callback_data=f"master_works:{master_index}"))
    
    # Добавляем кнопки для навигации
    kb.add(InlineKeyboardButton("📞 Связаться с мастером", callback_data=f"contact_master:{master_index}"))
    kb.add(InlineKeyboardButton("◀️ Вернуться к списку мастеров", callback_data="back_to_masters"))
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    # Отображаем информацию о мастере
    try:
        if master_photo_url:
            # Если есть фото мастера, отправляем его с подписью
            await bot.send_photo(
                chat_id=callback_query.message.chat.id,
                photo=master_photo_url,
                caption=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
    # Удаляем предыдущее сообщение
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id
            )
        else:
            # Если фото нет, просто обновляем текст сообщения
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке информации о мастере: {e}")
        # В случае ошибки просто обновляем текст сообщения
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"{message_text}\n\n⚠️ <i>Не удалось загрузить фото мастера</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
    
    await User.view_master.set()

# Обработчик для просмотра всех работ мастера
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('master_works:'), state=User.view_master)
async def process_master_works(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    master_works = data.get('master_works', [])
    master_info = data.get('master_info', {})
    
    # Получаем имя мастера
    master_name = master_info.get('text', 'Мастер')
    
    # Получаем первую строку из описания мастера (ФИО)
    master_fio = master_name.split('\n')[0] if master_name and '\n' in master_name else master_name
    
    if not master_works:
        await bot.answer_callback_query(callback_query.id, "У этого мастера нет загруженных работ")
        return
    
    # Показываем статус загрузки
    await bot.answer_callback_query(callback_query.id, "Загружаю работы мастера...")
    
    # Формируем сообщение с работами мастера
    message_text = f"📷 <b>Все работы мастера {master_fio}:</b>\n\n"
    
    # Добавляем информацию о каждой работе
    for i, work in enumerate(master_works):
        work_text = work.get('text', '').strip()
        if work_text:
            message_text += f"{i+1}. {work_text}\n\n"
    
    # Добавляем кнопку возврата
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Вернуться к информации о мастере", callback_data=f"back_to_master_info"))
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    # Отправляем сообщение с работами
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=message_text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

# Обработчик для возврата к информации о мастере
@dp.callback_query_handler(lambda c: c.data == "back_to_master_info", state=User.view_master)
async def back_to_master_info(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    master_info = data.get('master_info', {})
    master_works = data.get('master_works', [])
    
    # Получаем информацию о мастере
    master_name = master_info.get('text', 'Мастер')
    master_photo_url = master_info.get('url')
    
    # Формируем текст сообщения
    message_text = f"👨‍🔧 <b>{master_name}</b>\n\n"
    
    # Добавляем информацию о работах мастера
    if master_works:
        message_text += "<b>Работы мастера:</b>\n"
        for i, work in enumerate(master_works[:5]):  # Показываем до 5 работ
            work_text = work.get('text', '').strip()
            if work_text:
                message_text += f"\n{i+1}. {work_text}"
        
        # Если работ больше 5, добавляем сообщение
        if len(master_works) > 5:
            message_text += f"\n\n<i>И ещё {len(master_works) - 5} работ</i>"
    else:
        message_text += "<i>У этого мастера пока нет добавленных работ в нашей базе.</i>"
    
    # Создаем клавиатуру с кнопками
    kb = InlineKeyboardMarkup()
    
    # Добавляем кнопку для просмотра всех работ, если они есть
    if master_works:
        kb.add(InlineKeyboardButton("📷 Просмотреть все работы мастера", callback_data="master_works:0"))  # Индекс здесь не важен
    
    # Добавляем кнопки для навигации
    kb.add(InlineKeyboardButton("📞 Связаться с мастером", callback_data="contact_master:0"))  # Индекс здесь не важен
    kb.add(InlineKeyboardButton("◀️ Вернуться к списку мастеров", callback_data="back_to_masters"))
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    # Отвечаем на callback
    await bot.answer_callback_query(callback_query.id)
    
    # Отображаем информацию о мастере
    if master_photo_url:
        try:
            # Отправляем фото мастера с новой информацией
            await bot.send_photo(
                chat_id=callback_query.message.chat.id,
                photo=master_photo_url,
                caption=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
            # Удаляем предыдущее сообщение
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id
            )
        except Exception as e:
            # В случае ошибки просто обновляем текст
            logger.error(f"Ошибка при отправке фото мастера: {e}")
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=f"{message_text}\n\n⚠️ <i>Не удалось загрузить фото мастера</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb
            )
    else:
        # Если нет фото, просто обновляем сообщение
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

# Обработчик для возврата к списку мастеров в категории
@dp.callback_query_handler(lambda c: c.data == "back_to_masters", state=User.view_master)
async def back_to_masters_list(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    category_name = data.get('current_category')
    masters = data.get('masters', [])
    
    # Отвечаем на callback
    await bot.answer_callback_query(callback_query.id, "Возвращаемся к списку мастеров...")
    
    if not masters:
        # Если нет данных о мастерах, показываем сообщение об ошибке
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="❌ <b>Не удалось загрузить список мастеров</b>\n\nПожалуйста, вернитесь к категориям.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_masters_keyboard()
        )
        return
    
    # Создаем клавиатуру с мастерами
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем мастеров
    for i, photo in enumerate(masters):
        master_name = photo.get('text', f'Мастер #{i+1}')
        # Ограничиваем имя мастера 30 символами
        if len(master_name) > 30:
            master_name = master_name[:27] + "..."
        kb.add(InlineKeyboardButton(master_name, callback_data=f"master:{i}"))
    
    # Добавляем кнопку назад
    kb.add(InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_master_categories"))
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    
    # Отображаем список мастеров
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"👨‍🔧 <b>Мастера категории:</b> {category_name}\n\nВыберите мастера для просмотра информации:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    
    await User.select_master.set()

# Вспомогательная функция для создания клавиатуры возврата к мастерам
def get_back_to_masters_keyboard():
    """Создает клавиатуру с кнопками возврата к категориям мастеров"""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Вернуться к категориям мастеров", callback_data="back_to_master_categories"))
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"))
    return kb

# Обработчик для возврата к категориям мастеров (обработчик сообщений)
@dp.message_handler(lambda m: m.text == "◀️ НАЗАД К КАТЕГОРИЯМ МАСТЕРОВ ◀️", state="*")
async def back_to_master_categories_handler(message: types.Message, state: FSMContext):
    # Пишем в лог для отладки
    logger.info(f"Обработка возврата к категориям мастеров с кнопкой: '{message.text}'")
    
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
            # Если кэш отсутствует или устарел, запускаем полную предзагрузку
            logger.info("Кэш отсутствует или устарел, запускаем предзагрузку")
            await preload_masters_data()
            
            # Повторно проверяем наличие данных после загрузки
            if non_empty_masters_cache:
                category_buttons = non_empty_masters_cache.get("buttons", [])
                all_categories = non_empty_masters_cache.get("all_categories", {})
            else:
                await loading_message.delete()
                await message.answer("⚠️ Не удалось загрузить категории мастеров. Пожалуйста, попробуйте позже.",
                              reply_markup=buttons.go_back())
                return
        
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

# Обработчик для кнопки "Посмотреть работы мастера"
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
    
    # Получаем текущую фотографию мастера
    photos = data.get('master_photos', [])
    current_index = data.get('current_photo_index', 0)
    
    # Проверяем, что у нас есть фотографии мастеров и индекс в пределах списка
    if photos and 0 <= current_index < len(photos):
        # Сохраняем информацию о текущем мастере
        master_info = photos[current_index]
        logger.info(f"Сохраняем информацию о мастере: {master_info.get('text', 'Неизвестный мастер')}")
    
    try:
        # Сначала проверяем, есть ли работы мастера в кэше
        work_photos = []
        global non_empty_masters_cache
        if (non_empty_masters_cache and 
            "master_works" in non_empty_masters_cache and 
            category in non_empty_masters_cache["master_works"] and 
            photo_id in non_empty_masters_cache["master_works"][category]):
            # Берем работы из кэша
            work_photos = non_empty_masters_cache["master_works"][category][photo_id]
            logger.info(f"Использую кэшированные работы мастера для фото ID: {photo_id}")
        else:
            # Если в кэше нет, получаем комментарии к фотографии (работы мастера)
            logger.info(f"Загружаем работы мастера для фото ID: {photo_id}")
            work_photos = await get_photo_comments_async(config.VK_TOKEN, config.VK_GROUP_ID, photo_id)
            
            # Сохраняем в кэш для будущего использования
            if work_photos and len(work_photos) > 0:
                if not non_empty_masters_cache:
                    non_empty_masters_cache = {}
                if "master_works" not in non_empty_masters_cache:
                    non_empty_masters_cache["master_works"] = {}
                if category not in non_empty_masters_cache["master_works"]:
                    non_empty_masters_cache["master_works"][category] = {}
                non_empty_masters_cache["master_works"][category][photo_id] = work_photos
                logger.info(f"Сохранил {len(work_photos)} работ мастера в кэш для фото ID: {photo_id}")
        
        # Удаляем сообщение о загрузке
        await loading_message.delete()
        
        # Проверяем, есть ли фотографии работ
        if not work_photos or len(work_photos) == 0:
            await callback_query.message.answer(
                "⚠️ У этого мастера пока нет фотографий работ.",
                reply_markup=None
            )
            return
        
        # Логируем количество найденных работ
        logger.info(f"Найдено {len(work_photos)} работ мастера для фото ID: {photo_id}")
        
        # Удаляем предыдущее сообщение с фото мастера
        await callback_query.message.delete()
        
        # Полностью очищаем предыдущее состояние
        await state.finish()
        
        # Получаем информацию о мастере
        master_info = None
        if photos and 0 <= current_index < len(photos):
            master_info = photos[current_index]
            logger.info(f"Используем информацию о мастере из фотографии: {master_info.get('text', 'Неизвестный мастер')}")
        else:
            master_info = data.get('master_info', {})
            logger.info(f"Используем информацию о мастере из состояния: {master_info.get('text', 'Неизвестный мастер')}")
        
        # Переходим в состояние просмотра работ мастера
        await User.view_master_works.set()
        
        # Сохраняем необходимые данные, включая информацию о мастере
        await state.update_data(
            master_work_photos=work_photos,
            current_work_index=0,
            current_master_category=category,
            master_info=master_info
        )
        
        # Отправляем первую фотографию работы
        await send_master_work_photo(callback_query.message.chat.id, state)
    except Exception as e:
        logger.error(f"Ошибка при получении работ мастера: {e}")
        await loading_message.delete()
        await callback_query.message.answer(
            f"⚠️ Произошла ошибка при загрузке работ мастера: {str(e)}",
            reply_markup=None
        ) 
# Обработчик для кнопки "Главное меню" в inline-клавиатуре
@dp.callback_query_handler(lambda c: c.data == "main_menu", state="*")
async def main_menu_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Отвечаем на callback-запрос
    await callback_query.answer()
    
    # Сбрасываем состояние
    await state.finish()
    
    # Отправляем главное меню
    await callback_query.message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите раздел из меню ниже:", 
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.main
    )



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
