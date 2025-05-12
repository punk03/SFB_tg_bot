"""
Строй Форум Белгород - Telegram Bot
Оптимизированная версия с исправленными функциями для отображения категорий магазинов без сортировки по алфавиту
"""

# Импортируем все необходимые библиотеки и модули из основного файла
from main import *

# Заменяем функцию обработки запроса к магазинам-партнерам
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
    
    # Не сортируем категории по алфавиту, а используем их в исходном порядке
    categories_list = list(categories.keys())
    
    # Создаем клавиатуру для категорий магазинов (без количества)
    kb = buttons.generator(categories_list, row_width=1, force_single_column=True, preserve_emoji=True, sort_alphabetically=False)
    await message.answer('🏪 <b>Наши магазины-партнёры</b>\n\nВыберите категорию магазинов:', 
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb)
    await User.get_shop_category.set()
    await state.set_data(shop_categories)

# Заменяем обработчик для выбора категории магазинов
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
        # Не сортируем категории по алфавиту, а используем их в исходном порядке
        categories_list = list(categories.keys())
        await message.answer(
            f"⚠️ Категория '{message.text}' не найдена. Пожалуйста, выберите категорию из списка ниже.", 
            reply_markup=buttons.generator(categories_list, row_width=1, force_single_column=True, preserve_emoji=True, sort_alphabetically=False)
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

# Заменяем обработчик для возврата к категориям магазинов
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
    
    # Не сортируем категории по алфавиту, а используем их в исходном порядке
    categories_list = list(categories.keys())
    
    # Создаем клавиатуру для категорий магазинов (без количества)
    kb = buttons.generator(categories_list, row_width=1, force_single_column=True, preserve_emoji=True, sort_alphabetically=False)
    await message.answer('🏪 <b>Наши магазины-партнёры</b>\n\nВыберите категорию магазинов:', 
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb)
    
    # Сохраняем новые данные в состояние
    await state.set_data(shop_categories)
    await User.get_shop_category.set()

print("Исправленные функции для категорий магазинов загружены успешно!") 