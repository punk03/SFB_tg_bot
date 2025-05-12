import vk_api
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import re
import random
from functools import lru_cache
from urllib3.util import Retry
from vk_api.exceptions import ApiError, Captcha
import requests
from requests.adapters import HTTPAdapter

# Настройка логгера
logger = logging.getLogger(__name__)

# Исполнитель для асинхронных запросов
executor = ThreadPoolExecutor(max_workers=4)

async def run_in_executor(func, *args, **kwargs):
    """Выполняет функцию в отдельном потоке для неблокирующего IO"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

# Оптимизированные настройки сессии для HTTP запросов
def create_optimized_session():
    """Создает оптимизированную сессию для HTTP-запросов с настройками повторных попыток"""
    session = requests.Session()
    
    # Настройка стратегии повторных попыток для HTTP-запросов
    retry_strategy = Retry(
        total=3,  # Общее количество повторных попыток
        backoff_factor=0.5,  # Фактор задержки между попытками (0.5 * (2 ^ (retry - 1)))
        status_forcelist=[429, 500, 502, 503, 504],  # Коды состояния HTTP для повторной попытки
        allowed_methods=["GET", "POST"]  # Методы, для которых разрешены повторы
    )
    
    # Применяем стратегию ко всем адаптерам
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# Кэш для сессий VK API
vk_sessions = {}

@lru_cache(maxsize=32)
def get_vk_session(token):
    """Получает сессию VK API с использованием токена (с кэшированием)"""
    if token in vk_sessions:
        return vk_sessions[token]
    
    try:
        # Создаем оптимизированную сессию
        session = create_optimized_session()
        vk_session = vk_api.VkApi(token=token, session=session)
        
        # Проверяем работоспособность токена
        vk = vk_session.get_api()
        # Используем более надежный метод проверки работоспособности токена
        vk.users.get(user_ids=[1])
        
        # Кэшируем сессию
        vk_sessions[token] = vk_session
        return vk_session
    except Exception as e:
        logger.error(f"Ошибка при создании сессии VK API: {e}")
        return None

def api_call_with_retry(method, *args, max_retries=3, **kwargs):
    """Выполняет запрос к API с механизмом повторных попыток"""
    retries = 0
    while retries < max_retries:
        try:
            return method(*args, **kwargs)
        except ApiError as e:
            error_code = getattr(e, 'code', None)
            # Обрабатываем ошибки API
            if error_code == 6:  # Too many requests per second
                sleep_time = 0.5 * (2 ** retries)
                logger.warning(f"Слишком много запросов к API, ожидание {sleep_time} сек...")
                time.sleep(sleep_time)
                retries += 1
                continue
            elif error_code == 14:  # Captcha needed
                logger.error("Требуется ввод капчи. Необходимо обновить токен.")
                return None
            else:
                logger.error(f"Ошибка API VK: {e}")
                return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при запросе к API: {e}")
            sleep_time = 1 * (2 ** retries)
            time.sleep(sleep_time)
            retries += 1
            continue
    
    logger.error(f"Превышено максимальное количество попыток выполнения запроса: {max_retries}")
    return None

def get_group_description(token, group_id):
    """Получает описание группы ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return None
        
        vk = vk_session.get_api()
        
        # Получение описания группы
        group_info = api_call_with_retry(
            vk.groups.getById,
            group_id=group_id, 
            fields=["description"]
        )
        
        if not group_info:
            return None
        
        # Извлекаем и возвращаем описание группы
        description = group_info[0].get("description", "")
        return description
    except Exception as e:
        logger.error(f"Ошибка при получении описания группы: {e}")
        return None

def get_album_names(token, group_id):
    """Получает названия альбомов группы ВКонтакте"""
    try:
        # Авторизация через токен
        vk_session = get_vk_session(token)
        if not vk_session:
            return {}
            
        vk = vk_session.get_api()

        # Запрос списка альбомов группы
        response = vk.photos.getAlbums(
            owner_id=-group_id  # Знак '-' перед group_id указывает, что это группа
        )

        # Извлечение названий альбомов
        data = {}
        for i in response.get("items", []):
            album_title = i.get("title", "Неизвестный альбом")
            album_id = i.get("id")
            
            # Больше не добавляем эмодзи к названиям категорий
            data[album_title] = album_id
            
        logger.info(f"Получено {len(data)} альбомов из группы {group_id}")
        return data

    except Exception as e:
        logger.error(f"Ошибка при получении альбомов: {e}")
        return {}


def get_album_photos(token, owner_id, album_id):
    """Получает фотографии из альбома группы ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return []
            
        vk = vk_session.get_api()

        # Проверяем, что album_id имеет корректный формат (число)
        try:
            album_id = int(album_id)
        except (ValueError, TypeError):
            logger.error(f"Неверный формат album_id: {album_id}")
            return []

        # Получаем все фотографии из альбома
        try:
            photos = vk.photos.get(owner_id=-owner_id, album_id=album_id, extended=1)
            result = []

            for photo in photos.get("items", []):
                # Находим максимальный размер фото
                try:
                    max_size = max(photo.get("sizes", []), key=lambda size: size.get("width", 0) * size.get("height", 0))
                    photo_url = max_size.get("url")
                    
                    # Создаем структуру с информацией о фото
                    photo_info = {
                        "url": photo_url,
                        "description": photo.get("text", ""),
                        "likes": photo.get("likes", {}).get("count", 0),
                        "date": photo.get("date")
                    }
                    
                    result.append(photo_info)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Ошибка при обработке фото из альбома {album_id}: {e}")
                    continue

            logger.info(f"Получено {len(result)} фотографий из альбома {album_id}")
            return result
            
        except vk_api.exceptions.ApiError as e:
            error_msg = str(e)
            if "album_id is invalid" in error_msg:
                logger.error(f"Неверный album_id: {album_id}. Возможно, альбом был удален")
            else:
                logger.error(f"API ошибка при получении фотографий: {error_msg}")
            return []

    except Exception as e:
        logger.error(f"Ошибка при получении фотографий из альбома {album_id}: {e}")
        return []


def get_market_items(token, owner_id):
    """Получает категории товаров из маркета группы ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return {}
            
        vk = vk_session.get_api()

        # Получаем список категорий товаров
        albums = vk.market.getAlbums(owner_id=-owner_id, count=100)
        result = {}

        for item in albums.get("items", []):
            album_title = item.get("title", "Неизвестная категория")
            album_id = item.get("id")
            
            # Добавляем эмодзи к названиям категорий для улучшения UX
            if "строй" in album_title.lower() or "материал" in album_title.lower():
                album_title = f"🧱 {album_title}"
            elif "инстр" in album_title.lower():
                album_title = f"🔨 {album_title}"
            elif "мебел" in album_title.lower():
                album_title = f"🪑 {album_title}"
            elif "сад" in album_title.lower() or "огород" in album_title.lower():
                album_title = f"🌱 {album_title}"
            else:
                album_title = f"🛒 {album_title}"
                
            result[album_title] = album_id

        logger.info(f"Получено {len(result)} категорий товаров из группы {owner_id}")
        return result

    except Exception as e:
        logger.error(f"Ошибка при получении категорий товаров: {e}")
        return {}

def get_shop_list(token, owner_id):
    """Получает список магазинов-партнеров из группы ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return {}
            
        vk = vk_session.get_api()

        # Получаем категории товаров
        shop_categories = {}
        
        try:
            # Получаем информацию о группе для использования логотипа группы как запасного варианта
            group_info = vk.groups.getById(group_id=owner_id, fields=["photo_200"])
            default_photo = None
            if group_info and len(group_info) > 0:
                default_photo = group_info[0].get("photo_200")
                logger.info(f"Получен логотип группы для запасного варианта: {default_photo}")
            
            # Небольшая пауза после первого запроса
            time.sleep(0.3)
            
            # Сначала получаем категории маркета (альбомы)
            market_albums = vk.market.getAlbums(owner_id=-owner_id, count=100)
            logger.info(f"Получено {len(market_albums.get('items', []))} категорий маркета из группы {owner_id}")
            
            # Создаем словарь для всех магазинов
            all_shops = {}
            
            # Для каждой категории маркета
            for i, album in enumerate(market_albums.get("items", [])):
                # Добавляем небольшую паузу между запросами к API
                if i > 0:
                    time.sleep(0.3)
                    
                album_id = album.get("id")
                album_title = album.get("title", "Неизвестная категория")
                
                # Добавляем эмодзи к названиям категорий для улучшения UX
                category_emoji = "🏪"
                if "строй" in album_title.lower() or "материал" in album_title.lower():
                    category_emoji = "🧱"
                elif "инстр" in album_title.lower():
                    category_emoji = "🔨"
                elif "мебел" in album_title.lower():
                    category_emoji = "🪑"
                elif "сад" in album_title.lower() or "огород" in album_title.lower():
                    category_emoji = "🌱"
                elif "сантех" in album_title.lower() or "водосн" in album_title.lower():
                    category_emoji = "🚿"
                elif "электр" in album_title.lower() or "освещ" in album_title.lower():
                    category_emoji = "🔌"
                elif "хозтовар" in album_title.lower() or "для дома" in album_title.lower():
                    category_emoji = "🏡"
                
                # Создаем ключ категории без эмодзи для стабильной обработки
                original_category_title = album_title
                display_category_title = f"{category_emoji} {album_title}"
                
                # Создаем категорию, если её ещё нет
                if original_category_title not in shop_categories:
                    shop_categories[original_category_title] = {}
                
                try:
                    # Получаем товары (магазины) из этой категории - увеличиваем количество до 200
                    items = vk.market.get(owner_id=-owner_id, album_id=album_id, count=200, extended=1)
                    
                    logger.info(f"Получено {len(items.get('items', []))} товаров из категории '{display_category_title}'")
                    
                    # Добавляем каждый товар как магазин
                    for item in items.get("items", []):
                        try:
                            # Собираем информацию о магазине из товара
                            item_id = item.get("id")
                            title = item.get("title", "Магазин без названия")
                            description = item.get("description", "")
                            
                            # Улучшенное получение фото товара с несколькими резервными вариантами
                            photo_url = None
                            
                            # Вариант 1: Попытка получить фото из основных фотографий товара
                            if "photos" in item and item["photos"] and len(item["photos"]) > 0:
                                try:
                                    sizes = item["photos"][0].get("sizes", [])
                                    if sizes:
                                        best_photo = max(
                                            sizes, 
                                            key=lambda size: size.get("width", 0) * size.get("height", 0)
                                        )
                                        photo_url = best_photo.get("url")
                                        logger.info(f"Для товара '{title}' использовано фото из photos[0].sizes: {photo_url}")
                                except (IndexError, KeyError, ValueError) as e:
                                    logger.warning(f"Не удалось получить фото из photos для товара '{title}': {e}")
                                    
                            # Вариант 2: Попытка получить thumb_photo
                            if not photo_url:
                                photo_url = item.get("thumb_photo")
                                if photo_url:
                                    logger.info(f"Для товара '{title}' использовано фото из thumb_photo: {photo_url}")
                            
                            # Вариант 3: Попытка получить изображение из полей товара
                            if not photo_url and "images" in item and item["images"]:
                                try:
                                    photo_url = item["images"][0].get("url")
                                    logger.info(f"Для товара '{title}' использовано фото из images: {photo_url}")
                                except (IndexError, KeyError) as e:
                                    logger.warning(f"Не удалось получить фото из images для товара '{title}': {e}")
                            
                            # Вариант 4: Использование превью изображения товара
                            if not photo_url:
                                photo_url = item.get("preview", {}).get("photo", {}).get("sizes", [{}])[-1].get("url")
                                if photo_url:
                                    logger.info(f"Для товара '{title}' использовано фото из preview: {photo_url}")
                            
                            # Вариант 5: Если все методы не сработали, используем логотип группы как запасной вариант
                            if not photo_url:
                                photo_url = default_photo
                                logger.warning(f"Для товара '{title}' используется логотип группы как запасной вариант: {photo_url}")
                            
                            # Вариант 6: Если даже логотип группы недоступен, используем заглушку
                            if not photo_url:
                                photo_url = "https://vk.com/images/camera_200.png"  # Стандартная иконка VK
                                logger.warning(f"Для товара '{title}' используется стандартная иконка VK как заглушка")
                                
                            # Извлекаем дополнительную информацию из описания
                            address = ""
                            phone = ""
                            website = ""
                            work_hours = ""
                            
                            # Обработка и извлечение структурированной информации из описания
                            if description:
                                # Ищем адрес в описании (разные форматы указания адреса)
                                address_match = re.search(r'адрес[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                if address_match:
                                    address = address_match.group(1).strip()
                                else:
                                    # Альтернативный поиск адреса
                                    address_match = re.search(r'находимся[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                    if address_match:
                                        address = address_match.group(1).strip()
                                
                                # Ищем телефон (поддерживает различные форматы)
                                phone_match = re.search(r'(?:тел(?:ефон)?|звоните)[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                if phone_match:
                                    phone = phone_match.group(1).strip()
                                else:
                                    # Попытка найти телефон по формату
                                    phone_match = re.search(r'(?:\+7|8)[\s\-(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', description)
                                    if phone_match:
                                        phone = phone_match.group(0).strip()
                                
                                # Ищем сайт или страницу в VK
                                website_match = re.search(r'(?:сайт|страница|группа|vk)[:\s-]+([^\s]+)', description, re.IGNORECASE)
                                if website_match:
                                    website = website_match.group(1).strip()
                                else:
                                    # Ищем URL-адреса в описании
                                    url_match = re.search(r'https?://[^\s]+', description)
                                    if url_match:
                                        website = url_match.group(0).strip()
                                
                                # Ищем время работы
                                work_match = re.search(r'(?:график|работаем|часы работы|время работы)[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                if work_match:
                                    work_hours = work_match.group(1).strip()
                            
                            # Создаем ключ магазина без эмодзи для стабильной обработки
                            original_shop_title = title
                            shop_key = f"🏪 {title}"
                            
                            shop_data = {
                                "id": item_id,
                                "title": title,
                                "description": description,
                                "address": address,
                                "phone": phone,
                                "website": website,
                                "work_hours": work_hours,
                                "photo": photo_url,
                                "vk_url": f"https://vk.com/market-{owner_id}?w=product-{owner_id}_{item_id}",
                                "category": original_category_title
                            }
                            
                            # Добавляем магазин в категорию и общий список
                            shop_categories[original_category_title][original_shop_title] = shop_data
                            all_shops[original_shop_title] = shop_data
                        except Exception as item_e:
                            logger.error(f"Ошибка при обработке товара в категории '{display_category_title}': {item_e}")
                            continue
                
                except Exception as category_e:
                    logger.error(f"Ошибка при получении товаров из категории '{display_category_title}': {category_e}")
                    continue
            
            # Если категорий нет или они пустые, проверяем наличие товаров вне категорий
            if not shop_categories or all(len(shops) == 0 for category, shops in shop_categories.items()):
                logger.info("Категории пусты, проверяем товары вне категорий...")
                
                try:
                    # Получаем товары без категории
                    items = vk.market.get(owner_id=-owner_id, count=200, extended=1)
                    
                    if items and items.get("items"):
                        # Создаем категорию "Все магазины"
                        all_category = "Все магазины"
                        shop_categories[all_category] = {}
                        
                        logger.info(f"Получено {len(items.get('items', []))} товаров вне категорий")
                        
                        # Обрабатываем каждый товар
                        for item in items.get("items", []):
                            try:
                                # Получаем основную информацию о товаре
                                item_id = item.get("id")
                                title = item.get("title", "Магазин без названия")
                                description = item.get("description", "")
                                
                                # Получаем URL фотографии товара (используем лучшую доступную)
                                photo_url = item.get("thumb_photo")
                                
                                if not photo_url and "photos" in item and item["photos"] and len(item["photos"]) > 0:
                                    try:
                                        # Пытаемся получить лучшее качество фото
                                        sizes = item["photos"][0].get("sizes", [])
                                        if sizes:
                                            best_photo = max(sizes, key=lambda size: size.get("width", 0) * size.get("height", 0))
                                            photo_url = best_photo.get("url")
                                    except Exception as photo_e:
                                        logger.warning(f"Ошибка при получении фото для товара '{title}': {photo_e}")
                                
                                # Если не удалось получить фото, используем логотип группы
                                if not photo_url:
                                    photo_url = default_photo
                                
                                # Извлекаем дополнительную информацию из описания
                                address = ""
                                phone = ""
                                website = ""
                                work_hours = ""
                                
                                # Структурированная обработка описания товара
                                if description:
                                    # Аналогичная обработка описания, как и для товаров в категориях
                                    # (Для краткости код повторно не дублируется)
                                    address_match = re.search(r'адрес[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                    if address_match:
                                        address = address_match.group(1).strip()
                                    
                                    phone_match = re.search(r'(?:тел(?:ефон)?|звоните)[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                    if phone_match:
                                        phone = phone_match.group(1).strip()
                                    
                                    website_match = re.search(r'(?:сайт|страница|группа|vk)[:\s-]+([^\s]+)', description, re.IGNORECASE)
                                    if website_match:
                                        website = website_match.group(1).strip()
                                    
                                    work_match = re.search(r'(?:график|работаем|часы работы|время работы)[:\s-]+([^\n]+)', description, re.IGNORECASE)
                                    if work_match:
                                        work_hours = work_match.group(1).strip()
                                
                                # Формируем ключ без эмодзи для стабильной обработки
                                original_shop_title = title
                                
                                shop_data = {
                                    "id": item_id,
                                    "title": title,
                                    "description": description,
                                    "address": address,
                                    "phone": phone,
                                    "website": website,
                                    "work_hours": work_hours,
                                    "photo": photo_url,
                                    "vk_url": f"https://vk.com/market-{owner_id}?w=product-{owner_id}_{item_id}",
                                    "category": "Все магазины"
                                }
                                
                                shop_categories[all_category][original_shop_title] = shop_data
                                all_shops[original_shop_title] = shop_data
                            except Exception as item_e:
                                logger.error(f"Ошибка при обработке товара вне категорий: {item_e}")
                                continue
                
                except Exception as no_category_e:
                    logger.error(f"Ошибка при получении товаров вне категорий: {no_category_e}")
            
            # Если список категорий все ещё пуст, возвращаем пустой словарь
            if not shop_categories or all(len(shops) == 0 for category, shops in shop_categories.items()):
                logger.warning("Не удалось получить магазины из ВКонтакте")
                return {"all_shops": {}}
            
            # Добавляем плоский список ко всем категориям для совместимости
            shop_categories["all_shops"] = all_shops
            
            # Логируем количество категорий и магазинов
            category_count = len(shop_categories) - 1  # Без all_shops
            shop_count = len(all_shops)
            logger.info(f"Получено {shop_count} магазинов-партнеров в {category_count} категориях")
            
            # Для отладки выводим названия категорий
            logger.info(f"Категории магазинов: {[k for k in shop_categories.keys() if k != 'all_shops']}")
            
            # Создаём новый словарь с правильно отформатированными ключами
            formatted_shop_categories = {}
            
            # Преобразуем ключи категорий, добавляя эмодзи
            for category_name, shops in shop_categories.items():
                if category_name == "all_shops":
                    formatted_shop_categories["all_shops"] = all_shops
                    continue
                
                # Добавляем эмодзи к названию категории
                category_emoji = "🏪"
                if "строй" in category_name.lower() or "материал" in category_name.lower():
                    category_emoji = "🧱"
                elif "инстр" in category_name.lower():
                    category_emoji = "🔨"
                elif "мебел" in category_name.lower():
                    category_emoji = "🪑"
                elif "сад" in category_name.lower() or "огород" in category_name.lower():
                    category_emoji = "🌱"
                elif "сантех" in category_name.lower() or "водосн" in category_name.lower():
                    category_emoji = "🚿"
                elif "электр" in category_name.lower() or "освещ" in category_name.lower():
                    category_emoji = "🔌"
                elif "хозтовар" in category_name.lower() or "для дома" in category_name.lower():
                    category_emoji = "🏡"
                    
                formatted_category_name = f"{category_emoji} {category_name}"
                
                # Создаем новый словарь для магазинов этой категории
                formatted_shops = {}
                
                # Преобразуем ключи магазинов
                for shop_name, shop_data in shops.items():
                    formatted_shop_name = f"🏪 {shop_name}"
                    formatted_shops[formatted_shop_name] = shop_data
                    
                # Добавляем категорию с форматированными ключами
                formatted_shop_categories[formatted_category_name] = formatted_shops
            
            return formatted_shop_categories
            
        except Exception as inner_e:
            logger.error(f"Внутренняя ошибка при получении магазинов: {inner_e}")
            return {"all_shops": {}}
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка магазинов: {e}")
        return {"all_shops": {}}

def get_market_item_info(token, owner_id, album_id):
    """Получает информацию о товарах из категории маркета группы ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return []
            
        vk = vk_session.get_api()

        # Получаем товары из категории
        items = vk.market.get(
            owner_id=-owner_id, album_id=album_id, count=200, extended=1
        )
        result = []

        for item in items.get("items", []):
            # Получаем лучшее фото товара
            photo_url = None
            if "photos" in item and item["photos"]:
                try:
                    best_photo = max(
                        item["photos"][0].get("sizes", []), 
                        key=lambda size: size.get("width", 0) * size.get("height", 0)
                    )
                    photo_url = best_photo.get("url")
                except (IndexError, KeyError):
                    photo_url = item.get("thumb_photo")
            else:
                photo_url = item.get("thumb_photo")

            # Форматируем цену если она есть
            price_text = ""
            if "price" in item:
                price = item["price"].get("text", "")
                if price:
                    price_text = f"\n💰 Цена: {price}"

            # Добавляем информацию о товаре
            result.append(
                {
                    "title": item.get("title", "Товар без названия"),
                    "description": item.get("description", "") + price_text,
                    "photo": photo_url,
                    "url": f"https://vk.com/market-{owner_id}?w=product-{owner_id}_{item.get('id')}",
                    "price": item.get("price", {}).get("text", "")
                }
            )

        logger.info(f"Получено {len(result)} товаров из категории {album_id}")
        return result

    except Exception as e:
        logger.error(f"Ошибка при получении товаров из категории {album_id}: {e}")
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    token = "vk1.a.hyubBHqaBx7Pws9eH-kK0uZtw617T5GPhsRa8k0WvIEpz321CjWx3MpN-jqCTBuB6RXl1mb2dxd38WhBooney-79ZO1fjHXmwBQ4QNOhmJPvdPZiXE8KHPy05zYjUz72V7KXnrn-Bh7_DaKzkk-W5MdliJtsbR-RNo1HFUtByof4pLkaMz-wg27ezaLpet8U06nQ1skIk03sToud8eO7fA"
    group_id = 95855103
    
    # Тестирование функций
    albums = get_album_names(token, group_id)
    print(f"Альбомы: {len(albums)}")
    
    if albums:
        sample_album_id = list(albums.values())[0]
        photos = get_album_photos(token, group_id, sample_album_id)
        print(f"Фотографии: {len(photos)}")
    
    market_categories = get_market_items(token, group_id)
    print(f"Категории товаров: {len(market_categories)}")
    
    if market_categories:
        sample_category_id = list(market_categories.values())[0]
        items = get_market_item_info(token, group_id, sample_category_id)
        print(f"Товары: {len(items)}")
        
    shops = get_shop_list(token, group_id)
    print(f"Магазины: {len(shops)}") 