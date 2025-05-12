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