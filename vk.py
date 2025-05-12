import vk_api
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Настройка логгера
logger = logging.getLogger(__name__)

# Исполнитель для асинхронных запросов
executor = ThreadPoolExecutor(max_workers=4)

async def run_in_executor(func, *args, **kwargs):
    """Выполняет функцию в отдельном потоке для неблокирующего IO"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

def get_vk_session(token):
    """Создает сессию ВКонтакте"""
    try:
        vk_session = vk_api.VkApi(token=token)
        return vk_session
    except Exception as e:
        logger.error(f"Ошибка при создании VK сессии: {e}")
        return None

def get_group_description(token, group_id):
    """Получает описание группы ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return None
            
        vk = vk_session.get_api()

        # Запрос информации о группе
        group_info = vk.groups.getById(
            group_id=group_id,
            fields=["description"]
        )
        
        if not group_info or not isinstance(group_info, list) or len(group_info) == 0:
            logger.error(f"Не удалось получить информацию о группе {group_id}")
            return None
            
        # Получаем описание группы
        description = group_info[0].get("description", "")
        
        logger.info(f"Получено описание группы {group_id}, длина: {len(description)} символов")
        
        # Форматируем описание для более красивого отображения
        formatted_description = ""
        if description:
            # Разбиваем на абзацы и обрабатываем каждый
            paragraphs = description.split("\n\n")
            
            for i, paragraph in enumerate(paragraphs):
                # Для первого абзаца добавляем заголовок с жирным шрифтом
                if i == 0:
                    formatted_description += f"<b>🏗 {paragraph}</b>\n\n"
                else:
                    # Добавляем эмодзи к каждому абзацу
                    formatted_description += f"🔹 {paragraph}\n\n"
            
            # Убираем лишние символы новой строки в конце
            formatted_description = formatted_description.rstrip()
            
        return formatted_description or "Информация о сообществе временно недоступна."
        
    except Exception as e:
        logger.error(f"Ошибка при получении описания группы {group_id}: {e}")
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
            
            # Добавляем эмодзи к названиям категорий для улучшения UX
            if "маст" in album_title.lower():
                album_title = f"🔨 {album_title}"
            elif "спецтех" in album_title.lower():
                album_title = f"🚜 {album_title}"
            elif "строит" in album_title.lower():
                album_title = f"🏗 {album_title}"
            elif "ремонт" in album_title.lower():
                album_title = f"🔧 {album_title}"
            else:
                album_title = f"📁 {album_title}"
                
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

        # Получаем все фотографии из альбома
        photos = vk.photos.get(owner_id=-owner_id, album_id=album_id, extended=1)
        result = []

        for photo in photos.get("items", []):
            # Находим максимальный размер фото
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

        logger.info(f"Получено {len(result)} фотографий из альбома {album_id}")
        return result

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
            # Сначала получаем категории маркета (альбомы)
            market_albums = vk.market.getAlbums(owner_id=-owner_id, count=100)
            logger.info(f"Получено {len(market_albums.get('items', []))} категорий маркета из группы {owner_id}")
            
            # Создаем словарь для всех магазинов
            all_shops = {}
            
            # Для каждой категории маркета
            for album in market_albums.get("items", []):
                album_id = album.get("id")
                album_title = album.get("title", "Неизвестная категория")
                
                # Добавляем эмодзи к названиям категорий для улучшения UX
                if "строй" in album_title.lower() or "материал" in album_title.lower():
                    album_title = f"🧱 {album_title}"
                elif "инстр" in album_title.lower():
                    album_title = f"🔨 {album_title}"
                elif "мебел" in album_title.lower():
                    album_title = f"🪑 {album_title}"
                elif "сад" in album_title.lower() or "огород" in album_title.lower():
                    album_title = f"🌱 {album_title}"
                elif "сантех" in album_title.lower() or "водосн" in album_title.lower():
                    album_title = f"🚿 {album_title}"
                elif "электр" in album_title.lower() or "освещ" in album_title.lower():
                    album_title = f"🔌 {album_title}"
                elif "хозтовар" in album_title.lower() or "для дома" in album_title.lower():
                    album_title = f"🏡 {album_title}"
                else:
                    album_title = f"🏪 {album_title}"
                
                # Создаем категорию, если её ещё нет
                if album_title not in shop_categories:
                    shop_categories[album_title] = {}
                
                # Получаем товары (магазины) из этой категории - увеличиваем количество до 200
                items = vk.market.get(owner_id=-owner_id, album_id=album_id, count=200, extended=1)
                
                logger.info(f"Получено {len(items.get('items', []))} товаров из категории '{album_title}'")
                
                # Добавляем каждый товар как магазин
                for item in items.get("items", []):
                    # Собираем информацию о магазине из товара
                    item_id = item.get("id")
                    title = item.get("title", "Магазин без названия")
                    description = item.get("description", "")
                    
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
                    
                    # Парсим дополнительную информацию из описания
                    address = "Адрес не указан"
                    phone = "Телефон не указан"
                    website = "#"
                    work_hours = "Не указаны"
                    
                    # Пытаемся извлечь информацию из описания
                    for line in description.split("\n"):
                        line = line.strip()
                        if line.startswith("Адрес:") or line.startswith("📍"):
                            address = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                        elif line.startswith("Телефон:") or line.startswith("📞"):
                            phone = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                        elif line.startswith("Сайт:") or line.startswith("🌐"):
                            website = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                        elif line.startswith("Режим работы:") or line.startswith("Часы работы:") or line.startswith("🕒"):
                            work_hours = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                    
                    # Формируем уникальный ключ для магазина
                    shop_key = f"🏪 {title}"
                    
                    # Формируем данные магазина
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
                        "category": album_title.replace("🏪 ", "").replace("🧱 ", "").replace("🔨 ", "").replace("🪑 ", "").replace("🌱 ", "").replace("🚿 ", "").replace("🔌 ", "").replace("🏡 ", "")
                    }
                    
                    # Добавляем магазин в категорию
                    shop_categories[album_title][shop_key] = shop_data
                    # Добавляем магазин в общий список
                    all_shops[shop_key] = shop_data
            
            # Если категорий нет или они пустые, проверяем наличие товаров вне категорий
            if not shop_categories or all(len(shops) == 0 for category, shops in shop_categories.items()):
                logger.info("Категории пусты, проверяем товары вне категорий...")
                
                # Получаем товары без категории
                items = vk.market.get(owner_id=-owner_id, count=200, extended=1)
                
                if items and items.get("items"):
                    # Создаем категорию "Все магазины"
                    all_category = "🏪 Все магазины"
                    shop_categories[all_category] = {}
                    
                    for item in items.get("items", []):
                        # Аналогичная обработка товаров как выше
                        item_id = item.get("id")
                        title = item.get("title", "Магазин без названия")
                        description = item.get("description", "")
                        
                        photo_url = item.get("thumb_photo")
                        
                        # Парсим дополнительную информацию из описания
                        address = "Адрес не указан"
                        phone = "Телефон не указан"
                        website = "#"
                        work_hours = "Не указаны"
                        
                        for line in description.split("\n"):
                            line = line.strip()
                            if line.startswith("Адрес:") or line.startswith("📍"):
                                address = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                            elif line.startswith("Телефон:") or line.startswith("📞"):
                                phone = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                            elif line.startswith("Сайт:") or line.startswith("🌐"):
                                website = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                            elif line.startswith("Режим работы:") or line.startswith("Часы работы:") or line.startswith("🕒"):
                                work_hours = line.split(":", 1)[1].strip() if ":" in line else line[1:].strip()
                        
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
                            "category": "Все магазины"
                        }
                        
                        shop_categories[all_category][shop_key] = shop_data
                        all_shops[shop_key] = shop_data
            
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
            
            return shop_categories
            
        except Exception as e:
            logger.error(f"Ошибка при получении товаров из категории: {e}")
            # Возвращаем пустой словарь без использования тестовых данных
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
