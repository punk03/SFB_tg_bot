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
                "date": photo.get("date"),
                "id": photo.get("id")  # Добавляем ID фотографии
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
                    lines = description.split("\n")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Ищем адрес
                        if line.lower().startswith("адрес:") or line.lower().startswith("адрес "):
                            address = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                        
                        # Ищем телефон
                        elif (line.lower().startswith("тел:") or 
                              line.lower().startswith("телефон:") or
                              line.lower().startswith("тел.") or
                              line.lower().startswith("т:")):
                            phone = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                        
                        # Ищем сайт
                        elif (line.lower().startswith("сайт:") or 
                              line.lower().startswith("website:") or
                              line.lower().startswith("http") or
                              ".ru" in line or ".com" in line or ".рф" in line):
                            website = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                            
                        # Ищем время работы
                        elif (line.lower().startswith("режим") or 
                              line.lower().startswith("время") or
                              line.lower().startswith("часы") or
                              "работаем" in line.lower()):
                            work_hours = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                    
                    # Создаем структуру с информацией о магазине
                    shop_info = {
                        "title": title,
                        "description": description,
                        "photo": photo_url,
                        "address": address,
                        "phone": phone,
                        "website": website,
                        "work_hours": work_hours,
                        # Ссылка на товар в ВК
                        "vk_url": f"https://vk.com/market-{owner_id}?w=product-{owner_id}_{item_id}"
                    }
                    
                    # Добавляем магазин в категорию и в общий список магазинов
                    key = f"🏪 {title}"
                    shop_categories[album_title][key] = shop_info
                    all_shops[key] = shop_info
            
            # Добавляем все магазины в отдельную категорию
            shop_categories["all_shops"] = all_shops
            
            return shop_categories
            
        except Exception as e:
            logger.error(f"Ошибка при обработке категорий товаров: {e}")
            return {"all_shops": {}}
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка магазинов: {e}")
        return {"all_shops": {}}

def get_market_item_info(token, owner_id, album_id):
    """Получает товары из выбранной категории"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return []
            
        vk = vk_session.get_api()

        # Получаем товары из категории
        items = vk.market.get(owner_id=-owner_id, album_id=album_id, count=200, extended=1)
        result = []

        for item in items.get("items", []):
            # Собираем основную информацию о товаре
            item_id = item.get("id")
            title = item.get("title", "Товар без названия")
            description = item.get("description", "")
            price = item.get("price", {}).get("text", "Цена не указана")
            
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
            
            # Создаем структуру с информацией о товаре
            item_info = {
                "title": title,
                "description": description,
                "price": price,
                "photo": photo_url,
                "url": f"https://vk.com/market-{owner_id}?w=product-{owner_id}_{item_id}"
            }
            
            result.append(item_info)

        logger.info(f"Получено {len(result)} товаров из категории {album_id}")
        return result

    except Exception as e:
        logger.error(f"Ошибка при получении товаров из категории {album_id}: {e}")
        return []

def get_photo_comments(token, owner_id, photo_id):
    """Получает комментарии к фотографии от сообщества ВКонтакте"""
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return []
            
        vk = vk_session.get_api()

        # Получаем комментарии к фотографии
        comments = vk.photos.getComments(
            owner_id=-owner_id, 
            photo_id=photo_id,
            need_likes=0,
            count=100,  # Максимальное количество комментариев
            extended=1,  # Расширенная информация
            fields="attachments"  # Запрашиваем вложения
        )
        
        result = []
        
        # Фильтруем только комментарии от сообщества
        for comment in comments.get("items", []):
            # Проверяем, что комментарий от сообщества (от имени группы)
            from_group = comment.get("from_group", 0)
            from_id = comment.get("from_id", 0)
            
            # Комментарий от имени группы или от администратора группы
            if from_group == owner_id or from_id == -owner_id:
                # Извлекаем текст комментария
                text = comment.get("text", "")
                
                # Извлекаем прикрепления (фотографии)
                attachments = comment.get("attachments", [])
                photos = []
                
                for attachment in attachments:
                    if attachment.get("type") == "photo":
                        photo = attachment.get("photo", {})
                        # Находим максимальный размер фото
                        if photo.get("sizes"):
                            max_size = max(photo.get("sizes", []), 
                                        key=lambda size: size.get("width", 0) * size.get("height", 0))
                            photo_url = max_size.get("url")
                            
                            photo_info = {
                                "url": photo_url,
                                "description": text,
                                "likes": photo.get("likes", {}).get("count", 0),
                                "date": photo.get("date")
                            }
                            
                            photos.append(photo_info)
                
                if photos:
                    result.extend(photos)
        
        return result

    except Exception as e:
        logger.error(f"Ошибка при получении комментариев к фотографии {photo_id}: {e}")
        return []


def get_topic_comments(token, group_id, topic_id, count=100):
    """
    Получает комментарии из темы (обсуждения) ВКонтакте
    
    Args:
        token: токен доступа ВКонтакте
        group_id: ID группы ВКонтакте (без минуса)
        topic_id: ID темы (обсуждения)
        count: количество комментариев для получения (максимум 100)
    
    Returns:
        Список комментариев с информацией об авторах и прикреплениях
    """
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return []
            
        vk = vk_session.get_api()
        
        # Получаем комментарии из обсуждения
        comments = vk.board.getComments(
            group_id=group_id,
            topic_id=topic_id,
            count=count,
            extended=1,  # Получаем расширенную информацию
            need_likes=0,
            sort="desc"  # Сначала новые комментарии
        )
        
        result = []
        
        # Получаем информацию о пользователях для маппинга
        users_map = {}
        if "profiles" in comments:
            for profile in comments.get("profiles", []):
                user_id = profile.get("id")
                first_name = profile.get("first_name", "")
                last_name = profile.get("last_name", "")
                full_name = f"{first_name} {last_name}".strip()
                photo = profile.get("photo_100", "")
                
                users_map[user_id] = {
                    "name": full_name,
                    "photo": photo
                }
        
        # Обрабатываем комментарии
        for comment in comments.get("items", []):
            # Получаем основную информацию
            text = comment.get("text", "")
            date = comment.get("date", 0)
            from_id = comment.get("from_id", 0)
            
            # Получаем информацию о пользователе
            user_info = users_map.get(from_id, {"name": "Неизвестный пользователь", "photo": ""})
            
            # Извлекаем прикрепления
            attachments = comment.get("attachments", [])
            attachment_data = []
            
            for attachment in attachments:
                att_type = attachment.get("type", "")
                
                if att_type == "photo":
                    photo = attachment.get("photo", {})
                    if photo.get("sizes"):
                        try:
                            max_size = max(
                                photo.get("sizes", []), 
                                key=lambda size: size.get("width", 0) * size.get("height", 0)
                            )
                            photo_url = max_size.get("url", "")
                            attachment_data.append({
                                "type": "photo",
                                "url": photo_url
                            })
                        except (ValueError, KeyError):
                            logger.warning(f"Не удалось получить URL фото из прикрепления")
                            
                elif att_type == "doc":
                    doc = attachment.get("doc", {})
                    doc_url = doc.get("url", "")
                    doc_title = doc.get("title", "Документ")
                    attachment_data.append({
                        "type": "doc",
                        "url": doc_url,
                        "title": doc_title
                    })
                    
                elif att_type == "link":
                    link = attachment.get("link", {})
                    link_url = link.get("url", "")
                    link_title = link.get("title", "Ссылка")
                    attachment_data.append({
                        "type": "link",
                        "url": link_url,
                        "title": link_title
                    })
            
            # Формируем объект комментария
            comment_data = {
                "id": comment.get("id", 0),
                "date": date,
                "text": text,
                "from_id": from_id,
                "user": user_info,
                "attachments": attachment_data
            }
            
            result.append(comment_data)
        
        logger.info(f"Получено {len(result)} комментариев из темы {topic_id} группы {group_id}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении комментариев из темы {topic_id}: {e}")
        return []


def get_topic_info(token, group_id, topic_id):
    """
    Получает информацию о теме обсуждения ВКонтакте
    
    Args:
        token: токен доступа ВКонтакте
        group_id: ID группы ВКонтакте (без минуса)
        topic_id: ID темы (обсуждения)
    
    Returns:
        Словарь с информацией о теме
    """
    try:
        vk_session = get_vk_session(token)
        if not vk_session:
            return None
            
        vk = vk_session.get_api()
        
        # Получаем информацию о теме
        topic = vk.board.getTopics(
            group_id=group_id,
            topic_ids=[topic_id],
            extended=1,  # Расширенная информация
            preview=1,   # Получаем текст первого сообщения
            preview_length=0  # Полный текст
        )
        
        if not topic or "items" not in topic or not topic["items"]:
            logger.warning(f"Тема {topic_id} не найдена в группе {group_id}")
            return None
        
        # Получаем первую тему из списка
        topic_data = topic["items"][0]
        
        # Собираем информацию
        result = {
            "id": topic_data.get("id", 0),
            "title": topic_data.get("title", "Без названия"),
            "created": topic_data.get("created", 0),
            "comments": topic_data.get("comments", 0),
            "text": topic_data.get("first_comment", ""),
            "updated": topic_data.get("updated", 0),
        }
        
        logger.info(f"Получена информация о теме {topic_id} группы {group_id}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о теме {topic_id}: {e}")
        return None


# Асинхронные обертки для функций парсинга

async def get_topic_comments_async(token, group_id, topic_id, count=100):
    """Асинхронная обертка для get_topic_comments"""
    return await run_in_executor(get_topic_comments, token, group_id, topic_id, count)

async def get_topic_info_async(token, group_id, topic_id):
    """Асинхронная обертка для get_topic_info"""
    return await run_in_executor(get_topic_info, token, group_id, topic_id) 