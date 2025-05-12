"""
Строй Форум Белгород - Telegram Bot
Исправленная версия функции для отображения всех категорий мастеров, даже пустых
"""

# Импортируем все необходимые библиотеки и модули из основного файла
from main import *

# Общая функция для обработки запроса к базе мастеров
async def masters_sfb_handler(message, state: FSMContext):
    # Показываем пользователю сообщение о загрузке
    loading_message = await message.answer("🔄 <b>Загружаю категории мастеров...</b>\n\nПожалуйста, подождите.", parse_mode=ParseMode.HTML)
    
    global non_empty_masters_cache, non_empty_masters_cache_time
    current_time = time.time()
    
    # Проверяем, есть ли актуальный кэш категорий
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
            non_empty = {}
            all_categories = {}
            
            for cat, album_id, task in tasks:
                photos = await task
                # Сохраняем все категории, независимо от наличия фотографий
                all_categories[cat] = album_id
                # Формируем кнопки для всех категорий, даже пустых
                photo_count = len(photos) if photos else 0
                category_buttons.append((cat, photo_count))
                
                # Для обратной совместимости сохраняем также непустые категории
                if photos and len(photos) > 0:
                    non_empty[cat] = album_id
            
            # Сохраняем результаты в кэш
            non_empty_masters_cache = {
                "buttons": category_buttons,
                "categories": non_empty,
                "all_categories": all_categories
            }
            non_empty_masters_cache_time = current_time
            
            # Логируем ключи для отладки
            logger.info(f"Все категории мастеров в кэше: {list(all_categories.keys())}")
            logger.info(f"Непустые категории мастеров в кэше: {list(non_empty.keys())}")
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
    # Сохраняем все категории в состояние, а не только непустые
    await state.set_data(all_categories)

print("Исправленная функция для отображения всех категорий мастеров загружена успешно!") 