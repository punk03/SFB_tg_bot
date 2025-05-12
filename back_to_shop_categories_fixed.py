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