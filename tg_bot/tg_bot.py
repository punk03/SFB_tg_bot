import loader
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from pyrogram import Client
from loader import topics, api_hash, api_id
from handlers import *

# Создайте экземпляры aiogram бота и диспетчера
bot = Bot(token=loader.tg_bot_token)
dp = Dispatcher(bot)

# Создайте экземпляр Pyrogram клиента
client = Client("my_account", api_id=api_id, api_hash=api_hash)
CHAT_ID = int(loader.tg_group_id)

# Команда старта, которая выводит кнопки с темами
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    for topic in topics.keys():
        keyboard.add(types.InlineKeyboardButton(text=topic, callback_data=topic))
    await message.reply("Выберите тему:", reply_markup=keyboard)


posts = {}

# Обработчик нажатий на кнопки тем 
@dp.callback_query_handler()
async def process_callback(call: types.CallbackQuery):
    topic_name, post_index = call.data.split(' ', 1)
    post_index = int(post_index)

    if topic_name in topics:
        # Если топик еще не загружен, загружаем его
        if topic_name not in posts:
            posts[topic_name] = await get_posts_from_topic(CHAT_ID, topics[topic_name])

        # Если индекс в пределах допустимого, отправляем пост
        if 0 <= post_index < len(posts[topic_name]):
            keyboard = types.InlineKeyboardMarkup()
            if post_index > 0:
                keyboard.add(types.InlineKeyboardButton(text='Предыдущий', callback_data=f'{topic_name} {post_index-1}'))
            if post_index < len(posts[topic_name]) - 1:
                keyboard.add(types.InlineKeyboardButton(text='Следующий', callback_data=f'{topic_name} {post_index+1}'))
            keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='back'))

            # Копирование сообщения из топика в чат с пользователем
            await client.copy_message(chat_id=call.message.chat.id, 
                                      from_chat_id=CHAT_ID, 
                                      message_id=posts[topic_name][post_index].message_id)

        else:
            await call.answer('Нет больше постов в этой теме.')
    elif call.data == 'back':
        keyboard = types.InlineKeyboardMarkup()
        for topic in topics.keys():
            keyboard.add(types.InlineKeyboardButton(text=topic, callback_data=f'{topic} 0'))
        await call.message.edit_text('Выберите тему:', reply_markup=keyboard)
    else:
        await call.answer('Неизвестный запрос.')


async def get_posts_from_topic(chat_id: str, message_id: int):
    topic_posts = []
    async with Client("my_account", api_id, api_hash) as app:
        async for message in app.get_chat_history(chat_id):
            if message.reply_to_message_id and int(message.reply_to_message_id) == int(message_id) and message.text or message.caption:
                topic_posts.append(message.id)
    print(topic_posts)
    return topic_posts



if __name__ == '__main__':
    executor.start_polling(dp)