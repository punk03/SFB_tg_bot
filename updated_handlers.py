# Обработчик для кнопки "База мастеров СФБ"
@dp.message_handler(lambda m: m.text == "👷‍♂️ База мастеров СФБ" or m.text == "База мастеров СФБ")
async def masters_sfb_message(message: types.Message, state: FSMContext):
    await masters_sfb_button_handler(message)

# Обработчик для кнопки "Магазины-партнеры СФБ"
@dp.message_handler(lambda m: m.text == "🏪 Магазины-партнеры СФБ" or m.text == "Магазины-партнеры СФБ")
async def partners_stores_message(message: types.Message, state: FSMContext):
    await partners_stores_handler(message, state)

@dp.message_handler(lambda m: m.text == "📝 Предложить запись" or m.text == "Предложить запись")
async def offer_post_message(message: types.Message):
    answer = InlineKeyboardMarkup()
    answer.add(InlineKeyboardButton(
        "Отправить пост", url="https://vk.com/write-95855103?ref=chats"
    ))
    await message.answer(
        "📝 <b>Предложить свою публикацию для нашего сообщества</b>\n\n"
        "Вы можете отправить предложение в сообщениях нашего сообщества ВКонтакте:",
        reply_markup=answer,
        parse_mode=ParseMode.HTML
    )

@dp.message_handler(lambda m: m.text == "🤝 Стать магазином-партнером" or m.text == "Стать магазином-партнером")
async def vk_partner_handler(message: types.Message):
    answer = InlineKeyboardMarkup()
    answer.add(InlineKeyboardButton(
        "Обсуждение ВК", url=config.VK_PARTNER_TOPIC_URL
    ))
    await message.answer(
        "🤝 <b>Стать партнером Строй Форум Белгород</b>\n\nВся информация доступна в обсуждении ВКонтакте:",
        reply_markup=answer,
        parse_mode=ParseMode.HTML
    )

@dp.message_handler(lambda m: m.text == "📋 Попасть в базу мастеров" or m.text == "Попасть в базу мастеров")
async def vk_master_handler(message: types.Message):
    answer = InlineKeyboardMarkup()
    answer.add(InlineKeyboardButton(
        "Обсуждение ВК", url=config.VK_MASTER_TOPIC_URL
    ))
    await message.answer(
        "📋 <b>Попасть в базу мастеров Строй Форум Белгород</b>\n\nВся информация доступна в обсуждении ВКонтакте:",
        reply_markup=answer,
        parse_mode=ParseMode.HTML
    )

@dp.message_handler(lambda m: m.text == "📰 Стена сообщества" or m.text == "Стена сообщества")
async def community_wall_handler(message: types.Message):
    answer = InlineKeyboardMarkup()
    answer.add(InlineKeyboardButton(
        "Канал Telegram", url=config.TG_CHANNEL_URL
    ))
    answer.add(InlineKeyboardButton(
        "Группа ВКонтакте", url=config.VK_GROUP_URL
    ))
    await message.answer(
        "📰 <b>Стена сообщества</b>\n\nВы можете читать наши новости и публикации здесь:",
        reply_markup=answer,
        parse_mode=ParseMode.HTML
    ) 