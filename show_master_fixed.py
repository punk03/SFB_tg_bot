"""
Строй Форум Белгород - Telegram Bot
Исправленная версия функции для отображения информации о мастерах, корректно обрабатывающая пустые категории
"""

# Импортируем все необходимые библиотеки и модули из основного файла
from main import *

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
                photo_count = len(photos) if photos else 0
                category_buttons.append((cat, photo_count))
        
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
    
    # Сохраняем выбранную категорию в состоянии для возможности возврата
    await state.update_data(current_master_category=found_category)
    
    if not photos:
        # Если категория пустая, показываем соответствующее сообщение
        await message.answer(f"📸 <b>Категория {found_category}</b>\n\n⚠️ В этой категории пока нет мастеров.\n\nВы можете стать первым мастером в этой категории, нажав на кнопку 'Попасть в базу мастеров' в главном меню.", 
                         parse_mode=ParseMode.HTML,
                         reply_markup=buttons.navigation_keyboard(include_masters_categories=True))
        return
    
    # Отправляем информацию о том, сколько фотографий будет показано
    await message.answer(f"📸 <b>Категория {found_category}</b>\n\nНайдено фотографий: {len(photos)}. Загружаю...", 
                         parse_mode=ParseMode.HTML)
    
    # Ограничиваем количество фотографий для отправки, чтобы не превысить лимиты Telegram
    # и не заставлять пользователя ждать слишком долго
    max_photos = min(config.MAX_PHOTOS_PER_REQUEST, len(photos))  # Используем лимит из конфига
    
    # Отправляем фотографии группами, чтобы ускорить процесс
    sent_count = 0
    for i, photo in enumerate(photos[:max_photos]):
        caption = photo['description'] if photo['description'] else f"Фото {i+1} из {max_photos}"
        full_caption = f"<b>📸 {found_category}</b>\n\n{caption}"
        
        # Добавляем ссылку на основной паблик ВКонтакте
        full_caption += f"\n\n🌐 <a href='{config.VK_GROUP_URL}'>Перейти в основной паблик СФБ ВКонтакте</a>"
        
        try:
            # Проверяем длину подписи
            if len(full_caption) <= 1024:
                await message.answer_photo(
                    photo=photo['url'], 
                    caption=full_caption, 
                    parse_mode=ParseMode.HTML
                )
            else:
                # Если подпись слишком длинная, отправляем фото и текст отдельно
                logger.info(f"Слишком длинная подпись для фото мастера в категории '{found_category}': {len(full_caption)} символов. Отправляем фото и текст отдельно.")
                await message.answer_photo(photo=photo['url'])
                await message.answer(full_caption, parse_mode=ParseMode.HTML)
                
            sent_count += 1
            
            # Небольшая задержка между сообщениями, чтобы избежать флуда и лимитов Telegram
            if i < max_photos - 1:  # Не добавляем задержку после последнего фото
                await asyncio.sleep(config.PHOTO_DELAY)  # Используем задержку из конфига
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка при отправке фото мастера: {error_msg}")
            
            # Обработка различных ошибок
            if "Bad Request" in error_msg and ("Wrong file identifier" in error_msg or "PHOTO_INVALID_DIMENSIONS" in error_msg):
                logger.warning(f"Проблема с фото мастера: {error_msg}")
                await message.answer(
                    f"<b>📸 {found_category}</b>\n\n{caption}\n\n⚠️ Изображение недоступно.",
                    parse_mode=ParseMode.HTML
                )
            elif "Message caption is too long" in error_msg:
                # Если проверка длины выше не сработала
                logger.warning(f"Слишком длинная подпись для фото мастера: {len(full_caption)} символов")
                try:
                    await message.answer_photo(photo=photo['url'])
                    await message.answer(full_caption, parse_mode=ParseMode.HTML)
                except Exception as inner_e:
                    logger.error(f"Повторная ошибка при отправке фото мастера: {inner_e}")
                    await message.answer(full_caption, parse_mode=ParseMode.HTML)
            else:
                # Общая обработка ошибок
                await message.answer(f"⚠️ Не удалось загрузить фото мастера. Описание: {caption}")
    
    # Если фотографий больше, чем мы показали, сообщаем об этом
    if len(photos) > max_photos:
        await message.answer(f"⚠️ <b>Показано {max_photos} из {len(photos)} доступных фотографий.</b>\n\nДля просмотра остальных фотографий посетите группу ВКонтакте.", 
                             parse_mode=ParseMode.HTML)
    
    # После отправки всех фото показываем клавиатуру с кнопками навигации
    await message.answer("🔍 <b>Просмотр завершен.</b> Вы можете вернуться к категориям мастеров или в главное меню.", 
                         parse_mode=ParseMode.HTML,
                         reply_markup=buttons.navigation_keyboard(include_masters_categories=True))

print("Исправленная функция для отображения информации о мастерах загружена успешно!") 