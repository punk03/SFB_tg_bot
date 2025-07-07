import config
import logging
from aiogram.utils.markdown import hide_link, link

logger = logging.getLogger(__name__)

def add_links_footer(message_text: str) -> str:
    """
    Добавляет футер с ссылками на все ресурсы в конец сообщения, 
    если они ещё не присутствуют в сообщении.
    
    Args:
        message_text: исходный текст сообщения
    
    Returns:
        Текст сообщения с добавленными ссылками
    """
    # Проверяем, есть ли уже ссылки в тексте
    if "🔗 <b>Наши ресурсы:</b>" in message_text:
        return message_text
        
    if config.VK_GROUP_URL in message_text and config.TG_CHANNEL_URL in message_text and config.TG_BOT_URL in message_text:
        return message_text
    
    # Если ссылки отсутствуют, добавляем их
    return message_text + config.LINKS_FOOTER

async def send_message_with_links(message, text, parse_mode=None, reply_markup=None, **kwargs):
    """
    Отправляет сообщение с добавлением ссылок на ресурсы в конце.
    
    Args:
        message: объект сообщения Telegram
        text: текст сообщения
        parse_mode: режим парсинга
        reply_markup: клавиатура
        **kwargs: другие параметры для message.answer
    
    Returns:
        Результат выполнения message.answer
    """
    text_with_links = add_links_footer(text)
    return await message.answer(
        text_with_links, 
        parse_mode=parse_mode, 
        reply_markup=reply_markup, 
        **kwargs
    )

async def edit_message_with_links(message, text, parse_mode=None, reply_markup=None, **kwargs):
    """
    Редактирует сообщение с добавлением ссылок на ресурсы в конце.
    
    Args:
        message: объект сообщения Telegram
        text: текст сообщения
        parse_mode: режим парсинга
        reply_markup: клавиатура
        **kwargs: другие параметры для message.edit_text
    
    Returns:
        Результат выполнения message.edit_text
    """
    text_with_links = add_links_footer(text)
    return await message.edit_text(
        text_with_links, 
        parse_mode=parse_mode, 
        reply_markup=reply_markup, 
        **kwargs
    )

async def send_photo_with_links(message, photo, caption=None, parse_mode=None, reply_markup=None, **kwargs):
    """
    Отправляет фото с подписью, добавляя ссылки на ресурсы в конце подписи.
    
    Args:
        message: объект сообщения Telegram
        photo: фото для отправки
        caption: текст подписи
        parse_mode: режим парсинга
        reply_markup: клавиатура
        **kwargs: другие параметры для message.answer_photo
    
    Returns:
        Результат выполнения message.answer_photo
    """
    if caption:
        caption_with_links = add_links_footer(caption)
        
        # Проверяем длину подписи (Telegram ограничивает длину подписи до 1024 символов)
        if len(caption_with_links) <= 1024:
            return await message.answer_photo(
                photo=photo, 
                caption=caption_with_links, 
                parse_mode=parse_mode, 
                reply_markup=reply_markup, 
                **kwargs
            )
        else:
            # Если подпись слишком длинная, отправляем фото без подписи
            photo_message = await message.answer_photo(
                photo=photo,
                reply_markup=reply_markup,
                **kwargs
            )
            
            # А затем отправляем текст отдельным сообщением
            await message.answer(
                caption_with_links,
                parse_mode=parse_mode
            )
            
            return photo_message
    else:
        # Если нет подписи, просто отправляем фото
        return await message.answer_photo(
            photo=photo,
            reply_markup=reply_markup,
            **kwargs
        ) 